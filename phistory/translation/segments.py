"""Extract reusable prose spans without changing archived source documents."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

EXTRACTOR_VERSION = "1"
MAX_SEGMENT_CHARS = 5000
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)")
_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
_LIST = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
_JSON_PROSE = re.compile(r'"(?:description|title)"\s*:\s*("(?:\\.|[^"\\])*")')
_CODE = re.compile(r"(`+).*?\1|[A-Za-z][A-Za-z0-9+.-]*://\S*|\$\{[^{}]*\}|\$[A-Z][A-Z0-9_]*|</?[^>\n]+>", re.DOTALL)
# Only leaf fields: placeholders and XML containers may surround translatable prose.
_MACHINE_XML = re.compile(r"<(name|id|location|path|url|uri|model|type|version|command)(?:\s[^<>]*)?>[^<]*</\1\s*>")
_IDENTIFIER = re.compile(r"(?:[a-z][A-Z]|[a-zA-Z]_\w|[a-zA-Z]/\w|[a-zA-Z]\.\w)")
_PROSE_FENCES = {"text", "plaintext", "markdown", "md", "prompt"}
_STATIC_WRAPPER = re.compile(r"^### [^\n]+\n\n(?:[^\n]+\n\n)?\n```text\n", re.MULTILINE)
_WRAPPER_HEADINGS = {
    "system prompt",
    "developer prompt",
    "user message",
    "system message",
    "developer message",
    "system instruction",
    "instructions",
    "tools",
}


@dataclass(frozen=True)
class Segment:
    id: str
    text: str
    context: str = ""


@dataclass(frozen=True)
class ExtractedSource:
    """An offset-only source index and its unique, separately stored prose units."""

    index: dict[str, Any]
    segments: tuple[Segment, ...]


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def needs_translation(text: str) -> bool:
    """Ignore Chinese with embedded identifiers, markup and machine-only values."""
    if text.lstrip().startswith(("{", "[")):
        try:
            if isinstance(json.loads(text), (dict, list)):
                return False
        except ValueError:
            pass
    plain = _CODE.sub(" ", _MACHINE_XML.sub(" ", text))
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", plain)
    if not words:
        return False
    if re.search(r"[\u3400-\u9fff]", plain):
        return bool(re.search(r"[A-Za-z]{2,}(?:[ \t]+[A-Za-z]{2,}){2,}", plain))
    stripped = plain.strip(" \t\r\n#*_|:;.-")
    if not re.search(r"\s", stripped) and _IDENTIFIER.search(stripped):
        return False
    if re.fullmatch(r"[A-Z][A-Z0-9_ -]*", stripped) and len(words) < 2:
        return False
    if len(words) == 1:
        return bool(re.fullmatch(r"[A-Za-z]{3,}", stripped) and not _IDENTIFIER.search(stripped))
    if re.match(r"^(?:[a-z][\w-]*[.:=]|/|\.\.?/|\w+://)", stripped) and len(words) < 4:
        return False
    if re.fullmatch(r"[\s|:+\-=`~0-9]+", plain):
        return False
    return True


def _segment(text: str, context: str = "") -> Segment:
    """Keep one translation per source text; context guides the API, not cache identity."""
    identity = f"{EXTRACTOR_VERSION}\0{text}"
    return Segment(source_hash(identity), text, context)


def _chunks(text: str, start: int, end: int):
    while end - start > MAX_SEGMENT_CHARS:
        limit = start + MAX_SEGMENT_CHARS
        candidates = [m.end() for m in re.finditer(r"\n|(?<=[.!?。！？])\s+", text[start:limit])]
        boundary = start + candidates[-1] if candidates else text.rfind(" ", start, limit)
        if boundary <= start:
            boundary = limit
        yield start, boundary
        start = boundary
    if end > start:
        yield start, end


def _add_span(text, start, end, refs, unique, *, context=""):
    literal_fields = list(_MACHINE_XML.finditer(text, start, end))
    if literal_fields:
        for literal in literal_fields:
            _add_span(text, start, literal.start(), refs, unique, context=context)
            start = literal.end()
        _add_span(text, start, end, refs, unique, context=context)
        return
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    for left, right in _chunks(text, start, end):
        value = text[left:right]
        if not needs_translation(value):
            continue
        unit = _segment(value, context)
        unique[unit.id] = unit
        refs.append({"id": unit.id, "start": left, "end": right, "kind": "text"})


def _fence_end(lines, first, marker, language):
    stack = [(marker, language)]
    for index in range(first, len(lines)):
        match = _FENCE.match(lines[index].group())
        if not match:
            continue
        ticks, info = match.groups()
        current, kind = stack[-1]
        if not info.strip() and ticks[0] == current[0] and len(ticks) >= len(current):
            stack.pop()
            if not stack:
                return index
        elif info.strip() and kind in _PROSE_FENCES:
            stack.append((ticks, info.strip().lower().split(" ")[0]))
    return len(lines)


def _json_offsets(raw: str) -> list[int]:
    """Map decoded Unicode offsets back to a JSON literal, including surrogate pairs."""
    offsets = [1]
    position = 1
    while position < len(raw) - 1:
        if raw[position] == "\\":
            width = 6 if raw[position + 1] == "u" else 2
            if width == 6 and 0xD800 <= int(raw[position + 2 : position + 6], 16) <= 0xDBFF:
                following = raw[position + 6 : position + 12]
                if following.startswith("\\u") and 0xDC00 <= int(following[2:], 16) <= 0xDFFF:
                    width = 12
            position += width
        else:
            position += 1
        offsets.append(position)
    return offsets


def _json_spans(raw, start, refs, unique, context="", scope=""):
    try:
        decoded = json.loads(raw)
        offsets = _json_offsets(raw)
    except ValueError:
        return
    nested, units = _markdown_spans(decoded, context, scope)
    for ref in nested:
        mapped = {
            "id": ref["id"],
            "start": start + offsets[ref["start"]],
            "end": start + offsets[ref["end"]],
            "kind": "json-string-part",
        }
        if ref["kind"] == "json-string-part":
            mapped["escape_depth"] = ref.get("escape_depth", 1) + 1
        refs.append(mapped)
    unique.update((unit.id, unit) for unit in units)


def _markdown_spans(text: str, context: str = "", scope: str = "") -> tuple[list[dict], tuple[Segment, ...]]:
    refs: list[dict] = []
    unique: dict[str, Segment] = {}
    scan_text = _MACHINE_XML.sub(lambda match: re.sub(r"[^\n]", " ", match.group()), text)
    lines = list(re.finditer(r"[^\n]*\n|[^\n]+$", scan_text))
    pending: list[tuple[int, int]] = []
    tool_section = False

    def nearby(start, detailed=False):
        return "\n".join(
            part
            for part in (
                context,
                f"Section: {scope}" if scope else "",
                text[max(0, start - 120) : start].strip() if detailed else "",
            )
            if part
        )[-200:]

    def flush():
        if pending:
            _add_span(
                text,
                pending[0][0],
                pending[-1][1],
                refs,
                unique,
                context=nearby(pending[0][0], pending[-1][1] - pending[0][0] <= 80),
            )
            pending.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        value = line.group().rstrip("\r\n")
        fence = _FENCE.match(value)
        if fence:
            flush()
            marker, language = fence.groups()
            language = language.strip().lower().split(" ")[0]
            first = i + 1
            i = _fence_end(lines, first, marker, language)
            start = lines[first].start() if first < len(lines) else line.end()
            end = lines[i].start() if i < len(lines) else len(text)
            body = text[start:end]
            if language in {"json", "jsonc", "jsonschema"}:
                for match in _JSON_PROSE.finditer(body):
                    _json_spans(match.group(1), start + match.start(1), refs, unique, nearby(start), scope)
            elif language in _PROSE_FENCES:
                nested, units = _markdown_spans(body, nearby(start), scope)
                refs.extend({**ref, "start": start + ref["start"], "end": start + ref["end"]} for ref in nested)
                unique.update((unit.id, unit) for unit in units)
            i += 1
            continue
        heading = _HEADING.match(value)
        if heading:
            flush()
            title = heading.group(1)
            if value.startswith("# "):
                tool_section = title.strip() == "Tools"
            if not (tool_section and value.startswith("## ")):
                _add_span(
                    text,
                    line.start() + heading.start(1),
                    line.start() + heading.end(1),
                    refs,
                    unique,
                    context=nearby(line.start(), True),
                )
            if tool_section and value.startswith("## "):
                scope = f"Tool: {title.strip()}"
            elif title.strip().lower() in _WRAPPER_HEADINGS:
                scope = ""
            else:
                scope = title.strip()
        elif not value.strip() or re.fullmatch(r"\s*(?:</?[^>]+>|[-*_]{3,}|[| :\-]+)\s*", value):
            flush()
        elif re.match(r"^\s*(?:x-anthropic-billing-header:|[a-z][a-z0-9_-]*=)", value):
            flush()
        elif value.lstrip().startswith("|"):
            flush()
            for cell in re.finditer(r"(?:`[^`]*`|\\\||[^|])+", value.strip("\r\n")):
                _add_span(
                    text,
                    line.start() + cell.start(),
                    line.start() + cell.end(),
                    refs,
                    unique,
                    context=nearby(line.start(), True),
                )
        elif item := _LIST.match(value):
            flush()
            pending.append((line.start() + item.end(), line.end()))
        else:
            pending.append((line.start(), line.end()))
        i += 1
    flush()
    return refs, tuple(unique.values())


def _static_spans(text: str) -> tuple[list[dict], tuple[Segment, ...]]:
    """Isolate generated wrappers: extracted templates can contain unfinished fences."""
    wrappers = list(_STATIC_WRAPPER.finditer(text))
    if not wrappers:
        return _markdown_spans(text)
    refs = []
    unique = {}
    metadata = re.match(r"# Static Prompts\s*\n+\s*Agent:\s*`[^`]*`\s*\n\s*Version:\s*`[^`]*`\s*\n+", text)
    previous = metadata.end() if metadata else 0
    for index, wrapper in enumerate(wrappers):
        boundary = wrappers[index + 1].start() if index + 1 < len(wrappers) else len(text)
        closing = text.rfind("\n```\n", wrapper.end(), boundary)
        if closing < 0:
            raise ValueError("Unclosed static prompt export wrapper")
        for start, end in ((previous, wrapper.end() - len("```text\n")), (wrapper.end(), closing)):
            nested, units = _markdown_spans(text[start:end])
            refs.extend({**ref, "start": start + ref["start"], "end": start + ref["end"]} for ref in nested)
            unique.update((unit.id, unit) for unit in units)
        previous = closing + len("\n```\n")
    return refs, tuple(unique.values())


def extract_markdown(text: str, *, source_hash: str | None = None) -> ExtractedSource:
    """Index prose by Unicode offsets; preserve raw Markdown and JSON escaping."""
    refs, segments = _static_spans(text) if text.startswith("# Static Prompts\n") else _markdown_spans(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if source_hash is not None and source_hash != digest:
        raise ValueError("Source hash does not match Markdown text")
    return ExtractedSource(
        {
            "schema_version": 1,
            "extractor_version": EXTRACTOR_VERSION,
            "source_hash": digest,
            "kind": "markdown",
            "segments": refs,
        },
        segments,
    )


def _pointer(path: tuple) -> str:
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in path)


def _request_body(record: dict) -> tuple[dict, tuple]:
    request = record.get("request")
    body = request.get("body") if isinstance(request, dict) else None
    if not isinstance(body, dict):
        return {}, ()
    if isinstance(body.get("request"), dict):
        return body["request"], ("request", "body", "request")
    return body, ("request", "body")


def _tool_leaves(tools):
    if not isinstance(tools, list):
        return 0
    count = 0
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        nested = tool.get("tools")
        if isinstance(nested, list) and any(isinstance(item, dict) for item in nested):
            count += _tool_leaves(nested)
        else:
            declarations = tool.get("functionDeclarations", tool.get("function_declarations"))
            count += sum(isinstance(item, dict) for item in declarations) if isinstance(declarations, list) else 1
    return count


def trace_record_score(record: dict) -> int:
    body, _ = _request_body(record)
    weights = {
        "system": 100,
        "instructions": 100,
        "system_instruction": 100,
        "systemInstruction": 100,
        "messages": 35,
        "input": 35,
        "contents": 35,
        "tools": 20,
        "toolConfig": 20,
    }
    score = sum(weight for key, weight in weights.items() if key in body)
    score += _tool_leaves(body.get("tools"))
    for item in body.get("input", []) if isinstance(body.get("input"), list) else []:
        if isinstance(item, dict) and item.get("type") == "additional_tools":
            score += _tool_leaves(item.get("tools"))
    config = body.get("toolConfig")
    if isinstance(config, dict) and isinstance(config.get("tools"), list):
        score += sum(isinstance(item, dict) and isinstance(item.get("toolSpec"), dict) for item in config["tools"])
    tools = body.get("tools")
    config = body.get("tool_config")
    declarations = tools.get("functionDeclarations") if isinstance(tools, dict) else None
    if declarations is None and isinstance(config, dict):
        declarations = config.get("function_declarations")
    if isinstance(declarations, list):
        score += sum(isinstance(item, dict) for item in declarations)
    return score


def select_main_trace_record(records: list[dict]) -> int | None:
    """Match the website's highest-scoring prompt request; keep the first on ties."""
    if not records:
        return None
    index = max(range(len(records)), key=lambda position: trace_record_score(records[position]))
    return index if trace_record_score(records[index]) > 0 else None


