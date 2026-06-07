import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

from phistory.render import _version_key, read_capture_rows

AGENT_ICONS = {
    "claude-code": "docs/agent-icons/claude-code.png",
    "codex": "docs/agent-icons/codex.png",
    "hermes": "docs/agent-icons/hermes.png",
    "kimi": "docs/agent-icons/kimi.png",
    "openclaw": "docs/agent-icons/openclaw.png",
    "opencode": "docs/agent-icons/opencode.png",
    "pi": "docs/agent-icons/pi.png",
}
CHANGE_SMALL_MAX_LINES = 12
CHANGE_MEDIUM_MAX_LINES = 80
CHANGE_FULL_SCALE_RATIO = 0.30
CHANGE_MIN_SCALE = 14


def render_site(root: Path, output: Path) -> None:
    output.write_text(_HTML.replace("__PHISTORY_MANIFEST__", _json_for_script(_build_manifest(root))), encoding="utf-8")


def _build_manifest(root: Path) -> dict:
    rows = read_capture_rows(root)
    agents = []
    for agent_id in sorted({row["agent_id"] for row in rows}):
        agent_rows = sorted(
            [row for row in rows if row["agent_id"] == agent_id],
            key=lambda row: _version_key(row["version"]),
            reverse=True,
        )
        versions = _site_versions(agent_rows)
        latest = versions[0] if versions else None
        agents.append(
            {
                "id": agent_id,
                "name": latest["agent"] if latest else agent_id,
                "icon": AGENT_ICONS.get(agent_id),
                "latest": latest,
                "versions": versions,
            }
        )
    return {"agents": agents, "count": len(rows)}


def _site_versions(rows: list[dict]) -> list[dict]:
    versions = []
    for index, row in enumerate(rows):
        previous = rows[index + 1] if index + 1 < len(rows) else None
        item = _site_row(row)
        item["change"] = _change_summary(row, previous)
        versions.append(item)
    _add_relative_change_scale(versions)
    return versions


def _site_row(row: dict) -> dict:
    return {
        "agent_id": row["agent_id"],
        "agent": row["agent"],
        "version": row["version"],
        "published_compact": _compact_date(row["published_at"]),
        "published_display": _display_time(row["published_at"]),
        "captured_display": _display_time(row.get("captured_at") or ""),
        "prompt": row["prompt"].as_posix(),
        "trace": row["trace"].as_posix(),
    }


def _change_summary(current: dict, previous: dict | None) -> dict:
    try:
        new_lines = current["prompt"].read_text(encoding="utf-8").splitlines()
    except OSError:
        new_lines = []
    if previous is None:
        return {
            "previous_version": None,
            "added_lines": 0,
            "removed_lines": 0,
            "changed_lines": 0,
            "level": 0,
            "line_count": len(new_lines),
            "_compared_line_count": len(new_lines),
        }
    try:
        old_lines = previous["prompt"].read_text(encoding="utf-8").splitlines()
    except OSError:
        return {
            "previous_version": previous["version"],
            "added_lines": 0,
            "removed_lines": 0,
            "changed_lines": 0,
            "level": 0,
            "line_count": len(new_lines),
            "_compared_line_count": len(new_lines),
        }

    added = 0
    removed = 0
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "insert":
            added += new_end - new_start
        elif tag == "delete":
            removed += old_end - old_start
        elif tag == "replace":
            removed += old_end - old_start
            added += new_end - new_start
    changed = added + removed
    return {
        "previous_version": previous["version"],
        "added_lines": added,
        "removed_lines": removed,
        "changed_lines": changed,
        "level": _change_level(changed),
        "line_count": len(new_lines),
        "_compared_line_count": max(len(old_lines), len(new_lines)),
    }


def _display_time(value: str) -> str:
    dt = _parse_time(value)
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _change_level(changed_lines: int) -> int:
    if changed_lines == 0:
        return 0
    if changed_lines <= CHANGE_SMALL_MAX_LINES:
        return 1
    if changed_lines <= CHANGE_MEDIUM_MAX_LINES:
        return 2
    return 3


def _add_relative_change_scale(versions: list[dict]) -> None:
    for item in versions:
        change = item["change"]
        compared_line_count = change.pop("_compared_line_count")
        change["scale"] = _relative_change_scale(change["changed_lines"], compared_line_count)


def _relative_change_scale(changed_lines: int, compared_line_count: int) -> int:
    if changed_lines <= 0 or compared_line_count <= 0:
        return 0
    ratio = changed_lines / compared_line_count
    return round(max(CHANGE_MIN_SCALE, min(100, ratio / CHANGE_FULL_SCALE_RATIO * 100)))


def _compact_date(value: str) -> str:
    dt = _parse_time(value)
    if dt is None:
        return value[:10] if value else "unknown"
    return dt.strftime("%Y-%m-%d")


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _json_for_script(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Phistory automatically archives versioned system prompt snapshots and diffs from agent CLIs like Claude Code, Codex, OpenClaw, Hermes, Kimi, opencode, and Pi.">
<meta name="keywords" content="Phistory, system prompt history, system prompt diff, Claude Code prompt, Codex CLI prompt, OpenClaw prompt, Hermes prompt, Kimi CLI prompt, opencode prompt, Pi prompt, agent CLI, prompt archive">
<meta name="application-name" content="Phistory">
<meta name="robots" content="index,follow">
<meta name="theme-color" content="#1c1c1e" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#fbfbfa" media="(prefers-color-scheme: light)">
<meta property="og:title" content="Phistory">
<meta property="og:description" content="Automatically archived system prompt snapshots and diffs for agent CLIs like Claude Code, Codex, OpenClaw, Hermes, Kimi, opencode, and Pi.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://phistory.cc/">
<meta property="og:image" content="https://phistory.cc/docs/screenshot.png">
<meta property="og:site_name" content="Phistory">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Phistory">
<meta name="twitter:description" content="Automatically archived system prompt snapshots and diffs for agent CLIs like Claude Code, Codex, OpenClaw, Hermes, Kimi, opencode, and Pi.">
<meta name="twitter:image" content="https://phistory.cc/docs/screenshot.png">
<link rel="canonical" href="https://phistory.cc/">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%230f1115'/%3E%3Cpath d='M8 10h16M8 16h10M8 22h14' stroke='%237cc7ff' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E">
<title>Phistory - Agent CLI System Prompt Diff History</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Phistory",
  "url": "https://phistory.cc/",
  "description": "Automatically archived system prompt snapshots and diffs for agent CLIs.",
  "sameAs": ["https://github.com/WEIFENG2333/phistory"],
  "about": ["Claude Code", "Codex CLI", "OpenClaw", "Hermes", "Kimi CLI", "opencode", "Pi"]
}
</script>
<style>
:root {
  color-scheme: dark;
  --bg: #1e1e1e;
  --top: #1c1c1e;
  --popover: rgba(42, 42, 44, .98);
  --line: rgba(255, 255, 255, .10);
  --text: #f2f2f3;
  --muted: #a0a0a7;
  --accent: #7ab7e6;
  --control-bg: rgba(255, 255, 255, .055);
  --control-hover: rgba(255, 255, 255, .075);
  --control-active: rgba(255, 255, 255, .14);
  --menu-active: rgba(255, 255, 255, .11);
  --focus-line: rgba(255, 255, 255, .34);
  --scrollbar: rgba(255, 255, 255, .22);
  --diffstat-track: rgba(255, 255, 255, .16);
  --diffstat-add: #3fb950;
  --diffstat-remove: #f85149;
}
:root[data-theme="light"] {
  color-scheme: light;
  --bg: #f5f5f3;
  --top: #fbfbfa;
  --popover: rgba(255, 255, 255, .98);
  --line: rgba(0, 0, 0, .12);
  --text: #1d1d1f;
  --muted: #73737a;
  --accent: #0a66b2;
  --control-bg: rgba(0, 0, 0, .045);
  --control-hover: rgba(0, 0, 0, .052);
  --control-active: rgba(0, 0, 0, .095);
  --menu-active: rgba(0, 0, 0, .07);
  --focus-line: rgba(0, 0, 0, .30);
  --scrollbar: rgba(0, 0, 0, .22);
  --diffstat-track: rgba(0, 0, 0, .14);
  --diffstat-add: #1f883d;
  --diffstat-remove: #cf222e;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 13px/1.4 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  overflow: hidden;
}
button, input { font: inherit; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: none; }
.shell {
  height: 100vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}
