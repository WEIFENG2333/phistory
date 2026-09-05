# Chinese translations

Phistory translates archived prompt text after capture. The captured CLI still runs through `claude-tap` without calling its model provider. Translation is an independent API operation; the website only reads static files.

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

# Translate recent snapshots, including their static prompt archive.
uv run phistory translate --latest-captured 2

# Backfill every archived version. Completed segments are reused automatically.
uv run phistory translate --all-captured

# Focus on a subset; omit static prompts for a request-only run.
uv run phistory translate --agents claude-code,codex --no-static

uv run phistory render-index
uv run phistory render-site
```

`--max-batches N` caps batches per agent. The command exits nonzero if selected prose remains untranslated, including after reaching this cap. Running the same command resumes missing work; changing keys or model settings does not discard existing translations. `--dry-run` succeeds while reporting pending work.

## Validation

```bash
# Check source maps, dictionaries, provenance and deployment size without API calls.
uv run python scripts/audit_translations.py

# Require complete coverage after a historical backfill.
uv run python scripts/audit_translations.py --require-complete

# Export representative source/translation pairs, including preserved text.
uv run python scripts/review_translations.py --count 2
```

The audit reads the complete archive and writes its report to `.phistory-cache/translation-audit.json`. It checks source hashes, span bounds, each unique segment's text identity, shared runtime/static translations and changes to existing raw captures. Repeat `--verify-source PATH` to also re-extract selected documents and verify every span against the current extractor. The default reports actual model and prompt-version provenance, allowing historical translations to coexist; `--expected-model` and `--expected-prompt-version` optionally enforce a specific value.

Missing translations are reported and only fail with `--require-complete`; invalid data and a deployment candidate of 1 GB or more always fail. Harness terminology and missing bare `snake_case` identifiers appear as source/translation pairs for manual review, not automatic failures. The audit never changes captures, source maps or dictionaries.

The audit reports stored status counts and samples up to five `preserved` entries per agent and dictionary in `preserved_review`; adjust this with `--preserved-samples N`. Reviewers check whether preserving each sampled source was appropriate. The script checks exact source equality but does not infer whether text is code. `review_translations.py` also includes short preserved entries when sampling representative historical snapshots. Older entries without a status remain valid and appear as `legacy` in reports; no status is inferred or written back.

## Data model

```text
translations/
  sources/<original-sha256>-v<extractor-version>.json
  zh-CN/<agent>/runtime.json
  zh-CN/<agent>/static.json
```

Source indexes contain original-file hashes and non-overlapping spans, not full copies of the original or translated documents. Identical source files share an index. Each segment ID hashes the original prose and extraction policy version; surrounding context does not change that identity. Dictionaries store one text per segment with model and translation-prompt provenance. New entries also record `status: "translated"` or `status: "preserved"`; historical entries without this optional field remain usable. An optional `review: "edited-against-source"` marks editorial corrections checked against the original; these retain their original API provenance. All versions of an agent reuse these dictionaries; runtime and static content are loaded separately. Context supplies the nearest heading, tool name or neighboring prose only for the first translation of a segment.

Markdown offsets count Unicode code points. Trace fields use an original request record number and JSON Pointer, followed by offsets inside that field's text. JSON string spans preserve JSON escaping when substituted. Original files remain the authority and are never edited by translation.

Only human-readable prose is translated, including headings, tool descriptions and JSON Schema descriptions. Code blocks (including code comments), tool/parameter names, format grammars, paths, links and template placeholders retain their original meaning and identity. Fences containing Markdown or plain prose are treated as readable documents; JSON Schema description fields are translated without changing the schema itself. The extractor excludes recognized code blocks before API calls, and the client protects embedded literals with placeholders. Line breaks and blank lines are checked; original indentation and edge whitespace are restored by code. The versioned translation prompt lives in `phistory/translation/prompts.py`. Validate changes against real old/new snapshots and held-out samples before retranslation.

Dictionary writes are atomic and deterministic. Successful results are retained as each batch finishes. The client validates segments independently and gives failed segments up to two correction rounds. Each round sends only failed items with their previous output and a specific validation issue, such as a missing placeholder or changed numeric constraint. The model revises the translation or explicitly chooses to preserve the original; successful siblings are not translated again. Remaining failures are reported while partial successes are saved. HTTP rate limits and temporary network/server errors use separate retries with backoff and `Retry-After`; authentication and permanent request errors stop new work while in-flight successes are saved.

Reviewers can pass source-specific feedback to `TranslationClient.translate(..., feedback={source_id: {"previous": {"text": protected_previous_text, "status": "translated"}, "issue": review_note}})` using the same correction loop. This keeps individual wording fixes out of the global prompt. A model revision accepted after reading the complete original can be saved with `review: "model-revised-against-source"` and its actual model and prompt provenance.

## Viewer

The 原文 / 中文 control stores its preference in the browser; it never adds language parameters to the URL. Both languages use the same compact Monaco diff, with side-by-side panes on desktop and inline changes on mobile. Switching languages preserves the reading position. Original text determines changes and diff statistics; a subtle yellow line marker identifies original changes whose Chinese translations are identical. Missing, outdated or invalid translations fall back to source text. A changed pair with incomplete translation uses original text on both sides.

Static archives use Monaco's legacy diff algorithm with a 20-second computation budget, which performed better on the large historical files in browser checks. Ordinary prompt diffs keep the advanced algorithm. Very large comparisons can still reach the time budget and produce coarser changes; the complete text remains available in either language.

Trace translates readable fields on a copy. Raw request bodies and raw tool definitions remain original. Translation assets are fetched only when needed and cached using content fingerprints.

## CI

Configure repository Secret `PHISTORY_TRANSLATION_API_KEY` and Variables `PHISTORY_TRANSLATION_BASE_URL`, `PHISTORY_TRANSLATION_MODEL`. The hourly capture workflow supplies them only to its translation step, after capture and static extraction. It fills the latest ten archived versions per agent, regenerates indexes and commits translation data with the capture artifacts. Translation failure does not prevent publishing successful captures; the workflow reports incomplete work for a later retry. Repositories without a key continue publishing original text.
