from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from phistory.models import CaptureTarget
from phistory.static_prompts.bun import extract_bun_entrypoint_js
from phistory.static_prompts.catalog import content_hash, known_content_hashes, match_candidates
from phistory.static_prompts.javascript import extract_string_candidates, is_prompt_like, is_static_resource
from phistory.static_prompts.models import (
    StaticCandidatesResult,
    StaticPromptCandidate,
    StaticPromptMatch,
    StaticPromptResult,
)

STATIC_CANDIDATES_EXTRACTOR = "tree-sitter-javascript/raw-template-body"
STATIC_CANDIDATES_MIN_LENGTH = 20
STATIC_PROMPT_DOUBLE_TERNARY_EXPR_RE = re.compile(
    r'\$\{[^{}\n?]{1,400}\?"(?P<yes>(?:[^"\\\n]|\\.)*)":"(?P<no>(?:[^"\\\n]|\\.)*)"\}'
)
STATIC_PROMPT_SINGLE_TERNARY_EXPR_RE = re.compile(
    r"\$\{[^{}\n?]{1,400}\?'(?P<yes>(?:[^'\\\n]|\\.)*)':'(?P<no>(?:[^'\\\n]|\\.)*)'\}"
)
STATIC_PROMPT_DOUBLE_STRING_EXPR_RE = re.compile(r'\$\{"(?P<value>(?:[^"\\\n]|\\.)*)"\}')
STATIC_PROMPT_SINGLE_STRING_EXPR_RE = re.compile(r"\$\{'(?P<value>(?:[^'\\\n]|\\.)*)'\}")
STATIC_PROMPT_TERNARY_PREFIX_RE = re.compile(r"\$\{[^{}\n?]{1,400}\?")
STATIC_PROMPT_VARIABLE_RE = re.compile(r"\$\{[^{}\n]{1,2000}\}")
STATIC_PROMPT_JOIN_EXPR_RE = re.compile(r"\$\{[A-Za-z_$][A-Za-z0-9_$]*\.join\(")
STATIC_PROMPT_MAP_EXPR_RE = re.compile(r"\$\{[A-Za-z_$][A-Za-z0-9_$]*\.map\(\([A-Za-z_$][A-Za-z0-9_$]*\)=>")
STATIC_PROMPT_SIMPLE_TERNARY_NAME_RE = re.compile(r"\$\{\?[A-Za-z_$][A-Za-z0-9_$]*:[A-Za-z_$][A-Za-z0-9_$]*\}")
STATIC_PROMPT_DOUBLE_TERNARY_RE = re.compile(r'\$\{\}\?"(?P<branch>(?:[^"\\\n]|\\.)*)":"(?P=branch)"')
STATIC_PROMPT_SINGLE_TERNARY_RE = re.compile(r"\$\{\}\?'(?P<branch>(?:[^'\\\n]|\\.)*)':'(?P=branch)'")


class StaticSourceUnavailable(RuntimeError):
    """The installed package does not expose source that can be statically inspected."""


def extract_static_prompts(target: CaptureTarget, install_dir: Path) -> StaticPromptResult | None:
    if target.agent.id != "claude-code":
        return None
    target.static_dir.mkdir(parents=True, exist_ok=True)
    candidates = load_or_extract_static_candidates(target, install_dir)
    result = match_static_candidates(target, candidates)
    _write_json(target.static_prompts_json_path, result)
    target.static_prompts_path.write_text(render_static_prompts_markdown(result), encoding="utf-8")
    return result


def load_or_extract_static_candidates(target: CaptureTarget, install_dir: Path) -> StaticCandidatesResult:
    cached = (
        read_static_candidates(target.static_candidates_json_path)
        if target.static_candidates_json_path.exists()
        else None
    )
    result = cached
    if result is None:
        source_path, source = _claude_code_source(install_dir)
        result = StaticCandidatesResult(
            agent_id=target.agent.id,
            version=target.version.version,
            source=source_path,
            extractor=STATIC_CANDIDATES_EXTRACTOR,
            min_length=STATIC_CANDIDATES_MIN_LENGTH,
            candidates=tuple(extract_string_candidates(source, min_length=STATIC_CANDIDATES_MIN_LENGTH)),
        )
    # Replaying an archive must apply today's filters without reinstalling old packages.
    result = replace(
        result,
        candidates=tuple(_prune_static_candidates(target.agent.id, list(result.candidates))),
    )
    if result != cached:
        write_static_candidates(target.static_candidates_json_path, result)
    return result


