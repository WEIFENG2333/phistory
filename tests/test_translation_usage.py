import json
import runpy
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "summarize_translation_usage.py"
summarize = runpy.run_path(str(SCRIPT))["summarize"]


def test_usage_summary_deduplicates_replays_and_prices_token_subsets_once(tmp_path):
    failed = {
        "model": "model-a",
        "batch_id": "batch-a",
        "attempt": 1,
        "correction_round": 0,
        "status": "http_error",
        "http_status": 429,
        "usage": None,
    }
    success = {
        **failed,
        "attempt": 2,
        "status": "success",
        "http_status": 200,
        "response_id": "response-a",
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 200},
            "completion_tokens_details": {"reasoning_tokens": 300},
        },
    }
    correction = {
        **success,
        "attempt": 1,
        "correction_round": 1,
        "response_id": "response-b",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "prompt_cache_hit_tokens": 25,
            "reasoning_tokens": 150,
        },
    }
    other = {
        **success,
        "model": "model-b",
        "response_id": "response-other",
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    path = tmp_path / "usage.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in [failed, success, correction, other, success, failed]))
    result = summarize([path], input_price=10, output_price=20, cached_input_price=1)
    assert result["duplicate_records"] == 2
    row = result["models"]["model-a"]
    assert (row["requests"], row["http_failures"], row["known_usage_requests"], row["unknown_usage_requests"]) == (
        3,
        1,
        2,
        1,
    )
    assert (row["input_tokens"], row["cached_input_tokens"], row["output_tokens"], row["reasoning_tokens"]) == (
        1100,
        225,
        700,
        450,
    )
    assert row["correction_rounds"] == row["correction_requests"] == 1
    assert row["estimated_known_usage_cost_cny"] == pytest.approx(0.022975)
    other_row = result["models"]["model-b"]
    assert other_row["unknown_cache_requests"] == other_row["unknown_reasoning_requests"] == 1
    assert other_row["estimated_known_usage_cost_cny"] == pytest.approx(0.002)
    assert list(summarize([path], model="model-a")["models"]) == ["model-a"]


def test_usage_summary_reports_unknown_billing_without_inventing_zero_cost(tmp_path):
    path = tmp_path / "usage.jsonl"
    path.write_text(json.dumps({"model": "test", "status": "connection_error", "usage": None}))
    row = summarize([path], input_price=10, output_price=20)["models"]["test"]
    assert row["unknown_usage_requests"] == row["transport_failures"] == 1
    assert row["known_usage_requests"] == 0 and row["estimated_known_usage_cost_cny"] is None


@pytest.mark.parametrize("prices", [["--input-price", "10"], ["--input-price", "nan"], ["--cached-input-price", "1"]])
def test_usage_summary_cli_rejects_ambiguous_prices(monkeypatch, prices):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "unused.jsonl", *prices])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert exc.value.code == 2
