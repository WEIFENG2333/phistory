# Phistory Agent Guide

Phistory archives versioned system prompt snapshots from agent CLIs. It installs a specific CLI release, runs it once through `claude-tap`, captures the prompt-bearing HTTP request, and stores normalized Markdown plus raw trace evidence under `captures/`.

This file is for future coding agents. Read it before changing the project.

## Project Shape

- `phistory/registry.py`: supported agent definitions. Add or adjust CLI support here first.
- `phistory/models.py`: shared dataclasses and type literals for package sources, tap modes, and capture results.
- `phistory/packages.py`: version discovery and installation for public package and release sources.
- `phistory/capture.py`: installs an agent, creates an isolated HOME, runs `claude-tap`, exports `prompt.md`, copies `trace.jsonl`, writes `meta.json`, and normalizes volatile text in prompt Markdown only.
- `phistory/workflow.py`: orchestration for latest captures and backfills.
- `phistory/storage.py`: capture directory preparation, cleanup, trace copying, and metadata writing.
- `phistory/render.py`: regenerates `README.md` from capture metadata.
- `phistory/site.py`: regenerates the single-file static web UI in `index.html`.
- `phistory/static_prompts/`: static prompt extraction for package-embedded prompt strings. It currently targets Claude Code and is structured so other agents can be added later.
- `phistory/cli.py`: CLI entrypoint for `capture`, `backfill`, `extract-static`, `render-index`, and `render-site`.
- `tests/`: focused unit and local integration tests for package sources, registry contracts, capture behavior, and rendering.
- `.github/workflows/capture.yml`: hourly capture workflow. It runs lint, tests, build, latest smoke capture for all agents, real latest capture, Claude Code static prompt extraction for the latest captured versions, renders artifacts, and commits updates.
- `.github/workflows/pages.yml`: GitHub Pages deployment for the static site.

Generated capture artifacts live in:

```text
captures/<agent>/<version>/variants/<variant>/prompt.md
captures/<agent>/<version>/variants/<variant>/trace.jsonl
captures/<agent>/<version>/variants/<variant>/meta.json
```

`prompt.md` is normalized for human reading and diffs. `trace.jsonl` is raw evidence and should not be rewritten for presentation-only cleanup.

Claude Code captures may also include:

```text
captures/claude-code/<version>/static/candidates.json
captures/claude-code/<version>/static/prompts.json
captures/claude-code/<version>/static/prompts.md
```

`static/candidates.json` is the archived raw candidate set after broad resource filtering. Keep it deterministic and useful for future rematching. `static/prompts.*` is the matched/readable output derived from those candidates and the local catalog in `phistory/static_prompts/catalogs/`.

## Capture Principle

Phistory does not call the real model provider when exporting prompts. It relies on `claude-tap --export-prompt`, which captures the request body and returns a protocol-specific dummy response.

Typical latest capture:

```bash
uv run phistory capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp
```

For each agent/version/variant, the flow is:

1. Discover versions through `phistory.packages`.
2. Install the exact release into `.phistory-cache/installs/<agent>/<version>/`.
3. Create a temporary isolated HOME and XDG directories.
4. Write only the minimal fake auth/config needed for the CLI to emit a prompt-bearing request.
5. Dispatch the variant's capture driver. Most variants launch `python -m claude_tap run <tap_client> --export-prompt ... -- <agent command>`; interactive surfaces can use a focused driver such as `dsh-web`.
6. Save `prompt.md`, raw `trace.jsonl`, and `meta.json`.
7. For Claude Code, also extract package-embedded static prompt candidates and matched static prompts.
8. Remove temporary tap output unless `--keep-tap` is used.

Do not add direct model API calls to Phistory. The capture boundary is `claude-tap`.

Static prompt extraction is separate from request capture. It parses installed package code, keeps plausible prompt-like string/template candidates, matches known catalog entries by hash or anchor, and writes deterministic Markdown/JSON. Prefer improving general filters and catalog anchors over adding version-specific special cases.

## Supported Agents

Current agents are defined in `phistory/registry.py`:

- `claude-code`: npm package `@anthropic-ai/claude-code`, tap client `claude`.
- `codex`: npm package `@openai/codex`, tap client `codex`, fake ChatGPT auth enabled; archives the real default plus pinned GPT-5.6 Sol, GPT-5.6 Terra, GPT-5.6 Luna, and GPT-5.5 variants. The retired `gpt-5.6` alias capture remains archived but is hidden from the site because the CLI treated it as unknown local model metadata.
  Fixed-model lanes begin at the first Codex CLI release whose bundled model catalog includes that model: 0.125.0 for GPT-5.5 and 0.144.0 for the GPT-5.6 family.
