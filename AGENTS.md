# Phistory Agent Guide

Phistory archives versioned system prompt snapshots from agent CLIs. It installs a specific CLI release, runs it once through `claude-tap`, captures the prompt-bearing HTTP request, and stores normalized Markdown plus raw trace evidence under `captures/`.

This file is for future coding agents. Read it before changing the project.

## Project Shape

- `phistory/registry.py`: supported agent definitions. Add or adjust CLI support here first.
- `phistory/models.py`: shared dataclasses and type literals for package sources, tap modes, and capture results.
- `phistory/packages.py`: version discovery and installation for public package and release sources.
- `phistory/capture.py`: installs an agent, creates an isolated HOME, runs a capture driver, copies `trace.jsonl`, renders `prompt.md`, and writes `meta.json`.
- `phistory/prompt.py`: the archive's own prompt surface. Selects the prompt-bearing request in a trace, normalizes Anthropic/OpenAI/Gemini shapes into system blocks, messages and tools, and renders the Markdown.
- `phistory/sanitize.py`: pattern-driven normalization of capture-run noise, shared by capture and re-render.
- `phistory/drivers/`: one runner per capture surface. `oneshot` runs a headless command, `pty` types into a real terminal, `dsh-web` drives a web RPC. A driver's only job is to produce a trace.
- `phistory/workflow.py`: orchestration for latest captures and backfills.
- `phistory/storage.py`: capture directory preparation, cleanup, trace copying, and metadata writing.
- `phistory/render.py`: regenerates `README.md`, capture indexes, and the agent-facing `llms.txt` from capture metadata.
- `phistory/build.py`: assembles public archives, dictionaries and generated translation assets into the disposable site directory.
- `phistory/site.py`: renders the single-file static web UI for the site build.
- `phistory/cli.py`: CLI entrypoint for `capture`, `backfill`, `rerender`, `translate`, `render-index`, and `build-site`.
- `tests/`: focused unit and local integration tests for package sources, registry contracts, capture behavior, and rendering.
- `.github/workflows/capture.yml`: hourly capture workflow. It runs lint, tests, build, real latest capture, renders artifacts, and commits updates. Manual runs also perform a fresh latest smoke capture for all agents.
- `.github/workflows/pages.yml`: builds the static site from archived data and deploys only the build output to GitHub Pages.

Generated capture artifacts live in:

```text
captures/<agent>/<version>/variants/<variant>/prompt.md
captures/<agent>/<version>/variants/<variant>/trace.jsonl
captures/<agent>/<version>/variants/<variant>/meta.json
```

`trace.jsonl` is raw evidence and is never rewritten. `prompt.md` is derived from it: `uv run phistory rerender` rebuilds every archived Markdown file from stored traces without reinstalling anything, so improvements to rendering or normalization reach the whole archive in one pass. Treat `prompt.md` as reproducible output, not as a second source of truth.

Manually supplied traces are the explicit exception when private runtime data must be removed before publication. Preserve the source outside the repository, record its SHA-256 and the redaction categories in `meta.json`, and set `trace_redacted` to `true`. Remove embedded private memory payloads as well as credentials, identifiers, user messages, and local paths. The site and generated indexes label these traces as redacted; do not describe them as byte-for-byte raw evidence.
For Claude Tag, use the shared importer and review steps in `docs/manual-traces.md` for every version.

`prompt.md` must not drop prompt material. Each system block keeps its own section and cache boundary, reminder blocks stay separate from what the user typed, and system messages interleaved with the conversation are archived as part of the system surface. Tool containers flatten to the names a model can actually call.

`llms.txt` is the concise machine-readable entry point for the hosted archive. Keep it generated from the same capture rows as `captures/index.json`; do not hand-maintain snapshot links or duplicate the full archive into `llms-full.txt`.


`candidates.json` and `prompts.json` are repository-only: they exist to replay extraction filters offline, the viewer reads only `prompts.md`, and publishing them costs more than half of the GitHub Pages size budget. Anything added to the published set has to earn its bytes — `scripts/audit_translations.py` fails the build when the deploy artifact exceeds the limit.

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
5. Dispatch the variant's capture driver. Most variants launch `python -m claude_tap run <tap_client> -- <agent command>`; interactive surfaces use a focused driver such as `pty` or `dsh-web`. `--export-prompt` stays on the claude-tap command line because it is what selects capture-only mode; its output is discarded.
6. Copy the raw `trace.jsonl`, render `prompt.md` from it, and write `meta.json`.
7. Remove temporary tap output unless `--keep-tap` is used.

