# Capture validation — 2026-11-11

The archive stopped updating because both scheduled capture and Pages failed during
`uv sync`: the runner selected Python 3.14, but locked `backports-zstd==1.5.0`
rejects Python 3.14. Runs 42797778227 and 42797830124 failed before capture/build.
The project now selects Python 3.13 through `.python-version`; a clean frozen
installation with all dependency groups passed locally.

Additional repairs:

- Isolate the session bus and XDG runtime directory during capture. Antigravity
  otherwise prefers the host keyring over the synthetic credentials in its
  temporary HOME, prompting for login instead of emitting a request.
- Recognize MiniMax Code's `local-runtime-v2` during installation and select its
  bundled agent/skill assets, matching the launcher's existing v2 support.
- Sort archive releases by publication time, then version. Hermes changed from
  date-based tags to semantic tags; numerical sorting incorrectly kept an old
  date-based tag at the top.

## Latest release checks

All variants listed below were actually launched locally through claude-tap in
capture-only mode. Existing captures were retained when already current. The
MiMo binary download needed the local network proxy; MiniMax's official archive
was checked against its published SHA-512 before installation.

| Agent | Queried target | Local result |
| --- | --- | --- |
| Claude Code | 2.1.322 | Terminal and Headless passed |
| Codex | 0.167.0 | Default, GPT-5.5 and GPT-5.6 passed |
| DSH | 0.2.2-rc.1 | All six variants passed |
| Antigravity | 1.5.4 | Passed after runtime isolation |
| Grok | 1.0.77 | Passed |
| MiniMax Code | 3.1.14 | Passed after runtime-v2 installation fix |
| Kimi Code | 2.5.3 | Passed |
| MiMo | 0.1.16 | Fresh capture passed; prompt matched archive |
| OpenClaw | 2026.11.2 | Passed |
| Hermes | v0.23.1 | Upstream dependency resolution failed |
| Kimi CLI | 1.51.0 | Last supported version; fresh capture passed |
| OpenCode | 1.19.5 | Passed |
| Pi | 1.5.2 | Passed |
| Oh My Pi | 18.18.6 | Passed |

Hermes v0.23.1 requires `pillow==13.0.0`, while its required
`browser-harness==0.1.13` requires `pillow==12.3.0`. A fresh install cannot satisfy
both. No dependency override or false latest snapshot was introduced; the archive
retains its latest successful Hermes release. Capture CI should continue reporting
this failure until upstream resolves it, while publishing successful captures.

Kimi's upstream latest remains 1.52.0. Its official release notes say the CLI entry
points were replaced with a Kimi Code installer (MoonshotAI/kimi-cli PR #2666).
The existing last-supported pin remains at 1.51.0 because 1.52.0 no longer exposes
that capture surface. Claude Tag and Grokbot are manually supplied sources and
cannot be refreshed without a new user-provided export.

The initial read-only audit parsed 1,902 existing snapshots without errors and
reproduced every checked prompt from its saved trace. A fresh Kimi capture differed
only in its Python installation path (3.12 versus 3.13); its historical raw trace
was not rewritten.