- `dsh`: npm package `@deepseek-ai/dsh`, tap client `dsh`, isolated DSH home and forward capture mode; uses a Web RPC driver for default, Standard, PTC, Minimal, and Creator snapshots, plus the headless snapshot.
- `antigravity`: GitHub release asset source `google-antigravity/antigravity-cli`, tap client `agy`, isolated Antigravity config and forward capture mode.
- `grok`: npm package `@xai-official/grok`, tap client `grok`, isolated Grok home and fake xAI API key.
- `minimax-code`: official MiniMax Code desktop updater source, tap client `minimax-code`; Phistory extracts the bundled Mavis runtime, installs matching Linux native dependencies (plus the pinned OpenCode engine for legacy releases), and launches it headlessly through an isolated provider.
- `kimi-code`: npm package `@moonshot-ai/kimi-code`, tap client `kimi-code`, executable `kimi`, isolated Kimi Code config.
- `mimo`: npm package `@mimo-ai/cli`, tap client `mimo`, reverse tap mode with OpenAI-compatible provider config.
- `openclaw`: npm package `openclaw`, tap client `openclaw`, Node 24 wrapper, isolated OpenClaw config.
- `hermes`: GitHub release source `NousResearch/hermes-agent`, tap client `hermes`, OpenRouter provider path.
- `kimi`: GitHub release source `MoonshotAI/kimi-cli`, tap client `kimi`, isolated Kimi TOML config.
- `opencode`: npm package `opencode-ai`, tap client `opencode`, reverse tap mode so opencode can fetch its model registry while the model request is redirected locally.
- `pi`: npm package `@earendil-works/pi-coding-agent`, tap client `pi`, isolated Pi provider config.
- `omp`: npm package `@oh-my-pi/pi-coding-agent` for version discovery, official `can1357/oh-my-pi` release binary for installation, tap client `omp`, isolated Oh My Pi provider config.

When adding another CLI, prefer extending the existing abstractions:

- Add a `PackageSource` only if `npm`, `pypi`, or `github-release` cannot model the release channel.
- Add a `HomeProfile` only when the CLI needs isolated config files. Keep config minimal and deterministic.
- Add a `TapMode` only when the existing `auto`, `reverse`, or `forward` modes are insufficient.
- Keep each `CaptureVariant.run_args` as the normal user-facing CLI command that makes the tool send one prompt-bearing request.
- Every agent must keep a real `default` variant with no explicit model or mode override. Add named variants only for stable, meaningful prompt surfaces.

## Design Rules

- Do not patch around broken historical releases with bespoke compatibility hacks. If a package cannot install or start far enough to emit a request, let that version fail and move on.
- Do not add one-off version maps unless there is a stable upstream rule behind them.
- Prefer official release metadata: npm registry for npm packages, PyPI JSON for Python packages, GitHub Releases for release-tagged projects.
- Keep raw traces raw. Normalize only `prompt.md` via the sanitizer in `capture.py`.
- Keep generated files deterministic enough for CI and GitHub Pages. After changing capture, render, registry, or package logic, run both render commands.
- Avoid “insert-only” changes. If a new agent exposes a weakness in the architecture, refactor the shared abstraction cleanly instead of stacking special cases.
- Keep the CLI boring and scriptable. The GitHub Action depends on predictable exit codes and printed result lines.
- Keep comments sparse and useful. Prefer clear names and small helpers over explanatory comments.

## Validation

Before committing code changes, run:

```bash
uv run ruff format --check phistory tests
uv run ruff check phistory tests
uv run pytest
```

For capture-affecting changes, also run a local latest smoke:

```bash
uv run phistory --root /tmp/phistory-smoke --cache-dir /tmp/phistory-smoke-cache capture --latest --agents claude-code,codex,dsh,antigravity,grok,minimax-code,kimi-code,mimo,openclaw,hermes,kimi,opencode,pi,omp --force
```

For generated artifacts:

```bash
uv run phistory render-index
uv run phistory render-site
```

For Claude Code static prompt artifacts:

```bash
uv run phistory extract-static claude-code --latest-captured 10
```

Use `--refresh-candidates` only when the extractor/filtering logic changed and the raw candidate archives should be regenerated from installed packages.

For a targeted historical check:

```bash
uv run phistory backfill <agent> --from <version> --to <version> --force
```

If you push changes that affect CI capture, verify the `Capture prompts` workflow and the Pages deployment with `gh run list` / `gh run watch`.

## Known Failure Semantics

Backfill can legitimately fail for some historical versions. Examples seen in this project:

- Package installs but exposes no CLI binary.
- The CLI crashes before making a model request because upstream package dependencies are missing.
- The CLI starts plugin/runtime setup but never emits a request before Phistory's timeout.
- The CLI's historical provider model does not support an interceptable local base URL.

These should remain normal failed captures, not Phistory compatibility branches, unless there is a general fix that also improves future captures.

## Web UI Notes

The site is a single generated `index.html` using manifest data embedded by `phistory/site.py`. It is intentionally static so GitHub Pages can serve it directly.

When modifying UI:

- Keep the diff view as the primary experience.
- Preserve mobile usability.
- Do not add frameworks or build steps unless there is a strong reason.
- Regenerate `index.html` with `uv run phistory render-site`.
- Keep SEO metadata aligned with the project description in `README.md`.

## Git Hygiene

- The repository may contain many generated capture files. Do not delete or rewrite existing captures unless the task explicitly requires it.
- Ignore unrelated dirty files if present; do not revert user work.
- Commit generated `README.md`, `index.html`, and `captures/` changes together when they are part of the same capture/update.
- Prefer small, focused commits. For large backfills, one generated-data commit is acceptable after validation.
