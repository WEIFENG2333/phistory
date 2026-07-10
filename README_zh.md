# Phistory

[English](README.md)

Phistory 追踪 Claude Code、Codex、Antigravity、Kimi Code、MiMo Code、OpenClaw、Hermes、Kimi CLI、opencode、Pi、Oh My Pi 等热门 coding-agent CLI 的系统提示词如何随版本变化。

打开网页查看器，可以对比不同版本的提示词快照，从 prompts、tools、策略和运行时指令里观察 agent 设计如何变化。

**从这里开始：** [phistory.cc](https://phistory.cc/)

> 每小时自动检查新版本，归档最近更新于 **2026-07-10 03:58 UTC**。

![Phistory prompt diff viewer](docs/screenshot.png)

## 为什么看它

- 观察 Anthropic、OpenAI 等团队如何持续迭代 system prompt。
- 看到新工具、权限检查、默认模型行为和用户确认规则是什么时候加入的。
- 对比不同 CLI 如何组织 agent 行为、工具调用和面向开发者的约束。
- 在文章、研究笔记、审计或排障记录里引用稳定的提示词快照。

## 工作原理

Phistory 会安装每个受支持的具体 CLI 版本，通过 [`claude-tap`](https://github.com/liaohch3/claude-tap) 运行一次，抓取包含系统提示词的 HTTP 请求，不调用真实模型服务，然后把结果保存到 `captures/<agent>/<version>/`，里面包含 `prompt.md`、`trace.jsonl` 和 `meta.json`。

对于最近的 Claude Code 版本，Phistory 还会从安装包里提取疑似静态 prompt 的字符串，保存为 `static-prompts.md`、`static-prompts.json` 和 `static-candidates.json`。`static-candidates.json` 会保留原始候选内容，方便以后改进匹配规则时不用重新安装所有历史包。

GitHub Actions 每小时检查一次支持的 CLI 版本；发现新版本后，会自动抓取并提交新的提示词快照。

## 本地开发

日常查看直接使用托管网页：[phistory.cc](https://phistory.cc/)。下面这些命令主要用于本地开发、复现抓取、回填历史版本，以及重新生成项目里的生成文件。

```bash
# 安装锁定的开发环境。
uv sync --all-groups

# 抓取所有受支持 CLI 的最新版本。
uv run phistory capture --latest --agents claude-code,codex,antigravity,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp

# 回填某个 agent 的历史版本区间。
uv run phistory backfill claude-code --from 2.1.113 --to latest

# 重建最近 10 个已捕获 Claude Code 版本的静态 prompt 文件。
uv run phistory extract-static claude-code --latest-captured 10

# 重新生成 README.md、README_zh.md、docs/captures.md 和 captures/index.json。
uv run phistory render-index

# 重新生成静态网页查看器 index.html。
uv run phistory render-site
```

## 支持的 Agent

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

## 抓取状态

最近抓取更新：2026-07-10 03:58 UTC

| Agent | 最新版本 | 快照数 | 最近抓取 |
| --- | --- | ---: | --- |
| Claude Code | [2.1.206 - 2026-07-09](captures/claude-code/2.1.206/prompt.md) | 363 | 2026-07-09 23:52 UTC |
| Codex CLI | [0.144.1 - 2026-07-09](captures/codex/0.144.1/prompt.md) | 65 | 2026-07-09 23:52 UTC |
| Antigravity CLI | [1.1.1 - 2026-07-10](captures/antigravity/1.1.1/prompt.md) | 15 | 2026-07-10 03:58 UTC |
| Kimi Code | [0.23.4 - 2026-07-09](captures/kimi-code/0.23.4/prompt.md) | 40 | 2026-07-09 18:23 UTC |
| MiMo Code | [0.1.5 - 2026-07-07](captures/mimo/0.1.5/prompt.md) | 5 | 2026-07-08 02:58 UTC |
| OpenClaw | [2026.6.11 - 2026-06-30](captures/openclaw/2026.6.11/prompt.md) | 67 | 2026-06-30 18:23 UTC |
| Hermes Agent | [v2026.7.7.2 - 2026-07-08](captures/hermes/v2026.7.7.2/prompt.md) | 19 | 2026-07-08 03:49 UTC |
| Kimi CLI | [1.48.0 - 2026-06-22](captures/kimi/1.48.0/prompt.md) | 20 | 2026-06-22 17:19 UTC |
| opencode | [1.17.18 - 2026-07-09](captures/opencode/1.17.18/prompt.md) | 83 | 2026-07-09 20:27 UTC |
| Pi | [0.80.6 - 2026-07-09](captures/pi/0.80.6/prompt.md) | 29 | 2026-07-09 23:52 UTC |
| Oh My Pi | [16.3.15 - 2026-07-09](captures/omp/16.3.15/prompt.md) | 8 | 2026-07-09 22:09 UTC |

## 项目趋势

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
