# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, DeepSeek Harness, Antigravity, Grok Build, MiniMax Code, Kimi Code, MiMo Code, OpenClaw, Hermes, Kimi CLI, opencode, Pi, Oh My Pi, and Qwen Code.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-10-09 21:10 UTC**.

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
uv run phistory capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp,qwen-code

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
- Qwen Code (`@qwen-code/qwen-code`)

## Capture Status

Last capture update: 2026-10-09 21:10 UTC

| Agent | Latest | Versions | Snapshots | Last Captured |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.296 - 2026-10-09](captures/claude-code/2.1.296/variants/default/prompt.md) | 439 | 758 | 2026-10-09 21:10 UTC |
| Codex CLI | [0.162.1 - 2026-10-09](captures/codex/0.162.1/variants/default/prompt.md) | 104 | 170 | 2026-10-09 21:10 UTC |
| DeepSeek Harness | [0.2.0-rc.2 - 2026-09-29](captures/dsh/0.2.0-rc.2/variants/default/prompt.md) | 14 | 75 | 2026-09-29 16:06 UTC |
| Antigravity CLI | [1.3.2 - 2026-10-08](captures/antigravity/1.3.2/variants/default/prompt.md) | 63 | 63 | 2026-10-09 02:28 UTC |
| Claude Tag | [2026-10-07 - 2026-10-06](captures/claude-tag/2026-10-07/variants/default/prompt.md) | 3 | 3 | 2026-10-06 18:05 UTC |
| Grok Build | [1.0.50 - 2026-10-06](captures/grok/1.0.50/variants/default/prompt.md) | 140 | 140 | 2026-10-08 16:50 UTC |
| MiniMax Code | [3.1.1 - 2026-10-04](captures/minimax-code/3.1.1/variants/default/prompt.md) | 40 | 40 | 2026-10-04 15:28 UTC |
| Kimi Code | [2.1.1 - 2026-09-24](captures/kimi-code/2.1.1/variants/default/prompt.md) | 79 | 79 | 2026-09-24 10:26 UTC |
| MiMo Code | [0.1.15 - 2026-09-22](captures/mimo/0.1.15/variants/default/prompt.md) | 15 | 15 | 2026-09-22 19:03 UTC |
| OpenClaw | [2026.9.9 - 2026-10-08](captures/openclaw/2026.9.9/variants/default/prompt.md) | 80 | 80 | 2026-10-08 16:51 UTC |
| Hermes Agent | [v2026.9.24 - 2026-09-24](captures/hermes/v2026.9.24/variants/default/prompt.md) | 34 | 34 | 2026-09-24 10:27 UTC |
| Kimi CLI | [1.51.0 - 2026-09-21](captures/kimi/1.51.0/variants/default/prompt.md) | 23 | 23 | 2026-09-21 17:12 UTC |
| opencode | [1.18.35 - 2026-10-06](captures/opencode/1.18.35/variants/default/prompt.md) | 119 | 119 | 2026-10-06 21:52 UTC |
| Pi | [1.1.0 - 2026-10-07](captures/pi/1.1.0/variants/default/prompt.md) | 57 | 57 | 2026-10-08 02:14 UTC |
| Oh My Pi | [18.8.7 - 2026-10-09](captures/omp/18.8.7/variants/default/prompt.md) | 135 | 135 | 2026-10-09 16:29 UTC |
| Qwen Code | [0.22.3 - 2026-08-28](captures/qwen-code/0.22.3/variants/default/prompt.md) | 1 | 1 | 2026-09-02 08:33 UTC |

## Project Trend

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