Do not call model providers during capture. The capture boundary is `claude-tap`. The separate `translate` command may call the configured translation provider to translate already archived text.

## Chinese Translations

- `phistory/translation/` extracts source spans, calls the translation provider, and maintains shared Chinese dictionaries.
- `translations/zh-CN/<agent>/runtime.json` is shared across all versions and both runtime views. These dictionaries are the only translation data committed to Git. Do not generate a complete translated prompt for every version.
- `build-site` generates content-addressed source indexes with offsets into all archived runtime Prompt and Trace files under the output directory's `translations/sources/`. Indexes and the generated `index.html` are disposable build artifacts; never commit them. Building does not call a provider or require translation credentials.
- Raw capture files remain unchanged. Translate human prose, including tool and schema descriptions; preserve technical identifiers, code, paths and placeholders.
- Translation credentials belong in `~/.config/phistory/translation.toml` or translation-step-only environment variables. Never commit keys or pass them to captured CLIs.
- Language is a browser preference, not a URL parameter. Original text determines diff changes. Missing, stale or invalid translation data falls back to original text.
- `uv run phistory translate --all-captured --dry-run` reports missing work without API calls. Normal translation resumes automatically from dictionaries; successful batches are saved atomically.
- CI retains `translation-usage` and `translation-dictionaries` artifacts for 30 days before rendering and publishing. If publishing fails after translation, recover missing dictionary entries from that run before retrying paid requests; retain current entries on matching source IDs.
- Test real translation prompt changes on representative old/new archive samples before backfilling. Keep evaluation evidence in `docs/translation-evaluation.md`; store verbose trial outputs only under the ignored cache directory.


## Supported Agents

Current agents are defined in `phistory/registry.py`:

- `claude-code`: npm package `@anthropic-ai/claude-code`, tap client `claude`. `default` drives the interactive terminal through the `pty` driver; `sdk` archives the `-p` headless surface. The two differ in identity line, entrypoint header and tool set, so both are kept.
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

The DSH Web driver exchanges the printed local launch URL for a session cookie when authentication is required. It supports Remote RPC and legacy RPC by endpoint discovery. The PTC archive variant remains `code`; current releases call its preset `ptc`, and older releases can use the archive variant ID when the server reports it as available. Driver-observed preset IDs are saved in `meta.json` alongside model and tool observations.

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
- Keep raw traces raw. Normalize only `prompt.md`, through `phistory/sanitize.py`, using patterns rather than one run's directories so re-rendering is reproducible.
- A capture must never reach a real model provider. `claude-tap` serves dummy responses only in capture-only mode; a trace containing upstream status codes means the capture escaped that mode and is invalid.
- Keep generated files deterministic enough for CI and GitHub Pages. After changing capture, render, registry, or package logic, run `render-index` and `build-site`.
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
uv run phistory build-site --output .phistory-cache/site
uv run python scripts/audit_translations.py --site-dir .phistory-cache/site
```

For local preview, serve the same build output that Pages deploys:

```bash
python -m http.server --directory .phistory-cache/site
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

The site is a single generated `index.html` using manifest data embedded by `phistory/site.py`. `build-site` assembles this HTML, public archive assets, shared dictionaries and regenerated source indexes into an ignored output directory. GitHub Pages serves that directory directly. `captures/index.json` remains the archive metadata; translation availability is joined into the page manifest only during the build.

When modifying UI:

- Keep the diff view as the primary experience.
- Preserve mobile usability.
- Do not add frameworks or build steps unless there is a strong reason.
- Rebuild and preview with `uv run phistory build-site --output .phistory-cache/site`; do not serve the repository root.
- Keep SEO metadata aligned with the project description in `README.md`.

## Git Hygiene

- The repository may contain many generated capture files. Do not delete or rewrite existing captures unless the task explicitly requires it.
- Ignore unrelated dirty files if present; do not revert user work.
- Commit generated `README.md`, `README_zh.md`, `llms.txt`, `captures/`, and shared dictionary changes together when they are part of the same capture/update. Keep site HTML and source indexes out of Git.
- Prefer small, focused commits. For large backfills, one generated-data commit is acceptable after validation.