.topbar {
  min-width: 0;
  background: var(--top);
  border-bottom: 1px solid var(--line);
  padding: 7px 14px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 18px;
  user-select: none;
  -webkit-user-select: none;
}
.left-tools {
  display: flex;
  align-items: center;
  justify-self: start;
  gap: 18px;
  min-width: 0;
}
.brand {
  display: flex;
  align-items: center;
  min-width: 0;
}
.brand h1 {
  margin: 0;
  font-size: 16px;
  line-height: 1;
  letter-spacing: 0;
  font-weight: 700;
}
.compare {
  min-width: 0;
  display: grid;
  grid-template-columns: 196px 22px 236px;
  gap: 0;
  align-items: center;
  justify-content: center;
  padding: 2px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--control-bg);
}
.control {
  min-width: 0;
  height: 30px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text);
  padding: 0 9px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 7px;
  cursor: pointer;
  box-shadow: none;
}
.control:hover { background: var(--control-hover); }
.control[aria-expanded="true"] {
  background: var(--control-active);
  box-shadow: none;
}
.agent-control {
  width: auto;
  height: 30px;
  min-width: 136px;
  padding: 0 9px 0 10px;
  justify-content: flex-start;
  gap: 8px;
  border: 1px solid var(--line);
  background: var(--control-bg);
}
.agent-control:hover,
.agent-control[aria-expanded="true"] {
  color: var(--text);
  background: var(--control-hover);
}
.agent-control strong {
  max-width: 128px;
}
.agent-control::after {
  content: "";
  width: 6px;
  height: 6px;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  color: var(--muted);
  margin-left: auto;
  transform: rotate(45deg) translate(-1px, -1px);
  transform-origin: center;
  transition: transform .14s ease, color .14s ease;
}
.agent-control[aria-expanded="true"]::after {
  color: var(--text);
  transform: rotate(225deg) translate(-1px, -1px);
}
.agent-icon {
  width: 17px;
  height: 17px;
  border-radius: 4px;
  object-fit: cover;
  flex: 0 0 auto;
  background: var(--control-hover);
}
.version-control {
  width: 100%;
}
.control:focus-visible,
.icon-button:focus-visible,
.option:focus-visible {
  outline: 1px solid var(--focus-line);
  outline-offset: 2px;
}
.control strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  height: 100%;
}
.control small {
  color: var(--muted);
  flex-shrink: 0;
  font-size: 12px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  height: 100%;
}
.version-sub {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  color: var(--muted);
  line-height: 1;
}
.version-sub small {
  height: auto;
}
.latest-mark {
  color: var(--accent);
  font-size: 11px;
  font-style: normal;
  font-weight: 650;
  letter-spacing: 0;
}
.arrow {
  color: var(--muted);
  font-size: 14px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
}
.actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  justify-self: end;
  gap: 4px;
}
.icon-button {
  width: 26px;
  height: 28px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: inset 0 -1px 0 transparent;
}
.icon-button:hover {
  color: var(--text);
  box-shadow: none;
  text-decoration: none;
}
.view-button {
  width: auto;
  min-width: 42px;
  padding: 0 8px;
  font-weight: 650;
  color: var(--muted);
}
.view-button:hover {
  color: var(--text);
}
.github-mark {
  width: 17px;
  height: 17px;
  fill: currentColor;
  display: block;
}
.theme-mark {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid currentColor;
  display: block;
  background: linear-gradient(90deg, currentColor 0 50%, transparent 50% 100%);
}
.editor {
  min-height: 0;
  position: relative;
  touch-action: pan-y;
  overscroll-behavior: contain;
}
#diff { position: absolute; inset: 0; }
.trace-view {
  position: absolute;
  inset: 0;
  display: none;
  overflow: auto;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar) transparent;
  background: var(--bg);
}
.trace-view::-webkit-scrollbar { width: 8px; height: 8px; }
.trace-view::-webkit-scrollbar-track { background: transparent; }
.trace-view::-webkit-scrollbar-thumb {
  background: var(--scrollbar);
  border-radius: 999px;
}
.shell[data-view="trace"] #diff { display: none; }
.shell[data-view="trace"] .trace-view { display: block; }
.shell[data-view="trace"] .compare {
  grid-template-columns: 236px;
}
.shell[data-view="trace"] #from,
.shell[data-view="trace"] .arrow {
  display: none;
}
.trace-page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 22px 22px 42px;
}
.trace-hero {
  border-bottom: 1px solid var(--line);
  padding: 4px 0 18px;
  margin-bottom: 14px;
}
.trace-eyebrow {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 7px;
}
.trace-title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 9px 12px;
}
.trace-title h2 {
  margin: 0;
  font-size: 26px;
  line-height: 1.12;
  letter-spacing: 0;
}
.trace-title span {
  color: var(--muted);
  font-size: 13px;
}
.trace-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 12px;
  color: var(--muted);
}
.trace-meta b {
  color: var(--text);
  font-weight: 600;
}
.trace-jumpbar {
  position: sticky;
  top: 0;
  z-index: 3;
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 8px 0;
  margin: -4px 0 6px;
  background: color-mix(in srgb, var(--bg) 92%, transparent);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(14px);
  overflow-x: auto;
  scrollbar-width: none;
}
.trace-jumpbar::-webkit-scrollbar {
  display: none;
}
.trace-jump {
  flex: 0 0 auto;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  padding: 6px 9px;
  font: inherit;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}
