from __future__ import annotations

import json
from pathlib import Path


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
        "`phistory` captures versioned prompt snapshots from agent CLIs.",
        "",
        "It installs a specific CLI version, runs it once through `claude-tap`, and archives the prompt-bearing request body as Markdown. The upstream target is a local dummy server, so the model request is never sent to the real provider.",
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
        "- `prompt.md`: normalized prompt snapshot",
        "- `trace.jsonl`: raw captured HTTP trace",
        "- `meta.json`: package, version, command, and capture metadata",
        "",
    ]
    lines.extend(["## Captures", ""])
    if not rows:
        lines.extend(["No captures yet.", ""])
    else:
        lines.append("| Agent | Version | Published | Captured | Prompt | Trace |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in sorted(rows, key=lambda item: (item["agent_id"], item["version"]), reverse=True):
            prompt = _rel(row["prompt"], output.parent)
            trace = _rel(row["trace"], output.parent)
            lines.append(
                f"| {row['agent']} | `{row['version']}` | {row['published_at']} | {row['captured_at']} | "
                f"[prompt]({prompt}) | [trace]({trace}) |"
            )
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
