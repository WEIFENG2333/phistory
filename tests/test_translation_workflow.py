import json
import threading
from pathlib import Path

import pytest

from phistory.build import build_site
from phistory.render import read_capture_rows
from phistory.translation.assets import TranslationAssets
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


def publish(root: Path):
    site = root.parent / "site"
    build_site(root, site)
    assets = TranslationAssets(site)
    rows = read_capture_rows(site / "captures")
    for row in rows:
        row["translations"] = assets.for_row(row)
    return site, rows


def run_audit(tmp_path, monkeypatch, site, *args):
    import runpy

    audit = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "audit_translations.py"))["main"]
    monkeypatch.setitem(audit.__globals__, "REPO", tmp_path)
    monkeypatch.setitem(audit.__globals__, "git_paths", lambda *args: [])
    report_path = tmp_path / "audit.json"
    monkeypatch.setattr(
        "sys.argv", ["audit_translations.py", "--site-dir", str(site), "--report", str(report_path), *args]
    )
    result = audit()
    return result, json.loads(report_path.read_text())


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
    assert not (tmp_path / "translations" / "sources").exists()
    assert all("translations" not in row for row in read_capture_rows(root))
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


def test_static_archive_never_enters_runtime_translation_queue(tmp_path, monkeypatch):
    from phistory.translation.storage import read_dictionary

    root = tmp_path / "captures"
    path = capture(root, "1.0", "Read the runtime prompt.")
    static = path.parents[1] / "static" / "prompts.md"
    static.parent.mkdir()
    static.write_text("# Static Prompts\n\nThis package document must never be translated.")
    original = static.read_bytes()
    assert read_capture_rows(root)[0]["static_prompts"] == static
    calls = []

    def translate(self, segments):
        calls.extend(segment.text for segment in segments)
        return TranslationBatch({segment.id: "读取运行时提示词。" for segment in segments})

    monkeypatch.setattr("phistory.translation.workflow.TranslationClient.translate", translate)
    result = translate_archive(
        root, config=TranslationConfig("https://example.test/v1", "model", "test"), progress=lambda _: None
    )
    assert calls == ["Read the runtime prompt."]
    assert result[0].total == result[0].translated == 1
    translations = tmp_path / "translations"
    assert len(read_dictionary(translations, "agent")["entries"]) == 1
    assert not list(translations.glob("zh-CN/*/static.json"))
    assert not (translations / "sources").exists()
    assert static.read_bytes() == original


def test_trace_dynamic_values_reuse_existing_prompt_translation(tmp_path, monkeypatch):
    from phistory.translation.segments import extract_markdown
    from phistory.translation.storage import write_dictionary

    root = tmp_path / "captures"
    text = "Primary working directory: $PHISTORY_WORKSPACE"
    for version in ("1.0", "1.1"):
        path = capture(root, version, text)
        raw = text.replace("$PHISTORY_WORKSPACE", "/tmp/phistory-work-" + version.replace(".", ""))
        (path / "trace.jsonl").write_text(json.dumps({"request": {"body": {"instructions": raw}}}))
    key = extract_markdown(text).segments[0].id
    write_dictionary(
        tmp_path / "translations",
        "agent",
        {
            "schema_version": 1,
            "locale": "zh-CN",
            "entries": {
                key: {"text": "主工作目录：$PHISTORY_WORKSPACE", "model": "previous", "prompt_version": "previous"}
            },
        },
    )
    monkeypatch.setattr(
        "phistory.translation.workflow.TranslationClient.translate",
        lambda *args: (_ for _ in ()).throw(AssertionError("cached prose must not call API")),
    )
    result = translate_archive(root, progress=lambda _: None)[0]
    assert result.total == result.reused == 1


@pytest.mark.parametrize(
    "translated,complete",
    [
        ("主工作目录：$PHISTORY_WORKSPACE", True),
        ("主工作目录", False),
        ("主工作目录：$PHISTORY_WORKSPACE $PHISTORY_WORKSPACE", False),
    ],
)
def test_manifest_and_audit_do_not_count_unusable_trace_templates(tmp_path, monkeypatch, translated, complete):
    root = tmp_path / "captures"
    path = capture(root, "1.0", "Primary working directory: $PHISTORY_WORKSPACE")
    (path / "trace.jsonl").write_text(
        json.dumps({"request": {"body": {"instructions": "Primary working directory: /tmp/phistory-work-one"}}})
    )
    monkeypatch.setattr(
        "phistory.translation.workflow.TranslationClient.translate",
        lambda self, segments: TranslationBatch({segment.id: translated for segment in segments}),
    )
    translate_archive(
        root, config=TranslationConfig("https://example.test/v1", "model", "key"), progress=lambda _: None
    )
    site, rows = publish(root)
    trace = rows[0]["translations"]["zh-CN"]["trace"]
    assert trace["total"] == 1
    assert trace["translated"] == int(complete)
    assert (trace["translated_chars"] == trace["source_chars"]) == complete

    result, report = run_audit(tmp_path, monkeypatch, site, "--require-complete")
    assert result == int(not complete)
    assert report["coverage"][0]["translated"] == int(complete)
    assert report["coverage"][0]["missing"] == int(not complete)
    assert bool(report["errors"]) != complete