.trace-jump:hover,
.trace-jump:focus-visible {
  color: var(--text);
  background: var(--control-bg);
  outline: none;
}
.trace-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-bottom: 1px solid var(--line);
  margin-bottom: 20px;
}
.trace-stat {
  min-width: 0;
  padding: 13px 14px 13px 0;
}
.trace-stat small {
  display: block;
  color: var(--muted);
  font-size: 11px;
  margin-bottom: 4px;
}
.trace-stat strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.trace-section {
  border-bottom: 1px solid var(--line);
  scroll-margin-top: 48px;
}
.trace-summary {
  width: 100%;
  border: 0;
  background: transparent;
  cursor: pointer;
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 8px;
  color: var(--text);
  font: inherit;
  text-align: left;
  transition: color .14s ease, background-color .14s ease;
}
.trace-summary:hover {
  color: var(--text);
  background: color-mix(in srgb, var(--control-bg) 45%, transparent);
}
.trace-chevron {
  flex: 0 0 auto;
  width: 14px;
  height: 14px;
  color: var(--muted);
  transition: color .14s ease, transform .14s ease;
}
.trace-chevron svg {
  display: block;
  width: 100%;
  height: 100%;
  stroke: currentColor;
}
.trace-section.is-open > .trace-summary .trace-chevron,
.tool-card.is-open > .trace-summary .trace-chevron {
  color: var(--text);
  transform: rotate(90deg);
}
.trace-summary strong {
  font-size: 15px;
}
.trace-summary small {
  margin-left: auto;
  color: var(--muted);
}
.trace-body {
  padding: 6px 10px 22px 34px;
}
.trace-content {
  max-height: 0;
  overflow: hidden;
}
.trace-section.is-open > .trace-content,
.tool-card.is-open > .trace-content {
  max-height: none;
  overflow: visible;
}
.prompt-block + .prompt-block {
  margin-top: 22px;
}
.trace-rendered {
  color: var(--text);
  font-size: 14px;
  line-height: 1.62;
  overflow-wrap: anywhere;
}
.trace-rendered h1,
.trace-rendered h2,
.trace-rendered h3,
.trace-rendered h4 {
  margin: 18px 0 8px;
  font-size: 15px;
  line-height: 1.35;
}
.trace-rendered h1:first-child,
.trace-rendered h2:first-child,
.trace-rendered h3:first-child,
.trace-rendered h4:first-child {
  margin-top: 0;
}
.trace-rendered p {
  margin: 0 0 11px;
}
.trace-rendered p:last-child,
.trace-rendered ul:last-child {
  margin-bottom: 0;
}
.trace-rendered ul {
  margin: 0 0 12px 18px;
  padding: 0;
}
.trace-rendered li {
  margin: 4px 0;
}
.trace-rendered code {
  color: var(--text);
  background: color-mix(in srgb, var(--muted) 14%, transparent);
  border-radius: 4px;
  padding: 0 3px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
.trace-rendered pre {
  margin: 10px 0;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--control-bg);
  overflow: auto;
  white-space: pre-wrap;
}
.trace-mode {
  display: none;
  margin-left: 6px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  padding: 4px 7px;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.trace-mode:hover,
.trace-mode:focus-visible {
  color: var(--text);
  background: var(--control-bg);
  outline: none;
}
.trace-section.is-open > .trace-summary .trace-mode {
  display: inline-flex;
}
.trace-raw {
  display: none;
}
.trace-section.is-raw .trace-rendered {
  display: none;
}
.trace-section.is-raw .trace-raw {
  display: block;
}
.trace-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  color: var(--text);
  font: 13px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
.trace-message {
  padding: 12px 0;
  border-top: 1px solid var(--line);
}
.trace-message:first-child {
  border-top: 0;
  padding-top: 0;
}
.trace-role {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .04em;
  margin-bottom: 6px;
}
.tool-list {
  display: grid;
  gap: 9px;
}
.tool-card {
  border: 1px solid var(--line);
  border-radius: 9px;
  background: color-mix(in srgb, var(--control-bg) 86%, var(--bg));
  overflow: hidden;
  transition: border-color .14s ease, background-color .14s ease;
}
.tool-card.is-open {
  border-color: color-mix(in srgb, var(--muted) 34%, var(--line));
  background: color-mix(in srgb, var(--control-bg) 94%, var(--bg));
}
.tool-card .trace-summary {
  min-height: 44px;
  padding: 0 14px 0 10px;
}
.tool-card .trace-summary strong {
  font-size: 13px;
}
.tool-card .trace-summary small {
  max-width: 52%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-card .trace-body {
  padding: 10px 16px 16px 35px;
}
.tool-description {
  margin: 0 0 14px;
  color: var(--text);
  font-size: 13px;
  line-height: 1.56;
}
.tool-params {
  display: grid;
  gap: 7px;
  margin: 0 0 11px;
}
.tool-param {
  display: grid;
  grid-template-columns: minmax(120px, .7fr) minmax(82px, .28fr) minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: color-mix(in srgb, var(--bg) 82%, var(--control-bg));
}
.tool-param-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 650;
  font-size: 13px;
}
.tool-param-type {
  color: var(--muted);
  font-size: 12px;
}
.tool-param-required {
  color: var(--text);
  font-weight: 700;
}
.tool-param-desc {
  min-width: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}
.tool-raw .trace-summary {
  min-height: 28px;
  width: auto;
  padding: 0 4px;
  color: var(--muted);
  font-size: 12px;
}
.tool-raw {
  border-bottom: 0;
  margin-top: 8px;
}
.tool-raw .trace-summary strong {
  font-size: 12px;
  font-weight: 650;
}
.tool-raw .trace-chevron {
  width: 10px;
  height: 10px;
}
.tool-raw .trace-body {
  padding: 6px 0 0;
}
.tool-raw .raw-json {
  max-height: 360px;
  font-size: 11px;
}
.raw-json {
  margin: 0;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--control-bg);
  overflow: auto;
  max-height: 520px;
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
#diff .inputarea {
  caret-color: transparent;
}
.empty { padding: 22px; color: var(--muted); }
.popover {
  position: fixed;
  z-index: 20;
  --popover-max-height: min(420px, calc(100vh - 24px));
  max-height: var(--popover-max-height);
  background: var(--popover);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: none;
  overflow: hidden;
  display: none;
  backdrop-filter: blur(18px);
}
.popover.open { display: block; }
.options {
  overflow: auto;
  padding: 4px 4px 12px;
  max-height: calc(var(--popover-max-height) - 2px);
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar) transparent;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}
.options::-webkit-scrollbar {
  width: 6px;
}
.options::-webkit-scrollbar-track {
  background: transparent;
}
.options::-webkit-scrollbar-thumb {
  background: var(--scrollbar);
  border-radius: 999px;
}
.options::-webkit-scrollbar-thumb:hover {
  background: var(--muted);
}
.option {
  width: 100%;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text);
  padding: 6px 7px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  text-align: left;
  cursor: pointer;
}
.version-option {
  min-height: 44px;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  padding: 7px 8px;
}
.version-copy {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, auto) auto;
  gap: 12px;
  align-items: baseline;
}
.version-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
}
.mini-diffstat {
  --fill-width: 0%;
  --added-part: 50%;
  --removed-part: 50%;
  width: 42px;
  height: 7px;
  border-radius: 999px;
  background: var(--diffstat-track);
  display: flex;
  justify-content: flex-end;
  overflow: hidden;
}
.diffstat-fill {
  width: var(--fill-width);
  height: 100%;
  display: flex;
  border-radius: inherit;
  overflow: hidden;
  min-width: 0;
}
.mini-diffstat i {
  display: block;
  height: 100%;
}
.mini-diffstat .removed {
  width: var(--removed-part);
  background: var(--diffstat-remove);
}
.mini-diffstat .added {
  width: var(--added-part);
  background: var(--diffstat-add);
}
.mini-diffstat.no-change {
  width: 28px;
  height: 3px;
}
.mini-diffstat.no-change .diffstat-fill {
  display: none;
}
.option:hover { background: var(--control-hover); }
.option.active {
  background: var(--menu-active);
  box-shadow: none;
}
.agent-option {
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  padding: 8px 9px;
}
.agent-option small {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.option strong { font-weight: 600; }
.option span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.option small {
  color: var(--muted);
  white-space: nowrap;
}
@media (max-width: 880px) {
  body { overflow: hidden; }
  .shell {
    height: 100vh;
    height: 100dvh;
    grid-template-rows: auto minmax(0, 1fr);
  }
  .topbar {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: stretch;
    gap: 7px 10px;
    padding: 8px 12px;
  }
  .left-tools {
    gap: 10px;
  }
  .brand h1 {
    font-size: 16px;
  }
  .agent-control {
    min-width: 0;
    max-width: min(210px, 56vw);
    height: 32px;
    padding-inline: 10px;
  }
  .agent-icon {
    width: 19px;
    height: 19px;
    border-radius: 5px;
  }
  .compare {
    grid-column: 1 / -1;
    grid-template-columns: minmax(0, 1fr) 22px minmax(0, 1fr);
    gap: 6px;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
  }
  .version-control {
    width: 100%;
    height: 42px;
    padding: 6px 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--control-bg);
    flex-direction: column;
    align-items: flex-start;
    justify-content: center;
    gap: 3px;
  }
  .version-control strong,
  .version-control small,
  .version-sub {
    height: auto;
    line-height: 1;
  }
  .version-sub {
    width: 100%;
    justify-content: flex-start;
    gap: 7px;
  }
  .version-control small {
    font-size: 11px;
  }
  .arrow {
    display: inline-flex;
    height: 42px;
    font-size: 13px;
  }
  .actions { grid-column: 2; grid-row: 1; }
  .shell[data-view="trace"] .compare {
    grid-template-columns: minmax(0, 1fr);
  }
  .trace-page {
    padding: 18px 14px 34px;
  }
  .trace-title h2 {
    font-size: 22px;
  }
  .trace-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .trace-stat {
    padding: 11px 10px 11px 0;
  }
  .trace-summary {
    min-height: 46px;
    padding: 0 4px;
  }
  .trace-body {
    padding: 6px 3px 19px 24px;
  }
  .tool-card .trace-body {
    padding: 10px 12px 14px 27px;
  }
  .tool-card .trace-summary small {
    display: none;
  }
  .tool-param {
    grid-template-columns: minmax(0, 1fr);
    gap: 3px;
    padding: 10px;
  }
  .tool-raw .trace-body {
    padding: 6px 0 0;
  }
  .popover {
    border-radius: 12px;
  }
  .options {
    padding: 5px;
  }
  .option {
    min-height: 42px;
    padding: 9px 10px;
    border-radius: 8px;
  }
  .version-option {
    min-height: 50px;
    padding: 8px 10px;
  }
  .version-copy {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }
  .mini-diffstat {
    width: 46px;
    height: 8px;
  }
  .mini-diffstat.no-change {
    width: 32px;
    height: 3px;
  }
}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="left-tools">
      <div class="brand">
        <h1>Phistory</h1>
      </div>
      <button id="agent" class="control agent-control" type="button" aria-haspopup="listbox"></button>
    </div>
    <div class="compare">
      <button id="from" class="control version-control" type="button" aria-haspopup="listbox"></button>
      <span class="arrow" aria-hidden="true">→</span>
      <button id="to" class="control version-control" type="button" aria-haspopup="listbox"></button>
    </div>
    <div class="actions">
      <button id="view-toggle" class="icon-button view-button" type="button" title="Open trace detail">Trace</button>
      <button id="theme" class="icon-button" type="button" title="Toggle theme"></button>
      <a class="icon-button" href="https://github.com/WEIFENG2333/phistory" target="_blank" rel="noreferrer" aria-label="Open GitHub project" title="Open GitHub project">
        <svg class="github-mark" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 3.86c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>
      </a>
    </div>
  </header>
  <main class="editor">
    <div id="diff"><div class="empty">Loading diff viewer...</div></div>
    <div id="trace" class="trace-view"><div class="empty">Loading trace detail...</div></div>
  </main>
