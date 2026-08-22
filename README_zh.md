# Phistory

[English](README.md)

Phistory 追踪 Claude Code、Codex、DeepSeek Harness、Antigravity、Grok Build、MiniMax Code、Kimi Code、MiMo Code、OpenClaw、Hermes、Kimi CLI、opencode、Pi、Oh My Pi、Qwen Code 等热门 coding-agent CLI 的系统提示词如何随版本变化。

打开网页查看器，可以对比不同版本的提示词快照，从 prompts、tools、策略和运行时指令里观察 agent 设计如何变化。

**从这里开始：** [phistory.cc](https://phistory.cc/)

> 每小时自动检查新版本，归档最近更新于 **2026-08-22 14:51 UTC**。

![Phistory prompt diff viewer](docs/screenshot.png)

## 为什么看它

- 观察 Anthropic、OpenAI 等团队如何持续迭代 system prompt。
- 看到新工具、权限检查、默认模型行为和用户确认规则是什么时候加入的。
- 对比不同 CLI 如何组织 agent 行为、工具调用和面向开发者的约束。
- 在文章、研究笔记、审计或排障记录里引用稳定的提示词快照。

## 工作原理

Phistory 会安装每个受支持的具体 CLI 版本，再通过 [`claude-tap`](https://github.com/WEIFENG2333/claude-tap) 分别运行每个已配置快照，抓取包含系统提示词的 HTTP 请求，不调用真实模型服务，然后把结果保存到 `captures/<agent>/<version>/variants/<variant>/`，里面包含 `prompt.md`、`trace.jsonl` 和 `meta.json`。抓取配置以 `default` 快照为基线，显式选择的模型或模式会作为额外变体保存。

对于最近的 Claude Code 版本，Phistory 还会从安装包里提取疑似静态 prompt 的字符串，保存在 `captures/<agent>/<version>/static/`。候选文件会保留原始内容，方便以后改进匹配规则时不用重新安装所有历史包。

GitHub Actions 每小时检查一次已自动追踪的 CLI 版本；发现新版本后，会自动抓取并提交新的提示词快照。

## 本地开发

日常查看直接使用托管网页：[phistory.cc](https://phistory.cc/)。下面这些命令主要用于本地开发、复现抓取、回填历史版本，以及重新生成项目里的生成文件。

```bash
# 安装锁定的开发环境。
uv sync --all-groups

# 抓取每个 CLI 的最新版本及其全部已配置快照。
uv run phistory capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp,qwen-code

# 只抓取 Codex 的指定快照。
uv run phistory capture --latest --agents codex --variants default,gpt-5.5,gpt-5.6

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
- DeepSeek Harness (`@deepseek-ai/dsh`)
- Antigravity CLI (`google-antigravity/antigravity-cli`)
- Grok Build (`@xai-official/grok`)
- MiniMax Code 桌面应用（[官方下载](https://agent.minimax.io/download)）
- Kimi Code (`@moonshot-ai/kimi-code`)
- MiMo Code (`@mimo-ai/cli`)
- OpenClaw (`openclaw`)
- Hermes Agent (`hermes-agent`)
- Kimi CLI (`MoonshotAI/kimi-cli`)
- opencode (`opencode-ai`)
- Pi (`@earendil-works/pi-coding-agent`)
- Oh My Pi (`@oh-my-pi/pi-coding-agent`)
- Qwen Code (`@qwen-code/qwen-code`)

## 抓取状态

最近抓取更新：2026-08-22 14:51 UTC

| Agent | 最新版本 | 版本数 | 快照数 | 最近抓取 |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.240 - 2026-08-22](captures/claude-code/2.1.240/variants/default/prompt.md) | 394 | 394 | 2026-08-22 14:51 UTC |
| Codex CLI | [0.149.0 - 2026-08-20](captures/codex/0.149.0/variants/default/prompt.md) | 76 | 86 | 2026-08-20 21:55 UTC |
| DeepSeek Harness | [0.1.1-rc.2 - 2026-08-21](captures/dsh/0.1.1-rc.2/variants/default/prompt.md) | 8 | 39 | 2026-08-21 13:43 UTC |
| Antigravity CLI | [1.1.18 - 2026-08-22](captures/antigravity/1.1.18/variants/default/prompt.md) | 32 | 32 | 2026-08-22 02:00 UTC |
| Grok Build | [1.0.5 - 2026-08-16](captures/grok/1.0.5/variants/default/prompt.md) | 130 | 130 | 2026-08-18 02:00 UTC |
| MiniMax Code | [3.0.67 - 2026-08-21](captures/minimax-code/3.0.67/variants/default/prompt.md) | 31 | 31 | 2026-08-21 09:31 UTC |
| Kimi Code | [0.38.0 - 2026-08-20](captures/kimi-code/0.38.0/variants/default/prompt.md) | 66 | 66 | 2026-08-20 13:28 UTC |
| MiMo Code | [0.1.13 - 2026-08-19](captures/mimo/0.1.13/variants/default/prompt.md) | 13 | 13 | 2026-08-19 11:53 UTC |
| OpenClaw | [2026.7.1-2 - 2026-07-18](captures/openclaw/2026.7.1-2/variants/default/prompt.md) | 69 | 69 | 2026-07-18 04:30 UTC |
| Hermes Agent | [v2026.8.19 - 2026-08-21](captures/hermes/v2026.8.19/variants/default/prompt.md) | 27 | 27 | 2026-08-21 13:44 UTC |
| Kimi CLI | [1.49.0 - 2026-07-16](captures/kimi/1.49.0/variants/default/prompt.md) | 21 | 21 | 2026-07-16 11:21 UTC |
| opencode | [1.18.21 - 2026-08-21](captures/opencode/1.18.21/variants/default/prompt.md) | 106 | 106 | 2026-08-21 15:05 UTC |
| Pi | [0.84.2 - 2026-08-14](captures/pi/0.84.2/variants/default/prompt.md) | 41 | 41 | 2026-08-14 10:35 UTC |
| Oh My Pi | [18.0.0 - 2026-08-22](captures/omp/18.0.0/variants/default/prompt.md) | 66 | 66 | 2026-08-22 11:48 UTC |
| Qwen Code | [0.21.13 - 2026-08-17](captures/qwen-code/0.21.13/variants/default/prompt.md) | 1 | 1 | 2026-08-18 17:11 UTC |

## 项目趋势

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
