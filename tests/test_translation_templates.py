import json

import pytest

from phistory.translation.segments import extract_markdown, extract_trace
from phistory.translation.storage import read_source, write_source
from phistory.translation.templates import restore_template, trace_template


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("Primary working directory: /tmp/phistory-work-one", "Primary working directory: $PHISTORY_WORKSPACE"),
        ("Today's date is 2026-09-06.", "Today's date is $PHISTORY_DATE."),
        (
            "Artifact path: /tmp/phistory-home-one/.gemini/antigravity-cli/brain/667b20b8-bfce-40e6-9d7f-72df226096b1",
            "Artifact path: $PHISTORY_HOME/.gemini/antigravity-cli/brain/$PHISTORY_CONVERSATION",
        ),
        (
            "Read /tmp/phistory-work-one and write /tmp/phistory-work-one.",
            "Read $PHISTORY_WORKSPACE and write $PHISTORY_WORKSPACE.",
        ),
    ],
)
def test_capture_templates_reuse_prompt_identity_and_restore_trace(original, expected, tmp_path):
    raw = json.dumps({"request": {"body": {"instructions": original}}})
    trace = extract_trace(raw)
    prompt = extract_markdown(expected)
    assert trace.segments[0].text == expected
    assert trace.segments[0].id == prompt.segments[0].id
    ref = trace.index["fields"][0]["segments"][0]
    assert original[ref["start"] : ref["end"]] == original
    assert restore_template(expected, ref["bindings"]) == original
    path = write_source(tmp_path, trace.index)
    assert read_source(tmp_path / path) == trace.index
    assert json.loads(raw)["request"]["body"]["instructions"] == original


@pytest.mark.parametrize(
    "original",
    [
        "Read /tmp/phistory-work-one and write /tmp/phistory-work-two.",
        "Read $PHISTORY_WORKSPACE and write /tmp/phistory-work-one.",
        "The current local time is: 2026-09-06T00:00:00Z",  # Sanitizer adds punctuation; not reversible.
        "Read `tool_a`, then `tool_b`; retry 3 times.",
        "Use /etc/config and https://example.com/docs.",
        "Bearer phistory-example",  # Redaction is not a translation template.
    ],
)
def test_only_reversible_capture_literals_are_shared(original):
    assert trace_template(original) == (original, {})


def test_bindings_are_restored_once_and_must_preserve_counts():
    bindings = {"$PHISTORY_HOME": {"value": "literal $& \\" + "$PHISTORY_HOME", "count": 2}}
    assert restore_template("$PHISTORY_HOME $PHISTORY_HOME", bindings) == " ".join(
        [bindings["$PHISTORY_HOME"]["value"]] * 2
    )
    with pytest.raises(ValueError, match="placeholders"):
        restore_template("主目录", bindings)


def test_nested_json_description_keeps_template_bindings():
    original = "Read /tmp/phistory-work-one before changing files."
    content = "```json\n" + json.dumps({"description": original}) + "\n```"
    trace = extract_trace(json.dumps({"request": {"body": {"instructions": content}}}))
    ref = trace.index["fields"][0]["segments"][0]
    assert ref["kind"] == "json-string-part"
    assert restore_template(trace.segments[0].text, ref["bindings"]) == original
