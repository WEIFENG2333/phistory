"""Normalize a captured provider request into the archived prompt surface.

The archive diffs Markdown, so every prompt-bearing block of the chosen request
has to survive into it: reminder blocks and system messages interleaved with the
conversation carry as much agent design as the leading system prompt does.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from phistory.sanitize import sanitize

_SYSTEM_KEYS = ("system", "instructions", "system_instruction", "systemInstruction")
_MESSAGE_KEYS = ("messages", "input", "contents")
_SYSTEM_ROLES = ("system", "developer")
_REMINDER_PREFIX = "<system-reminder>"


@dataclass(frozen=True)
class PromptBlock:
    """One content block, kept separate so block boundaries stay visible in diffs."""

    text: str
    kind: str = "text"
    cached: bool = False


@dataclass(frozen=True)
class PromptMessage:
    role: str
    blocks: tuple[PromptBlock, ...]


@dataclass(frozen=True)
class PromptTool:
    name: str
    description: str = ""
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptSnapshot:
    provider: str
    model: str
    system: tuple[PromptBlock, ...] = ()
    messages: tuple[PromptMessage, ...] = ()
    tools: tuple[PromptTool, ...] = ()

    @property
    def observation(self) -> dict[str, object]:
        observed: dict[str, object] = {"provider": self.provider}
        if self.model:
            observed["model"] = self.model
        if self.tools:
            observed["tool_count"] = len(self.tools)
        return observed


def render_archive_markdown(trace_path: Path) -> str:
    """The archived Markdown for one capture: snapshot plus run-noise normalization."""
    records = read_records(trace_path)
    markdown = sanitize(render_markdown(_snapshot(records, trace_path)), ports=capture_ports(records))
    if any(record.get("provenance", {}).get("kind") == "model-self-report" for record in records):
        markdown = (
            "> Model self-report, redacted before publication. Not a captured network request; "
            "completeness and accuracy are unverified.\n\n" + markdown
        )
    if any(record.get("capture_environment", {}).get("kind") == "mocked-bootstrap" for record in records):
        markdown = (
            "> Captured with locally simulated startup settings. See meta.json for the exact configuration.\n\n"
            + markdown
        )
    return markdown


def snapshot_from_trace(path: Path) -> PromptSnapshot:
    """Pick the richest prompt-bearing request in a trace and normalize it."""
    return _snapshot(read_records(path), path)


def _snapshot(records: list[dict[str, Any]], path: Path) -> PromptSnapshot:
    body = select_request_body(records)
    if body is None:
        raise ValueError(f"no prompt-bearing request in {path}")
    return snapshot_from_body(body)


def read_records(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def capture_ports(records: list[dict[str, Any]]) -> set[int]:
    """Local proxy ports this run listened on, so only they get normalized."""
    ports: set[int] = set()
    for record in records:
        request = record.get("request")
        headers = request.get("headers") if isinstance(request, dict) else None
        if not isinstance(headers, dict):
            continue
        for key, value in headers.items():
            if key.lower() != "host" or not isinstance(value, str):
                continue
            match = re.fullmatch(r"(?:127\.0\.0\.1|localhost|\[::1\]):(\d+)", value.strip())
            if match:
                ports.add(int(match.group(1)))
    return ports


def select_request_body(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Ignore health checks and model listings: a prompt request carries prompt material."""
    best: tuple[int, dict[str, Any]] | None = None
    for record in records:
        body = request_body(record)
        if not body:
            continue
        score = _score(body)
        if score > 0 and (best is None or score > best[0]):
            best = (score, body)
    return best[1] if best else None