</div>
<div id="popover" class="popover">
  <div id="options" class="options" role="listbox"></div>
</div>
<script id="manifest" type="application/json">__PHISTORY_MANIFEST__</script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.7/dist/purify.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.min.js"></script>
<script>
const manifest = JSON.parse(document.getElementById('manifest').textContent);
const agents = new Map(manifest.agents.map(agent => [agent.id, agent]));
const els = {
  agent: document.getElementById('agent'),
  from: document.getElementById('from'),
  to: document.getElementById('to'),
  viewToggle: document.getElementById('view-toggle'),
  theme: document.getElementById('theme'),
  diff: document.getElementById('diff'),
  trace: document.getElementById('trace'),
  popover: document.getElementById('popover'),
  options: document.getElementById('options')
};
const state = {
  view: 'diff',
  agent: manifest.agents[0]?.id || '',
  from: '',
  to: '',
  followLatest: true,
  normalizeQuery: false,
  theme: localStorage.getItem('phistory-theme') || 'dark',
  picker: null,
  cache: new Map(),
  traceCache: new Map(),
  traceScrollTop: 0,
  traceOpenSections: new Set(),
  traceOpenTools: new Set(),
  editor: null,
  monaco: null
};

boot();

function boot() {
  if (!manifest.agents.length) {
    showError(new Error('No prompt captures found.'));
    return;
  }
  readQuery();
  if (state.normalizeQuery) writeQuery();
  applyTheme();
  bindEvents();
  renderControls();
  refreshView();
}

function readQuery() {
  const params = new URLSearchParams(location.search);
  state.view = params.get('view') === 'trace' ? 'trace' : 'diff';
  const agentId = params.get('agent');
  if (agentId && agents.has(agentId)) state.agent = agentId;
  const agent = currentAgent();
  if (state.view === 'trace') {
    const version = params.get('version') || params.get('to');
    state.to = hasVersion(agent, version) ? version : agent.latest.version;
    state.from = previousVersion(agent, state.to).version;
    state.followLatest = !params.has('version') && !params.has('to');
    return;
  }
  const to = params.get('to');
  const from = params.get('from');
  const hasPinnedVersions = params.has('from') || params.has('to');
  state.followLatest = !hasPinnedVersions && params.get('range') === 'latest';
  state.normalizeQuery = hasPinnedVersions && params.has('range');
  if (!hasPinnedVersions && !params.has('range')) state.followLatest = true;
  if (state.followLatest) {
    useLatestRange(agent);
    return;
  }
  state.to = hasVersion(agent, to) ? to : agent.latest.version;
  state.from = hasVersion(agent, from) ? from : previousVersion(agent, state.to).version;
  state.normalizeQuery = normalizeVersionRange(agent, 'to') || state.normalizeQuery;
}

function writeQuery() {
  const params = state.view === 'trace'
    ? new URLSearchParams({ view: 'trace', agent: state.agent, version: state.to })
    : (state.followLatest
      ? new URLSearchParams({ agent: state.agent, range: 'latest' })
      : new URLSearchParams({ agent: state.agent, from: state.from, to: state.to }));
  history.replaceState(null, '', `${location.pathname}?${params.toString()}`);
}

