# Phistory

[中文](README_zh.md)

Phistory tracks how system prompts change across popular coding-agent CLIs like Claude Code, Codex, DeepSeek Harness, Antigravity, Grok Build, MiniMax Code, Kimi Code, MiMo Code, OpenClaw, Hermes, Kimi CLI, opencode, Pi, and Oh My Pi.

Open the web viewer to compare prompt snapshots across versions and see how agent design changes through prompts, tools, policies, and runtime instructions.

**Start here:** [phistory.cc](https://phistory.cc/)

> Checks for new releases hourly. Archive last updated: **2026-09-11 06:35 UTC**.

![Phistory prompt diff viewer](docs/screenshot.png)

## Why Use It

- Follow how Anthropic, OpenAI, and other agent builders iterate on system prompts over time.
- See when new tools, permission checks, model defaults, and user-confirmation rules are added.
- Compare how different CLIs structure agent behavior, tool use, and developer-facing constraints.
- Cite stable prompt snapshots in posts, research notes, audits, or debugging reports.

## How It Works

For each supported release, Phistory installs the exact CLI package and runs each configured snapshot through [`claude-tap`](https://github.com/WEIFENG2333/claude-tap), captures the prompt-bearing HTTP request without calling the real model provider, and stores the result under `captures/<agent>/<version>/variants/<variant>/` with `prompt.md`, `trace.jsonl`, and `meta.json`. Capture configurations use a `default` snapshot as their baseline; selected models or modes are stored as additional variants.

For recent Claude Code releases, Phistory also extracts static prompt-like strings from the installed package and stores them under `captures/<agent>/<version>/static/`. The candidate archive preserves extracted text after resource filtering, so filters and matching rules can be reapplied without reinstalling historical packages. See [Static extraction and cleanup](docs/static-prompts.md).

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

# Rebuild static prompt files for the latest 10 captured Claude Code versions.
uv run phistory extract-static claude-code --latest-captured 10

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

Last capture update: 2026-09-11 06:35 UTC

| Agent | Latest | Versions | Snapshots | Last Captured |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.268 - 2026-09-10](captures/claude-code/2.1.268/variants/default/prompt.md) | 413 | 413 | 2026-09-10 22:44 UTC |
| Codex CLI | [0.154.0 - 2026-09-09](captures/codex/0.154.0/variants/default/prompt.md) | 88 | 122 | 2026-09-09 22:42 UTC |
| DeepSeek Harness | [0.1.5-rc.1 - 2026-09-10](captures/dsh/0.1.5-rc.1/variants/default/prompt.md) | 10 | 51 | 2026-09-10 06:35 UTC |
| Antigravity CLI | [1.2.0 - 2026-09-10](captures/antigravity/1.2.0/variants/default/prompt.md) | 43 | 43 | 2026-09-10 06:36 UTC |
| Grok Build | [1.0.25 - 2026-09-09](captures/grok/1.0.25/variants/default/prompt.md) | 133 | 133 | 2026-09-09 19:59 UTC |
| MiniMax Code | [3.0.70 - 2026-09-09](captures/minimax-code/3.0.70/variants/default/prompt.md) | 34 | 34 | 2026-09-09 16:53 UTC |
| Kimi Code | [0.42.0 - 2026-09-09](captures/kimi-code/0.42.0/variants/default/prompt.md) | 72 | 72 | 2026-09-09 06:35 UTC |
| MiMo Code | [0.1.14 - 2026-09-02](captures/mimo/0.1.14/variants/default/prompt.md) | 14 | 14 | 2026-09-02 11:39 UTC |
| OpenClaw | [2026.9.4 - 2026-09-11](captures/openclaw/2026.9.4/variants/default/prompt.md) | 75 | 75 | 2026-09-11 06:35 UTC |
| Hermes Agent | [v2026.9.7 - 2026-09-07](captures/hermes/v2026.9.7/variants/default/prompt.md) | 30 | 30 | 2026-09-08 00:39 UTC |
| Kimi CLI | [1.50.0 - 2026-09-01](captures/kimi/1.50.0/variants/default/prompt.md) | 22 | 22 | 2026-09-01 17:26 UTC |
| opencode | [1.18.30 - 2026-09-09](captures/opencode/1.18.30/variants/default/prompt.md) | 114 | 114 | 2026-09-09 06:35 UTC |
| Pi | [0.85.1 - 2026-09-05](captures/pi/0.85.1/variants/default/prompt.md) | 45 | 45 | 2026-09-05 13:05 UTC |
| Oh My Pi | [18.1.17 - 2026-09-10](captures/omp/18.1.17/variants/default/prompt.md) | 91 | 91 | 2026-09-10 20:00 UTC |

## Project Trend

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