def _prune_static_candidates(agent_id: str, candidates: list[StaticPromptCandidate]) -> list[StaticPromptCandidate]:
    known_hashes = known_content_hashes(agent_id)
    return [candidate for candidate in candidates if _keep_static_candidate(candidate, known_hashes)]


def _keep_static_candidate(candidate: StaticPromptCandidate, known_hashes: frozenset[str]) -> bool:
    if is_static_resource(candidate.content):
        return False
    if candidate.score > 0:
        return True
    if content_hash(candidate.content) in known_hashes:
        return True
    if _has_short_instruction_marker(candidate.content):
        return True
    return len(candidate.content) >= 160


def _has_short_instruction_marker(content: str) -> bool:
    if len(content) >= 240:
        return False
    markers = ("DO NOT", "MUST", "IMPORTANT", "You are", "Your task", "Today's date", "conversation is provided")
    return any(marker in content for marker in markers)


def match_static_candidates(target: CaptureTarget, candidates: StaticCandidatesResult) -> StaticPromptResult:
    matches = _keep_known_or_prompt_like(match_candidates(target.agent.id, list(candidates.candidates)))
    result = StaticPromptResult(
        agent_id=target.agent.id,
        version=target.version.version,
        source=candidates.source,
        matches=matches,
    )
    return result


def read_static_candidates(path: Path) -> StaticCandidatesResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return StaticCandidatesResult(
        agent_id=str(payload.get("agent_id") or ""),
        version=str(payload.get("version") or ""),
        source=str(payload.get("source") or ""),
        extractor=str(payload.get("extractor") or ""),
        min_length=int(payload.get("min_length") or 0),
        candidates=tuple(
            _candidate_from_payload(item) for item in payload.get("candidates", []) if isinstance(item, dict)
        ),
    )


