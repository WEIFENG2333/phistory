# Phistory

[English](README.md)

Phistory 追踪 Claude Code、Codex、DeepSeek Harness、Antigravity、Grok Build、MiniMax Code、Kimi Code、MiMo Code、OpenClaw、Hermes、Kimi CLI、opencode、Pi、Oh My Pi 等热门 coding-agent CLI 的系统提示词如何随版本变化。

打开网页查看器，可以对比不同版本的提示词快照，从 prompts、tools、策略和运行时指令里观察 agent 设计如何变化。

**从这里开始：** [phistory.cc](https://phistory.cc/)

> 每小时自动检查新版本，归档最近更新于 **2026-09-11 11:45 UTC**。

![Phistory prompt diff viewer](docs/screenshot.png)

## 为什么看它

- 观察 Anthropic、OpenAI 等团队如何持续迭代 system prompt。
- 看到新工具、权限检查、默认模型行为和用户确认规则是什么时候加入的。
- 对比不同 CLI 如何组织 agent 行为、工具调用和面向开发者的约束。
- 在文章、研究笔记、审计或排障记录里引用稳定的提示词快照。

## 工作原理

Phistory 会安装每个受支持的具体 CLI 版本，再通过 [`claude-tap`](https://github.com/WEIFENG2333/claude-tap) 分别运行每个已配置快照，抓取包含系统提示词的 HTTP 请求，不调用真实模型服务，然后把结果保存到 `captures/<agent>/<version>/variants/<variant>/`，里面包含 `prompt.md`、`trace.jsonl` 和 `meta.json`。抓取配置以 `default` 快照为基线，显式选择的模型或模式会作为额外变体保存。

对于最近的 Claude Code 版本，Phistory 还会从安装包里提取疑似静态 prompt 的字符串，保存在 `captures/<agent>/<version>/static/`。候选文件保留过滤资源代码后的原文，改进过滤或匹配规则时可以直接重放，无需重新安装历史包。详见 [Static 提取与整理](docs/static-prompts.md)。

GitHub Actions 每小时检查一次已自动追踪的 CLI 版本；发现新版本后，会自动抓取并提交新的提示词快照。

网页支持运行时提示词 diff 和 Trace 可读字段的中文切换。未变段落在历史版本间复用译文，原始证据保持不变；缺少译文时显示原文。配置和存储方式见[翻译说明](docs/translations.md)，实际样本与提示词迭代见[翻译评测](docs/translation-evaluation.md)。

## 本地开发

日常查看直接使用托管网页：[phistory.cc](https://phistory.cc/)。下面这些命令主要用于本地开发、复现抓取、回填历史版本，以及重新生成项目里的生成文件。

```bash
# 安装锁定的开发环境。
uv sync --all-groups

# 抓取每个 CLI 的最新版本及其全部已配置快照。
uv run phistory capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp

# 只抓取 Codex 的指定快照。
uv run phistory capture --latest --agents codex --variants default,gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna,gpt-5.5

# 回填某个 agent 的历史版本区间。
uv run phistory backfill claude-code --from 2.1.113 --to latest

# 重建最近 10 个已捕获 Claude Code 版本的静态 prompt 文件。
uv run phistory extract-static claude-code --latest-captured 10

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

## 抓取状态

最近抓取更新：2026-09-11 11:45 UTC

| Agent | 最新版本 | 版本数 | 快照数 | 最近抓取 |
| --- | --- | ---: | ---: | --- |
| Claude Code | [2.1.268 - 2026-09-10](captures/claude-code/2.1.268/variants/default/prompt.md) | 413 | 413 | 2026-09-10 22:44 UTC |
| Codex CLI | [0.154.0 - 2026-09-09](captures/codex/0.154.0/variants/default/prompt.md) | 88 | 125 | 2026-09-09 22:42 UTC |
| DeepSeek Harness | [0.1.5-rc.1 - 2026-09-10](captures/dsh/0.1.5-rc.1/variants/default/prompt.md) | 10 | 51 | 2026-09-10 06:35 UTC |
| Antigravity CLI | [1.2.1 - 2026-09-11](captures/antigravity/1.2.1/variants/default/prompt.md) | 44 | 44 | 2026-09-11 11:44 UTC |
| Grok Build | [1.0.25 - 2026-09-09](captures/grok/1.0.25/variants/default/prompt.md) | 133 | 133 | 2026-09-09 19:59 UTC |
| MiniMax Code | [3.0.71 - 2026-09-11](captures/minimax-code/3.0.71/variants/default/prompt.md) | 35 | 35 | 2026-09-11 11:45 UTC |
| Kimi Code | [0.42.0 - 2026-09-09](captures/kimi-code/0.42.0/variants/default/prompt.md) | 72 | 72 | 2026-09-09 06:35 UTC |
| MiMo Code | [0.1.14 - 2026-09-02](captures/mimo/0.1.14/variants/default/prompt.md) | 14 | 14 | 2026-09-02 11:39 UTC |
| OpenClaw | [2026.9.4 - 2026-09-11](captures/openclaw/2026.9.4/variants/default/prompt.md) | 75 | 75 | 2026-09-11 06:35 UTC |
| Hermes Agent | [v2026.9.7 - 2026-09-07](captures/hermes/v2026.9.7/variants/default/prompt.md) | 30 | 30 | 2026-09-08 00:39 UTC |
| Kimi CLI | [1.50.0 - 2026-09-01](captures/kimi/1.50.0/variants/default/prompt.md) | 22 | 22 | 2026-09-01 17:26 UTC |
| opencode | [1.18.30 - 2026-09-09](captures/opencode/1.18.30/variants/default/prompt.md) | 114 | 114 | 2026-09-09 06:35 UTC |
| Pi | [0.85.1 - 2026-09-05](captures/pi/0.85.1/variants/default/prompt.md) | 45 | 45 | 2026-09-05 13:05 UTC |
| Oh My Pi | [18.1.17 - 2026-09-10](captures/omp/18.1.17/variants/default/prompt.md) | 91 | 91 | 2026-09-10 20:00 UTC |

## 项目趋势

![Phistory star history](https://api.star-history.com/svg?repos=WEIFENG2333/phistory&type=Date)
