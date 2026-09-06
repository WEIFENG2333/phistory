# Chinese translations

Phistory translates archived runtime Prompt and Trace prose after capture. Package-embedded Static archives stay in their original language and are excluded from translation. The captured CLI still runs through `claude-tap` without calling its model provider. Translation is an independent API operation; the website only reads static files. Git stores the original archives and shared translation dictionaries. Site HTML and source indexes are rebuilt for publication and are not committed.

## Configuration

Keep local credentials outside the repository in `~/.config/phistory/translation.toml` (or under `$XDG_CONFIG_HOME/phistory/`). Set file permissions to `600`.

```toml
[translation]
base_url = "https://api.siliconflow.cn/v1"
model = "zai-org/GLM-5.3"
api_key = "YOUR_KEY"
concurrency = 6
batch_chars = 6000
timeout = 180
attempts = 5
enable_thinking = true
thinking_budget = 4096
```

`PHISTORY_TRANSLATION_API_KEY`, `PHISTORY_TRANSLATION_BASE_URL`, and `PHISTORY_TRANSLATION_MODEL` override the file. `--config`, `--model`, and `--concurrency` support one-off runs. API keys are excluded from child-process environments, generated artifacts, and error messages.

The client uses Chat Completions with strict JSON Schema output and a bounded thinking budget. Each requested segment ID returns `{text, status}`, where `status` is `translated` or `preserved`; extra keys are forbidden. The model chooses whether a segment contains prose to translate or text that should remain unchanged. Local validation checks completeness, literals and layout, and requires preserved text to match the source exactly. GLM-5.3 with a 4096-token thinking budget is the evaluated default; both thinking settings are configurable. Provider support is verified with real requests; see [the model evaluation](translation-evaluation.md). Models and response formats are never silently substituted after failure.

## Commands

```bash
# Inspect the complete archive without API calls or writes.
uv run phistory translate --all-captured --dry-run

# Translate runtime Prompt and Trace prose from recent snapshots.
uv run phistory translate --latest-captured 2

# Backfill every archived version. Completed segments are reused automatically.
uv run phistory translate --all-captured

# Focus on a subset of agents.
uv run phistory translate --agents claude-code,codex

uv run phistory render-index
uv run phistory build-site --output .phistory-cache/site

# Preview exactly the directory that Pages deploys.
python -m http.server --directory .phistory-cache/site
```

`--max-batches N` caps batches per agent. The command exits nonzero if selected prose remains untranslated, including after reaching this cap. Running the same command resumes missing work; changing keys or model settings does not discard existing translations. `--dry-run` succeeds while reporting pending work.

Each actual translation request appends usage to `.phistory-cache/translation-usage.jsonl`; `--usage-log PATH` overrides the location. Records include the agent, source IDs, requested thinking budget, request/response IDs, HTTP status, elapsed time, correction round and provider token accounting. They omit credentials and text. Failed requests without provider usage remain unknown, and rejected model output still counts as a paid response. CLI progress also reports request counts and cumulative input/output tokens.

Summarize one or more logs with `uv run python scripts/summarize_translation_usage.py PATH`. Optional `--model`, `--input-price`, `--cached-input-price` and `--output-price` select a model and CNY prices per million tokens. Response IDs are deduplicated; reasoning and cached tokens are subsets of output and input, respectively. See [the cost audit](translation-cost.md) for real sampling, historical estimates and completed-backfill accounting.

## Validation

```bash
# Build every historical source index without API calls or translation credentials.
uv run phistory build-site --output .phistory-cache/site

# Check the built source maps, dictionaries, provenance and deployment size.
uv run python scripts/audit_translations.py --site-dir .phistory-cache/site

# Require complete coverage after a historical backfill.
uv run python scripts/audit_translations.py --site-dir .phistory-cache/site --require-complete

# Export representative source/translation pairs, including preserved text.
uv run python scripts/review_translations.py --count 2
```

The audit reads original runtime Prompt and Trace files and shared dictionaries from the repository, then checks the generated indexes and published copies in the site output. Build the site first: `--site-dir` defaults to `.phistory-cache/site`, and a missing build is an error. The report is written to `.phistory-cache/translation-audit.json`. It checks source hashes, span bounds, each unique segment's text identity, translation coverage and changes to existing raw captures. Repeat `--verify-source PATH` to also re-extract selected runtime documents and verify every span against the current extractor. The default reports actual model and prompt-version provenance, allowing historical translations to coexist; `--expected-model` and `--expected-prompt-version` optionally enforce a specific value.

