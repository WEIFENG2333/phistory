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

Last capture update: 2026-05-30 21:16 UTC

| Agent | Latest | Captures | Last Captured |
| --- | --- | ---: | --- |
| Claude Code | [2.1.158 - 2026-05-30](captures/claude-code/2.1.158/prompt.md) | 326 | 2026-05-30 04:18 UTC |
| Codex CLI | [0.135.0 - 2026-05-28](captures/codex/0.135.0/prompt.md) | 50 | 2026-05-28 19:46 UTC |
| Hermes Agent | [v2026.5.29.2 - 2026-05-29](captures/hermes/v2026.5.29.2/prompt.md) | 14 | 2026-05-29 16:55 UTC |
| Kimi CLI | [1.46.0 - 2026-05-29](captures/kimi/1.46.0/prompt.md) | 18 | 2026-05-29 08:53 UTC |
| OpenClaw | [2026.5.28 - 2026-05-30](captures/openclaw/2026.5.28/prompt.md) | 60 | 2026-05-30 21:16 UTC |
| opencode | [1.15.12 - 2026-05-28](captures/opencode/1.15.12/prompt.md) | 63 | 2026-05-28 19:46 UTC |
| Pi | [0.78.0 - 2026-05-29](captures/pi/0.78.0/prompt.md) | 12 | 2026-05-30 04:18 UTC |