function bindEvents() {
  els.agent.addEventListener('click', () => togglePicker('agent', els.agent));
  els.from.addEventListener('click', () => togglePicker('from', els.from));
  els.to.addEventListener('click', () => togglePicker('to', els.to));
  els.viewToggle.addEventListener('click', toggleView);
  els.theme.addEventListener('click', toggleTheme);
  els.diff.addEventListener('focusin', guardMobileEditorFocus);
  els.trace.addEventListener('click', event => {
    const jump = event.target.closest?.('.trace-jump');
    if (jump) {
      scrollToTraceSection(jump.dataset.jump);
      return;
    }
    const mode = event.target.closest?.('.trace-mode');
    if (mode) {
      event.stopPropagation();
      const section = mode.closest('.trace-section');
      section?.classList.toggle('is-raw');
      updateTraceModeLabel(section);
      return;
    }
    const summary = event.target.closest?.('.trace-summary');
    if (summary) toggleTracePanel(summary);
  });
  els.trace.addEventListener('keydown', event => {
    const summary = event.target.closest?.('.trace-summary');
    if (!summary || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    toggleTracePanel(summary);
  });
  addEventListener('click', event => {
    if (!els.popover.contains(event.target) && !event.target.closest('.control')) closePicker();
  });
  addEventListener('keydown', event => {
    if (event.key === 'Escape') closePicker();
  });
  addEventListener('resize', debounce(() => {
    closePicker();
    state.editor?.layout();
  }, 100));
}

function renderControls() {
  const agent = currentAgent();
  const from = versionInfo(state.from);
  const to = versionInfo(state.to);
  document.querySelector('.shell')?.setAttribute('data-view', state.view);
  els.agent.innerHTML = `${agentIconHtml(agent)}<strong>${escapeHtml(agent.name)}</strong>`;
  els.from.innerHTML = versionLabel(from);
  els.to.innerHTML = versionLabel(to, isLatestVersion(agent, to.version));
  els.viewToggle.textContent = state.view === 'trace' ? 'Diff' : 'Trace';
  els.viewToggle.title = state.view === 'trace' ? 'Open prompt diff' : 'Open trace detail';
}

function agentIconHtml(agent) {
  if (!agent.icon) return '';
  return `<img class="agent-icon" src="${escapeHtml(agent.icon)}" alt="" loading="lazy" decoding="async">`;
}

function versionLabel(item, latest = false) {
  const marker = latest ? '<em class="latest-mark">Latest</em>' : '';
  return `<strong>${escapeHtml(item.version)}</strong><span class="version-sub"><small>${escapeHtml(item.published_compact)}</small>${marker}</span>`;
}

function togglePicker(kind, anchor) {
  if (state.picker === kind && els.popover.classList.contains('open')) {
    closePicker();
    return;
  }
  openPicker(kind, anchor);
}

function openPicker(kind, anchor) {
  closePicker();
  state.picker = kind;
  els.popover.dataset.kind = kind;
  positionPopover(anchor);
  renderPickerOptions();
  els.popover.classList.add('open');
  anchor.setAttribute('aria-expanded', 'true');
}

function closePicker() {
  els.agent.removeAttribute('aria-expanded');
  els.from.removeAttribute('aria-expanded');
  els.to.removeAttribute('aria-expanded');
  state.picker = null;
  delete els.popover.dataset.kind;
  els.popover.classList.remove('open');
}

function positionPopover(anchor) {
  const rect = anchor.getBoundingClientRect();
  const margin = 12;
  const isMobile = matchMedia('(max-width: 880px)').matches;
  const minWidth = state.picker === 'agent' ? 260 : rect.width;
  const width = isMobile && state.picker !== 'agent'
    ? innerWidth - margin * 2
    : Math.min(Math.max(rect.width, minWidth, state.picker === 'agent' ? 0 : 250), innerWidth - margin * 2);
  const left = Math.max(margin, Math.min(rect.left, innerWidth - width - margin));
  let top = rect.bottom + (isMobile ? 8 : 5);
  let maxHeight = Math.min(isMobile ? 460 : 420, innerHeight - top - margin);
  if (maxHeight < 180) {
    maxHeight = Math.min(isMobile ? 460 : 420, innerHeight - margin * 2);
    top = Math.max(margin, innerHeight - maxHeight - margin);
  }
  els.popover.style.width = `${width}px`;
  els.popover.style.left = `${left}px`;
  els.popover.style.top = `${top}px`;
  els.popover.style.setProperty('--popover-max-height', `${Math.max(160, maxHeight)}px`);
}

function renderPickerOptions() {
  if (!state.picker) return;
  const items = state.picker === 'agent' ? manifest.agents : currentAgent().versions;
  els.options.innerHTML = items.map(optionHtml).join('');
  els.options.querySelectorAll('.option').forEach(button => {
    button.addEventListener('click', () => selectOption(button.dataset.value));
  });
  requestAnimationFrame(() => {
    els.options.querySelector('.option.active')?.scrollIntoView({ block: 'nearest' });
  });
}

function optionHtml(item) {
  const active = selectedValue() === item.id || selectedValue() === item.version;
  const value = item.id || item.version;
  const isAgent = state.picker === 'agent';
  const primary = isAgent ? item.name : item.version;
  if (isAgent) {
    return `<button class="option agent-option${active ? ' active' : ''}" type="button" role="option" aria-selected="${active}" data-value="${escapeHtml(value)}">${agentIconHtml(item)}<span><strong>${escapeHtml(primary)}</strong><small>${escapeHtml(item.id)}</small></span></button>`;
  }
  const secondary = item.published_compact;
  return `<button class="option version-option${active ? ' active' : ''}" type="button" role="option" aria-selected="${active}" data-value="${escapeHtml(value)}"><span class="version-copy"><strong>${escapeHtml(primary)}</strong><small>${escapeHtml(secondary)}</small></span>${miniDiffstatHtml(item.change)}</button>`;
}

function miniDiffstatHtml(change) {
  const added = Math.max(0, Number(change?.added_lines || 0));
  const removed = Math.max(0, Number(change?.removed_lines || 0));
  const changed = Number(change?.changed_lines || 0);
  const total = added + removed;
  const addPct = total ? (added / total) * 100 : 50;
  const removePct = total ? (removed / total) * 100 : 50;
  const scale = Math.max(0, Math.min(100, Number(change?.scale || 0)));
  const title = changed ? `${changed} changed lines from previous version` : 'No prompt change from previous version';
  return `<span class="mini-diffstat${changed ? '' : ' no-change'}" style="--fill-width:${scale.toFixed(2)}%;--removed-part:${removePct.toFixed(2)}%;--added-part:${addPct.toFixed(2)}%;" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}"><span class="diffstat-fill"><i class="removed"></i><i class="added"></i></span></span>`;
}

function selectedValue() {
  if (state.picker === 'agent') return state.agent;
  if (state.picker === 'from') return state.from;
  return state.to;
}

function selectOption(value) {
  if (state.picker === 'agent') {
    state.agent = value;
    const agent = currentAgent();
    if (state.view === 'trace') {
      state.to = agent.latest.version;
      state.from = previousVersion(agent, state.to).version;
      state.followLatest = true;
    } else {
      state.followLatest = true;
      useLatestRange(agent);
    }
  } else if (state.picker === 'from') {
    state.followLatest = false;
    state.from = value;
    normalizeVersionRange(currentAgent(), 'from');
  } else if (state.picker === 'to') {
    state.followLatest = false;
    state.to = value;
    if (state.view === 'trace') {
      state.from = previousVersion(currentAgent(), state.to).version;
    } else {
      normalizeVersionRange(currentAgent(), 'to');
    }
  }
  closePicker();
  refresh();
}

function refresh() {
  writeQuery();
  renderControls();
  refreshView();
}

function refreshView() {
  if (state.view === 'trace') {
    snapshotTraceState();
    renderTrace().catch(showError);
    return;
  }
  loadMonaco().then(renderDiff).catch(showError);
}

function toggleView() {
  state.view = state.view === 'trace' ? 'diff' : 'trace';
  if (state.view === 'trace') {
    state.from = previousVersion(currentAgent(), state.to).version;
  }
  refresh();
}

function loadMonaco() {
  return new Promise((resolve, reject) => {
    if (!window.require) {
      reject(new Error('Monaco loader did not load.'));
      return;
    }
    window.require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs' } });
    window.require(['vs/editor/editor.main'], monaco => {
      state.monaco = monaco;
      monaco.editor.setTheme(monacoTheme());
      resolve();
    }, reject);
  });
}

async function renderDiff() {
  if (!state.monaco) return;
  const monaco = state.monaco;
  const [from, to] = [versionInfo(state.from), versionInfo(state.to)];
  const [original, modified] = await Promise.all([loadPrompt(from), loadPrompt(to)]);
  const originalModel = monaco.editor.createModel(original, 'markdown');
  const modifiedModel = monaco.editor.createModel(modified, 'markdown');

  if (state.editor) {
    const model = state.editor.getModel();
    state.editor.dispose();
    model?.original?.dispose();
    model?.modified?.dispose();
  }

  els.diff.innerHTML = '';
  const isNarrow = matchMedia('(max-width: 880px)').matches;
  state.editor = monaco.editor.createDiffEditor(els.diff, {
    automaticLayout: true,
    renderSideBySide: !isNarrow,
    readOnly: true,
    domReadOnly: isNarrow,
    minimap: { enabled: !isNarrow },
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    originalEditable: false,
    contextmenu: !isNarrow,
    links: !isNarrow,
    hover: { enabled: !isNarrow },
    fontSize: isNarrow ? 12 : 13,
    lineHeight: isNarrow ? 19 : 20,
    lineNumbersMinChars: isNarrow ? 2 : 4,
    folding: false,
    glyphMargin: false,
    lineDecorationsWidth: isNarrow ? 8 : 10,
    overviewRulerLanes: isNarrow ? 0 : 3,
    renderLineHighlight: isNarrow ? 'none' : 'line',
    selectionHighlight: !isNarrow,
    occurrencesHighlight: isNarrow ? 'off' : 'singleFile',
    renderValidationDecorations: 'off',
    stickyScroll: { enabled: false },
    scrollbar: {
      alwaysConsumeMouseWheel: false,
      useShadows: false,
      verticalScrollbarSize: isNarrow ? 8 : 10,
      horizontalScrollbarSize: isNarrow ? 8 : 10
    },
    padding: { top: isNarrow ? 10 : 12, bottom: 12 }
  });
  state.editor.setModel({ original: originalModel, modified: modifiedModel });
  hardenMobileEditorInputs();
  requestAnimationFrame(hardenMobileEditorInputs);
}

function hardenMobileEditorInputs() {
  if (!matchMedia('(max-width: 880px)').matches) return;
  els.diff.querySelectorAll('textarea.inputarea').forEach(input => {
    input.readOnly = true;
    input.setAttribute('readonly', '');
    input.setAttribute('inputmode', 'none');
    input.setAttribute('aria-readonly', 'true');
    input.setAttribute('tabindex', '-1');
  });
}

function guardMobileEditorFocus(event) {
  if (!matchMedia('(max-width: 880px)').matches) return;
  if (event.target.matches?.('textarea.inputarea')) {
    event.target.blur();
  }
}

async function loadPrompt(item) {
  if (state.cache.has(item.prompt)) return state.cache.get(item.prompt);
  const response = await fetch(item.prompt);
  if (!response.ok) throw new Error(`Unable to load ${item.prompt}`);
  const text = await response.text();
  state.cache.set(item.prompt, text);
  return text;
}

async function loadTrace(item) {
  if (!item.trace) throw new Error('This capture has no trace path.');
  if (state.traceCache.has(item.trace)) return state.traceCache.get(item.trace);
  const response = await fetch(item.trace);
  if (!response.ok) throw new Error(`Unable to load ${item.trace}`);
  const text = await response.text();
  const records = text.split(/\n+/).filter(Boolean).map(line => JSON.parse(line));
  state.traceCache.set(item.trace, records);
  return records;
}

async function renderTrace() {
  const item = versionInfo(state.to);
  const records = await loadTrace(item);
  const selected = selectMainTraceRecord(records);
  if (!selected) {
    els.trace.innerHTML = '<div class="empty">No prompt-bearing trace request found.</div>';
    return;
  }
  const detail = normalizeTraceRecord(selected.record, selected.index, records.length);
  els.trace.innerHTML = traceDetailHtml(item, detail);
  restoreTraceState();
}

function selectMainTraceRecord(records) {
  let best = null;
  records.forEach((record, index) => {
    const score = traceRecordScore(record);
    if (!best || score > best.score) best = { record, index, score };
  });
  return best && best.score > 0 ? best : null;
}

function traceRecordScore(record) {
  const body = requestBody(record);
  let score = 0;
  for (const [key, weight] of [
    ['system', 100],
    ['instructions', 100],
    ['system_instruction', 100],
    ['systemInstruction', 100],
    ['messages', 35],
    ['input', 35],
    ['contents', 35],
    ['tools', 20],
    ['toolConfig', 20]
  ]) {
    if (body[key] !== undefined) score += weight;
  }
  const tools = normalizeTools(body);
  score += tools.length;
  return score;
}

function normalizeTraceRecord(record, index, total) {
  const req = record.request || {};
  const res = record.response || {};
  const body = requestBody(record);
  const provider = inferProvider(req.path || '', body);
  const prompts = normalizePromptBlocks(provider, body);
  const messages = normalizeMessages(provider, body);
  const tools = normalizeTools(body);
  return {
    index,
    total,
    provider,
    method: req.method || 'POST',
    path: req.path || '',
    status: res.status || '',
    model: body.model || body.name || '',
    upstream: record.upstream_base_url || '',
    beta: importantHeader(req.headers, 'anthropic-beta'),
    userAgent: importantHeader(req.headers, 'user-agent'),
    systemBlocks: prompts.system,
    developerBlocks: prompts.developer,
    messages,
    tools,
    rawBody: body
  };
}

function requestBody(record) {
  const req = record.request || {};
  const body = req.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)) return {};
  const nested = body.request;
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) return nested;
  return body;
}