Missing translations are reported and only fail with `--require-complete`; invalid data and a deployment candidate of 1 GB or more always fail. Harness terminology and missing bare `snake_case` identifiers appear as source/translation pairs for manual review, not automatic failures. The audit never changes captures, source maps or dictionaries.

The audit reports stored status counts and samples up to five `preserved` entries per agent in `preserved_review`; adjust this with `--preserved-samples N`. Reviewers check whether preserving each sampled source was appropriate. The script checks exact source equality but does not infer whether text is code. `review_translations.py` also includes short preserved entries when sampling representative historical runtime snapshots. Older entries without a status remain valid and appear as `legacy` in reports; no status is inferred or written back. Historical Static evaluation fixtures remain as evidence for old reports; `evaluate_translation.py` skips them by default and rejects explicitly selecting them.

## Data model

```text
# Version-controlled data
captures/<agent>/<version>/variants/<variant>/
  prompt.md
  trace.jsonl
translations/
  zh-CN/<agent>/runtime.json

# Disposable build output, ignored by Git
.phistory-cache/site/
  index.html
  captures/...
  translations/
    sources/<original-sha256>-v<extractor-version>.json
    zh-CN/<agent>/runtime.json
```

`translate` extracts prose and persists only dictionary entries. `build-site` independently regenerates indexes from all archived versions, copies the public archive assets and dictionaries into the output directory, and joins translation availability into the page manifest. `captures/index.json` remains archive metadata. Neither generated HTML nor source indexes belong in Git. Building requires no API key and makes no translation requests; it never changes archived source files or shared dictionaries. Deleting the output directory is safe because the next build recreates it without paying for translation again.

`build-site` replaces the former `render-site` CLI command. Its output defaults to `<cache-dir>/site`; `--output` can select an empty directory or a previous Phistory build. A failed build leaves the previous preview intact. Rebuilding removes obsolete generated assets from the output.

Source indexes contain original-file hashes and non-overlapping spans, not full copies of the original or translated documents. Identical source files share an index. Each segment ID hashes the prose and `SEGMENT_VERSION`; the source index's `EXTRACTOR_VERSION` can change without invalidating existing translations. Surrounding context does not change that identity. Dictionaries store one text per segment with model and translation-prompt provenance. New entries also record `status: "translated"` or `status: "preserved"`; historical entries without this optional field remain usable. An optional `review: "edited-against-source"` marks editorial corrections checked against the original; these retain their original API provenance. All versions of an agent reuse one runtime dictionary for Prompt and Trace. Context supplies the nearest heading, tool name, neighboring prose and schema property/type structure for the first translation of a segment. Union types retain their alternatives instead of borrowing only the last branch; context changes do not invalidate cached text identities.

Markdown offsets count Unicode code points. Trace fields use an original request record number and JSON Pointer, followed by offsets inside that field's text. JSON string spans preserve JSON escaping when substituted. Original files remain the authority and are never edited by translation.

Trace prose can reuse a normalized Prompt paragraph through optional `bindings`, for example `{"$PHISTORY_WORKSPACE": {"value": "/tmp/phistory-work-example", "count": 1}}`. The existing capture sanitizer supplies the template; reuse is allowed only if binding its placeholders reconstructs the complete original span exactly. Conflicting values, presentation changes and ambiguous placeholders retain their original identities. The browser validates placeholder counts, restores each value once, then applies JSON escaping. Missing or damaged templates fall back to original text. Arbitrary identifiers, tool names and numeric requirements are not normalized for cache reuse.

Only human-readable prose is translated, including headings, tool descriptions and JSON Schema descriptions. Code blocks (including code comments), tool/parameter names, format grammars, paths, links and template placeholders retain their original meaning and identity. Fences containing Markdown or plain prose are treated as readable documents; JSON Schema description fields are translated without changing the schema itself. The extractor excludes recognized code blocks before API calls, and the client protects embedded literals with placeholders. Line breaks and blank lines are checked; original indentation and edge whitespace are restored by code. The versioned translation prompt lives in `phistory/translation/prompts.py`. Validate changes against real old/new snapshots and held-out samples before retranslation.

Static archives contain package-embedded prompts, skills and other candidate documents beyond the runtime system prompt. They remain available in the original Static browser and diff, with no translation dictionary or source index. Runtime dry-run counts do not include them. See [the volume audit](translation-volume.md) for the measured causes of the earlier queue size.

