# Phistory

[English](README.md)

Phistory 追踪 Claude Code、Codex、Antigravity、Kimi、opencode、OpenClaw、Hermes、Pi 等热门 coding-agent CLI 的系统提示词如何随版本变化。

打开网页查看器，可以对比不同版本的提示词快照，从 prompts、tools、策略和运行时指令里观察 agent 设计如何变化。

**从这里开始：** [phistory.cc](https://phistory.cc/)

> 每小时自动检查新版本，归档最近更新于 **2026-06-27 06:44 UTC**。

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
uv run phistory capture --latest --agents antigravity,claude-code,codex,openclaw,hermes,kimi,opencode,pi

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
- OpenClaw (`openclaw`)
- Hermes Agent (`hermes-agent`)
- Kimi CLI (`MoonshotAI/kimi-cli`)
- opencode (`opencode-ai`)
- Pi (`@earendil-works/pi-coding-agent`)

## 抓取状态

最近抓取更新：2026-06-27 06:44 UTC

| Agent | 最新版本 | 快照数 | 最近抓取 |
| --- | --- | ---: | --- |
| Antigravity CLI | [1.0.13 - 2026-06-27](captures/antigravity/1.0.13/prompt.md) | 10 | 2026-06-27 06:41 UTC |
| Claude Code | [2.1.195 - 2026-06-26](captures/claude-code/2.1.195/prompt.md) | 352 | 2026-06-26 21:51 UTC |
| Codex CLI | [0.142.3 - 2026-06-26](captures/codex/0.142.3/prompt.md) | 60 | 2026-06-26 21:51 UTC |
| Hermes Agent | [v2026.6.19 - 2026-06-19](captures/hermes/v2026.6.19/prompt.md) | 16 | 2026-06-19 19:52 UTC |
| Kimi CLI | [1.48.0 - 2026-06-22](captures/kimi/1.48.0/prompt.md) | 20 | 2026-06-22 17:19 UTC |
| OpenClaw | [2026.6.10 - 2026-06-24](captures/openclaw/2026.6.10/prompt.md) | 66 | 2026-06-24 04:50 UTC |
| opencode | [1.17.11 - 2026-06-25](captures/opencode/1.17.11/prompt.md) | 77 | 2026-06-25 12:40 UTC |
| Pi | [0.80.2 - 2026-06-23](captures/pi/0.80.2/prompt.md) | 26 | 2026-06-23 23:39 UTC |

## 项目趋势

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
