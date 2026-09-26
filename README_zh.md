# Phistory

[English](README.md)

Phistory 追踪 Claude Code、Codex、DeepSeek Harness、Antigravity、Grok Build、MiniMax Code、Kimi Code、MiMo Code、OpenClaw、Hermes、Kimi CLI、opencode、Pi、Oh My Pi、Qwen Code 等热门 coding-agent CLI 的系统提示词如何随版本变化。

打开网页查看器，可以对比不同版本的提示词快照，从 prompts、tools、策略和运行时指令里观察 agent 设计如何变化。

**从这里开始：** [phistory.cc](https://phistory.cc/)

> 每小时自动检查新版本，归档最近更新于 **2026-09-26 01:53 UTC**。

![Phistory prompt diff viewer](docs/screenshot.png)

## 为什么看它

- 观察 Anthropic、OpenAI 等团队如何持续迭代 system prompt。
- 看到新工具、权限检查、默认模型行为和用户确认规则是什么时候加入的。
- 对比不同 CLI 如何组织 agent 行为、工具调用和面向开发者的约束。
- 在文章、研究笔记、审计或排障记录里引用稳定的提示词快照。

## 工作原理

Phistory 会安装每个受支持的具体 CLI 版本，再通过 [`claude-tap`](https://github.com/WEIFENG2333/claude-tap) 分别运行每个已配置快照，抓取包含系统提示词的 HTTP 请求，不调用真实模型服务，然后把结果保存到 `captures/<agent>/<version>/variants/<variant>/`，里面包含 `prompt.md`、`trace.jsonl` 和 `meta.json`。`default` 快照按用户实际的用法运行 CLI，自带终端界面的就走真实终端；显式选择的模型或其他调用面会作为额外变体保存。`prompt.md` 由归档的 trace 渲染而来，因此请求里的每个块都会保留：每段系统提示词及其缓存边界、reminder 块，以及夹在对话中间的 system 消息。

GitHub Actions 每小时检查一次已自动追踪的 CLI 版本；发现新版本后，会自动抓取并提交新的提示词快照。

网页支持运行时提示词 diff 和 Trace 可读字段的中文切换。未变段落在历史版本间复用译文，原始证据保持不变；缺少译文时显示原文。配置和存储方式见[翻译说明](docs/translations.md)，实际样本与提示词迭代见[翻译评测](docs/translation-evaluation.md)。

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

# 使用仓库外配置的凭证翻译历史正文；已有段落自动复用。
uv run phistory translate --all-captured

# 重新生成 README.md、README_zh.md、docs/captures.md、captures/index.json 和 llms.txt。
uv run phistory render-index

# 构建完整静态网站，包括中文翻译索引。
uv run phistory build-site
python -m http.server --directory .phistory-cache/site
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

最近抓取更新：2026-09-26 01:53 UTC

| Agent | 最新版本 | 版本数 | 快照数 | 最近抓取 |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.283 - 2026-09-25](captures/claude-code/2.1.283/variants/default/prompt.md) | 427 | 734 | 2026-09-25 22:43 UTC |
| Codex CLI | [0.157.1 - 2026-09-26](captures/codex/0.157.1/variants/default/prompt.md) | 94 | 140 | 2026-09-26 01:53 UTC |
| DeepSeek Harness | [0.1.5-rc.3 - 2026-09-22](captures/dsh/0.1.5-rc.3/variants/default/prompt.md) | 12 | 63 | 2026-09-23 12:03 UTC |
| Antigravity CLI | [1.2.11 - 2026-09-25](captures/antigravity/1.2.11/variants/default/prompt.md) | 54 | 54 | 2026-09-25 08:08 UTC |
| Claude Tag | [2026-09-26 - 2026-09-25](captures/claude-tag/2026-09-26/variants/default/prompt.md) | 2 | 2 | 2026-09-25 23:51 UTC |
| Grok Build | [1.0.41 - 2026-09-22](captures/grok/1.0.41/variants/default/prompt.md) | 137 | 137 | 2026-09-22 22:23 UTC |
| MiniMax Code | [3.0.73 - 2026-09-18](captures/minimax-code/3.0.73/variants/default/prompt.md) | 37 | 37 | 2026-09-18 11:41 UTC |
| Kimi Code | [2.1.1 - 2026-09-24](captures/kimi-code/2.1.1/variants/default/prompt.md) | 79 | 79 | 2026-09-24 10:26 UTC |
| MiMo Code | [0.1.15 - 2026-09-22](captures/mimo/0.1.15/variants/default/prompt.md) | 15 | 15 | 2026-09-22 19:03 UTC |
| OpenClaw | [2026.9.6 - 2026-09-23](captures/openclaw/2026.9.6/variants/default/prompt.md) | 77 | 77 | 2026-09-23 23:55 UTC |
| Hermes Agent | [v2026.9.24 - 2026-09-24](captures/hermes/v2026.9.24/variants/default/prompt.md) | 34 | 34 | 2026-09-24 10:27 UTC |
| Kimi CLI | [1.51.0 - 2026-09-21](captures/kimi/1.51.0/variants/default/prompt.md) | 23 | 23 | 2026-09-21 17:12 UTC |
| opencode | [1.18.32 - 2026-09-21](captures/opencode/1.18.32/variants/default/prompt.md) | 116 | 116 | 2026-09-22 00:15 UTC |
| Pi | [0.87.1 - 2026-09-22](captures/pi/0.87.1/variants/default/prompt.md) | 49 | 49 | 2026-09-22 22:23 UTC |
| Oh My Pi | [18.3.2 - 2026-09-26](captures/omp/18.3.2/variants/default/prompt.md) | 111 | 111 | 2026-09-26 01:53 UTC |
| Qwen Code | [0.22.3 - 2026-08-28](captures/qwen-code/0.22.3/variants/default/prompt.md) | 1 | 1 | 2026-09-02 08:33 UTC |

## 项目趋势

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