def extract_trace(text: str) -> ExtractedSource:
    """Index visible prose fields using record numbers and RFC 6901 JSON pointers."""
    records = [json.loads(line) for line in text.splitlines() if line.strip()]
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("Trace records must be JSON objects")
    selected = select_main_trace_record(records)
    fields: list[dict] = []
    unique: dict[str, Segment] = {}
    visited: set[tuple] = set()

    def add(value, path, context="", scope=""):
        if not isinstance(value, str) or not value or path in visited:
            return
        visited.add(path)
        refs, units = _markdown_spans(value, context, scope)
        if refs:
            fields.append({"record": selected, "pointer": _pointer(path), "segments": refs})
            unique.update((unit.id, unit) for unit in units)

    def content(value, path):
        if isinstance(value, str):
            add(value, path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                content(item, (*path, index))
        elif isinstance(value, dict):
            for key in ("text", "input_text", "output_text", "content", "message"):
                if isinstance(value.get(key), (str, list)):
                    content(value[key], (*path, key))
                    return
            if "parts" in value:
                content(value["parts"], (*path, "parts"))

    def schema(value, path, context="", scope=""):
        if isinstance(value, list):
            for index, item in enumerate(value):
                schema(item, (*path, index), context, scope)
        elif isinstance(value, dict):
            for key in ("description", "title"):
                add(value.get(key), (*path, key), context, scope)
            for key in ("properties", "$defs", "definitions", "patternProperties", "dependentSchemas"):
                if isinstance(value.get(key), dict):
                    for name, item in value[key].items():
                        schema(item, (*path, key, name), context, scope)
            for key in (
                "items",
                "prefixItems",
                "additionalProperties",
                "unevaluatedProperties",
                "contains",
                "allOf",
                "anyOf",
                "oneOf",
                "not",
                "if",
                "then",
                "else",
                "propertyNames",
                "contentSchema",
            ):
                if key in value:
                    schema(value[key], (*path, key), context, scope)

    def tool(value, path):
        if isinstance(value, list):
            for index, item in enumerate(value):
                tool(item, (*path, index))
        elif isinstance(value, dict):
            name = value.get("name", "")
            scope = f"Tool: {name}" if name else ""
            add(value.get("description"), (*path, "description"), scope, scope)
            for key in ("tools", "function", "functionDeclarations", "function_declarations", "toolSpec"):
                if key in value:
                    tool(value[key], (*path, key))
            for key in ("parameters", "input_schema", "schema", "parametersJsonSchema"):
                if key in value:
                    schema(value[key], (*path, key), scope, scope)
            if isinstance(value.get("inputSchema"), dict):
                schema(value["inputSchema"].get("json"), (*path, "inputSchema", "json"), scope, scope)

    if selected is not None:
        body, path = _request_body(records[selected])
        for key in ("system", "instructions", "system_instruction", "systemInstruction"):
            if key in body:
                content(body[key], (*path, key))
        for key in ("messages", "input", "contents"):
            items = body.get(key)
            if isinstance(items, str):
                content(items, (*path, key))
            elif isinstance(items, list):
                for index, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue
                    item_path = (*path, key, index)
                    if item.get("type") == "additional_tools":
                        tool(item.get("tools"), (*item_path, "tools"))
                    else:
                        for field in ("parts", "content", "text", "output"):
                            if item.get(field):
                                content(item[field], (*item_path, field))
                                break
        tool(body.get("tools"), (*path, "tools"))
        for key in ("toolConfig", "tool_config"):
            tool(body.get(key), (*path, key))
    index = {
        "schema_version": 1,
        "extractor_version": EXTRACTOR_VERSION,
        "source_hash": source_hash(text),
        "kind": "trace",
        "selected_record": selected,
        "fields": fields,
    }
    return ExtractedSource(index, tuple(unique.values()))