function inferProvider(path, body) {
  if (path.includes('/chat/completions')) return 'OpenAI Chat';
  if (path.includes('/responses') || body.instructions || body.input) return 'OpenAI Responses';
  if (path.includes('/messages') || body.system || body.anthropic_version) return 'Anthropic';
  if (path.includes('/models/') || body.contents || body.system_instruction || body.systemInstruction) return 'Gemini';
  return 'Unknown';
}

function normalizePromptBlocks(provider, body) {
  const system = [];
  const developer = [];
  if (body.system !== undefined) system.push(...contentBlocks(body.system, 'System Prompt'));
  if (typeof body.instructions === 'string' && body.instructions) system.push({ title: 'Instructions', text: body.instructions });
  const systemInstruction = body.system_instruction ?? body.systemInstruction;
  if (systemInstruction !== undefined) system.push(...contentBlocks(systemInstruction, 'System Instruction'));

  for (const message of messageItems(body.messages)) {
    const role = String(message.role || '').toLowerCase();
    if (role === 'system') system.push({ title: 'System Message', text: contentText(message.content) });
    if (role === 'developer') developer.push({ title: 'Developer Message', text: contentText(message.content) });
  }
  for (const item of messageItems(body.input)) {
    const role = String(item.role || item.type || '').toLowerCase();
    if (role === 'system') system.push({ title: 'System Input', text: contentText(item.content || item.text) });
    if (role === 'developer') developer.push({ title: 'Developer Input', text: contentText(item.content || item.text) });
  }
  for (const item of messageItems(body.contents)) {
    const role = String(item.role || 'user').toLowerCase();
    if (role === 'system') system.push({ title: 'System Content', text: contentText(item.parts || item.content) });
  }
  return {
    system: system.filter(block => block.text),
    developer: developer.filter(block => block.text)
  };
}

function normalizeMessages(provider, body) {
  const out = [];
  for (const message of messageItems(body.messages)) {
    const role = String(message.role || 'message');
    if (role === 'system' || role === 'developer') continue;
    const text = contentText(message.content || message.text);
    if (text) out.push({ role, text });
  }
  for (const item of messageItems(body.input)) {
    const role = String(item.role || item.type || 'input');
    if (role === 'system' || role === 'developer') continue;
    const text = contentText(item.content || item.text || item.output);
    if (text) out.push({ role, text });
  }
  for (const item of messageItems(body.contents)) {
    const role = String(item.role || 'user');
    const text = contentText(item.parts || item.content);
    if (text) out.push({ role, text });
  }
  return out;
}

