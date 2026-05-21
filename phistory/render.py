from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_VERSION_PART_RE = re.compile(r"\d+|[A-Za-z]+")


def render_index(root: Path, output: Path) -> None:
    rows: list[dict] = []
    for meta_path in sorted(root.glob("*/*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        version_dir = meta_path.parent
        rows.append(
            {
                "agent": meta.get("agent") or meta.get("agent_id") or version_dir.parent.name,
                "agent_id": meta.get("agent_id") or version_dir.parent.name,
                "version": meta.get("version") or version_dir.name,
                "published_at": meta.get("published_at") or "",
                "captured_at": meta.get("captured_at") or "",
                "prompt": version_dir / "prompt.md",
                "trace": version_dir / "trace.jsonl",
            }
        )

    lines = [
        "# phistory",
        "",
        "`phistory` archives versioned system prompt snapshots from agent CLIs.",
        "",
        "It installs a specific CLI release, runs it once through [`claude-tap`](https://github.com/WEIFENG2333/claude-tap), captures the prompt-bearing HTTP request, and writes a comparison-friendly Markdown snapshot. The upstream target is a local dummy server, so the captured run does not send a model request to the real provider.",
        "",
        "GitHub Actions runs this on a schedule and updates the repository when a new supported CLI version appears.",
        "",
        "## Usage",
        "",
        "```bash",
        "uv run phistory capture --latest --agents claude-code,codex",
        "uv run phistory backfill claude-code --from 2.1.113 --to latest",
        "uv run phistory render-index",
        "```",
        "",
        "## Supported Agents",
        "",
        "- Claude Code (`@anthropic-ai/claude-code`)",
        "- Codex CLI (`@openai/codex`)",
        "",
        "## Capture Format",
        "",
        "Each capture is stored under `captures/<agent>/<version>/`:",
        "",
        "- `prompt.md`: normalized prompt snapshot for reading and diffing",
        "- `trace.jsonl`: raw captured HTTP trace, kept unnormalized as evidence",
        "- `meta.json`: package, version, command, and capture metadata",
        "",
    ]
    if rows:
        lines.extend(["## Latest Captures", ""])
        for row in _latest_rows(rows):
            published = _human_time(row["published_at"])
            captured = _human_time(row["captured_at"])
            lines.append(f"- {row['agent']}: `{row['version']}` published {published}, captured {captured}")
        lines.append("")
    lines.extend(["## Captures", ""])
    if not rows:
        lines.extend(["No captures yet.", ""])
    else:
        lines.append("| Agent | Version | Published | Captured | Snapshot | Raw Trace |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in sorted(rows, key=lambda item: (item["agent_id"], _version_key(item["version"])), reverse=True):
            prompt = _rel(row["prompt"], output.parent)
            trace = _rel(row["trace"], output.parent)
            published = _human_time(row["published_at"])
            captured = _human_time(row["captured_at"])
            prompt_label = _snapshot_label(row["agent_id"], row["version"], published)
            lines.append(
                f"| {row['agent']} | `{row['version']}` | {published} | {captured} | "
                f"[{prompt_label}]({prompt}) | [trace.jsonl]({trace}) |"
            )
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _version_key(version: str) -> tuple:
    parts: list[tuple[int, int | str]] = []
    for part in _VERSION_PART_RE.findall(version):
        if part.isdigit():
            parts.append((1, int(part)))
        else:
            parts.append((0, part))
    return tuple(parts)


def _human_time(value: str) -> str:
    if not value:
        return ""
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _snapshot_label(agent_id: str, version: str, published: str) -> str:
    published_part = f", published {published}" if published else ""
    return f"{agent_id} {version}{published_part}"


def _latest_rows(rows: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for row in rows:
        current = latest.get(row["agent_id"])
        if current is None or _version_key(row["version"]) > _version_key(current["version"]):
            latest[row["agent_id"]] = row
    return sorted(latest.values(), key=lambda item: item["agent_id"])
