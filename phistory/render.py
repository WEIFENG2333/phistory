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
    "like Claude Code, Codex, Antigravity, OpenClaw, Hermes, Kimi, opencode, and Pi."
)
CAPTURE_DOC = Path("docs/captures.md")
CAPTURE_JSON = Path("captures/index.json")
CHINESE_README = Path("README_zh.md")


def render_index(root: Path, output: Path) -> None:
    rows = read_capture_rows(root)
    base = output.parent
    output.write_text(_readme_markdown(rows, base), encoding="utf-8")
    (base / CHINESE_README).write_text(_readme_zh_markdown(rows, base), encoding="utf-8")
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
        static_prompts = version_dir / "static-prompts.md"
        static_prompts_json = version_dir / "static-prompts.json"
        static_candidates_json = version_dir / "static-candidates.json"
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
                "static_prompts": static_prompts if static_prompts.exists() else None,
                "static_prompts_json": static_prompts_json if static_prompts_json.exists() else None,
                "static_candidates_json": static_candidates_json if static_candidates_json.exists() else None,
                "meta": meta_path,
            }
        )
    return rows


def _readme_markdown(rows: list[dict[str, Any]], base: Path) -> str:
    status_rows = _agent_status_rows(rows)
    last_update = _latest_capture_time(rows)
    latest_capture = _latest_capture_row(rows)
    lines = [
        "# Phistory",
        "",
        "[中文](README_zh.md)",
        "",
        "Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, Antigravity, Kimi, opencode, OpenClaw, Hermes, and Pi.",
        "",
        (
            "Open the web viewer to compare prompt snapshots across versions and see how agent design "
            "changes through prompts, tools, policies, and runtime instructions."
        ),
        "",
        "**Start here:** [phistory.cc](https://phistory.cc/)",
        "",
    ]
    if latest_capture:
        lines.extend(
            [
                (
                    f"> Checks for new releases hourly. Archive last updated: **{_human_time(latest_capture['captured_at'])}**."
                ),
                "",
            ]
        )
    lines.extend(
        [
            "![Phistory prompt diff viewer](docs/screenshot.png)",
            "",
            "## Why Use It",
            "",
            "- Follow how Anthropic, OpenAI, and other agent builders iterate on system prompts over time.",
            "- See when new tools, permission checks, model defaults, and user-confirmation rules are added.",
            "- Compare how different CLIs structure agent behavior, tool use, and developer-facing constraints.",
            "- Cite stable prompt snapshots in posts, research notes, audits, or debugging reports.",
            "",
            "## How It Works",
            "",
            (
                "For each supported release, Phistory installs the exact CLI package, runs it once through "
                "[`claude-tap`](https://github.com/liaohch3/claude-tap), captures the prompt-bearing HTTP "
                "request without calling the real model provider, and stores the result under "
                "`captures/<agent>/<version>/` with `prompt.md`, `trace.jsonl`, and `meta.json`."
            ),
            "",
            (
                "For recent Claude Code releases, Phistory also extracts static prompt-like strings from the "
                "installed package and stores them as `static-prompts.md`, `static-prompts.json`, and "
                "`static-candidates.json`. The candidate archive keeps the raw extraction input so matching "
                "rules can be improved later without reinstalling every historical package."
            ),
            "",
            "GitHub Actions checks supported CLI releases every hour and commits new snapshots when they appear.",
            "",
            "## Local Development",
            "",
            "Use the hosted viewer at [phistory.cc](https://phistory.cc/). These commands are for local development, capture reproduction, historical backfills, and regenerating generated files.",
            "",
            "```bash",
            "# Install the locked development environment.",
            "uv sync --all-groups",
            "",
            "# Capture the latest supported CLI releases.",
            "uv run phistory capture --latest --agents antigravity,claude-code,codex,openclaw,hermes,kimi,opencode,pi",
            "",
            "# Capture a historical version range for one agent.",
            "uv run phistory backfill claude-code --from 2.1.113 --to latest",
            "",
            "# Rebuild static prompt files for the latest 10 captured Claude Code versions.",
            "uv run phistory extract-static claude-code --latest-captured 10",
            "",
            "# Regenerate README.md, README_zh.md, docs/captures.md, and captures/index.json.",
            "uv run phistory render-index",
            "",
            "# Regenerate the static web viewer at index.html.",
            "uv run phistory render-site",
            "```",
            "",
            "## Supported Agents",
            "",
            "- Claude Code (`@anthropic-ai/claude-code`)",
            "- Codex CLI (`@openai/codex`)",
            "- Antigravity CLI (`google-antigravity/antigravity-cli`)",
            "- OpenClaw (`openclaw`)",
            "- Hermes Agent (`hermes-agent`)",
            "- Kimi CLI (`MoonshotAI/kimi-cli`)",
            "- opencode (`opencode-ai`)",
            "- Pi (`@earendil-works/pi-coding-agent`)",
            "",
        ]
    )

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

    lines.extend(
        [
            "## Project Trend",
            "",
            "![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)",
            "",
        ]
    )

    return "\n".join(lines)


