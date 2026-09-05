import json
import threading
from pathlib import Path

import pytest

from phistory.render import read_capture_rows
from phistory.translation.client import PermanentTranslationError, TranslationBatch
from phistory.translation.config import TranslationConfig
from phistory.translation.workflow import translate_archive


def capture(root: Path, version: str, text: str):
    path = root / "agent" / version / "variants" / "default"
    path.mkdir(parents=True)
    (path / "prompt.md").write_text(text)
    (path / "trace.jsonl").write_text("{}\n")
    (path / "meta.json").write_text(json.dumps({"agent_id": "agent", "version": version}))
    return path


def test_incremental_translation_reuses_archived_dictionary_and_preserves_sources(tmp_path, monkeypatch):
    root = tmp_path / "captures"
    one = capture(root, "1.0", "Read files before editing.\n\nConfirm before deleting.\n")
    two = capture(root, "1.1", "Read files before editing.\n\nConfirm before deleting.\n\nExplain your changes.\n")
    original = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    calls = []

    def translate(self, segments):
        calls.extend(segment.text for segment in segments)
        return TranslationBatch({segment.id: "中文 " + segment.text for segment in segments})

    monkeypatch.setattr("phistory.translation.workflow.TranslationClient.translate", translate)
    config = TranslationConfig("https://example.test/v1", "model", "private-test-key")
    first = translate_archive(root, config=config, progress=lambda _: None)
    assert len(calls) == 3 and first[0].translated == 3
    second = translate_archive(root, config=config, progress=lambda _: None)
    assert len(calls) == 3 and second[0].reused == 3
    assert all(path.read_bytes() == data for path, data in original.items())
    assert not list(root.rglob("translations"))
    rows = read_capture_rows(root)
    assert all(
        row["translations"]["zh-CN"]["prompt"]["translated"] == row["translations"]["zh-CN"]["prompt"]["total"]
        for row in rows
    )
    for path in (one, two):
        assert not (path / "prompt.zh.md").exists()


def test_dry_run_does_not_call_api_or_write_translations(tmp_path, monkeypatch):
    root = tmp_path / "captures"
    capture(root, "1.0", "Confirm before deleting.\n")
    monkeypatch.setattr(
        "phistory.translation.workflow.TranslationClient.translate",
        lambda *args: (_ for _ in ()).throw(AssertionError("must not call API")),
    )
    result = translate_archive(root, dry_run=True, progress=lambda _: None)
    assert result[0].total == 1
    assert not (tmp_path / "translations").exists()


def test_source_index_shared_between_identical_versions(tmp_path, monkeypatch):
    root = tmp_path / "captures"
    capture(root, "1.0", "Confirm before deleting.\n")
    capture(root, "1.1", "Confirm before deleting.\n")
    monkeypatch.setattr(
        "phistory.translation.workflow.TranslationClient.translate",
        lambda self, segments: TranslationBatch({s.id: "删除前确认。" for s in segments}),
    )
    translate_archive(
        root, config=TranslationConfig("https://example.test/v1", "model", "key"), progress=lambda _: None
    )
    rows = read_capture_rows(root)
    assert rows[0]["translations"]["zh-CN"]["prompt"]["index"] == rows[1]["translations"]["zh-CN"]["prompt"]["index"]


def test_partial_batch_is_saved_and_resume_requests_only_missing_entries(tmp_path, monkeypatch):
    root = tmp_path / "captures"
    capture(root, "1.0", "Read files.\n\nRetry 2 times.\n")
    calls = []

    def translate(self, segments):
        calls.append([segment.text for segment in segments])
        segment = segments[0]
        return TranslationBatch(
            {segment.id: "读取文件。" if len(calls) == 1 else "重试 2 次。"},
            errors=("incomplete",) if len(calls) == 1 else (),
        )

    monkeypatch.setattr("phistory.translation.workflow.TranslationClient.translate", translate)
    config = TranslationConfig("https://example.test/v1", "model", "key")
    first = translate_archive(root, config=config, progress=lambda _: None)
    second = translate_archive(root, config=config, progress=lambda _: None)
    assert first[0].translated == 1 and first[0].failed == 1
    assert second[0].reused == 1 and second[0].translated == 1 and second[0].failed == 0
    assert calls == [["Read files.", "Retry 2 times."], ["Retry 2 times."]]


def test_permanent_error_saves_running_batches_without_scheduling_more(tmp_path, monkeypatch):
    from phistory.translation.storage import read_dictionary, write_dictionary

    root = tmp_path / "captures"
    capture(root, "1.0", "\n\n".join(f"Read entry {index} carefully." for index in range(25)))
    second_started, partial_saved = threading.Event(), threading.Event()
    calls, accepted = [], {}
    fatal = PermanentTranslationError("translation API request failed (HTTP 402)")

    def checkpoint(*args, **kwargs):
        changed = write_dictionary(*args, **kwargs)
        partial_saved.set()
        return changed

    def translate(self, segments):
        calls.append([segment.text for segment in segments])
        if segments[0].text == "Read entry 0 carefully.":
            assert second_started.wait(2)
            accepted[segments[0].id] = "读取第 0 条。"
            fatal.partial = TranslationBatch({segments[0].id: accepted[segments[0].id]})
            raise fatal
        assert segments[0].text == "Read entry 12 carefully."
        second_started.set()
        assert partial_saved.wait(2)
        texts = {segment.id: "中文 " + segment.text for segment in segments}
        accepted.update(texts)
        return TranslationBatch(texts)

    monkeypatch.setattr("phistory.translation.workflow.TranslationClient.translate", translate)
    monkeypatch.setattr("phistory.translation.workflow.write_dictionary", checkpoint)
    config = TranslationConfig("https://example.test/v1", "model", "key", concurrency=2)
    with pytest.raises(PermanentTranslationError) as error:
        translate_archive(root, config=config, progress=lambda _: None)

    assert error.value is fatal
    assert len(calls) == 2 and len(accepted) == 13
    entries = read_dictionary(tmp_path / "translations", "agent")["entries"]
    assert {key: entry["text"] for key, entry in entries.items()} == accepted


def test_fatal_error_during_correction_saves_already_accepted_entries(tmp_path, monkeypatch):
    from phistory.translation.client import AuthenticationError
    from phistory.translation.storage import read_dictionary

    root = tmp_path / "captures"
    capture(root, "1.0", "Read files.\n\nRetry 2 times.\n")
    calls = []

    def request(self, payload):
        calls.append(payload)
        if len(calls) == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "translations": {
                                        "0": {"text": "读取文件。", "status": "translated"},
                                        "1": {"text": "重试两次。", "status": "translated"},
                                    }
                                }
                            )
                        },
                    }
                ]
            }
        raise AuthenticationError("HTTP 403")

    monkeypatch.setattr("phistory.translation.workflow.TranslationClient._request", request)
    with pytest.raises(AuthenticationError, match="HTTP 403"):
        translate_archive(
            root, config=TranslationConfig("https://example.test/v1", "model", "key"), progress=lambda _: None
        )
    entries = read_dictionary(tmp_path / "translations", "agent")["entries"]
    assert len(calls) == 2 and [entry["text"] for entry in entries.values()] == ["读取文件。"]
