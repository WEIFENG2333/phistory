# Phistory

[中文](README_zh.md)

Phistory automatically archives versioned system prompt snapshots from agent CLIs like Claude Code, Codex, OpenClaw, Hermes, Kimi, opencode, and Pi.

It installs a specific CLI release, runs it once through [`claude-tap`](https://github.com/WEIFENG2333/claude-tap), captures the prompt-bearing HTTP request, and writes a comparison-friendly Markdown snapshot.

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

Last capture update: 2026-05-27 04:49 UTC

| Agent | Latest | Captures | Last Captured |
| --- | --- | ---: | --- |
| Claude Code | [2.1.152 - 2026-05-26](captures/claude-code/2.1.152/prompt.md) | 321 | 2026-05-27 02:52 UTC |
| Codex CLI | [0.134.0 - 2026-05-26](captures/codex/0.134.0/prompt.md) | 49 | 2026-05-26 22:00 UTC |
| Hermes Agent | [v2026.5.16 - 2026-05-16](captures/hermes/v2026.5.16/prompt.md) | 11 | 2026-05-22 12:31 UTC |
| Kimi CLI | [1.45.0 - 2026-05-27](captures/kimi/1.45.0/prompt.md) | 17 | 2026-05-27 04:49 UTC |
| OpenClaw | [2026.5.22 - 2026-05-24](captures/openclaw/2026.5.22/prompt.md) | 57 | 2026-05-24 04:40 UTC |
| opencode | [1.15.11 - 2026-05-27](captures/opencode/1.15.11/prompt.md) | 62 | 2026-05-27 04:49 UTC |
| Pi | [0.75.5 - 2026-05-23](captures/pi/0.75.5/prompt.md) | 9 | 2026-05-23 10:45 UTC |
