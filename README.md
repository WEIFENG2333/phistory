# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, DeepSeek Harness, Antigravity, Grok Build, MiniMax Code, Kimi Code, MiMo Code, OpenClaw, Hermes, Kimi CLI, opencode, Pi, and Oh My Pi.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-10-26 14:31 UTC**.

![Phistory prompt diff viewer](docs/screenshot.png)

## Why Use It

- Follow how Anthropic, OpenAI, and other agent builders iterate on system prompts over time.
- See when new tools, permission checks, model defaults, and user-confirmation rules are added.
- Compare how different CLIs structure agent behavior, tool use, and developer-facing constraints.
- Cite stable prompt snapshots in posts, research notes, audits, or debugging reports.

## How It Works

For each supported release, Phistory installs the exact CLI package and runs each configured snapshot through [`claude-tap`](https://github.com/WEIFENG2333/claude-tap), captures the prompt-bearing HTTP request without calling the real model provider, and stores the result under `captures/<agent>/<version>/variants/<variant>/` with `prompt.md`, `trace.jsonl`, and `meta.json`. The `default` snapshot runs each CLI the way its users do, through a real terminal when it ships one; selected models or alternative surfaces are stored as additional variants. `prompt.md` is rendered from the archived trace, so every block of the request survives into it: each system block and its cache boundary, reminder blocks, and system messages interleaved with the conversation.

GitHub Actions checks automatically tracked CLI releases every hour and commits new snapshots when they appear.

The viewer supports Chinese translations for runtime prompt diffs and readable trace fields. Unchanged paragraphs reuse shared translations across versions; original evidence is preserved. See [translation setup and storage](docs/translations.md) and [model evaluation](docs/translation-evaluation.md).

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

# Translate archived prose using credentials configured outside the repository.
uv run phistory translate --all-captured

# Regenerate README.md, README_zh.md, docs/captures.md, captures/index.json, and llms.txt.
uv run phistory render-index

# Build the complete static site, including Chinese translation indexes.
uv run phistory build-site
python -m http.server --directory .phistory-cache/site
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

Last capture update: 2026-10-26 14:31 UTC

| Agent | Latest | Versions | Snapshots | Last Captured |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.310 - 2026-10-23](captures/claude-code/2.1.310/variants/default/prompt.md) | 451 | 782 | 2026-10-24 01:00 UTC |
| Codex CLI | [0.164.0 - 2026-10-23](captures/codex/0.164.0/variants/default/prompt.md) | 106 | 176 | 2026-10-23 07:53 UTC |
| DeepSeek Harness | [0.2.1-rc.2 - 2026-10-17](captures/dsh/0.2.1-rc.2/variants/default/prompt.md) | 15 | 81 | 2026-10-19 11:10 UTC |
| Antigravity CLI | [1.4.7 - 2026-10-24](captures/antigravity/1.4.7/variants/default/prompt.md) | 75 | 75 | 2026-10-24 06:22 UTC |
| Claude Tag | [2026-10-18 - 2026-10-18](captures/claude-tag/2026-10-18/variants/default/prompt.md) | 4 | 4 | 2026-10-18 08:57 UTC |
| Grokbot | [2026-10-20 - 2026-10-20](captures/grokbot/2026-10-20/variants/default/prompt.md) | 1 | 1 | 2026-10-20 18:10 UTC |
| Grok Build | [1.0.70 - 2026-10-23](captures/grok/1.0.70/variants/default/prompt.md) | 145 | 145 | 2026-10-24 06:22 UTC |
| MiniMax Code | [3.1.6 - 2026-10-23](captures/minimax-code/3.1.6/variants/default/prompt.md) | 44 | 44 | 2026-10-23 18:39 UTC |
| Kimi Code | [2.3.3 - 2026-10-26](captures/kimi-code/2.3.3/variants/default/prompt.md) | 84 | 84 | 2026-10-26 14:31 UTC |
| MiMo Code | [0.1.16 - 2026-10-26](captures/mimo/0.1.16/variants/default/prompt.md) | 16 | 16 | 2026-10-26 14:31 UTC |
| OpenClaw | [2026.10.7 - 2026-10-24](captures/openclaw/2026.10.7/variants/default/prompt.md) | 87 | 87 | 2026-10-24 11:29 UTC |
| Hermes Agent | [v2026.9.24 - 2026-09-24](captures/hermes/v2026.9.24/variants/default/prompt.md) | 37 | 37 | 2026-09-24 10:27 UTC |
| Kimi CLI | [1.51.0 - 2026-09-21](captures/kimi/1.51.0/variants/default/prompt.md) | 23 | 23 | 2026-09-21 17:12 UTC |
| opencode | [1.19.4 - 2026-10-22](captures/opencode/1.19.4/variants/default/prompt.md) | 124 | 124 | 2026-10-22 14:02 UTC |
| Pi | [1.4.0 - 2026-10-21](captures/pi/1.4.0/variants/default/prompt.md) | 60 | 60 | 2026-10-22 01:45 UTC |
| Oh My Pi | [18.12.6 - 2026-10-21](captures/omp/18.12.6/variants/default/prompt.md) | 154 | 154 | 2026-10-21 22:38 UTC |

## Project Trend

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