function normalizeTools(body) {
  const tools = [];
  for (const tool of Array.isArray(body.tools) ? body.tools : []) {
    if (!tool || typeof tool !== 'object') continue;
    const declarations = tool.functionDeclarations || tool.function_declarations;
    if (Array.isArray(declarations)) {
      tools.push(...toolDeclarations(declarations));
      continue;
    }
    const fn = tool.function && typeof tool.function === 'object' ? tool.function : null;
    tools.push({
      name: String(tool.name || fn?.name || tool.type || 'tool'),
      description: String(tool.description || fn?.description || ''),
      schema: tool.parameters || tool.input_schema || fn?.parameters || tool.schema || null,
      raw: tool
    });
  }
  const toolConfigTools = body.toolConfig?.tools;
  if (Array.isArray(toolConfigTools)) {
    for (const item of toolConfigTools) {
      const spec = item?.toolSpec;
      if (!spec) continue;
      tools.push({
        name: String(spec.name || 'tool'),
        description: String(spec.description || ''),
        schema: spec.inputSchema?.json || null,
        raw: item
      });
    }
  }
  const declarations = body.tools?.functionDeclarations || body.tool_config?.function_declarations;
  if (Array.isArray(declarations)) {
    tools.push(...toolDeclarations(declarations));
  }
  return tools;
}

function toolDeclarations(declarations) {
  return declarations
    .filter(fn => fn && typeof fn === 'object')
    .map(fn => ({
      name: String(fn.name || 'tool'),
      description: String(fn.description || ''),
      schema: fn.parameters || null,
      raw: fn
    }));
}

function contentBlocks(value, title) {
  if (typeof value === 'string') return [{ title, text: value }];
  if (Array.isArray(value)) {
    return value.map((item, index) => {
      const type = typeof item?.type === 'string' && item.type !== 'text' ? item.type : '';
      return { title: type || `${title} ${index + 1}`, text: contentText(item) };
    }).filter(block => block.text);
  }
  if (value && typeof value === 'object') return [{ title, text: contentText(value) }];
  return [];
}

function messageItems(value) {
  return Array.isArray(value) ? value.filter(item => item && typeof item === 'object') : [];
}

function contentText(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(contentText).filter(Boolean).join('\n\n');
  if (typeof value === 'object') {
    for (const key of ['text', 'input_text', 'output_text', 'content', 'message']) {
      if (typeof value[key] === 'string') return value[key];
      if (Array.isArray(value[key])) return contentText(value[key]);
    }
    if (value.parts) return contentText(value.parts);
  }
  return '';
}

function snapshotTraceState() {
  if (!els.trace.querySelector('.trace-page')) return;
  state.traceScrollTop = els.trace.scrollTop;
  state.traceOpenSections = new Set(
    [...els.trace.querySelectorAll('.trace-section[data-section]')]
      .filter(section => section.classList.contains('is-open'))
      .map(section => section.dataset.section)
  );
  state.traceOpenTools = new Set(
    [...els.trace.querySelectorAll('.tool-card[data-tool]')]
      .filter(tool => tool.classList.contains('is-open'))
      .map(tool => tool.dataset.tool)
  );
}

function restoreTraceState() {
  if (state.traceOpenSections.size) {
    els.trace.querySelectorAll('.trace-section[data-section]').forEach(section => {
      setTracePanelOpen(section, state.traceOpenSections.has(section.dataset.section));
    });
  }
  if (state.traceOpenTools.size) {
    els.trace.querySelectorAll('.tool-card[data-tool]').forEach(tool => {
      setTracePanelOpen(tool, state.traceOpenTools.has(tool.dataset.tool));
    });
  }
  requestAnimationFrame(() => {
    els.trace.scrollTop = Math.min(state.traceScrollTop, els.trace.scrollHeight);
  });
}

