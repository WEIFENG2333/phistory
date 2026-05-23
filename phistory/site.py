from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from phistory.render import _version_key


def render_site(root: Path, output: Path) -> None:
    output.write_text(_HTML.replace("__PHISTORY_MANIFEST__", _json_for_script(_build_manifest(root))), encoding="utf-8")


def _build_manifest(root: Path) -> dict:
    rows = [_capture_row(meta_path) for meta_path in sorted(root.glob("*/*/meta.json"))]
    rows = [row for row in rows if row is not None]
    agents = []
    for agent_id in sorted({row["agent_id"] for row in rows}):
        versions = sorted(
            [row for row in rows if row["agent_id"] == agent_id],
            key=lambda row: _version_key(row["version"]),
            reverse=True,
        )
        latest = versions[0] if versions else None
        agents.append(
            {
                "id": agent_id,
                "name": latest["agent"] if latest else agent_id,
                "latest": latest,
                "versions": versions,
            }
        )
    return {"agents": agents, "count": len(rows)}


def _capture_row(meta_path: Path) -> dict | None:
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    version_dir = meta_path.parent
    prompt = version_dir / "prompt.md"
    trace = version_dir / "trace.jsonl"
    if not prompt.exists() or not trace.exists():
        return None

    published_at = meta.get("published_at") or ""
    agent_id = meta.get("agent_id") or version_dir.parent.name
    prompt_path = prompt.as_posix()
    return {
        "agent_id": agent_id,
        "agent": meta.get("agent") or agent_id,
        "version": meta.get("version") or version_dir.name,
        "published_compact": _compact_date(published_at),
        "prompt": prompt_path,
    }


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
<meta name="description" content="Phistory automatically archives versioned system prompt snapshots from agent CLIs like Claude Code and Codex.">
<meta name="keywords" content="Phistory, system prompt history, Claude Code prompt, Codex CLI prompt, agent CLI, prompt diff, prompt archive">
<meta name="application-name" content="Phistory">
<meta property="og:title" content="Phistory">
<meta property="og:description" content="Automatically archived system prompt snapshots and diffs for agent CLIs like Claude Code and Codex.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://phistory.cc/">
<meta property="og:image" content="https://phistory.cc/docs/screenshot.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Phistory">
<meta name="twitter:description" content="Automatically archived system prompt snapshots and diffs for agent CLIs like Claude Code and Codex.">
<meta name="twitter:image" content="https://phistory.cc/docs/screenshot.png">
<link rel="canonical" href="https://phistory.cc/">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%230f1115'/%3E%3Cpath d='M8 10h16M8 16h10M8 22h14' stroke='%237cc7ff' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E">
<title>Phistory - Agent CLI System Prompt Diff History</title>
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
  grid-template-columns: 176px 24px 176px;
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
  gap: 10px;
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
  content: "⌄";
  color: var(--muted);
  font-size: 13px;
  line-height: 1;
  transform: translateY(-1px);
}
.version-control {
  width: 176px;
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
.editor { min-height: 0; position: relative; }
#diff { position: absolute; inset: 0; }
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
  padding: 4px;
  max-height: var(--popover-max-height);
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
.option:hover { background: var(--control-hover); }
.option.active {
  background: var(--menu-active);
  box-shadow: none;
}
.agent-option {
  grid-template-columns: minmax(0, 1fr);
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
    gap: 9px 10px;
    padding: 10px 12px 9px;
  }
  .left-tools {
    gap: 10px;
  }
  .brand h1 {
    font-size: 17px;
  }
  .agent-control {
    min-width: 0;
    max-width: min(190px, 52vw);
    height: 34px;
    padding-inline: 10px;
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
    height: 40px;
    padding: 0 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--control-bg);
  }
  .version-control small {
    font-size: 11px;
  }
  .arrow {
    display: inline-flex;
    height: 40px;
    font-size: 13px;
  }
  .actions { grid-column: 2; grid-row: 1; }
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
      <button id="theme" class="icon-button" type="button" title="Toggle theme"></button>
      <a class="icon-button" href="https://github.com/WEIFENG2333/phistory" target="_blank" rel="noreferrer" aria-label="Open GitHub project" title="Open GitHub project">
        <svg class="github-mark" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 3.86c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>
      </a>
    </div>
  </header>
  <main class="editor">
    <div id="diff"><div class="empty">Loading diff viewer...</div></div>
  </main>
