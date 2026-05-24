from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_VERSION_PART_RE = re.compile(r"\d+|[A-Za-z]+")

PROJECT_DESCRIPTION = (
    "Phistory automatically archives versioned system prompt snapshots from agent CLIs "
    "like Claude Code, Codex, OpenClaw, Hermes, Kimi, opencode, and Pi."
)
CAPTURE_DOC = Path("docs/captures.md")
CAPTURE_JSON = Path("captures/index.json")


def render_index(root: Path, output: Path) -> None:
    rows = read_capture_rows(root)
    base = output.parent
    output.write_text(_readme_markdown(rows, base), encoding="utf-8")
    _write_capture_doc(rows, base)
    _write_capture_json(rows, output.parent)


def read_capture_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for meta_path in sorted(root.glob("*/*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        version_dir = meta_path.parent
        prompt = version_dir / "prompt.md"
        trace = version_dir / "trace.jsonl"
        if not prompt.exists() or not trace.exists():
            continue
        rows.append(
            {
                "agent": meta.get("agent") or meta.get("agent_id") or version_dir.parent.name,
                "agent_id": meta.get("agent_id") or version_dir.parent.name,
                "version": meta.get("version") or version_dir.name,
                "published_at": meta.get("published_at") or "",
                "captured_at": meta.get("captured_at") or "",
                "prompt": prompt,
                "trace": trace,
                "meta": meta_path,
            }
        )
    return rows


def _readme_markdown(rows: list[dict[str, Any]], base: Path) -> str:
    status_rows = _agent_status_rows(rows)
    last_update = _latest_capture_time(rows)
    lines = [
        "# Phistory",
        "",
        PROJECT_DESCRIPTION,
        "",
        (
            "It installs a specific CLI release, runs it once through "
            "[`claude-tap`](https://github.com/WEIFENG2333/claude-tap), captures the prompt-bearing "
            "HTTP request, and writes a comparison-friendly Markdown snapshot."
        ),
        "",
        "GitHub Actions checks supported CLI releases every hour and commits new prompt snapshots when they appear.",
        "",
        "[Open the prompt diff viewer](https://phistory.cc/)",
        "",
        "![Phistory prompt diff viewer](docs/screenshot.png)",
        "",
        "## Usage",
        "",
        "```bash",
        "uv run phistory capture --latest --agents claude-code,codex,openclaw,hermes,kimi,opencode,pi",
        "uv run phistory backfill claude-code --from 2.1.113 --to latest",
        "uv run phistory render-index",
        "uv run phistory render-site",
        "```",
        "",
        "## Web UI",
        "",
        "`index.html` is a static prompt viewer with version navigation and Monaco-powered diffs. GitHub Pages deploys it directly from this repository.",
        "",
        (
            "Use the viewer for human comparison. Use [`captures/index.json`](captures/index.json) "
            "and [`docs/captures.md`](docs/captures.md) when you need an index of every archived snapshot."
        ),
        "",
        "## Supported Agents",
        "",
        "- Claude Code (`@anthropic-ai/claude-code`)",
        "- Codex CLI (`@openai/codex`)",
        "- OpenClaw (`openclaw`)",
        "- Hermes Agent (`hermes-agent`)",
        "- Kimi CLI (`MoonshotAI/kimi-cli`)",
        "- opencode (`opencode-ai`)",
        "- Pi (`@earendil-works/pi-coding-agent`)",
        "",
        "## Capture Format",
        "",
        "Each capture is stored under `captures/<agent>/<version>/`:",
        "",
        "- `prompt.md`: normalized prompt snapshot for reading and diffing",
        "- `trace.jsonl`: raw captured HTTP trace, kept unnormalized as evidence",
        "- `meta.json`: package, version, command, and capture metadata",
        "",
        "The generated indexes are:",
        "",
        "- [`captures/index.json`](captures/index.json): compact machine-readable capture index",
        "- [`docs/captures.md`](docs/captures.md): full human-readable capture table",
        "",
        "## For AI Agents",
        "",
        "- Use `README.md` for the project overview and current capture status.",
        "- Use `captures/index.json` to discover available agents, versions, prompt paths, and trace paths.",
        "- Use `captures/<agent>/<version>/prompt.md` when you need a normalized prompt snapshot.",
        "- Use `captures/<agent>/<version>/trace.jsonl` only when you need raw HTTP capture evidence.",
        "- Treat `index.html` as a human-facing viewer; it is not the canonical machine-readable index.",
        "",
        "## Links",
        "",
        "- [linux.do](https://linux.do)",
        "",
        "## License",
        "",
        "[MIT](LICENSE)",
        "",
    ]

    lines.extend(["## Capture Status", ""])
    if last_update:
        lines.extend([f"Last capture update: {last_update}", ""])
    if status_rows:
        lines.extend(["| Agent | Latest | Captures | Last Captured |", "| --- | --- | ---: | --- |"])
        for row in status_rows:
            latest = row["latest"]
            prompt = _rel(latest["prompt"], base)
            latest_label = _latest_label(latest)
            lines.append(
                f"| {latest['agent']} | [{latest_label}]({prompt}) | {row['count']} | "
                f"{_human_time(latest['captured_at'])} |"
            )
        lines.append("")
    else:
        lines.extend(["No captures yet.", ""])

    return "\n".join(lines)


def _write_capture_doc(rows: list[dict[str, Any]], base: Path) -> None:
    output = base / CAPTURE_DOC
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Capture Index",
        "",
        (
            "Full generated index of archived prompt snapshots. "
            "The short project overview lives in [README.md](../README.md)."
        ),
        "",
    ]
    if not rows:
        lines.extend(["No captures yet.", ""])
    else:
        lines.append("| Agent | Version | Published | Captured | Snapshot | Raw Trace |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in _sorted_capture_rows(rows):
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


def _write_capture_json(rows: list[dict[str, Any]], base: Path) -> None:
    output = base / CAPTURE_JSON
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": PROJECT_DESCRIPTION,
        "site": "https://phistory.cc/",
        "updated_at": _latest_capture_iso(rows),
        "agents": [
            {
                "agent_id": item["latest"]["agent_id"],
                "agent": item["latest"]["agent"],
                "latest_version": item["latest"]["version"],
                "latest_published_at": item["latest"]["published_at"],
                "latest_captured_at": item["latest"]["captured_at"],
                "captures": item["count"],
            }
            for item in _agent_status_rows(rows)
        ],
        "captures": [
            {
                "agent_id": row["agent_id"],
                "agent": row["agent"],
                "version": row["version"],
                "published_at": row["published_at"],
                "captured_at": row["captured_at"],
                "prompt": _rel(row["prompt"], base),
                "trace": _rel(row["trace"], base),
                "meta": _rel(row["meta"], base),
            }
            for row in _sorted_capture_rows(rows)
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return Path(os.path.relpath(path.resolve(), base.resolve())).as_posix()


def _version_key(version: str) -> tuple:
    parts: list[tuple[int, int | str]] = []
    for part in _VERSION_PART_RE.findall(version):
        if part.isdigit():
            parts.append((1, int(part)))
        else:
            parts.append((0, part))
    return tuple(parts)


def _human_time(value: str) -> str:
    dt = _parse_time(value)
    if dt is None:
        return value.strip() if value else ""
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _snapshot_label(agent_id: str, version: str, published: str) -> str:
    published_part = f", published {published}" if published else ""
    return f"{agent_id} {version}{published_part}"


def _latest_label(row: dict[str, Any]) -> str:
    published = _date_only(row["published_at"])
    if not published:
        return row["version"]
    return f"{row['version']} - {published}"


def _date_only(value: str) -> str:
    dt = _parse_time(value)
    if dt is None:
        return value[:10] if value else ""
    return dt.strftime("%Y-%m-%d")


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _latest_capture_time(rows: list[dict[str, Any]]) -> str:
    value = _latest_capture_iso(rows)
    return _human_time(value) if value else ""


def _latest_capture_iso(rows: list[dict[str, Any]]) -> str:
    times = [dt for row in rows if (dt := _parse_time(row["captured_at"])) is not None]
    latest = max(times, default=None)
    return latest.isoformat().replace("+00:00", "Z") if latest else ""


def _agent_status_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_agent.setdefault(row["agent_id"], []).append(row)
    status = []
    for agent_id, agent_rows in by_agent.items():
        latest = max(agent_rows, key=lambda item: _version_key(item["version"]))
        status.append({"agent_id": agent_id, "latest": latest, "count": len(agent_rows)})
    return sorted(status, key=lambda item: item["agent_id"])


def _sorted_capture_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda item: (item["agent_id"], _version_key(item["version"])), reverse=True)
