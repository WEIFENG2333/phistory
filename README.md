# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, DeepSeek Harness, Antigravity, Grok Build, MiniMax Code, Kimi Code, MiMo Code, OpenClaw, Hermes, Kimi CLI, opencode, Pi, and Oh My Pi.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-08-20 13:28 UTC**.

![Phistory prompt diff viewer](docs/screenshot.png)

## Why Use It

- Follow how Anthropic, OpenAI, and other agent builders iterate on system prompts over time.
- See when new tools, permission checks, model defaults, and user-confirmation rules are added.
- Compare how different CLIs structure agent behavior, tool use, and developer-facing constraints.
- Cite stable prompt snapshots in posts, research notes, audits, or debugging reports.

## How It Works

For each supported release, Phistory installs the exact CLI package and runs each configured snapshot through [`claude-tap`](https://github.com/WEIFENG2333/claude-tap), captures the prompt-bearing HTTP request without calling the real model provider, and stores the result under `captures/<agent>/<version>/variants/<variant>/` with `prompt.md`, `trace.jsonl`, and `meta.json`. Capture configurations use a `default` snapshot as their baseline; selected models or modes are stored as additional variants.

For recent Claude Code releases, Phistory also extracts static prompt-like strings from the installed package and stores them under `captures/<agent>/<version>/static/`. The candidate archive keeps the raw extraction input so matching rules can be improved later without reinstalling every historical package.

GitHub Actions checks automatically tracked CLI releases every hour and commits new snapshots when they appear.

## Local Development

Use the hosted viewer at [phistory.cc](https://phistory.cc/). These commands are for local development, capture reproduction, historical backfills, and regenerating generated files.

```bash
# Install the locked development environment.
uv sync --all-groups

# Capture the latest release and every configured snapshot for each CLI.
uv run phistory capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp

# Capture only selected Codex snapshots.
uv run phistory capture --latest --agents codex --variants default,gpt-5.5,gpt-5.6

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
- DeepSeek Harness (`@deepseek-ai/dsh`)
- Antigravity CLI (`google-antigravity/antigravity-cli`)
- Grok Build (`@xai-official/grok`)
- MiniMax Code desktop app ([official download](https://agent.minimax.io/download))
- Kimi Code (`@moonshot-ai/kimi-code`)
- MiMo Code (`@mimo-ai/cli`)
- OpenClaw (`openclaw`)
- Hermes Agent (`hermes-agent`)
- Kimi CLI (`MoonshotAI/kimi-cli`)
- opencode (`opencode-ai`)
- Pi (`@earendil-works/pi-coding-agent`)
- Oh My Pi (`@oh-my-pi/pi-coding-agent`)

## Capture Status

Last capture update: 2026-08-20 13:28 UTC

| Agent | Latest | Versions | Snapshots | Last Captured |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.237 - 2026-08-19](captures/claude-code/2.1.237/variants/default/prompt.md) | 391 | 391 | 2026-08-20 03:25 UTC |
| Codex CLI | [0.148.0 - 2026-08-18](captures/codex/0.148.0/variants/default/prompt.md) | 75 | 83 | 2026-08-18 22:53 UTC |
| DeepSeek Harness | [0.1.0-rc.7 - 2026-08-17](captures/dsh/0.1.0-rc.7/variants/default/prompt.md) | 6 | 27 | 2026-08-17 13:25 UTC |
| Antigravity CLI | [1.1.16 - 2026-08-20](captures/antigravity/1.1.16/variants/default/prompt.md) | 30 | 30 | 2026-08-20 05:06 UTC |
| Grok Build | [1.0.5 - 2026-08-16](captures/grok/1.0.5/variants/default/prompt.md) | 130 | 130 | 2026-08-18 02:00 UTC |
| MiniMax Code | [3.0.66 - 2026-08-20](captures/minimax-code/3.0.66/variants/default/prompt.md) | 30 | 30 | 2026-08-20 07:24 UTC |
| Kimi Code | [0.38.0 - 2026-08-20](captures/kimi-code/0.38.0/variants/default/prompt.md) | 66 | 66 | 2026-08-20 13:28 UTC |
| MiMo Code | [0.1.13 - 2026-08-19](captures/mimo/0.1.13/variants/default/prompt.md) | 13 | 13 | 2026-08-19 11:53 UTC |
| OpenClaw | [2026.7.1-2 - 2026-07-18](captures/openclaw/2026.7.1-2/variants/default/prompt.md) | 69 | 69 | 2026-07-18 04:30 UTC |
| Hermes Agent | [v2026.8.18 - 2026-08-18](captures/hermes/v2026.8.18/variants/default/prompt.md) | 26 | 26 | 2026-08-18 08:04 UTC |
| Kimi CLI | [1.49.0 - 2026-07-16](captures/kimi/1.49.0/variants/default/prompt.md) | 21 | 21 | 2026-07-16 11:21 UTC |
| opencode | [1.18.19 - 2026-08-20](captures/opencode/1.18.19/variants/default/prompt.md) | 104 | 104 | 2026-08-20 07:25 UTC |
| Pi | [0.84.2 - 2026-08-14](captures/pi/0.84.2/variants/default/prompt.md) | 41 | 41 | 2026-08-14 10:35 UTC |
| Oh My Pi | [17.4.0 - 2026-08-20](captures/omp/17.4.0/variants/default/prompt.md) | 63 | 63 | 2026-08-20 07:25 UTC |

## Project Trend

![Phistory star history](https://star-history.dera.page/svg?repos=WEIFENG2333/phistory&type=Date)
