# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, Antigravity, Kimi, opencode, OpenClaw, Hermes, and Pi.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-06-27 06:44 UTC**.

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
uv run phistory capture --latest --agents antigravity,claude-code,codex,openclaw,hermes,kimi,opencode,pi

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
- OpenClaw (`openclaw`)
- Hermes Agent (`hermes-agent`)
- Kimi CLI (`MoonshotAI/kimi-cli`)
- opencode (`opencode-ai`)
- Pi (`@earendil-works/pi-coding-agent`)

## Capture Status

Last capture update: 2026-06-27 06:44 UTC

| Agent | Latest | Captures | Last Captured |
| --- | --- | ---: | --- |
| Antigravity CLI | [1.0.13 - 2026-06-27](captures/antigravity/1.0.13/prompt.md) | 10 | 2026-06-27 06:41 UTC |
| Claude Code | [2.1.195 - 2026-06-26](captures/claude-code/2.1.195/prompt.md) | 352 | 2026-06-26 21:51 UTC |
| Codex CLI | [0.142.3 - 2026-06-26](captures/codex/0.142.3/prompt.md) | 60 | 2026-06-26 21:51 UTC |
| Hermes Agent | [v2026.6.19 - 2026-06-19](captures/hermes/v2026.6.19/prompt.md) | 16 | 2026-06-19 19:52 UTC |
| Kimi CLI | [1.48.0 - 2026-06-22](captures/kimi/1.48.0/prompt.md) | 20 | 2026-06-22 17:19 UTC |
| OpenClaw | [2026.6.10 - 2026-06-24](captures/openclaw/2026.6.10/prompt.md) | 66 | 2026-06-24 04:50 UTC |
| opencode | [1.17.11 - 2026-06-25](captures/opencode/1.17.11/prompt.md) | 77 | 2026-06-25 12:40 UTC |
| Pi | [0.80.2 - 2026-06-23](captures/pi/0.80.2/prompt.md) | 26 | 2026-06-23 23:39 UTC |

## Project Trend

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
