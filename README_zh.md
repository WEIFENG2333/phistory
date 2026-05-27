# Phistory

[English](README.md)

Phistory 自动归档 Claude Code、Codex、OpenClaw、Hermes、Kimi、opencode、Pi 等 Agent CLI 的版本化系统提示词快照。

它会安装指定的 CLI 版本，通过 [`claude-tap`](https://github.com/WEIFENG2333/claude-tap) 运行一次，抓取包含系统提示词的 HTTP 请求，并写成方便阅读和对比的 Markdown 快照。

GitHub Actions 每小时检查一次支持的 CLI 版本；发现新版本后，会自动抓取并提交新的提示词快照。

[打开提示词 diff 查看器](https://phistory.cc/)

![Phistory prompt diff viewer](docs/screenshot.png)

## 使用

```bash
uv run phistory capture --latest --agents claude-code,codex,openclaw,hermes,kimi,opencode,pi
uv run phistory backfill claude-code --from 2.1.113 --to latest
uv run phistory render-index
uv run phistory render-site
```

## Web UI

`index.html` 是一个静态提示词查看器，支持版本切换和基于 Monaco 的 diff。GitHub Pages 会直接从这个仓库部署它。

人工对比时使用网页查看器；如果需要完整快照索引，可以读取 [`captures/index.json`](captures/index.json) 或 [`docs/captures.md`](docs/captures.md)。

## 支持的 Agent

- Claude Code (`@anthropic-ai/claude-code`)
- Codex CLI (`@openai/codex`)
- OpenClaw (`openclaw`)
- Hermes Agent (`hermes-agent`)
- Kimi CLI (`MoonshotAI/kimi-cli`)
- opencode (`opencode-ai`)
- Pi (`@earendil-works/pi-coding-agent`)

## 抓取格式

每次抓取会存到 `captures/<agent>/<version>/`：

- `prompt.md`：标准化后的提示词快照，用于阅读和 diff
- `trace.jsonl`：原始 HTTP 抓取记录，保持未标准化，作为证据留存
- `meta.json`：包名、版本、执行命令和抓取元数据

生成的索引包括：

- [`captures/index.json`](captures/index.json)：紧凑的机器可读快照索引
- [`docs/captures.md`](docs/captures.md)：完整的人类可读快照表

## 给 AI Agent

- 用 `README.md` 或 `README_zh.md` 了解项目概览和当前抓取状态。
- 用 `captures/index.json` 发现可用的 agent、版本、prompt 路径和 trace 路径。
- 需要标准化提示词快照时，读取 `captures/<agent>/<version>/prompt.md`。
- 只有需要原始 HTTP 抓取证据时，才读取 `captures/<agent>/<version>/trace.jsonl`。
- `index.html` 是面向人的网页查看器，不是 canonical 的机器可读索引。

## 链接

- [linux.do](https://linux.do)

## 抓取状态

最近抓取更新：2026-05-27 22:09 UTC

| Agent | 最新版本 | 快照数 | 最近抓取 |
| --- | --- | ---: | --- |
| Claude Code | [2.1.152 - 2026-05-26](captures/claude-code/2.1.152/prompt.md) | 321 | 2026-05-27 02:52 UTC |
| Codex CLI | [0.134.0 - 2026-05-26](captures/codex/0.134.0/prompt.md) | 49 | 2026-05-26 22:00 UTC |
| Hermes Agent | [v2026.5.16 - 2026-05-16](captures/hermes/v2026.5.16/prompt.md) | 11 | 2026-05-22 12:31 UTC |
| Kimi CLI | [1.45.0 - 2026-05-27](captures/kimi/1.45.0/prompt.md) | 17 | 2026-05-27 04:49 UTC |
| OpenClaw | [2026.5.26 - 2026-05-27](captures/openclaw/2026.5.26/prompt.md) | 58 | 2026-05-27 16:52 UTC |
| opencode | [1.15.11 - 2026-05-27](captures/opencode/1.15.11/prompt.md) | 62 | 2026-05-27 04:49 UTC |
| Pi | [0.76.0 - 2026-05-27](captures/pi/0.76.0/prompt.md) | 10 | 2026-05-27 22:09 UTC |