def test_audit_checks_each_trace_binding_after_seeing_its_prompt_template(tmp_path, monkeypatch):
    root = tmp_path / "captures"
    path = capture(root, "1.0", "Primary working directory: $PHISTORY_WORKSPACE")
    (path / "trace.jsonl").write_text(
        json.dumps({"request": {"body": {"instructions": "Primary working directory: /tmp/phistory-work-one"}}})
    )
    monkeypatch.setattr(
        "phistory.translation.workflow.TranslationClient.translate",
        lambda self, segments: TranslationBatch(
            {segment.id: "主工作目录：$PHISTORY_WORKSPACE" for segment in segments}
        ),
    )
    translate_archive(
        root, config=TranslationConfig("https://example.test/v1", "model", "key"), progress=lambda _: None
    )
    site, rows = publish(root)
    trace = rows[0]["translations"]["zh-CN"]["trace"]
    index_path = site / trace["index"]
    index = json.loads(index_path.read_text())
    index["fields"][0]["segments"][0]["bindings"]["$PHISTORY_WORKSPACE"]["value"] = "/tmp/phistory-work-wrong"
    index_path.write_text(json.dumps(index))

    result, report = run_audit(tmp_path, monkeypatch, site)
    assert result == 1
    assert any("does not restore its original source" in error["error"] for error in report["errors"])


def test_published_source_index_shared_between_identical_versions(tmp_path, monkeypatch):
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
    assert not (tmp_path / "translations" / "sources").exists()
    _, rows = publish(root)
    assert rows[0]["translations"]["zh-CN"]["prompt"]["index"] == rows[1]["translations"]["zh-CN"]["prompt"]["index"]


@pytest.mark.parametrize("damaged", ["prompt", "dictionary", "source-index", "index.html"])
def test_audit_requires_consistent_published_assets(tmp_path, monkeypatch, damaged):
    root = tmp_path / "captures"
    path = capture(root, "1.0", "Read files before editing.")
    monkeypatch.setattr(
        "phistory.translation.workflow.TranslationClient.translate",
        lambda self, segments: TranslationBatch({s.id: "编辑前先阅读文件。" for s in segments}),
    )
    translate_archive(
        root, config=TranslationConfig("https://example.test/v1", "model", "key"), progress=lambda _: None
    )
    site, rows = publish(root)
    assert not (tmp_path / "translations" / "sources").exists()
    expected_bytes = sum(file.stat().st_size for file in site.rglob("*") if file.is_file())
    # Cache and other workspace files never contribute to the published site's size.
    (tmp_path / "local-cache.bin").write_bytes(b"x" * expected_bytes)
    result, report = run_audit(
        tmp_path, monkeypatch, site, "--require-complete", "--size-limit", str(expected_bytes + 1)
    )
    assert result == 0 and report["errors"] == []
    assert report["deployment_total_bytes"] == expected_bytes
    assert report["published_source_copies_checked"] == 4

    metadata = rows[0]["translations"]["zh-CN"]
    if damaged == "prompt":
        (site / path.relative_to(tmp_path) / "prompt.md").write_text("A stale published prompt.")
    elif damaged == "dictionary":
        (site / metadata["runtime"]["path"]).write_text("{}")
    elif damaged == "source-index":
        (site / metadata["prompt"]["index"]).unlink()
    else:
        (site / "index.html").unlink()

    result, report = run_audit(tmp_path, monkeypatch, site, "--require-complete")
    assert result == 1
    if damaged == "source-index":
        assert report["missing_source_maps"] == [str((path / "prompt.md").relative_to(tmp_path))]
        assert report["errors"] == []
    elif damaged == "index.html":
        assert any("missing index.html" in error["error"] for error in report["errors"])
    else:
        assert any("published copy differs" in error["error"] for error in report["errors"])


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

    def request(self, payload, **kwargs):
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
