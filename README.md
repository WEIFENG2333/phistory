# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, DeepSeek Harness, Antigravity, Grok Build, MiniMax Code, Kimi Code, MiMo Code, OpenClaw, Hermes, Kimi CLI, opencode, Pi, Oh My Pi, and Qwen Code.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-09-04 01:15 UTC**.

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
uv run phistory capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp,qwen-code

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
- Qwen Code (`@qwen-code/qwen-code`)

## Capture Status

Last capture update: 2026-09-04 01:15 UTC

| Agent | Latest | Versions | Snapshots | Last Captured |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.260 - 2026-09-03](captures/claude-code/2.1.260/variants/default/prompt.md) | 407 | 407 | 2026-09-04 01:15 UTC |
| Codex CLI | [0.153.2 - 2026-09-03](captures/codex/0.153.2/variants/default/prompt.md) | 85 | 113 | 2026-09-04 01:15 UTC |
| DeepSeek Harness | [0.1.1-rc.2 - 2026-08-21](captures/dsh/0.1.1-rc.2/variants/default/prompt.md) | 8 | 39 | 2026-08-21 13:43 UTC |
| Antigravity CLI | [1.1.25 - 2026-09-03](captures/antigravity/1.1.25/variants/default/prompt.md) | 39 | 39 | 2026-09-03 06:24 UTC |
| Grok Build | [1.0.13 - 2026-08-28](captures/grok/1.0.13/variants/default/prompt.md) | 131 | 131 | 2026-08-29 02:24 UTC |
| MiniMax Code | [3.0.68 - 2026-08-27](captures/minimax-code/3.0.68/variants/default/prompt.md) | 32 | 32 | 2026-08-27 11:57 UTC |
| Kimi Code | [0.40.1 - 2026-09-02](captures/kimi-code/0.40.1/variants/default/prompt.md) | 70 | 70 | 2026-09-02 11:39 UTC |
| MiMo Code | [0.1.14 - 2026-09-02](captures/mimo/0.1.14/variants/default/prompt.md) | 14 | 14 | 2026-09-02 11:39 UTC |
| OpenClaw | [2026.9.1 - 2026-09-03](captures/openclaw/2026.9.1/variants/default/prompt.md) | 72 | 72 | 2026-09-03 20:05 UTC |
| Hermes Agent | [v2026.8.31 - 2026-08-31](captures/hermes/v2026.8.31/variants/default/prompt.md) | 29 | 29 | 2026-08-31 21:01 UTC |
| Kimi CLI | [1.50.0 - 2026-09-01](captures/kimi/1.50.0/variants/default/prompt.md) | 22 | 22 | 2026-09-01 17:26 UTC |
| opencode | [1.18.27 - 2026-09-02](captures/opencode/1.18.27/variants/default/prompt.md) | 111 | 111 | 2026-09-02 22:48 UTC |
| Pi | [0.84.4 - 2026-08-28](captures/pi/0.84.4/variants/default/prompt.md) | 43 | 43 | 2026-08-29 02:24 UTC |
| Oh My Pi | [18.1.8 - 2026-09-04](captures/omp/18.1.8/variants/default/prompt.md) | 83 | 83 | 2026-09-04 01:15 UTC |
| Qwen Code | [0.22.3 - 2026-08-28](captures/qwen-code/0.22.3/variants/default/prompt.md) | 1 | 1 | 2026-09-02 08:33 UTC |

## Project Trend

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
