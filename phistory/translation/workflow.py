from __future__ import annotations

import hashlib
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from phistory.translation.client import PermanentTranslationError, TranslationBatch, TranslationClient
from phistory.translation.config import TranslationConfig
from phistory.translation.prompts import PROMPT_VERSION
from phistory.translation.segments import Segment, extract_markdown, extract_trace
from phistory.translation.storage import read_dictionary, write_dictionary, write_source


@dataclass
class TranslationResult:
    agent_id: str
    total: int = 0
    reused: int = 0
    translated: int = 0
    failed: int = 0
    source_chars: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def translate_archive(
    root: Path,
    *,
    translation_root: Path | None = None,
    agent_ids: list[str] | None = None,
    latest_captured: int | None = None,
    include_static: bool = True,
    dry_run: bool = False,
    config: TranslationConfig | None = None,
    max_batches: int | None = None,
    progress: Callable[[str], None] = print,
) -> list[TranslationResult]:
    """Index archived prose and persist only missing translations, batch by batch."""
    from phistory.render import _version_key, read_capture_rows

    translation_root = translation_root or root.parent / "translations"
    grouped = defaultdict(list)
    for row in read_capture_rows(root):
        if agent_ids is None or row["agent_id"] in agent_ids:
            grouped[row["agent_id"]].append(row)
    results = []
    for agent_id, rows in sorted(grouped.items()):
        if latest_captured is not None:
            versions = sorted({row["version"] for row in rows}, key=_version_key, reverse=True)[:latest_captured]
            rows = [row for row in rows if row["version"] in versions]
        dictionaries = {kind: read_dictionary(translation_root, agent_id, kind) for kind in ("runtime", "static")}
        needed = {kind: {} for kind in dictionaries}
        seen = set()
        for row in rows:
            paths = [("runtime", row["prompt"]), ("runtime", row["trace"])]
            if include_static and row.get("static_prompts"):
                paths.append(("static", row["static_prompts"]))
            for kind, path in paths:
                raw = path.read_bytes()
                identity = (kind, hashlib.sha256(raw).hexdigest())
                if identity in seen:
                    continue
                seen.add(identity)
                source = (
                    extract_trace(raw.decode("utf-8"))
                    if path.suffix == ".jsonl"
                    else extract_markdown(raw.decode("utf-8"))
                )
                if not dry_run:
                    write_source(translation_root, source.index)
                needed[kind].update((segment.id, segment) for segment in source.segments)
        all_segments = {key: segment for segments in needed.values() for key, segment in segments.items()}
        existing = {key: entry for dictionary in dictionaries.values() for key, entry in dictionary["entries"].items()}
        pending = [segment for key, segment in all_segments.items() if key not in existing]
        result = TranslationResult(
            agent_id,
            total=len(all_segments),
            reused=len(all_segments) - len(pending),
            source_chars=sum(len(s.text) for s in pending),
        )
        results.append(result)
        progress(
            f"[{agent_id}] {result.total} unique segments; {result.reused} reused; {len(pending)} pending ({result.source_chars:,} characters)"
        )
        if dry_run:
            continue

        def save() -> None:
            # Share identical translations across runtime/static without coupling their downloads.
            for kind, segments in needed.items():
                for key in segments:
                    if key in existing:
                        dictionaries[kind]["entries"][key] = existing[key]
                if dictionaries[kind]["entries"]:
                    write_dictionary(translation_root, agent_id, dictionaries[kind], kind)

        save()
        if not pending:
            continue
        if config is None:
            raise ValueError("translation requires API configuration unless --dry-run is used")
        batches = list(_batches(pending, config.batch_chars))
        if max_batches is not None:
            batches = batches[:max_batches]
        client = TranslationClient(config)

        def accept(outcome: TranslationBatch, batch_size: int) -> None:
            for key, text in outcome.texts.items():
                existing[key] = {
                    "text": text,
                    "model": config.model,
                    "prompt_version": PROMPT_VERSION,
                    "thinking_budget": config.thinking_budget if config.enable_thinking else 0,
                    "status": outcome.statuses.get(key, "translated"),
                }
            result.translated += len(outcome.texts)
            result.input_tokens += outcome.input_tokens
            result.output_tokens += outcome.output_tokens
            result.failed += batch_size - len(outcome.texts)
            for error in outcome.errors:
                progress(f"[{agent_id}] {error}")
            save()

        iterator = iter(batches)
        done_count = 0
        fatal_error = None
        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            active = {}

            def submit() -> None:
                batch = next(iterator, None)
                if batch:
                    active[executor.submit(client.translate, batch)] = batch

            for _ in range(config.concurrency):
                submit()
            while active:
                completed, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in completed:
                    batch = active.pop(future)
                    if future.cancelled():
                        continue
                    try:
                        outcome = future.result()
                    except PermanentTranslationError as exc:
                        if exc.partial is not None:
                            accept(exc.partial, len(batch))
                        else:
                            result.failed += len(batch)
                        if fatal_error is None:
                            fatal_error = exc
                            for other in active:
                                other.cancel()
                    except Exception as exc:
                        result.failed += len(batch)
                        progress(f"[{agent_id}] failed {len(batch)} segments: {exc}")
                    else:
                        accept(outcome, len(batch))
                    done_count += 1
                    progress(
                        f"[{agent_id}] batch {done_count}/{len(batches)}; translated {result.translated}; failed {result.failed}; tokens {result.input_tokens}/{result.output_tokens}"
                    )
                # Stop scheduling on permanent errors, but save results already in flight.
                if fatal_error is None:
                    for _ in completed:
                        submit()
        if fatal_error is not None:
            raise fatal_error
        result.failed = len(all_segments.keys() - existing.keys())
    return results


def _batches(segments: list[Segment], limit: int):
    batch = []
    size = 0
    for segment in segments:
        if batch and (size + len(segment.text) > limit or len(batch) >= 12):
            yield batch
            batch, size = [], 0
        batch.append(segment)
        size += len(segment.text)
    if batch:
        yield batch