Dictionary writes are atomic and deterministic. Successful results are retained as each batch finishes. The client validates segments independently and gives failed segments up to two correction rounds. Each round sends only failed items with their previous output and a specific validation issue, such as a missing placeholder or changed numeric constraint. The model revises the translation or explicitly chooses to preserve the original; successful siblings are not translated again. Remaining failures are reported while partial successes are saved. HTTP rate limits and temporary network/server errors use separate retries with backoff and `Retry-After`; authentication and permanent request errors stop new work while in-flight successes are saved.

Reviewers can pass source-specific feedback to `TranslationClient.translate(..., feedback={source_id: {"previous": {"text": protected_previous_text, "status": "translated"}, "issue": review_note}})` using the same correction loop. This keeps individual wording fixes out of the global prompt. A model revision accepted after reading the complete original can be saved with `review: "model-revised-against-source"` and its actual model and prompt provenance.

## Viewer

The 原文 / 中文 control appears in runtime Diff and Trace views and stores its preference in the browser; it never adds language parameters to the URL. Both languages use the same compact Monaco diff, with side-by-side panes on desktop and inline changes on mobile. Switching languages preserves the reading position. Original text determines changes and diff statistics; a subtle yellow line marker identifies original changes whose Chinese translations are identical. Missing, outdated or invalid translations fall back to source text. A changed pair with incomplete translation uses original text on both sides.

Static always displays original text, hides the language control and makes no translation asset requests. Opening Static preserves the runtime language preference, so returning to Diff or Trace restores it. Static archives use Monaco's legacy diff algorithm with a 20-second computation budget, which performed better on the large historical files in browser checks. Ordinary prompt diffs keep the advanced algorithm. Very large comparisons can still reach the time budget and produce coarser changes; the complete original text remains available.

Trace translates readable fields on a copy. Raw request bodies and raw tool definitions remain original. Translation assets are fetched only when needed and cached using content fingerprints. On `https://phistory.cc/`, these requests use the same origin: `/captures/.../prompt.md` or `trace.jsonl`, `/translations/sources/<hash>-v2.json`, and `/translations/zh-CN/<agent>/runtime.json`. The `?v=` fingerprint refreshes stale assets; it does not encode a language. The browser does not contact the translation provider.

The source indexes remain useful published assets: they tell the browser which original spans and Trace fields to replace. Precomputing them keeps the Python extractor as the single implementation for translation and display. They are downloaded only for the selected documents, while the agent's dictionary is shared across versions. A typical uncached Chinese Diff needs two original documents, two source indexes and one shared dictionary; a Trace needs one original document, one index and that same dictionary. Moving indexes out of Git does not make the browser download the full historical index set.

## CI

Configure repository Secret `PHISTORY_TRANSLATION_API_KEY` and Variables `PHISTORY_TRANSLATION_BASE_URL`, `PHISTORY_TRANSLATION_MODEL`. The hourly capture workflow supplies them only to its translation step, after capture and static extraction. It translates runtime Prompt and Trace prose from the latest ten archived versions per agent, runs `render-index`, and validates the complete site with `build-site`. It commits original captures, archive metadata, documentation and shared dictionaries under `translations/zh-CN/`; it does not commit site HTML or source indexes. Static extraction remains independent and its output is never sent for translation. Translation failure does not prevent publishing successful captures; the workflow reports incomplete work for a later retry. Repositories without a key continue publishing original text.

The Pages workflow checks out `main` and runs the same `build-site --output .phistory-cache/site` command used for local preview. It builds indexes for all historical versions and uploads only that directory. This build does not use translation credentials or depend on provider availability. Caches, usage logs and development files are not included in the published output.

Before rendering or committing, the workflow saves `translation-usage` and `translation-dictionaries` artifacts for 30 days, including after translation failures. The first contains request accounting; the second contains the shared dictionaries under `translations/zh-CN/`. This preserves paid results if a later render, commit or push fails. Usage logs are not published with the website.

If publishing fails, recover `translation-dictionaries` from that run before retrying translation: merge source IDs missing from the current dictionaries, retaining existing entries when an ID is already present. Then run the translation audit and resume missing work. Source indexes can be regenerated from captures; recovery never requires changing raw capture files. Artifact recovery is explicit, rather than automatically replacing newer dictionaries with an earlier checkpoint.