function scrollToTraceSection(section) {
  const target = els.trace.querySelector(`[data-section="${section}"]`);
  if (!target) return;
  setTracePanelOpen(target, true);
  target.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

function toggleTracePanel(summary) {
  const panel = summary.closest('.trace-section, .tool-card');
  if (!panel) return;
  setTracePanelOpen(panel, !panel.classList.contains('is-open'));
}

function setTracePanelOpen(panel, open) {
  panel.classList.toggle('is-open', open);
  panel.querySelector(':scope > .trace-summary')?.setAttribute('aria-expanded', String(open));
}

function traceDetailHtml(item, detail) {
  const title = `${currentAgent().name} ${item.version}`;
  return `<article class="trace-page">
    <header class="trace-hero">
      <div class="trace-eyebrow">Trace detail · request ${detail.index + 1} of ${detail.total}</div>
      <div class="trace-title"><h2>${escapeHtml(title)}</h2><span>${escapeHtml(item.published_compact)}</span></div>
      <div class="trace-meta">${metaItem('Provider', detail.provider)}${metaItem('Model', detail.model || 'unknown')}${metaItem('Endpoint', `${detail.method} ${detail.path}`)}${item.published_display ? metaItem('Published', item.published_display) : ''}${item.captured_display ? metaItem('Captured', item.captured_display) : ''}</div>
    </header>
    ${traceJumpbarHtml(detail)}
    ${blocksSectionHtml('System Prompt', detail.systemBlocks, true)}
    ${blocksSectionHtml('Developer Prompt', detail.developerBlocks, false)}
    ${toolsSectionHtml(detail.tools)}
    ${messagesSectionHtml(detail.messages)}
    ${traceSectionHtml('Raw Request Body', JSON.stringify(detail.rawBody, null, 2), { open: false, raw: true })}
  </article>`;
}

function traceJumpbarHtml(detail) {
  const items = [];
  if (detail.systemBlocks.length) items.push(['system-prompt', 'System']);
  if (detail.developerBlocks.length) items.push(['developer-prompt', 'Developer']);
  if (detail.tools.length) items.push(['tools', 'Tools']);
  if (detail.messages.length) items.push(['messages', 'Messages']);
  items.push(['raw-request-body', 'Raw']);
  return `<nav class="trace-jumpbar" aria-label="Trace sections">${items.map(([section, label]) => `<button class="trace-jump" type="button" data-jump="${section}">${label}</button>`).join('')}</nav>`;
}

function metaItem(label, value) {
  return `<span>${escapeHtml(label)} <b>${escapeHtml(value)}</b></span>`;
}

function traceSummaryHtml(title, open, extra = '', modeToggle = false) {
  const mode = modeToggle
    ? '<button class="trace-mode" type="button">View source</button>'
    : '';
  return `<div class="trace-summary" role="button" tabindex="0" aria-expanded="${open ? 'true' : 'false'}">${chevronIcon()}<strong>${escapeHtml(title)}</strong>${mode}${extra}</div>`;
}

function chevronIcon() {
  return '<span class="trace-chevron" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m6 4 4 4-4 4"/></svg></span>';
}

function updateTraceModeLabel(section) {
  const mode = section?.querySelector(':scope > .trace-summary .trace-mode');
  if (!mode) return;
  mode.textContent = section.classList.contains('is-raw') ? 'View rendered' : 'View source';
}

function blocksSectionHtml(title, blocks, open) {
  if (!blocks.length) return '';
  const section = sectionId(title);
  const body = blocks.map(block => `<div class="prompt-block"><div class="trace-rendered">${markdownHtml(block.text)}</div><pre class="trace-text trace-raw">${escapeHtml(block.text)}</pre></div>`).join('');
  return `<section class="trace-section${open ? ' is-open' : ''}" data-section="${section}">${traceSummaryHtml(title, open, '', true)}<div class="trace-content"><div class="trace-body">${body}</div></div></section>`;
}

function messagesSectionHtml(messages) {
  if (!messages.length) return '';
  const body = messages.map(message => `<div class="trace-message"><div class="trace-role">${escapeHtml(message.role)}</div><div class="trace-rendered">${markdownHtml(message.text)}</div><pre class="trace-text trace-raw">${escapeHtml(message.text)}</pre></div>`).join('');
  return `<section class="trace-section" data-section="messages">${traceSummaryHtml('Messages', false, '', true)}<div class="trace-content"><div class="trace-body">${body}</div></div></section>`;
}

function toolsSectionHtml(tools) {
  if (!tools.length) return '';
  const body = `<div class="tool-list">${tools.map(toolHtml).join('')}</div>`;
  return `<section class="trace-section is-open" data-section="tools">${traceSummaryHtml('Tools', true, `<small>${tools.length}</small>`)}<div class="trace-content"><div class="trace-body">${body}</div></div></section>`;
}

function toolHtml(tool) {
  const params = schemaParameters(tool.schema);
  const paramsHtml = params.length
    ? `<div class="tool-params">${params.map(param => `<div class="tool-param"><div class="tool-param-name" title="${escapeHtml(param.name)}">${escapeHtml(param.name)}</div><div class="tool-param-type">${escapeHtml(param.type)}${param.required ? ' <span class="tool-param-required">required</span>' : ''}</div><div class="tool-param-desc">${escapeHtml(param.description)}</div></div>`).join('')}</div>`
    : '<div class="tool-param-desc">No structured parameters.</div>';
  const raw = tool.schema || tool.raw;
  return `<section class="tool-card" data-tool="${escapeHtml(tool.name)}">${traceSummaryHtml(tool.name, false, `<small>${escapeHtml(tool.description || `${params.length} parameter${params.length === 1 ? '' : 's'}`)}</small>`)}<div class="trace-content"><div class="trace-body">${tool.description ? `<div class="tool-description trace-rendered">${markdownHtml(tool.description)}</div>` : ''}${paramsHtml}<section class="trace-section tool-raw">${traceSummaryHtml('Raw schema', false)}<div class="trace-content"><div class="trace-body"><pre class="raw-json">${escapeHtml(JSON.stringify(raw, null, 2))}</pre></div></div></section></div></div></section>`;
}

function schemaParameters(schema) {
  if (!schema || typeof schema !== 'object') return [];
  const root = schema.json && typeof schema.json === 'object' ? schema.json : schema;
  const properties = root.properties && typeof root.properties === 'object' ? root.properties : {};
  const required = new Set(Array.isArray(root.required) ? root.required.map(String) : []);
  return Object.entries(properties).map(([name, spec]) => {
    const item = spec && typeof spec === 'object' ? spec : {};
    const enumText = Array.isArray(item.enum) && item.enum.length ? ` Values: ${item.enum.map(String).join(', ')}.` : '';
    return {
      name,
      required: required.has(name),
      type: schemaType(item),
      description: `${item.description || ''}${enumText}`.trim()
    };
  });
}

function schemaType(spec) {
  if (!spec || typeof spec !== 'object') return 'value';
  if (Array.isArray(spec.type)) return spec.type.join(' | ');
  if (typeof spec.type === 'string') {
    if (spec.type === 'array' && spec.items) return `array<${schemaType(spec.items)}>`;
    return spec.type;
  }
  if (spec.anyOf) return spec.anyOf.map(schemaType).join(' | ');
  if (spec.oneOf) return spec.oneOf.map(schemaType).join(' | ');
  if (spec.properties) return 'object';
  return 'value';
}

function traceSectionHtml(title, text, options = {}) {
  const bodyClass = options.raw ? 'raw-json' : 'trace-text';
  return `<section class="trace-section${options.open ? ' is-open' : ''}" data-section="${sectionId(title)}">${traceSummaryHtml(title, Boolean(options.open), options.meta ? `<small>${escapeHtml(options.meta)}</small>` : '')}<div class="trace-content"><div class="trace-body"><pre class="${bodyClass}">${escapeHtml(text)}</pre></div></div></section>`;
}

function sectionId(title) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function markdownHtml(text) {
  const source = String(text || '');
  if (window.marked && window.DOMPurify) {
    const html = window.marked.parse(source, { gfm: true, breaks: false });
    return window.DOMPurify.sanitize(html);
  }
  return fallbackMarkdownHtml(source);
}

function fallbackMarkdownHtml(text) {
  const lines = String(text || '').split('\n');
  const html = [];
  let paragraph = [];
  let list = [];
  let code = [];
  let inCode = false;
  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${inlineMarkdown(paragraph.join(' '))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!list.length) return;
    html.push(`<ul>${list.map(item => `<li>${inlineMarkdown(item)}</li>`).join('')}</ul>`);
    list = [];
  };
  const flushCode = () => {
    if (!code.length) return;
    html.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`);
    code = [];
  };
  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCode) {
        flushCode();
        inCode = false;
      } else {
        flushParagraph();
        flushList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      code.push(line);
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      const level = Math.min(4, heading[1].length + 1);
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = /^\s*[-*]\s+(.+)$/.exec(line);
    if (bullet) {
      flushParagraph();
      list.push(bullet[1]);
      continue;
    }
    flushList();
    paragraph.push(line.trim());
  }
  flushParagraph();
  flushList();
  flushCode();
  return html.join('');
}

function inlineMarkdown(text) {
  return escapeHtml(text).replace(/`([^`]+)`/g, '<code>$1</code>');
}

function importantHeader(headers, name) {
  if (!headers || typeof headers !== 'object') return '';
  const target = name.toLowerCase();
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === target) return String(value);
  }
  return '';
}

function toggleTheme() {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('phistory-theme', state.theme);
  applyTheme();
  if (state.monaco) state.monaco.editor.setTheme(monacoTheme());
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  els.theme.innerHTML = '<span class="theme-mark" aria-hidden="true"></span>';
  els.theme.setAttribute('aria-label', state.theme === 'dark' ? 'Use light theme' : 'Use dark theme');
}

function monacoTheme() {
  return state.theme === 'dark' ? 'vs-dark' : 'vs';
}

function currentAgent() {
  return agents.get(state.agent) || manifest.agents[0];
}

function versionInfo(version) {
  return currentAgent().versions.find(item => item.version === version) || currentAgent().latest;
}

function previousVersion(agent, version) {
  const index = agent.versions.findIndex(item => item.version === version);
  return agent.versions[index + 1] || agent.versions[index] || agent.latest;
}

function nextVersion(agent, version) {
  const index = agent.versions.findIndex(item => item.version === version);
  return agent.versions[index - 1] || agent.versions[index] || agent.latest;
}

function versionIndex(agent, version) {
  return agent.versions.findIndex(item => item.version === version);
}

function normalizeVersionRange(agent, anchor) {
  const fromIndex = versionIndex(agent, state.from);
  const toIndex = versionIndex(agent, state.to);
  if (fromIndex < 0 || toIndex < 0 || fromIndex > toIndex) return false;
  if (anchor === 'from') {
    state.to = nextVersion(agent, state.from).version;
  } else {
    state.from = previousVersion(agent, state.to).version;
  }
  return true;
}

function useLatestRange(agent) {
  state.to = agent.latest.version;
  state.from = previousVersion(agent, state.to).version;
}

function hasVersion(agent, version) {
  return Boolean(version && agent.versions.some(item => item.version === version));
}

function isLatestVersion(agent, version) {
  return version === agent.latest.version;
}

function showError(error) {
  const target = state.view === 'trace' ? els.trace : els.diff;
  target.innerHTML = `<div class="empty">${escapeHtml(error.message || error)}</div>`;
}

function debounce(fn, delay) {
  let handle = 0;
  return () => {
    clearTimeout(handle);
    handle = setTimeout(fn, delay);
  };
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[char]);
}
</script>
</body>
</html>
"""