def _readme_zh_markdown(rows: list[dict[str, Any]], base: Path) -> str:
    status_rows = _agent_status_rows(rows)
    last_update = _latest_capture_time(rows)
    latest_capture = _latest_capture_row(rows)
    lines = [
        "# Phistory",
        "",
        "[English](README.md)",
        "",
        "Phistory 追踪 Claude Code、Codex、Antigravity、Kimi、opencode、OpenClaw、Hermes、Pi 等热门 coding-agent CLI 的系统提示词如何随版本变化。",
        "",
        (
            "打开网页查看器，可以对比不同版本的提示词快照，从 prompts、tools、策略和运行时指令里观察 "
            "agent 设计如何变化。"
        ),
        "",
        "**从这里开始：** [phistory.cc](https://phistory.cc/)",
        "",
    ]
    if latest_capture:
        lines.extend(
            [
                (f"> 每小时自动检查新版本，归档最近更新于 **{_human_time(latest_capture['captured_at'])}**。"),
                "",
            ]
        )
    lines.extend(
        [
            "![Phistory prompt diff viewer](docs/screenshot.png)",
            "",
            "## 为什么看它",
            "",
            "- 观察 Anthropic、OpenAI 等团队如何持续迭代 system prompt。",
            "- 看到新工具、权限检查、默认模型行为和用户确认规则是什么时候加入的。",
            "- 对比不同 CLI 如何组织 agent 行为、工具调用和面向开发者的约束。",
            "- 在文章、研究笔记、审计或排障记录里引用稳定的提示词快照。",
            "",
            "## 工作原理",
            "",
            (
                "Phistory 会安装每个受支持的具体 CLI 版本，通过 "
                "[`claude-tap`](https://github.com/liaohch3/claude-tap) 运行一次，抓取包含系统提示词的 "
                "HTTP 请求，不调用真实模型服务，然后把结果保存到 `captures/<agent>/<version>/`，"
                "里面包含 `prompt.md`、`trace.jsonl` 和 `meta.json`。"
            ),
            "",
            (
                "对于最近的 Claude Code 版本，Phistory 还会从安装包里提取疑似静态 prompt 的字符串，"
                "保存为 `static-prompts.md`、`static-prompts.json` 和 `static-candidates.json`。"
                "`static-candidates.json` 会保留原始候选内容，方便以后改进匹配规则时不用重新安装所有历史包。"
            ),
            "",
            "GitHub Actions 每小时检查一次支持的 CLI 版本；发现新版本后，会自动抓取并提交新的提示词快照。",
            "",
            "## 本地开发",
            "",
            "日常查看直接使用托管网页：[phistory.cc](https://phistory.cc/)。下面这些命令主要用于本地开发、复现抓取、回填历史版本，以及重新生成项目里的生成文件。",
            "",
            "```bash",
            "# 安装锁定的开发环境。",
            "uv sync --all-groups",
            "",
            "# 抓取所有受支持 CLI 的最新版本。",
            "uv run phistory capture --latest --agents antigravity,claude-code,codex,openclaw,hermes,kimi,opencode,pi",
            "",
            "# 回填某个 agent 的历史版本区间。",
            "uv run phistory backfill claude-code --from 2.1.113 --to latest",
            "",
            "# 重建最近 10 个已捕获 Claude Code 版本的静态 prompt 文件。",
            "uv run phistory extract-static claude-code --latest-captured 10",
            "",
            "# 重新生成 README.md、README_zh.md、docs/captures.md 和 captures/index.json。",
            "uv run phistory render-index",
            "",
            "# 重新生成静态网页查看器 index.html。",
            "uv run phistory render-site",
            "```",
            "",
            "## 支持的 Agent",
            "",
            "- Claude Code (`@anthropic-ai/claude-code`)",
            "- Codex CLI (`@openai/codex`)",
            "- Antigravity CLI (`google-antigravity/antigravity-cli`)",
            "- OpenClaw (`openclaw`)",
            "- Hermes Agent (`hermes-agent`)",
            "- Kimi CLI (`MoonshotAI/kimi-cli`)",
            "- opencode (`opencode-ai`)",
            "- Pi (`@earendil-works/pi-coding-agent`)",
            "",
        ]
    )

    lines.extend(["## 抓取状态", ""])
    if last_update:
        lines.extend([f"最近抓取更新：{last_update}", ""])
    if status_rows:
        lines.extend(["| Agent | 最新版本 | 快照数 | 最近抓取 |", "| --- | --- | ---: | --- |"])
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
        lines.extend(["暂无抓取。", ""])

    lines.extend(
        [
            "## 项目趋势",
            "",
            "![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)",
            "",
        ]
    )

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
        lines.append("| Agent | Version | Published | Captured | Snapshot | Static | Candidates | Raw Trace |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in _sorted_capture_rows(rows):
            prompt = _rel(row["prompt"], output.parent)
            trace = _rel(row["trace"], output.parent)
            static = _optional_link(row.get("static_prompts"), output.parent, "static-prompts.md")
            candidates = _optional_link(row.get("static_candidates_json"), output.parent, "static-candidates.json")
            published = _human_time(row["published_at"])
            captured = _human_time(row["captured_at"])
            prompt_label = _snapshot_label(row["agent_id"], row["version"], published)
            lines.append(
                f"| {row['agent']} | `{row['version']}` | {published} | {captured} | "
                f"[{prompt_label}]({prompt}) | {static} | {candidates} | [trace.jsonl]({trace}) |"
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
        "captures": [_capture_json_row(row, base) for row in _sorted_capture_rows(rows)],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _capture_json_row(row: dict[str, Any], base: Path) -> dict[str, str]:
    payload = {
        "agent_id": row["agent_id"],
        "agent": row["agent"],
        "version": row["version"],
        "published_at": row["published_at"],
        "captured_at": row["captured_at"],
        "prompt": _rel(row["prompt"], base),
        "trace": _rel(row["trace"], base),
        "meta": _rel(row["meta"], base),
    }
    if row.get("static_prompts"):
        payload["static_prompts"] = _rel(row["static_prompts"], base)
    if row.get("static_prompts_json"):
        payload["static_prompts_json"] = _rel(row["static_prompts_json"], base)
    if row.get("static_candidates_json"):
        payload["static_candidates_json"] = _rel(row["static_candidates_json"], base)
    return payload


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return Path(os.path.relpath(path.resolve(), base.resolve())).as_posix()


def _optional_link(path: Path | None, base: Path, label: str) -> str:
    if path is None:
        return ""
    return f"[{label}]({_rel(path, base)})"


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


def _latest_capture_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    dated_rows = [(dt, row) for row in rows if (dt := _parse_time(row["captured_at"])) is not None]
    if not dated_rows:
        return None
    return max(dated_rows, key=lambda item: item[0])[1]


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