def write_static_candidates(path: Path, result: StaticCandidatesResult) -> None:
    path.write_text(json.dumps(_candidates_payload(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _keep_known_or_prompt_like(matches: tuple[StaticPromptMatch, ...]) -> tuple[StaticPromptMatch, ...]:
    kept = [
        match
        for match in matches
        if not is_static_resource(match.candidate.content)
        and (match.entry is not None or is_prompt_like(match.candidate.content))
    ]
    return tuple(sorted(kept, key=lambda match: (-match.candidate.score, match.candidate.order)))


def render_static_prompts_markdown(result: StaticPromptResult) -> str:
    lines = [
        "# Static Prompts",
        "",
        f"Agent: `{result.agent_id}`",
        f"Version: `{result.version}`",
        "",
    ]
    grouped = _group_matches(result.matches)
    for category, matches in grouped:
        lines.extend([f"## {_category_title(category)}", ""])
        for match in matches:
            title = match.entry.name if match.entry else _unknown_prompt_title(match)
            lines.extend(_match_markdown(title, match))
    return "\n".join(lines).rstrip() + "\n"


def _claude_code_source(install_dir: Path) -> tuple[str, str]:
    install_dir = Path(install_dir)
    package_dir = install_dir / "node_modules" / "@anthropic-ai" / "claude-code"
    package_json = package_dir / "package.json"
    if not package_json.exists():
        raise RuntimeError(f"Claude Code package not found: {package_dir}")
    package = json.loads(package_json.read_text(encoding="utf-8"))
    bin_path = _package_bin_path(package_dir, package.get("bin"))
    if bin_path.exists() and _looks_text(bin_path):
        return _relative_source(install_dir, bin_path), bin_path.read_text(encoding="utf-8", errors="replace")

    for candidate in _source_candidates(package_dir, bin_path):
        if not candidate.exists():
            continue
        if _looks_text(candidate):
            return _relative_source(install_dir, candidate), candidate.read_text(encoding="utf-8", errors="replace")
        js = extract_bun_entrypoint_js(candidate)
        if js:
            return _relative_source(install_dir, candidate), js
    raise StaticSourceUnavailable(f"package does not include extractable source under {package_dir}")


def _package_bin_path(package_dir: Path, bin_field: object) -> Path:
    if isinstance(bin_field, str):
        return package_dir / bin_field
    if isinstance(bin_field, dict):
        value = bin_field.get("claude") or next(iter(bin_field.values()), None)
        if isinstance(value, str):
            return package_dir / value
    return package_dir / "cli.js"


def _source_candidates(package_dir: Path, bin_path: Path) -> list[Path]:
    return [
        bin_path,
        package_dir / "cli.js",
        package_dir / "sdk.mjs",
        package_dir / "bin" / "claude",
        package_dir / "bin" / "claude.exe",
    ]


def _looks_text(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\0" not in chunk and (chunk.startswith(b"#!") or b"function" in chunk or b"import " in chunk)


def _relative_source(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _write_json(path: Path, result: StaticPromptResult) -> None:
    path.write_text(json.dumps(_result_payload(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _candidates_payload(result: StaticCandidatesResult) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "agent_id": result.agent_id,
        "version": result.version,
        "source": result.source,
        "extractor": result.extractor,
        "min_length": result.min_length,
        "summary": {"total": len(result.candidates)},
        "candidates": [_candidate_payload(candidate) for candidate in result.candidates],
    }


def _candidate_payload(candidate: StaticPromptCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "kind": candidate.kind,
        "order": candidate.order,
        "score": candidate.score,
        "variables": list(candidate.variables),
        "content_hash": content_hash(candidate.content),
        "content": candidate.content,
    }


def _candidate_from_payload(payload: dict[str, Any]) -> StaticPromptCandidate:
    return StaticPromptCandidate(
        id=str(payload.get("id") or ""),
        content=str(payload.get("content") or ""),
        kind=str(payload.get("kind") or ""),
        score=int(payload.get("score") or 0),
        order=int(payload.get("order") or 0),
        variables=tuple(str(item) for item in payload.get("variables", []) if item),
    )


def _result_payload(result: StaticPromptResult) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "agent_id": result.agent_id,
        "version": result.version,
        "source": result.source,
        "summary": {
            "total": len(result.matches),
            "known": result.known_count,
            "unknown": result.unknown_count,
        },
        "prompts": [_match_payload(match) for match in result.matches],
    }


def _match_payload(match: StaticPromptMatch) -> dict[str, Any]:
    entry = match.entry
    candidate = match.candidate
    payload: dict[str, Any] = {
        "id": entry.id if entry else f"unknown-{candidate.id}",
        "name": entry.name if entry else "Unknown static prompt",
        "category": entry.category if entry else "unknown",
        "description": entry.description if entry else "",
        "confidence": match.confidence,
        "match_reason": match.reason,
        "similarity": round(match.similarity, 4),
        "content_hash": content_hash(candidate.content),
        "source_order": candidate.order,
        "source_kind": candidate.kind,
        "score": candidate.score,
        "variables": list(candidate.variables),
        "content": candidate.content,
    }
    return payload


def _group_matches(matches: tuple[StaticPromptMatch, ...]) -> list[tuple[str, list[StaticPromptMatch]]]:
    groups: dict[str, list[StaticPromptMatch]] = {}
    for match in matches:
        category = match.entry.category if match.entry else "unknown"
        groups.setdefault(category, []).append(match)
    for group_matches in groups.values():
        group_matches.sort(key=_match_sort_key)
    return sorted(groups.items(), key=lambda item: (_category_sort(item[0]), item[0]))


def _match_sort_key(match: StaticPromptMatch) -> tuple[str, int]:
    if match.entry is not None:
        return (match.entry.name.lower(), match.candidate.order)
    return (_unknown_prompt_title(match), match.candidate.order)


def _category_sort(category: str) -> int:
    order = {
        "system-prompt": 0,
        "agent-prompt": 1,
        "system-reminder": 2,
        "tool-description": 3,
        "tool-parameter": 4,
        "skill": 5,
        "data": 6,
        "unknown": 99,
    }
    return order.get(category, 50)


def _category_title(category: str) -> str:
    return " ".join(part.capitalize() for part in category.split("-"))


def _match_markdown(title: str, match: StaticPromptMatch) -> list[str]:
    candidate = match.candidate
    entry = match.entry
    description = entry.description if entry else ""
    lines = [f"### {title}", ""]
    if description:
        lines.extend([description, ""])
    lines.extend(["", "```text", normalize_static_prompt_markdown_content(candidate.content), "```", ""])
    return lines


def _unknown_prompt_title(match: StaticPromptMatch) -> str:
    digest = content_hash(normalize_static_prompt_markdown_content(match.candidate.content))[:8]
    return f"Unknown static prompt {digest}"


def normalize_static_prompt_markdown_content(content: str) -> str:
    ternaries: list[str] = []
    value = STATIC_PROMPT_DOUBLE_TERNARY_EXPR_RE.sub(
        lambda match: _stash_ternary(ternaries, _normalize_double_ternary_expr(match)), content
    )
    value = STATIC_PROMPT_SINGLE_TERNARY_EXPR_RE.sub(
        lambda match: _stash_ternary(ternaries, _normalize_single_ternary_expr(match)), value
    )
    value = STATIC_PROMPT_DOUBLE_STRING_EXPR_RE.sub(lambda match: match.group("value"), value)
    value = STATIC_PROMPT_SINGLE_STRING_EXPR_RE.sub(lambda match: match.group("value"), value)
    value = STATIC_PROMPT_TERNARY_PREFIX_RE.sub("__PHISTORY_STATIC_TERNARY_PREFIX__", value)
    value = STATIC_PROMPT_SIMPLE_TERNARY_NAME_RE.sub("__PHISTORY_STATIC_SIMPLE_TERNARY__", value)
    value = STATIC_PROMPT_VARIABLE_RE.sub("${}", value)
    value = STATIC_PROMPT_DOUBLE_TERNARY_RE.sub(lambda match: match.group("branch"), value)
    value = STATIC_PROMPT_SINGLE_TERNARY_RE.sub(lambda match: match.group("branch"), value)
    value = value.replace("__PHISTORY_STATIC_TERNARY_PREFIX__", "${?")
    value = value.replace("__PHISTORY_STATIC_SIMPLE_TERNARY__", "${?}")
    for index, replacement in enumerate(ternaries):
        value = value.replace(f"__PHISTORY_STATIC_TERNARY_{index}__", replacement)
    value = STATIC_PROMPT_JOIN_EXPR_RE.sub("${[].join(", value)
    value = STATIC_PROMPT_MAP_EXPR_RE.sub("${[].map(($)=>", value)
    value = STATIC_PROMPT_SIMPLE_TERNARY_NAME_RE.sub("${?}", value)
    value = value.replace("\t", "    ")
    return "\n".join(line.rstrip() for line in value.split("\n"))


def _stash_ternary(ternaries: list[str], value: str) -> str:
    token = f"__PHISTORY_STATIC_TERNARY_{len(ternaries)}__"
    ternaries.append(value)
    return token


def _normalize_double_ternary_expr(match: re.Match[str]) -> str:
    return _normalize_ternary_expr(match, quote='"')


def _normalize_single_ternary_expr(match: re.Match[str]) -> str:
    return _normalize_ternary_expr(match, quote="'")


def _normalize_ternary_expr(match: re.Match[str], *, quote: str) -> str:
    yes = match.group("yes")
    no = match.group("no")
    if yes == no:
        return yes
    return f"${{? {quote}{yes}{quote} : {quote}{no}{quote}}}"
