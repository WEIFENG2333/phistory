# Phistory

[English](README.md)

Phistory 追踪 Claude Code、Codex、DeepSeek Harness、Antigravity、Grok Build、MiniMax Code、Kimi Code、MiMo Code、OpenClaw、Hermes、Kimi CLI、opencode、Pi、Oh My Pi 等热门 coding-agent CLI 的系统提示词如何随版本变化。

打开网页查看器，可以对比不同版本的提示词快照，从 prompts、tools、策略和运行时指令里观察 agent 设计如何变化。

**从这里开始：** [phistory.cc](https://phistory.cc/)

> 每小时自动检查新版本，归档最近更新于 **2026-09-05 04:58 UTC**。

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
uv run phistory capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp

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

## 抓取状态

最近抓取更新：2026-09-05 04:58 UTC

| Agent | 最新版本 | 版本数 | 快照数 | 最近抓取 |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.261 - 2026-09-04](captures/claude-code/2.1.261/variants/default/prompt.md) | 408 | 408 | 2026-09-04 21:44 UTC |
| Codex CLI | [0.153.4 - 2026-09-04](captures/codex/0.153.4/variants/default/prompt.md) | 87 | 119 | 2026-09-05 00:19 UTC |
| DeepSeek Harness | [0.1.2-rc.1 - 2026-09-03](captures/dsh/0.1.2-rc.1/variants/headless/prompt.md) | 9 | 40 | 2026-09-04 06:31 UTC |
| Antigravity CLI | [1.1.27 - 2026-09-05](captures/antigravity/1.1.27/variants/default/prompt.md) | 41 | 41 | 2026-09-05 04:58 UTC |
| Grok Build | [1.0.13 - 2026-08-28](captures/grok/1.0.13/variants/default/prompt.md) | 131 | 131 | 2026-08-29 02:24 UTC |
| MiniMax Code | [3.0.68 - 2026-08-27](captures/minimax-code/3.0.68/variants/default/prompt.md) | 32 | 32 | 2026-08-27 11:57 UTC |
| Kimi Code | [0.41.0 - 2026-09-04](captures/kimi-code/0.41.0/variants/default/prompt.md) | 71 | 71 | 2026-09-04 11:44 UTC |
| MiMo Code | [0.1.14 - 2026-09-02](captures/mimo/0.1.14/variants/default/prompt.md) | 14 | 14 | 2026-09-02 11:39 UTC |
| OpenClaw | [2026.9.1 - 2026-09-03](captures/openclaw/2026.9.1/variants/default/prompt.md) | 72 | 72 | 2026-09-03 20:05 UTC |
| Hermes Agent | [v2026.8.31 - 2026-08-31](captures/hermes/v2026.8.31/variants/default/prompt.md) | 29 | 29 | 2026-08-31 21:01 UTC |
| Kimi CLI | [1.50.0 - 2026-09-01](captures/kimi/1.50.0/variants/default/prompt.md) | 22 | 22 | 2026-09-01 17:26 UTC |
| opencode | [1.18.29 - 2026-09-04](captures/opencode/1.18.29/variants/default/prompt.md) | 113 | 113 | 2026-09-05 00:25 UTC |
| Pi | [0.85.0 - 2026-09-04](captures/pi/0.85.0/variants/default/prompt.md) | 44 | 44 | 2026-09-04 11:44 UTC |
| Oh My Pi | [18.1.10 - 2026-09-04](captures/omp/18.1.10/variants/default/prompt.md) | 84 | 84 | 2026-09-04 11:44 UTC |

## 项目趋势

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
