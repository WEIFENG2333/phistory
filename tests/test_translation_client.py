import io
import json
from urllib.error import HTTPError

import pytest

from phistory.translation.client import (
    AuthenticationError,
    InvalidTranslation,
    PermanentTranslationError,
    TranslationClient,
    protect,
    restore,
    retry_delay,
)
from phistory.translation.config import TranslationConfig, load_config
from phistory.translation.segments import Segment


def config(**kwargs):
    return TranslationConfig("https://example.test/v1", "translator", "private-test-key", **kwargs)


def response(items, reason="stop"):
    items = {
        key: {"text": value, "status": "translated"} if isinstance(value, str) else value
        for key, value in items.items()
    }
    return io.BytesIO(
        json.dumps(
            {
                "choices": [{"finish_reason": reason, "message": {"content": json.dumps({"translations": items})}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        ).encode()
    )


def test_config_private_values_and_environment_override(tmp_path, monkeypatch):
    path = tmp_path / "translation.toml"
    path.write_text('[translation]\nbase_url="https://example.test/v1"\nmodel="old"\napi_key="private-test-key"\n')
    monkeypatch.setenv("PHISTORY_TRANSLATION_MODEL", "new")
    loaded = load_config(path)
    assert loaded.model == "new"
    assert "private-test-key" not in repr(loaded)
    assert load_config(path, model="explicit").model == "explicit"


@pytest.mark.parametrize(
    "url", ["file:///tmp/key", "https://user:password@example.test", "https://example.test/?key=secret"]
)
def test_config_rejects_credentials_in_url(url):
    with pytest.raises(ValueError):
        TranslationConfig(url, "model", "key")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test:bad/v1",
        "https://example.test:65536/v1",
        "https://example.test:0/v1",
        "https://bad host/v1",
        "https://bad\thost/v1",
        "https://:443/v1",
        "https://[invalid/v1",
    ],
)
def test_config_rejects_invalid_endpoints_before_network_calls(url):
    with pytest.raises(ValueError, match="base_url"):
        TranslationConfig(url, "model", "key")


def test_config_accepts_explicit_local_endpoint_port():
    assert TranslationConfig("http://[::1]:8000/v1", "model", "key").base_url == "http://[::1]:8000/v1"


@pytest.mark.parametrize("values", [{"timeout": "120"}, {"attempts": 1.5}, {"concurrency": True}])
def test_config_rejects_invalid_numeric_types(values):
    with pytest.raises(ValueError):
        config(**values)


def test_protected_tokens_roundtrip_and_integrity():
    original = "**Never** replace `old_string` with ${value}. Keep _still_ and https://example.test/docs."
    protected, replacements = protect(original)
    assert "old_string" not in protected and "https://" not in protected
    translated = (
        protected.replace("Never", "绝不").replace("replace", "替换").replace("Keep", "保留").replace("still", "仍然")
    )
    result = restore(translated, protected, replacements)
    assert "**绝不**" in result and "_仍然_" in result
    assert "`old_string`" in result and "${value}" in result
    with pytest.raises(InvalidTranslation):
        restore(translated.replace(next(iter(replacements)), ""), protected, replacements)


def test_client_retries_rate_limits_and_keeps_key_out_of_body(monkeypatch):
    calls, delays = [], []

    def request(req, timeout):
        calls.append(req)
        assert "private-test-key" not in req.data.decode()
        payload = json.loads(req.data)
        assert payload["enable_thinking"] is True and payload["thinking_budget"] == 4096
        assert payload["response_format"]["type"] == "json_schema"
        schema = payload["response_format"]["json_schema"]["schema"]["properties"]["translations"]
        assert schema["required"] == ["0"] and schema["additionalProperties"] is False
        if len(calls) == 1:
            raise HTTPError(req.full_url, 429, "rate limited", {"Retry-After": "3"}, None)
        return response({"0": "删除前请确认。"})

    monkeypatch.setattr("phistory.translation.client.urlopen", request)
    monkeypatch.setattr("phistory.translation.client.time.sleep", delays.append)
    translated = TranslationClient(config()).translate([Segment("one", "Confirm before deleting.")])
    assert translated.texts == {"one": "删除前请确认。"}
    assert (translated.input_tokens, translated.output_tokens) == (10, 20)
    assert len(calls) == 2 and delays == [3]


def test_client_does_not_retry_authentication_errors(monkeypatch):
    def request(req, timeout):
        raise HTTPError(req.full_url, 401, "private-test-key", {}, None)

    monkeypatch.setattr("phistory.translation.client.urlopen", request)
    monkeypatch.setattr(
        "phistory.translation.client.time.sleep", lambda _: pytest.fail("authentication must not retry")
    )
    with pytest.raises(AuthenticationError, match="HTTP 401") as error:
        TranslationClient(config()).translate([Segment("one", "Confirm before deleting.")])
    assert "private-test-key" not in str(error.value)


def test_invalid_endpoint_stops_archive_processing(monkeypatch):
    def request(req, timeout):
        raise HTTPError(req.full_url, 404, "endpoint missing", {}, None)

    monkeypatch.setattr("phistory.translation.client.urlopen", request)
    with pytest.raises(PermanentTranslationError, match="HTTP 404"):
        TranslationClient(config()).translate([Segment("one", "Confirm before deleting.")])


def test_keepalive_bytes_do_not_reset_response_deadline(monkeypatch):
    monkeypatch.setattr("phistory.translation.client.urlopen", lambda *args, **kwargs: io.BytesIO(b" " * 65537))
    ticks = iter([0, 0, 2])
    monkeypatch.setattr("phistory.translation.client.time.monotonic", lambda: next(ticks))
    result = TranslationClient(config(timeout=1, attempts=1)).translate([Segment("one", "Confirm before deleting.")])
    assert not result.texts and "timed out" in result.errors[0]


@pytest.mark.parametrize(
    "items,reason",
    [
        ({"wrong": "中文"}, "stop"),
        ({"0": "中文"}, "length"),
        ({"0": ""}, "stop"),
    ],
)
def test_client_rejects_incomplete_or_mismatched_output(monkeypatch, items, reason):
    monkeypatch.setattr("phistory.translation.client.urlopen", lambda *args, **kwargs: response(items, reason))
    result = TranslationClient(config()).translate([Segment("one", "Confirm before deleting.")])
    assert not result.texts and result.errors


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {"choices": None},
        {"choices": {}},
        {"choices": []},
        {"choices": [None]},
        {"choices": [42]},
        {"choices": [{"finish_reason": "stop", "message": None}]},
        {"choices": [{"finish_reason": "stop", "message": []}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": []}}]},
    ],
)
def test_client_classifies_malformed_response_envelopes_for_retry(monkeypatch, body):
    client = TranslationClient(config())
    monkeypatch.setattr(client, "_request", lambda payload: body)
    result = client.translate([Segment("one", "Confirm before deleting.")])
    assert not result.texts and result.errors


def test_malformed_response_receives_concrete_feedback(monkeypatch):
    client = TranslationClient(config())
    calls = []

    def request(payload):
        segments = json.loads(payload["messages"][1]["content"])["segments"]
        calls.append(len(segments))
        if len(calls) == 1:
            return {"choices": [None]}
        assert all("choices structure" in segment["feedback"]["issue"] for segment in segments)
        return json.load(response({"0": "删除前请确认。", "1": "删除前请询问。"}))

    monkeypatch.setattr(client, "_request", request)
    result = client.translate([Segment("one", "Confirm before deleting."), Segment("two", "Ask before deleting.")])
    assert result.texts == {"one": "删除前请确认。", "two": "删除前请询问。"}
    assert calls == [2, 2] and not result.errors


def test_feedback_retries_only_failed_entries_and_model_can_preserve_code(monkeypatch):
    calls = []
    client = TranslationClient(config())
    command = "cd /foo/bar && pytest tests"

    def request(payload):
        segments = json.loads(payload["messages"][1]["content"])["segments"]
        calls.append([item["id"] for item in segments])
        if len(calls) == 1:
            return json.load(response({"0": "读取文件。", "1": "最多重试两次。", "2": segments[2]["text"]}))
        assert calls[-1] == ["1", "2"]
        assert "'2': 1" in segments[0]["feedback"]["issue"]
        assert segments[0]["feedback"]["previous"]["text"] == "最多重试两次。"
        assert "preserved" in segments[1]["feedback"]["issue"]
        return json.load(response({"1": "最多重试 2 次。", "2": {"text": segments[1]["text"], "status": "preserved"}}))

    monkeypatch.setattr(client, "_request", request)
    result = client.translate(
        [Segment("good", "Read files."), Segment("number", "Retry up to 2 times."), Segment("code", command)]
    )
    assert calls == [["0", "1", "2"], ["1", "2"]]
    assert result.texts == {"good": "读取文件。", "number": "最多重试 2 次。", "code": command}
    assert result.statuses == {"good": "translated", "number": "translated", "code": "preserved"}
    assert not result.errors and (result.input_tokens, result.output_tokens) == (20, 40)


def test_feedback_is_bounded_and_keeps_successful_entries(monkeypatch):
    calls = []
    client = TranslationClient(config())

    def request(payload):
        segments = json.loads(payload["messages"][1]["content"])["segments"]
        calls.append([item["id"] for item in segments])
        return json.load(
            response({item["id"]: "读取文件。" if item["id"] == "0" else "重试两次。" for item in segments})
        )

    monkeypatch.setattr(client, "_request", request)
    result = client.translate([Segment("good", "Read files."), Segment("bad", "Retry 2 times.")])
    assert calls == [["0", "1"], ["1"], ["1"]]
    assert result.texts == {"good": "读取文件。"} and len(result.errors) == 1
    assert "numeric constraint" in result.errors[0]


def test_review_feedback_uses_source_identity_and_the_normal_validation_loop(monkeypatch):
    client = TranslationClient(config())
    hint = {"previous": {"text": "Search", "status": "preserved"}, "issue": "This is an ordinary heading."}

    def request(payload):
        segments = json.loads(payload["messages"][1]["content"])["segments"]
        assert segments[0]["feedback"] == hint
        assert "feedback" not in segments[1]
        return json.load(response({"0": "搜索", "1": "读取文件。"}))

    monkeypatch.setattr(client, "_request", request)
    result = client.translate(
        [Segment("heading", "Search"), Segment("body", "Read files.")], feedback={"heading": hint}
    )
    assert result.texts == {"heading": "搜索", "body": "读取文件。"} and not result.errors


def test_missing_ids_keep_valid_results_and_unknown_ids_are_ignored(monkeypatch):
    calls = []
    client = TranslationClient(config())

    def request(payload):
        segments = json.loads(payload["messages"][1]["content"])["segments"]
        calls.append([item["id"] for item in segments])
        if len(calls) == 1:
            return json.load(response({"0": "读取文件。", "unknown": "无关内容"}))
        assert "missing entry 1" in segments[0]["feedback"]["issue"]
        return json.load(response({"1": "搜索"}))

    monkeypatch.setattr(client, "_request", request)
    result = client.translate([Segment("good", "Read files."), Segment("title", "Search")])
    assert calls == [["0", "1"], ["1"]]
    assert result.texts == {"good": "读取文件。", "title": "搜索"} and not result.errors


def test_single_word_translation_needs_chinese_or_explicit_preserved_status(monkeypatch):
    client = TranslationClient(config())
    monkeypatch.setattr(client, "_request", lambda _: json.load(response({"0": "Search"})))
    result = client.translate([Segment("title", "Search")])
    assert not result.texts and "no Chinese prose" in result.errors[0]


def test_preserved_requires_exact_source_and_transport_failure_keeps_accepted_entries(monkeypatch):
    from phistory.translation.client import TranslationError

    calls = []
    client = TranslationClient(config())

    def request(payload):
        segments = json.loads(payload["messages"][1]["content"])["segments"]
        calls.append(segments)
        if len(calls) == 1:
            return json.load(response({"0": "读取文件。", "1": {"text": "changed", "status": "preserved"}}))
        assert "match the input exactly" in segments[0]["feedback"]["issue"]
        raise TranslationError("connection attempts exhausted")

    monkeypatch.setattr(client, "_request", request)
    result = client.translate([Segment("good", "Read files."), Segment("bad", "while true; do")])
    assert len(calls) == 2 and result.texts == {"good": "读取文件。"}
    assert "connection attempts exhausted" in result.errors[0]


def test_retry_delay_bounds():
    assert retry_delay(0, "4") == 4
    assert retry_delay(0, "9999") == 120
    assert 1 <= retry_delay(0, "invalid") <= 2


def test_layout_preserves_source_whitespace_and_rejects_lost_lines():
    source = "  Read the file.  \n\n    Keep all lines.\n"
    translated = "读取文件。\n\n保留所有行。\n"
    assert restore(translated, source, {}) == "  读取文件。  \n\n    保留所有行。\n"
    with pytest.raises(InvalidTranslation, match="line breaks"):
        restore("读取文件。保留所有行。", source, {})


def test_line_breaks_are_protected_and_cannot_be_reordered():
    source = "First line.  \n\n    Last line.\r\n"
    masked, tokens = protect(source)
    assert "\n" not in masked
    translated = masked.replace("First line.", "第一行。").replace("Last line.", "最后一行。")
    assert restore(translated, masked, tokens) == "第一行。  \n\n    最后一行。\r\n"
    keys = list(tokens)
    reordered = translated.replace(keys[0], "SWAP").replace(keys[1], keys[0]).replace("SWAP", keys[1])
    with pytest.raises(InvalidTranslation, match="reordered"):
        restore(reordered, masked, tokens)


def test_emphasis_inner_whitespace_does_not_break_markdown():
    masked, tokens = protect("If you _still_ need it, **always** ask.")
    translated = "如果你 ⟦PH0⟧ 仍然 ⟦PH1⟧ 需要它，⟦PH2⟧ 始终 ⟦PH3⟧ 询问。"
    assert restore(translated, masked, tokens) == "如果你 _仍然_ 需要它，**始终** 询问。"


def test_emphasis_cleanup_preserves_protected_list_indentation():
    source = "A parent item.\n    * A child item.\n    * Another child."
    masked, tokens = protect(source)
    translated = (
        masked.replace("A parent item.", "父条目。")
        .replace("A child item.", "子条目。")
        .replace("Another child.", "另一个子条目。")
    )
    assert restore(translated, masked, tokens) == "父条目。\n    * 子条目。\n    * 另一个子条目。"


def test_protection_preserves_machine_fields_and_separates_uri_punctuation():
    source = "Use <location>&lt;built-in&gt;</location> at xd://project/page. Read /tmp/a.txt."
    protected, replacements = protect(source)
    assert "&lt;built-in&gt;" not in protected and "xd://" not in protected and "/tmp/a.txt" not in protected
    assert "xd://project/page" in replacements.values()
    assert "xd://project/page." not in replacements.values()
    assert "/tmp/a.txt" in replacements.values()
    assert "/tmp/a.txt." not in replacements.values()
    assert (
        restore(protected.replace("Use", "使用").replace("Read", "读取"), protected, replacements).count(
            "&lt;built-in&gt;"
        )
        == 1
    )


def test_long_prose_summary_is_rejected_but_complete_translation_is_allowed():
    source = (
        "You MUST complete the work that is already authorized and necessary to make the proposed action concrete "
        "and reviewable before asking the user for permission as a final step. The user should be approving a "
        "concrete, reviewable result. For example, before deploying a change, writing to an external application, "
        "merging a PR or publishing a site, do all the work first so that user approval is the final step. "
        "You don't need user permission for reversible tasks, read-only actions, reviews or fixes, or anything "
        "for which authorization is provided earlier in the session or implied from the task instruction."
    )
    with pytest.raises(InvalidTranslation, match="summarize"):
        restore(
            "在采取任何行动之前，你必须先获得用户批准。对于可逆任务、只读操作、审查或修复，以及已获授权的事项，无需获得批准。",
            source,
            {},
        )
    complete = (
        "你必须先完成已获授权且为使拟议操作具体、可供审查所必需的工作，再把向用户请求许可作为最后一步。"
        "用户批准的应当是具体、可供审查的结果。例如，在部署更改、写入外部应用、合并 PR 或发布网站之前，"
        "先完成所有工作，让用户批准成为最后一步。对于可逆任务、只读操作、审查或修复，以及在此前会话中已获授权"
        "或任务指令中隐含授权的事项，无需获得用户许可。"
    )
    assert restore(complete, source, {}) == complete


def test_translation_credentials_are_not_inherited_by_captured_commands(monkeypatch):
    import subprocess

    from phistory.subprocesses import run

    def subprocess_run(argv, **kwargs):
        assert not any(key.startswith("PHISTORY_TRANSLATION_") for key in kwargs["env"])
        assert kwargs["env"]["CAPTURE_SETTING"] == "kept"
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setenv("PHISTORY_TRANSLATION_API_KEY", "private-test-key")
    monkeypatch.setattr(subprocess, "run", subprocess_run)
    run(["capture"], env={"PHISTORY_TRANSLATION_MODEL": "private-model", "CAPTURE_SETTING": "kept"})
