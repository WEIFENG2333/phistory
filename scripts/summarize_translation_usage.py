"""Summarize local request JSONL; prices are optional CNY per million tokens.

Input/output totals already contain cached/reasoning tokens. Missing provider
usage remains unknown; estimates cover reported usage only and assume uncached
input when the provider omits its cache breakdown.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def _count(value, key: str) -> int | None:
    count = value.get(key) if isinstance(value, dict) else None
    return count if type(count) is int and count >= 0 else None


def summarize(
    paths: list[Path],
    *,
    model: str | None = None,
    input_price: float | None = None,
    output_price: float | None = None,
    cached_input_price: float | None = None,
) -> dict:
    models, seen, corrections = {}, set(), defaultdict(set)
    duplicates = 0
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("expected an object")
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: invalid usage record") from exc
            name = record.get("model", "unknown")
            if model is not None and name != model:
                continue
            identity = None
            if record.get("response_id"):
                identity = (name, "response", record["response_id"])
            elif record.get("batch_id"):
                identity = (name, "attempt", record["batch_id"], record.get("correction_round"), record.get("attempt"))
            if identity is not None:
                if identity in seen:
                    duplicates += 1
                    continue
                seen.add(identity)
            row = models.setdefault(name, defaultdict(int))
            row["requests"] += 1
            row["http_failures"] += record.get("status") == "http_error"
            row["transport_failures"] += record.get("status") in {"connection_error", "invalid_response"}
            round_number = record.get("correction_round", 0)
            if round_number > 0:
                row["correction_requests"] += 1
                corrections[name].add((record.get("batch_id", identity), round_number))
            usage = record.get("usage")
            input_tokens, output_tokens = _count(usage, "prompt_tokens"), _count(usage, "completion_tokens")
            if input_tokens is None or output_tokens is None:
                row["unknown_usage_requests"] += 1
                continue
            row["known_usage_requests"] += 1
            row["input_tokens"] += input_tokens
            row["output_tokens"] += output_tokens
            cached = _count(usage.get("prompt_tokens_details"), "cached_tokens")
            if cached is None:
                cached = _count(usage, "prompt_cache_hit_tokens")
            if cached is None or cached > input_tokens:
                cached = 0
                row["unknown_cache_requests"] += 1
            row["cached_input_tokens"] += cached
            reasoning = _count(usage.get("completion_tokens_details"), "reasoning_tokens")
            if reasoning is None:
                reasoning = _count(usage, "reasoning_tokens")
            row["reasoning_tokens"] += reasoning or 0
            row["unknown_reasoning_requests"] += reasoning is None
    for name, row in models.items():
        row["correction_rounds"] = len(corrections[name])
        row["estimated_known_usage_cost_cny"] = None
        if input_price is not None and output_price is not None and row["known_usage_requests"]:
            cache_price = input_price if cached_input_price is None else cached_input_price
            row["estimated_known_usage_cost_cny"] = round(
                (
                    (row["input_tokens"] - row["cached_input_tokens"]) * input_price
                    + row["cached_input_tokens"] * cache_price
                    + row["output_tokens"] * output_price
                )
                / 1_000_000,
                8,
            )
        for field in (
            "http_failures",
            "transport_failures",
            "correction_requests",
            "unknown_usage_requests",
            "known_usage_requests",
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
            "unknown_cache_requests",
            "unknown_reasoning_requests",
        ):
            row.setdefault(field, 0)
    return {
        "models": dict(sorted(models.items())),
        "duplicate_records": duplicates,
        "prices_cny_per_million_tokens": {
            "input": input_price,
            "output": output_price,
            "cached_input": cached_input_price,
        },
        "cost_note": "Estimates exclude unknown usage; missing cache breakdown is priced as uncached input. Reasoning is included in output tokens.",
    }


def _price(value: str) -> float:
    price = float(value)
    if not math.isfinite(price) or price < 0:
        raise argparse.ArgumentTypeError("price must be finite and nonnegative")
    return price


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--model", help="Only summarize this model; supplied prices apply to all selected models")
    parser.add_argument("--input-price", type=_price)
    parser.add_argument("--output-price", type=_price)
    parser.add_argument("--cached-input-price", type=_price)
    args = parser.parse_args()
    if (args.input_price is None) != (args.output_price is None):
        parser.error("--input-price and --output-price must be supplied together")
    if args.cached_input_price is not None and args.input_price is None:
        parser.error("--cached-input-price requires input and output prices")
    try:
        result = summarize(**vars(args))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
