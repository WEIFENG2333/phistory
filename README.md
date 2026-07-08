# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, Antigravity, Kimi Code, MiMo Code, OpenClaw, Hermes, Kimi CLI, opencode, Pi, and Oh My Pi.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-07-08 02:48 UTC**.

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

Last capture update: 2026-07-08 02:48 UTC

| Agent | Latest | Captures | Last Captured |
| --- | --- | ---: | --- |
| Claude Code | [2.1.204 - 2026-07-08](captures/claude-code/2.1.204/prompt.md) | 361 | 2026-07-08 02:40 UTC |
| Codex CLI | [0.142.5 - 2026-07-01](captures/codex/0.142.5/prompt.md) | 62 | 2026-07-01 05:10 UTC |
| Antigravity CLI | [1.0.15 - 2026-07-01](captures/antigravity/1.0.15/prompt.md) | 12 | 2026-07-01 23:54 UTC |
| Kimi Code | [0.22.1 - 2026-07-02](captures/kimi-code/0.22.1/prompt.md) | 36 | 2026-07-02 14:44 UTC |
| MiMo Code | [0.1.4 - 2026-06-29](captures/mimo/0.1.4/prompt.md) | 4 | 2026-07-01 12:40 UTC |
| OpenClaw | [2026.6.11 - 2026-06-30](captures/openclaw/2026.6.11/prompt.md) | 67 | 2026-06-30 18:23 UTC |
| Hermes Agent | [v2026.7.1 - 2026-07-01](captures/hermes/v2026.7.1/prompt.md) | 17 | 2026-07-01 20:28 UTC |
| Kimi CLI | [1.48.0 - 2026-06-22](captures/kimi/1.48.0/prompt.md) | 20 | 2026-06-22 17:19 UTC |
| opencode | [1.17.13 - 2026-07-01](captures/opencode/1.17.13/prompt.md) | 79 | 2026-07-01 16:58 UTC |
| Pi | [0.80.3 - 2026-06-30](captures/pi/0.80.3/prompt.md) | 27 | 2026-06-30 22:01 UTC |
| Oh My Pi | [16.3.5 - 2026-07-04](captures/omp/16.3.5/prompt.md) | 3 | 2026-07-04 11:48 UTC |

## Project Trend

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