</div>
<div id="popover" class="popover">
  <div id="options" class="options" role="listbox"></div>
</div>
<script id="manifest" type="application/json">__PHISTORY_MANIFEST__</script>
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.min.js"></script>
<script>
const manifest = JSON.parse(document.getElementById('manifest').textContent);
const agents = new Map(manifest.agents.map(agent => [agent.id, agent]));
const els = {
  agent: document.getElementById('agent'),
  from: document.getElementById('from'),
  to: document.getElementById('to'),
  theme: document.getElementById('theme'),
  diff: document.getElementById('diff'),
  popover: document.getElementById('popover'),
  options: document.getElementById('options')
};
const state = {
  agent: manifest.agents[0]?.id || '',
  from: '',
  to: '',
  theme: localStorage.getItem('phistory-theme') || 'dark',
  picker: null,
  cache: new Map(),
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
  applyTheme();
  bindEvents();
  renderControls();
  loadMonaco().then(renderDiff).catch(showError);
}

function readQuery() {
  const params = new URLSearchParams(location.search);
  const agentId = params.get('agent');
  if (agentId && agents.has(agentId)) state.agent = agentId;
  const agent = currentAgent();
  const to = params.get('to');
  const from = params.get('from');
  state.to = hasVersion(agent, to) ? to : agent.latest.version;
  state.from = hasVersion(agent, from) ? from : previousVersion(agent, state.to).version;
}

function writeQuery() {
  const params = new URLSearchParams({ agent: state.agent, from: state.from, to: state.to });
  history.replaceState(null, '', `${location.pathname}?${params.toString()}`);
}

function bindEvents() {
  els.agent.addEventListener('click', () => openPicker('agent', els.agent));
  els.from.addEventListener('click', () => openPicker('from', els.from));
  els.to.addEventListener('click', () => openPicker('to', els.to));
  els.theme.addEventListener('click', toggleTheme);
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
  els.agent.innerHTML = `<strong>${escapeHtml(agent.name)}</strong>`;
  els.from.innerHTML = versionLabel(from);
  els.to.innerHTML = versionLabel(to);
}

function versionLabel(item) {
  return `<strong>${escapeHtml(item.version)}</strong><small>${escapeHtml(item.published_compact)}</small>`;
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
    : Math.min(Math.max(rect.width, minWidth), innerWidth - margin * 2);
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
    return `<button class="option agent-option${active ? ' active' : ''}" type="button" role="option" aria-selected="${active}" data-value="${escapeHtml(value)}"><span><strong>${escapeHtml(primary)}</strong><small>${escapeHtml(item.id)}</small></span></button>`;
  }
  const secondary = item.published_compact;
  return `<button class="option${active ? ' active' : ''}" type="button" role="option" aria-selected="${active}" data-value="${escapeHtml(value)}"><span><strong>${escapeHtml(primary)}</strong></span><small>${escapeHtml(secondary)}</small></button>`;
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
    state.to = agent.latest.version;
    state.from = previousVersion(agent, state.to).version;
  } else if (state.picker === 'from') {
    state.from = value;
  } else if (state.picker === 'to') {
    state.to = value;
  }
  closePicker();
  refresh();
}

function refresh() {
  writeQuery();
  renderControls();
  renderDiff();
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
    minimap: { enabled: !isNarrow },
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    originalEditable: false,
    fontSize: isNarrow ? 12 : 13,
    lineHeight: isNarrow ? 19 : 20,
    lineNumbersMinChars: isNarrow ? 2 : 4,
    folding: false,
    padding: { top: isNarrow ? 10 : 12, bottom: 12 }
  });
  state.editor.setModel({ original: originalModel, modified: modifiedModel });
}

async function loadPrompt(item) {
  if (state.cache.has(item.prompt)) return state.cache.get(item.prompt);
  const response = await fetch(item.prompt);
  if (!response.ok) throw new Error(`Unable to load ${item.prompt}`);
  const text = await response.text();
  state.cache.set(item.prompt, text);
  return text;
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

function hasVersion(agent, version) {
  return Boolean(version && agent.versions.some(item => item.version === version));
}

function showError(error) {
  els.diff.innerHTML = `<div class="empty">${escapeHtml(error.message || error)}</div>`;
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
