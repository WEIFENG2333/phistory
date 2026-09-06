import io
import json
import runpy
from pathlib import Path

import pytest

from phistory.translation.config import TranslationConfig
from phistory.translation.segments import Segment, extract_markdown

SCRIPTS = Path(__file__).parents[1] / "scripts"


def test_evaluation_skips_historical_static_samples_without_reading_sources(tmp_path, capsys):
    read_samples = runpy.run_path(str(SCRIPTS / "evaluate_translation.py"))["read_samples"]
    samples = tmp_path / "samples.json"
    samples.write_text(
        json.dumps(
            [
                {"id": "runtime", "text": "Read the file."},
                {"id": "static-entry", "static_prompt": "old-entry", "source": "missing.json"},
                {"id": "static-markdown", "source": "captures/agent/1/static/prompts.md"},
            ]
        )
    )
    rows = read_samples(samples, [])
    assert [row["segment"].id for row in rows] == ["runtime"]
    assert "Skipped 2 historical Static samples" in capsys.readouterr().err
    for sample in ("static-entry", "static-markdown"):
        with pytest.raises(ValueError, match="Static translation is disabled"):
            read_samples(samples, [sample])


def test_review_reads_only_runtime_and_preserves_review_strata(tmp_path):
    review = runpy.run_path(str(SCRIPTS / "review_translations.py"))
    text = "Read the relevant files before editing, and explain how the resulting changes address the user's request."
    prompt = tmp_path / "prompt.md"
    prompt.write_text(text)
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps({"request": {"body": {"instructions": text}}}))
    segment = extract_markdown(text).segments[0]
    dictionary = {"entries": {segment.id: {"text": "编辑前阅读相关文件，并解释修改如何满足用户需求。"}}}
    rows = [
        {"version": version, "prompt": prompt, "trace": trace, "static_prompts": tmp_path / "missing-static.md"}
        for version in ("1.0", "1.1", "1.2", "1.3")
    ]
    candidates = review["candidates"](rows, dictionary)
    assert {row["version"] for row in candidates} == {"1.0", "1.2", "1.3"}
    assert all(row["translation"] == dictionary["entries"][segment.id]["text"] for row in candidates)
    assert all("dictionary_kind" not in row for row in candidates)
    selected, coverage = review["select"](candidates, 1, "test")
    assert len(selected) == 1
    assert set(coverage) == {"preserved", "old", "latest", "long", "tool", "schema"}


def test_recording_client_preserves_request_accounting_through_corrections(monkeypatch):
    recording_client = runpy.run_path(str(SCRIPTS / "evaluate_translation.py"))["RecordingClient"]
    calls = []
    usage = {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "completion_tokens_details": {"reasoning_tokens": 15},
    }

    def request(req, timeout):
        payload = json.loads(req.data)
        calls.append(payload)
        text = "重试两次。" if len(calls) == 1 else "重试 2 次。"
        return io.BytesIO(
            json.dumps(
                {
                    "id": f"test-response-{len(calls)}",
                    "usage": usage,
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps({"translations": {"0": {"text": text, "status": "translated"}}})
                            },
                        }
                    ],
                }
            ).encode()
        )

    monkeypatch.setattr("phistory.translation.client.urlopen", request)
    client = recording_client(TranslationConfig("https://example.test/v1", "test-model", "private-test-key"))
    result = client.translate([Segment("source-id", "Retry 2 times.")])
    assert result.texts == {"source-id": "重试 2 次。"}
    assert (result.requests, result.input_tokens, result.output_tokens) == (2, 20, 40)
    assert client.attempts == [{"ids": ["source-id"], "accepted": 1}]
    assert [call["request"] for call in client.calls] == calls
    assert all(call["response"]["usage"] == usage and call["seconds"] >= 0 for call in client.calls)
    assert [call["response"]["id"] for call in client.calls] == ["test-response-1", "test-response-2"]
    assert "feedback" in json.loads(calls[1]["messages"][1]["content"])["segments"][0]
    assert "private-test-key" not in json.dumps(client.calls)
