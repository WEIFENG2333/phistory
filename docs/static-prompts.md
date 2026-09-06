# Static prompt extraction

Static archives contain prompt-like strings embedded in CLI packages. They are separate from runtime requests: finding a string in a package does not prove that the CLI sent it to a model. Static content stays in its original language.

## Pipeline and files

For Claude Code, Phistory reads the installed JavaScript entrypoint, including JavaScript embedded in a supported Bun binary. Tree-sitter extracts string and template literals, then a shared resource filter removes standalone programs, HTML assets, encoded blobs and similar resources. The remaining candidates are matched against the local catalog by content hash or anchors. Unmatched candidates must also meet the prompt-prose threshold to appear in the viewer.

Each version has three files under `captures/claude-code/<version>/static/`:

| File | Purpose |
| --- | --- |
| `candidates.json` | Filtered extraction input: original candidate text, ID, ordering, score and source provenance. It retains more text than the viewer displays, allowing future catalog rematching. |
| `prompts.json` | Selected candidates with catalog identity, confidence and summary counts. The Static viewer reads this file. |
| `prompts.md` | Deterministic, readable export of the selected prompts. |

Candidate bodies are not rewritten when filtering or matching changes. Runtime `prompt.md`, `trace.jsonl` and `meta.json` are unaffected. A package without an extractable JavaScript source is reported as `StaticSourceUnavailable`; the runtime capture remains available.

## Resource boundary

The same resource check runs for fresh literals, archived candidates and final matches. A script containing phrases such as “You are” or known catalog anchors is still a script. JavaScript syntax, including declarations, assignments and immediately invoked functions, identifies standalone programs; HTML and other resource formats have their own structural checks.

Fenced code examples are ignored only in the classifier's temporary copy. The stored document keeps its code, formatting and identifiers. Likewise, `${...}` template holes are substituted only in a temporary JavaScript parsing copy. No template is executed. Long instructional documents and guides with many examples remain eligible; there is no maximum document-length filter. Known short prompts can bypass the general prose-score threshold, but cannot bypass the resource filter.

These are general format heuristics, not proof of semantic relevance. Review both rejected resources and retained guides when changing them, and test fresh extraction as well as cached replay.

## Replaying historical data

```bash
# Refilter and rematch archived candidates without fetching or installing these packages.
uv run phistory extract-static claude-code 2.1.202 2.1.228

# Re-extract from the actual package when extraction changes require new candidates.
# This installs the package if necessary and replaces its candidate archive.
uv run phistory extract-static claude-code 2.1.228 --refresh-candidates

uv run phistory render-index
uv run phistory build-site
```

Cached replay applies the current filters even when an old candidate has a high stored score. Surviving records retain their contents, IDs, scores and extraction provenance; a second replay is deterministic. Replay can recover a prompt that was retained as a candidate but excluded from the viewer. Recovering a string absent from the candidate archive requires source re-extraction. None of these commands calls a model provider.

## Historical cleanup verification

The cleanup reviewed the latest 50 archived Claude Code runtime versions, **2.1.203–2.1.263**. Of those, 25 had Static archives. It also replayed **all 49 existing Static versions**, **2.1.170–2.1.228**; absent Static archives were not counted as cleaned data.

| Measurement | Before | After |
| --- | ---: | ---: |
| Candidate records | 105,186 | 104,012 |
| Displayed prompt records | 45,380 | 45,227 |
| Known prompt records | 24,240 | 24,240 |
| Standalone resource records among displayed prompts | 193 | 0 |

The 193 displayed resources contained 8,324,491 characters. They included a 3,312,873-character Mermaid bundle in 2.1.202 and standalone HTML apps, validators and hooks. The broader candidate cleanup removed 1,174 resource records, including items that were never displayed. Protecting fenced examples also restored one legitimate PHP Message Batches guide in 40 versions. Every retained prompt and candidate record was compared with its baseline and remained unchanged.

Validation included representative resource and instructional-document samples, deterministic cached replay, full unit tests, fresh extraction from the real 2.1.228 package, and desktop/mobile Static navigation and diffs. Fresh extraction also recovered four TypeScript guides that were absent from the older candidate archive; historical cleanup used the existing candidates rather than reinstalling all 49 packages.
