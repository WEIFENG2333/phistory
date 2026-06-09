# Phistory

[中文](README_zh.md)

Phistory automatically archives versioned system prompt snapshots from agent CLIs like Claude Code, Codex, OpenClaw, Hermes, Kimi, opencode, and Pi.

It installs a specific CLI release, runs it once through [`claude-tap`](https://github.com/liaohch3/claude-tap), captures the prompt-bearing HTTP request, and writes a comparison-friendly Markdown snapshot.

Phistory uses the PyPI release `claude-tap >= 0.1.102`, where capture-only prompt snapshot export is available upstream.

GitHub Actions checks supported CLI releases every hour and commits new prompt snapshots when they appear.

[Open the prompt diff viewer](https://phistory.cc/)

![Phistory prompt diff viewer](docs/screenshot.png)

## Usage

```bash
uv run phistory capture --latest --agents claude-code,codex,openclaw,hermes,kimi,opencode,pi
uv run phistory backfill claude-code --from 2.1.113 --to latest
uv run phistory render-index
uv run phistory render-site
```

## Web UI

`index.html` is a static prompt viewer with version navigation and Monaco-powered diffs. GitHub Pages deploys it directly from this repository.

Use the viewer for human comparison. Use [`captures/index.json`](captures/index.json) and [`docs/captures.md`](docs/captures.md) when you need an index of every archived snapshot.

## Supported Agents

- Claude Code (`@anthropic-ai/claude-code`)
- Codex CLI (`@openai/codex`)
- OpenClaw (`openclaw`)
- Hermes Agent (`hermes-agent`)
- Kimi CLI (`MoonshotAI/kimi-cli`)
- opencode (`opencode-ai`)
- Pi (`@earendil-works/pi-coding-agent`)

## Capture Format

Each capture is stored under `captures/<agent>/<version>/`:

- `prompt.md`: normalized prompt snapshot for reading and diffing
- `trace.jsonl`: raw captured HTTP trace, kept unnormalized as evidence
- `meta.json`: package, version, command, and capture metadata

The generated indexes are:

- [`captures/index.json`](captures/index.json): compact machine-readable capture index
- [`docs/captures.md`](docs/captures.md): full human-readable capture table

## For AI Agents

- Use `README.md` for the project overview and current capture status.
- Use `captures/index.json` to discover available agents, versions, prompt paths, and trace paths.
- Use `captures/<agent>/<version>/prompt.md` when you need a normalized prompt snapshot.
- Use `captures/<agent>/<version>/trace.jsonl` only when you need raw HTTP capture evidence.
- Treat `index.html` as a human-facing viewer; it is not the canonical machine-readable index.

## Links

- [linux.do](https://linux.do)

## Capture Status

Last capture update: 2026-06-09 00:16 UTC

| Agent | Latest | Captures | Last Captured |
| --- | --- | ---: | --- |
| Claude Code | [2.1.169 - 2026-06-08](captures/claude-code/2.1.169/prompt.md) | 335 | 2026-06-08 22:50 UTC |
| Codex CLI | [0.138.0 - 2026-06-08](captures/codex/0.138.0/prompt.md) | 53 | 2026-06-09 00:16 UTC |
| Hermes Agent | [v2026.6.5 - 2026-06-06](captures/hermes/v2026.6.5/prompt.md) | 15 | 2026-06-06 05:06 UTC |
| Kimi CLI | [1.47.0 - 2026-06-05](captures/kimi/1.47.0/prompt.md) | 19 | 2026-06-05 13:28 UTC |
| OpenClaw | [2026.6.1 - 2026-06-03](captures/openclaw/2026.6.1/prompt.md) | 61 | 2026-06-03 23:16 UTC |
| opencode | [1.16.2 - 2026-06-05](captures/opencode/1.16.2/prompt.md) | 66 | 2026-06-05 16:41 UTC |
| Pi | [0.79.0 - 2026-06-08](captures/pi/0.79.0/prompt.md) | 14 | 2026-06-08 18:09 UTC |