def request_body(record: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the provider request; some clients nest it under routing metadata."""
    request = record.get("request")
    body = request.get("body") if isinstance(request, dict) else None
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return {}
    if not isinstance(body, dict):
        return {}
    nested = body.get("request")
    if isinstance(nested, dict) and _score(nested) >= _score(body):
        # Routing envelopes keep the model name outside the provider request.
        if not nested.get("model") and body.get("model"):
            return {**nested, "model": body["model"]}
        return nested
    return body


def snapshot_from_body(body: dict[str, Any]) -> PromptSnapshot:
    """Group by prompt role, not by transport shape: CLIs put the same instructions
    in `system`, in `instructions`, or in a leading system message."""
    messages = tuple(_messages(body))
    directives = tuple(_directive_blocks(messages))
    conversation = tuple(message for message in messages if not _is_directive(message))
    return PromptSnapshot(
        provider=infer_provider(body),
        model=_model(body),
        system=tuple(_system_blocks(body)) + directives,
        messages=conversation,
        tools=tuple(_tools(body)),
    )


def _is_directive(message: PromptMessage) -> bool:
    return message.role.lower() in _SYSTEM_ROLES


def _directive_blocks(messages: tuple[PromptMessage, ...]) -> Iterator[PromptBlock]:
    for message in messages:
        if not _is_directive(message):
            continue
        for block in message.blocks:
            yield PromptBlock(block.text, kind=f"{message.role.lower()} message", cached=block.cached)


def infer_provider(body: dict[str, Any]) -> str:
    if "contents" in body or "systemInstruction" in body or "system_instruction" in body:
        return "gemini"
    if "input" in body or "instructions" in body:
        return "openai-responses"
    if "system" in body and "messages" in body:
        return "anthropic"
    if "messages" in body:
        return "openai-chat"
    return "unknown"


def render_markdown(snapshot: PromptSnapshot) -> str:
    """Render the snapshot as line-diff friendly Markdown."""
    lines: list[str] = []

    lines.append("# System Prompt")
    lines.append("")
    if snapshot.system:
        for index, block in enumerate(snapshot.system, start=1):
            lines.append(f"## Block {index}{_block_suffix(block)}")
            lines.append("")
            lines.append(block.text)
            lines.append("")
    else:
        lines.append("_No system prompt captured._")
        lines.append("")

    lines.append("# Messages")
    lines.append("")
    position = 0
    for message in snapshot.messages:
        for block in message.blocks:
            position += 1
            lines.append(f"## Message {position} · {message.role}{_block_suffix(block, message_block=True)}")
            lines.append("")
            lines.append(block.text)
            lines.append("")
    if not position:
        lines.append("_No messages captured._")
        lines.append("")

    lines.append("# Tools")
    lines.append("")
    if not snapshot.tools:
        lines.append("_No tools captured._")
        lines.append("")
    for tool in sorted(snapshot.tools, key=lambda item: item.name):
        lines.append(f"## {tool.name}")
        lines.append("")
        if tool.description:
            lines.append(_demote_headings(tool.description))
            lines.append("")
        lines.append("```json")
        lines.append(json.dumps(tool.schema, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _block_suffix(block: PromptBlock, *, message_block: bool = False) -> str:
    parts = []
    if block.kind != "text" or message_block:
        parts.append(block.kind)
    if block.cached:
        parts.append("cached")
    return f" · {' · '.join(parts)}" if parts else ""


def _demote_headings(text: str) -> str:
    """Keep tool prose from competing with the archive's own section headings."""
    return "\n".join(f"##{line}" if line.startswith("#") else line for line in text.splitlines())


def _score(body: dict[str, Any]) -> int:
    """The agent's own turn carries the tool surface; helper turns (titling, subagents)
    have instructions but few or no tools, so tools must outweigh prose."""
    score = sum(100 for key in _SYSTEM_KEYS if body.get(key))
    score += sum(35 for key in _MESSAGE_KEYS if body.get(key))
    score += 20 if body.get("tools") or body.get("toolConfig") else 0
    return score + _tool_count(body) * 10


def _tool_count(body: dict[str, Any]) -> int:
    return len(list(_tool_entries(body)))


def _model(body: dict[str, Any]) -> str:
    model = body.get("model") or body.get("name")
    return str(model) if isinstance(model, str) else ""


def _system_blocks(body: dict[str, Any]) -> Iterator[PromptBlock]:
    for key in _SYSTEM_KEYS:
        value = body.get(key)
        if value is None:
            continue
        if isinstance(value, dict) and ("parts" in value or "content" in value):
            value = value.get("parts") or value.get("content")
        yield from _content_blocks(value)


def _messages(body: dict[str, Any]) -> Iterator[PromptMessage]:
    for key in _MESSAGE_KEYS:
        items = body.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                if isinstance(item, str) and item.strip():
                    yield PromptMessage("user", (PromptBlock(item),))
                continue
            message = _message(item)
            if message is not None:
                yield message


def _message(item: dict[str, Any]) -> PromptMessage | None:
    role = str(item.get("role") or item.get("type") or "message")
    content = item.get("content")
    if content is None:
        content = item.get("parts")
    if content is None:
        content = item.get("text")
    if content is None:
        content = item.get("output")
    blocks = tuple(_content_blocks(content))
    return PromptMessage(role, blocks) if blocks else None


def _content_blocks(value: Any) -> Iterator[PromptBlock]:
    if value is None:
        return
    if isinstance(value, str):
        if value.strip():
            yield PromptBlock(value, kind=_kind("text", value))
        return
    if isinstance(value, dict):
        yield from _content_block(value)
        return
    if isinstance(value, list):
        for item in value:
            yield from _content_blocks(item)


def _content_block(block: dict[str, Any]) -> Iterator[PromptBlock]:
    kind = str(block.get("type") or "text")
    text = block.get("text")
    if not isinstance(text, str):
        text = block.get("content") if isinstance(block.get("content"), str) else None
    if not isinstance(text, str) or not text.strip():
        # Non-text parts (images, tool results, tool calls) stay as their JSON shape.
        payload = {key: value for key, value in block.items() if key != "cache_control"}
        if not payload or set(payload) <= {"type"}:
            return
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        yield PromptBlock(text, kind=kind, cached=bool(block.get("cache_control")))
        return
    yield PromptBlock(text, kind=_kind(kind, text), cached=bool(block.get("cache_control")))


def _kind(kind: str, text: str) -> str:
    if kind in ("text", "input_text", "output_text") and text.lstrip().startswith(_REMINDER_PREFIX):
        return "system-reminder"
    return kind


def _tools(body: dict[str, Any]) -> Iterator[PromptTool]:
    for entry in _tool_entries(body):
        tool = _tool(entry)
        if tool is not None:
            yield tool


def _tool_entries(body: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every tool declaration, including provider-specific containers."""
    sources: list[Any] = [body.get("tools")]
    for key in ("toolConfig", "tool_config"):
        config = body.get(key)
        if isinstance(config, dict):
            sources.extend([config.get("tools"), config.get("function_declarations")])
    inputs = body.get("input")
    if isinstance(inputs, list):
        sources.extend(item.get("tools") for item in inputs if isinstance(item, dict) and item.get("tools"))
    for source in sources:
        yield from _flatten_tools(source)


def _flatten_tools(value: Any, namespace: str = "") -> Iterator[dict[str, Any]]:
    """Flatten containers down to the leaves the model can actually call."""
    if isinstance(value, list):
        for item in value:
            yield from _flatten_tools(item, namespace)
        return
    if not isinstance(value, dict):
        return
    for key in ("functionDeclarations", "function_declarations"):
        if isinstance(value.get(key), list):
            yield from _flatten_tools(value[key], namespace)
            return
    qualified = ".".join(part for part in (namespace, str(value.get("name") or "")) if part)
    children = value.get("tools")
    if value.get("type") == "namespace" and isinstance(children, list) and children:
        yield from _flatten_tools(children, qualified)
        return
    yield {**value, "name": qualified} if qualified else value


def _tool(entry: dict[str, Any]) -> PromptTool | None:
    declaration = entry
    inner = entry.get("function")
    if isinstance(inner, dict):
        declaration = {**entry, **inner}
    name = declaration.get("name") or declaration.get("type")
    if not isinstance(name, str) or not name:
        return None
    description = declaration.get("description")
    schema = declaration.get("input_schema") or declaration.get("parameters") or declaration.get("parametersJsonSchema")
    if not isinstance(schema, dict):
        # Containers such as tool namespaces carry no schema; keep the declaration verbatim.
        schema = entry
    return PromptTool(name, description if isinstance(description, str) else "", schema)
