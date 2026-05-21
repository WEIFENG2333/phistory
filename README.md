# phistory

`phistory` captures versioned prompt snapshots from agent CLIs.

It installs a specific CLI version, runs it once through `claude-tap`, and archives the prompt-bearing request body as Markdown. The upstream target is a local dummy server, so the model request is never sent to the real provider.

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

- `prompt.md`: normalized prompt snapshot
- `trace.jsonl`: raw captured HTTP trace
- `meta.json`: package, version, command, and capture metadata

## Captures

| Agent | Version | Published | Captured | Prompt | Trace |
| --- | --- | --- | --- | --- | --- |
| Codex CLI | `0.132.0` | 2026-05-20T02:39:00.388Z | 2026-05-21T17:07:31.801991+00:00 | [prompt](captures/codex/0.132.0/prompt.md) | [trace](captures/codex/0.132.0/trace.jsonl) |
| Claude Code | `2.1.146` | 2026-05-20T20:14:13.615Z | 2026-05-21T17:07:20.392057+00:00 | [prompt](captures/claude-code/2.1.146/prompt.md) | [trace](captures/claude-code/2.1.146/trace.jsonl) |
