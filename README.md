# phistory

`phistory` archives versioned system prompt snapshots from agent CLIs.

It installs a specific CLI release, runs it once through [`claude-tap`](https://github.com/WEIFENG2333/claude-tap), captures the prompt-bearing HTTP request, and writes a comparison-friendly Markdown snapshot. The upstream target is a local dummy server, so the captured run does not send a model request to the real provider.

GitHub Actions runs this on a schedule and updates the repository when a new supported CLI version appears.

## Usage

```bash
uv run phistory capture --latest --agents claude-code,codex
uv run phistory backfill claude-code --from 2.1.113 --to latest
uv run phistory render-index
```

## Supported Agents

- Claude Code (`@anthropic-ai/claude-code`)
- Codex CLI (`@openai/codex`)

## Capture Format

Each capture is stored under `captures/<agent>/<version>/`:

- `prompt.md`: normalized prompt snapshot for reading and diffing
- `trace.jsonl`: raw captured HTTP trace, kept unnormalized as evidence
- `meta.json`: package, version, command, and capture metadata

## Latest Captures

- Claude Code: `2.1.147` published 2026-05-21 17:16 UTC, captured 2026-05-21 23:07 UTC
- Codex CLI: `0.133.0` published 2026-05-21 17:13 UTC, captured 2026-05-21 23:07 UTC

## Captures

| Agent | Version | Published | Captured | Snapshot | Raw Trace |
| --- | --- | --- | --- | --- | --- |
| Codex CLI | `0.133.0` | 2026-05-21 17:13 UTC | 2026-05-21 23:07 UTC | [codex 0.133.0, published 2026-05-21 17:13 UTC](captures/codex/0.133.0/prompt.md) | [trace.jsonl](captures/codex/0.133.0/trace.jsonl) |
| Codex CLI | `0.132.0` | 2026-05-20 02:39 UTC | 2026-05-21 22:42 UTC | [codex 0.132.0, published 2026-05-20 02:39 UTC](captures/codex/0.132.0/prompt.md) | [trace.jsonl](captures/codex/0.132.0/trace.jsonl) |
| Codex CLI | `0.131.0` | 2026-05-18 18:08 UTC | 2026-05-21 22:42 UTC | [codex 0.131.0, published 2026-05-18 18:08 UTC](captures/codex/0.131.0/prompt.md) | [trace.jsonl](captures/codex/0.131.0/trace.jsonl) |
| Claude Code | `2.1.147` | 2026-05-21 17:16 UTC | 2026-05-21 23:07 UTC | [claude-code 2.1.147, published 2026-05-21 17:16 UTC](captures/claude-code/2.1.147/prompt.md) | [trace.jsonl](captures/claude-code/2.1.147/trace.jsonl) |
| Claude Code | `2.1.146` | 2026-05-20 20:14 UTC | 2026-05-21 22:13 UTC | [claude-code 2.1.146, published 2026-05-20 20:14 UTC](captures/claude-code/2.1.146/prompt.md) | [trace.jsonl](captures/claude-code/2.1.146/trace.jsonl) |
| Claude Code | `2.1.145` | 2026-05-19 17:40 UTC | 2026-05-21 22:12 UTC | [claude-code 2.1.145, published 2026-05-19 17:40 UTC](captures/claude-code/2.1.145/prompt.md) | [trace.jsonl](captures/claude-code/2.1.145/trace.jsonl) |
| Claude Code | `2.1.144` | 2026-05-18 19:57 UTC | 2026-05-21 22:12 UTC | [claude-code 2.1.144, published 2026-05-18 19:57 UTC](captures/claude-code/2.1.144/prompt.md) | [trace.jsonl](captures/claude-code/2.1.144/trace.jsonl) |
