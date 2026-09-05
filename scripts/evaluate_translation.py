"""Compare translation models on archived excerpts without updating the archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from phistory.translation.client import TranslationClient
from phistory.translation.config import load_config
from phistory.translation.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from phistory.translation.segments import Segment, extract_markdown

ROOT = Path(__file__).resolve().parents[1]


class RecordingClient(TranslationClient):
    def __init__(self, config):
        super().__init__(config)
        self.calls = []
        self.attempts = []

    def _request(self, payload):
        started = time.monotonic()
        call = {"request": payload}
        self.calls.append(call)
        try:
            response = super()._request(payload)
            call["response"] = response
            return response
        except Exception as exc:
            call["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            call["seconds"] = round(time.monotonic() - started, 2)

    def translate(self, segments):
        attempt = {"ids": [segment.id for segment in segments]}
        self.attempts.append(attempt)
        try:
            result = super().translate(segments)
        except Exception as exc:
            attempt["error"] = f"{type(exc).__name__}: {exc}"
            raise
        attempt["accepted"] = len(result.texts)
        return result


def read_samples(path: Path, selected: list[str]):
    rows = []
    for spec in json.loads(path.read_text(encoding="utf-8")):
        if selected and spec["id"] not in selected:
            continue
        if "text" in spec:
            unit = Segment(spec["id"], spec["text"], "Synthetic translation control")
        else:
            source = ROOT / spec["source"]
            content = source.read_text(encoding="utf-8")
            if "static_prompt" in spec:
                entries = json.loads(content)["prompts"]
                content = next(entry["content"] for entry in entries if entry["id"] == spec["static_prompt"])
            matches = [unit for unit in extract_markdown(content).segments if spec["contains"] in unit.text]
            if len(matches) != 1:
                raise ValueError(f"{spec['id']}: expected one archived segment, found {len(matches)}")
            unit = Segment(spec["id"], matches[0].text, matches[0].context)
        rows.append({"spec": spec, "segment": unit})
    missing = set(selected) - {row["spec"]["id"] for row in rows}
    if not rows or missing:
        raise ValueError(f"no matching samples or unknown sample IDs: {sorted(missing)}")
    return rows


def evaluate(config, rows):
    client = RecordingClient(config)
    result = client.translate([row["segment"] for row in rows])
    pairs = []
    for row in rows:
        segment = row["segment"]
        translated = result.texts.get(segment.id)
        missing = [value for value in row["spec"].get("preserve", []) if translated and value not in translated]
        pairs.append(
            {
                "id": segment.id,
                "source": row["spec"].get("source", "synthetic"),
                "text": segment.text,
                "context": segment.context,
                "translation": translated,
                "status": result.statuses.get(segment.id),
                "missing_literals": missing,
            }
        )
    return {"pairs": pairs, "errors": result.errors, "attempts": client.attempts, "calls": client.calls}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, default=ROOT / "tests/fixtures/translation_samples.json")
    parser.add_argument("--sample", action="append", default=[], help="Select a sample ID; repeat to select more.")
    parser.add_argument("--models", help="Comma-separated model IDs; defaults to the configured translation model.")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180, help="Response time budget per API attempt, in seconds.")
    parser.add_argument(
        "--attempts", type=int, default=1, help="HTTP attempts; validation uses the production feedback loop."
    )
    thinking = parser.add_mutually_exclusive_group()
    thinking.add_argument("--thinking-budget", type=int, help="Enable thinking with this token budget.")
    thinking.add_argument("--no-thinking", action="store_true", help="Request non-thinking mode.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and count samples without API calls.")
    args = parser.parse_args()
    if args.batch_size < 1 or args.concurrency < 1:
        parser.error("batch size and concurrency must be positive")
    rows = read_samples(args.samples, args.sample)
    print(f"{len(rows)} samples; {sum(len(row['segment'].text) for row in rows):,} source characters")
    if args.dry_run:
        return 0
    config = load_config(args.config)
    models = [value.strip() for value in args.models.split(",")] if args.models else [config.model]
    output = args.output or ROOT / ".phistory-cache/translation-eval" / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    output.mkdir(parents=True, exist_ok=True)
    failed = False
    batches = [rows[start : start + args.batch_size] for start in range(0, len(rows), args.batch_size)]
    for model in models:
        configured = replace(load_config(args.config, model=model), timeout=args.timeout, attempts=args.attempts)
        if args.thinking_budget is not None:
            configured = replace(configured, enable_thinking=True, thinking_budget=args.thinking_budget)
        elif args.no_thinking:
            configured = replace(configured, enable_thinking=False)
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(lambda batch: evaluate(configured, batch), batches))
        pairs = [pair for result in results for pair in result["pairs"]]
        report = {
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
            "batches": results,
        }
        name = re.sub(r"[^A-Za-z0-9_.-]", "-", model)
        (output / f"{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        review = "\n\n".join(
            f"## {row['id']}\n\n{row['source']}\n\n原文：\n\n{row['text']}\n\n译文：\n\n{row['translation'] or '未完成'}"
            for row in pairs
        )
        (output / f"{name}.md").write_text(review + "\n", encoding="utf-8")
        errors = sum(not row["translation"] or bool(row["missing_literals"]) for row in pairs)
        failed |= errors > 0
        print(f"{model}: {len(pairs) - errors}/{len(pairs)} structurally valid; review {output / (name + '.md')}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
