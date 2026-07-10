# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, Antigravity, Kimi Code, MiMo Code, OpenClaw, Hermes, Kimi CLI, opencode, Pi, and Oh My Pi.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-07-10 06:23 UTC**.

![Phistory prompt diff viewer](docs/screenshot.png)

## Why Use It

- Follow how Anthropic, OpenAI, and other agent builders iterate on system prompts over time.
- See when new tools, permission checks, model defaults, and user-confirmation rules are added.
- Compare how different CLIs structure agent behavior, tool use, and developer-facing constraints.
- Cite stable prompt snapshots in posts, research notes, audits, or debugging reports.

## How It Works

For each supported release, Phistory installs the exact CLI package, runs it once through [`claude-tap`](https://github.com/liaohch3/claude-tap), captures the prompt-bearing HTTP request without calling the real model provider, and stores the result under `captures/<agent>/<version>/` with `prompt.md`, `trace.jsonl`, and `meta.json`.

For recent Claude Code releases, Phistory also extracts static prompt-like strings from the installed package and stores them as `static-prompts.md`, `static-prompts.json`, and `static-candidates.json`. The candidate archive keeps the raw extraction input so matching rules can be improved later without reinstalling every historical package.

GitHub Actions checks supported CLI releases every hour and commits new snapshots when they appear.

## Local Development

Use the hosted viewer at [phistory.cc](https://phistory.cc/). These commands are for local development, capture reproduction, historical backfills, and regenerating generated files.

```bash
# Install the locked development environment.
uv sync --all-groups

# Capture the latest supported CLI releases.
uv run phistory capture --latest --agents claude-code,codex,antigravity,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp

# Capture a historical version range for one agent.
uv run phistory backfill claude-code --from 2.1.113 --to latest

# Rebuild static prompt files for the latest 10 captured Claude Code versions.
uv run phistory extract-static claude-code --latest-captured 10

# Regenerate README.md, README_zh.md, docs/captures.md, and captures/index.json.
uv run phistory render-index

# Regenerate the static web viewer at index.html.
uv run phistory render-site
```

## Supported Agents

- Claude Code (`@anthropic-ai/claude-code`)
- Codex CLI (`@openai/codex`)
- Antigravity CLI (`google-antigravity/antigravity-cli`)
- Kimi Code (`@moonshot-ai/kimi-code`)
- MiMo Code (`@mimo-ai/cli`)
- OpenClaw (`openclaw`)
- Hermes Agent (`hermes-agent`)
- Kimi CLI (`MoonshotAI/kimi-cli`)
- opencode (`opencode-ai`)
- Pi (`@earendil-works/pi-coding-agent`)
- Oh My Pi (`@oh-my-pi/pi-coding-agent`)

## Capture Status

Last capture update: 2026-07-10 06:23 UTC

| Agent | Latest | Captures | Last Captured |
| --- | --- | ---: | --- |
| Claude Code | [2.1.206 - 2026-07-09](captures/claude-code/2.1.206/prompt.md) | 363 | 2026-07-09 23:52 UTC |
| Codex CLI | [0.144.1 - 2026-07-09](captures/codex/0.144.1/prompt.md) | 65 | 2026-07-10 06:23 UTC |
| Antigravity CLI | [1.1.1 - 2026-07-10](captures/antigravity/1.1.1/prompt.md) | 15 | 2026-07-10 03:58 UTC |
| Kimi Code | [0.23.4 - 2026-07-09](captures/kimi-code/0.23.4/prompt.md) | 40 | 2026-07-09 18:23 UTC |
| MiMo Code | [0.1.5 - 2026-07-07](captures/mimo/0.1.5/prompt.md) | 5 | 2026-07-08 02:58 UTC |
| OpenClaw | [2026.6.11 - 2026-06-30](captures/openclaw/2026.6.11/prompt.md) | 67 | 2026-06-30 18:23 UTC |
| Hermes Agent | [v2026.7.7.2 - 2026-07-08](captures/hermes/v2026.7.7.2/prompt.md) | 19 | 2026-07-08 03:49 UTC |
| Kimi CLI | [1.48.0 - 2026-06-22](captures/kimi/1.48.0/prompt.md) | 20 | 2026-06-22 17:19 UTC |
| opencode | [1.17.18 - 2026-07-09](captures/opencode/1.17.18/prompt.md) | 83 | 2026-07-09 20:27 UTC |
| Pi | [0.80.6 - 2026-07-09](captures/pi/0.80.6/prompt.md) | 29 | 2026-07-09 23:52 UTC |
| Oh My Pi | [16.3.15 - 2026-07-09](captures/omp/16.3.15/prompt.md) | 8 | 2026-07-09 22:09 UTC |

## Project Trend

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
