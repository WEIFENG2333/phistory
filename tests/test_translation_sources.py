import json
from copy import deepcopy

import pytest

from phistory.translation.segments import (
    MAX_SEGMENT_CHARS,
    extract_markdown,
    extract_trace,
    needs_translation,
    select_main_trace_record,
    source_hash,
)
from phistory.translation.storage import (
    read_dictionary,
    read_source,
    source_path,
    write_dictionary,
    write_source,
)


def texts(document):
    return [segment.text for segment in document.segments]


def translated_markdown(original, document, dictionary):
    for ref in reversed(document.index["segments"]):
        value = dictionary[ref["id"]]
        if ref["kind"] == "json-string":
            value = json.dumps(value, ensure_ascii=False)
        elif ref["kind"] == "json-string-part":
            for _ in range(ref.get("escape_depth", 1)):
                value = json.dumps(value, ensure_ascii=False)[1:-1]
        original = original[: ref["start"]] + value + original[ref["end"] :]
    return original


def test_markdown_structure_unicode_and_json_prose():
    original = """# Working with users\r
\r
😀 Always ask before deleting files.\r
\r
- Keep `tool_name` unchanged.\r
  Continue the same instruction.\r
- Read before writing.\r
\r
| Field | Meaning |\r
| --- | --- |\r
| `path` | The file path |\r
\r
```python\r
print("Never translate this string.")\r
```\r
\r
```json\r
{"properties":{"path":{"description":"The file path","type":"string","enum":["production"]}}}\r
```\r
"""
    document = extract_markdown(original)
    assert "Never translate this string." not in texts(document)
    assert "The file path" in texts(document)
    assert "production" not in texts(document)
    assert "😀 Always ask before deleting files." in texts(document)
    values = {segment.id: "中文内容" for segment in document.segments}
    rendered = translated_markdown(original, document, values)
    assert 'print("Never translate this string.")' in rendered
    assert '"description":"中文内容","type":"string","enum":["production"]' in rendered
    assert "# 中文内容\r\n" in rendered
    assert "| `path` | 中文内容 |" in rendered
    assert "- 中文内容\r\n" in rendered
    assert document.index["source_hash"] == source_hash(original)
    assert document.index["source_hash"] != source_hash(original.replace("\r\n", "\n"))


def test_shared_paragraphs_and_prompt_trace_dictionary_identity():
    instruction = "Always request permission before deleting files."
    first = extract_markdown(f"# Instructions\n\n{instruction}\n\nKeep commands unchanged.\n")
    second = extract_markdown(f"# Instructions\n\n{instruction}\n\nKeep paths unchanged.\n")
    trace = extract_trace(json.dumps({"request": {"body": {"instructions": instruction}}}))
    first_id = next(segment.id for segment in first.segments if segment.text == instruction)
    assert first_id in {segment.id for segment in second.segments}
    assert first_id in {segment.id for segment in trace.segments}
    duplicate = extract_markdown(instruction + "\n\n" + instruction)
    assert len(duplicate.segments) == 1
    assert len(duplicate.index["segments"]) == 2
    assert "text" not in duplicate.index["segments"][0]


@pytest.mark.parametrize(
    "value",
    [
        "这是中文说明，使用 API 调用。",
        "`tool_name`",
        "https://example.com/docs",
        "${placeholder}",
        "file_path",
        "WebSearch",
        "# MCP",
    ],
)
def test_machine_values_and_existing_chinese_do_not_need_api(value):
    assert not needs_translation(value)


@pytest.mark.parametrize("value", ["Instructions", "Keep API keys private.", "说明：Always keep credentials private."])
def test_natural_english_prose_needs_translation(value):
    assert needs_translation(value)


def test_tool_names_stay_original_but_section_titles_translate():
    document = extract_markdown("# Tools\n\n## Bash\n\nRun a shell command.\n\n## WebSearch\n\nSearch the web.\n")
    assert texts(document) == ["Tools", "Run a shell command.", "Search the web."]


def test_static_text_fences_and_long_paragraph_chunks():
    long = ("A complete sentence about permission checks. " * 300).strip()
    original = "```text\n# Important rules\n\n" + long + "\n```\n"
    document = extract_markdown(original)
    assert "Important rules" in texts(document)
    assert all(len(segment.text) <= MAX_SEGMENT_CHARS for segment in document.segments)
    assert len(document.segments) >= 3
    covered = "".join(original[ref["start"] : ref["end"]] for ref in document.index["segments"][1:])
    assert covered == long


def test_invalid_explicit_source_hash_rejected():
    with pytest.raises(ValueError, match="does not match"):
        extract_markdown("Read the file.", source_hash="0" * 64)


def test_static_export_nested_fences_do_not_hide_following_prompt():
    original = """# Static Prompts

### First prompt

```text
Read these instructions.

```python
print("Do not translate code.")
```

Keep following the instructions.
```

### Second prompt

```text
Translate this complete prompt too.
```
"""
    document = extract_markdown(original)
    assert "Read these instructions." in texts(document)
    assert "Keep following the instructions." in texts(document)
    assert "Translate this complete prompt too." in texts(document)
    assert not any("print(" in value for value in texts(document))


def test_static_export_incomplete_candidate_does_not_hide_following_candidates():
    original = """# Static Prompts

### First prompt

An incomplete extracted template.


```text
Keep the natural language instruction.

```python
print("An unfinished code sample.")
```

### Second prompt


```text
Keep the next prompt fully visible.
```
"""
    document = extract_markdown(original)
    assert "Keep the natural language instruction." in texts(document)
    assert "Keep the next prompt fully visible." in texts(document)
    assert not any("print(" in value for value in texts(document))


def test_json_prose_parts_escape_unicode_and_preserve_embedded_code():
    instruction = "😀 Read the file before changing it."
    description = instruction + '\n\n```python\nprint("Keep the code.")\n```\n\n' + "Read the instructions. " * 400
    original = "```json\n" + json.dumps({"description": description}) + "\n```\n"
    document = extract_markdown(original)
    assert max(len(segment.text) for segment in document.segments) <= MAX_SEGMENT_CHARS
    instruction_id = extract_markdown(instruction).segments[0].id
    assert instruction_id in {segment.id for segment in document.segments}
    assert not any("Keep the code." in segment.text for segment in document.segments)
    result = translated_markdown(
        original, document, {segment.id: '使用"引号"和\\反斜杠。' for segment in document.segments}
    )
    decoded = json.loads(result.removeprefix("```json\n").removesuffix("\n```\n"))
    assert 'print("Keep the code.")' in decoded["description"]
    assert '使用"引号"和\\反斜杠。' in decoded["description"]


def test_nested_json_prose_escaping_depth():
    inner = "```json\n" + json.dumps({"description": "An inner description."}) + "\n```"
    original = "```json\n" + json.dumps({"description": inner}) + "\n```\n"
    document = extract_markdown(original)
    assert document.index["segments"][0]["escape_depth"] == 2
    result = translated_markdown(
        original, document, {segment.id: '包含"引号"的译文。' for segment in document.segments}
    )
    outer = json.loads(result.removeprefix("```json\n").removesuffix("\n```\n"))["description"]
    assert json.loads(outer.removeprefix("```json\n").removesuffix("\n```"))["description"] == '包含"引号"的译文。'


def test_unfenced_json_examples_keep_machine_identifiers():
    assert not needs_translation('{"op":"send","message":"Keep this literal payload."}')


def test_static_generated_metadata_is_not_translated():
    original = "# Static Prompts\n\nAgent: `claude-code`\nVersion: `1.2.3`\n\n## System Prompt\n\n### Follow instructions\n\n\n```text\nFollow these instructions.\n```\n"
    document = extract_markdown(original)
    assert texts(document) == ["System Prompt", "Follow instructions", "Follow these instructions."]
    assert document.index["source_hash"] == source_hash(original)


def test_xml_machine_fields_keep_values_but_descriptions_translate():
    original = """<skill>
  <name>customize-opencode</name>
  <description>Configure your assistant's behavior.</description>
  <location>&lt;built-in&gt;</location>
  <id>
    machine skill identifier
  </id>
</skill>

Read <path>the exact file path</path> before making changes.
"""
    document = extract_markdown(original)
    assert all(
        "built-in" not in unit.text
        and "customize-opencode" not in unit.text
        and "machine skill identifier" not in unit.text
        and "the exact file path" not in unit.text
        for unit in document.segments
    )
    assert any("Configure your assistant's behavior." in unit.text for unit in document.segments)
    rendered = translated_markdown(original, document, {unit.id: "中文说明" for unit in document.segments})
    assert "<location>&lt;built-in&gt;</location>" in rendered
    assert "<name>customize-opencode</name>" in rendered
    assert "<path>the exact file path</path>" in rendered
    assert "machine skill identifier" in rendered


def test_xml_placeholders_and_container_tags_do_not_hide_prose():
    original = """Read the skill at <location> with `read`; obey.
Several: most specific. None: read none.

<skills>
  <name>create-agent</name>
  <location>/skills/create-agent/SKILL.md</location>
</skills>

Create a task with `task <name> --every <interval>`.

The task includes checking CI and following the pull request until it merges.

<available_skills>
  <skill><name>create-agent</name></skill>
</available_skills>

<type>
    <name>feedback</name>
    <description>Guidance the user has given you about how to approach work.</description>
    <examples>Prefers one bundled PR over many small ones.</examples>
</type>
"""
    document = extract_markdown(original)
    joined = "\n".join(unit.text for unit in document.segments)
    assert "Several: most specific. None: read none." in joined
    assert "The task includes checking CI" in joined
    assert "Guidance the user has given you" in joined
    assert "Prefers one bundled PR over many small ones." in joined
    assert "create-agent" not in joined
    assert "/skills/create-agent/SKILL.md" not in joined


@pytest.mark.parametrize(
    "value",
    [
        "<location>&lt;built-in&gt;</location>",
        "<name>customize-opencode</name>",
        "file://$PHISTORY_WORKSPACE/%3Cbuilt-in%3E",
        "xd://workspace",
        "file://",
    ],
)
def test_machine_fields_and_generic_uri_schemes_need_no_api(value):
    assert not needs_translation(value)
    assert not extract_markdown(value).segments


def test_context_guides_translation_without_changing_any_text_identity():
    long = "Restate the schedule and task, obtain approval, create the automation, and run it once as a visible test."
    first = extract_markdown("## Automations\n\n" + long + "\n\nPromote\n")
    second = extract_markdown("## Subagent sessions\n\n" + long + "\n\nPromote\n")
    first_long = next(unit for unit in first.segments if unit.text == long)
    second_long = next(unit for unit in second.segments if unit.text == long)
    assert first_long.id == second_long.id
    assert "Automations" in first_long.context
    assert "Subagent sessions" in second_long.context
    assert all(len(unit.context) <= 200 for unit in (*first.segments, *second.segments))
    assert first_long.context == "Section: Automations"
    first_short = next(unit for unit in first.segments if unit.text == "Promote")
    second_short = next(unit for unit in second.segments if unit.text == "Promote")
    assert first_short.id == second_short.id
    assert first_short.context != second_short.context
    assert long in first_short.context


def test_prompt_and_trace_tool_context_share_translation_identity():
    description = "Create a persistent automation."
    prompt = extract_markdown("# Tools\n\n## automations\n\n" + description + "\n")
    trace = extract_trace(
        json.dumps({"request": {"body": {"tools": [{"name": "automations", "description": description}]}}})
    )
    prompt_unit = next(unit for unit in prompt.segments if unit.text == description)
    trace_unit = next(unit for unit in trace.segments if unit.text == description)
    assert prompt_unit.id == trace_unit.id
    assert "automations" in prompt_unit.context
    assert "automations" in trace_unit.context


def test_trace_primary_request_matches_tool_count_and_keeps_raw_immutable():
    records = [
        {"request": {"body": {"messages": [{"role": "user", "content": "An initial message."}]}}},
        {"request": {"body": {"instructions": "A later prompt.", "tools": [{"name": "first"}]}}},
        {
            "request": {
                "body": {"instructions": "The complete prompt.", "tools": [{"name": "first"}, {"name": "second"}]}
            }
        },
    ]
    saved = deepcopy(records)
    assert select_main_trace_record(records) == 2
    document = extract_trace("\n".join(json.dumps(record) for record in records))
    assert document.index["selected_record"] == 2
    assert texts(document) == ["The complete prompt."]
    assert document.index["fields"][0]["pointer"] == "/request/body/instructions"
    assert records == saved
    assert select_main_trace_record([{"request": {"body": {}}}]) is None
    assert extract_trace("").index["fields"] == []


def test_responses_nested_namespace_and_schema_fields():
    body = {
        "instructions": "Follow the developer instructions.",
        "input": [
            {"role": "developer", "content": [{"type": "input_text", "text": "Check all changed files."}]},
            {
                "type": "additional_tools",
                "tools": [
                    {
                        "type": "namespace",
                        "name": "functions",
                        "description": "Workspace tools.",
                        "tools": [
                            {
                                "type": "function",
                                "name": "read_file",
                                "description": "Read a local file.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "a/b~c": {
                                            "description": "The file path",
                                            "title": "Target file",
                                            "enum": ["Do not translate this enum."],
                                        }
                                    },
                                    "$defs": {"value": {"description": "A shared definition."}},
                                    "anyOf": [{"description": "First available choice."}],
                                    "examples": [{"description": "Do not translate this example."}],
                                },
                            },
                        ],
                    }
                ],
            },
            {"type": "function_call", "name": "read_file", "arguments": '{"path":"Never translate arguments."}'},
        ],
    }
    document = extract_trace(json.dumps({"request": {"body": body}}))
    assert "Workspace tools." in texts(document)
    assert "Read a local file." in texts(document)
    assert "The file path" in texts(document)
    assert "A shared definition." in texts(document)
    assert "First available choice." in texts(document)
    assert "Do not translate this enum." not in texts(document)
    assert "Do not translate this example." not in texts(document)
    assert any("a~1b~0c/description" in field["pointer"] for field in document.index["fields"])
    assert not any("arguments" in field["pointer"] for field in document.index["fields"])


@pytest.mark.parametrize(
    "body,expected_pointer",
    [
        (
            {
                "system": [{"type": "text", "text": "You are a helpful assistant."}],
                "tools": [
                    {
                        "name": "read",
                        "description": "Read a local file.",
                        "input_schema": {"description": "Input data."},
                    }
                ],
            },
            "/request/body/system/0/text",
        ),
        (
            {
                "request": {
                    "systemInstruction": {"parts": [{"text": "You are a helpful assistant."}]},
                    "contents": [{"role": "user", "parts": [{"text": "Read the project files."}]}],
                    "tools": [
                        {
                            "functionDeclarations": [
                                {
                                    "name": "read",
                                    "description": "Read a local file.",
                                    "parameters": {"description": "Input data."},
                                }
                            ]
                        }
                    ],
                }
            },
            "/request/body/request/systemInstruction/parts/0/text",
        ),
        (
            {
                "messages": [{"role": "system", "content": "You are a helpful assistant."}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "read",
                            "description": "Read a local file.",
                            "parameters": {"description": "Input data."},
                        },
                    }
                ],
            },
            "/request/body/messages/0/content",
        ),
        (
            {
                "system": "You are a helpful assistant.",
                "toolConfig": {
                    "tools": [
                        {
                            "toolSpec": {
                                "name": "read",
                                "description": "Read a local file.",
                                "inputSchema": {"json": {"description": "Input data."}},
                            }
                        }
                    ]
                },
            },
            "/request/body/system",
        ),
    ],
)
def test_trace_supported_protocols(body, expected_pointer):
    document = extract_trace(json.dumps({"request": {"body": body}}))
    assert any(field["pointer"] == expected_pointer for field in document.index["fields"])
    assert "You are a helpful assistant." in texts(document)
    assert "Read a local file." in texts(document)
    assert "Input data." in texts(document)


def test_storage_deterministic_and_corrupt_indexes_fallback(tmp_path):
    source = extract_markdown("Keep user credentials private.")
    relative = write_source(tmp_path, source.index)
    assert relative == source_path(source.index)
    path = tmp_path / relative
    assert read_source(path, source.index["source_hash"]) == source.index
    assert len(path.read_text().splitlines()) == 1
    assert '"segments":[{' in path.read_text()
    previous_mtime = path.stat().st_mtime_ns
    write_source(tmp_path, source.index)
    assert path.stat().st_mtime_ns == previous_mtime
    assert read_source(path, "0" * 64) is None
    corrupt = deepcopy(source.index)
    corrupt["segments"][0]["end"] = -1
    path.write_text(json.dumps(corrupt))
    assert read_source(path) is None
    path.write_text("not json")
    assert read_source(path) is None


def test_shared_dictionary_provenance_and_corruption(tmp_path):
    dictionary = read_dictionary(tmp_path, "codex")
    unit = extract_markdown("Read the file.").segments[0]
    dictionary["entries"][unit.id] = {
        "text": "读取文件。",
        "model": "test-model",
        "prompt_version": "1",
        "source_chars": len(unit.text),
    }
    assert write_dictionary(tmp_path, "codex", dictionary)
    assert not write_dictionary(tmp_path, "codex", dictionary)
    assert read_dictionary(tmp_path, "codex") == dictionary
    assert (tmp_path / "zh-CN" / "codex" / "runtime.json").exists()
    assert len((tmp_path / "zh-CN" / "codex" / "runtime.json").read_text().splitlines()) > 1
    with pytest.raises(ValueError, match="dictionary name"):
        read_dictionary(tmp_path, "../codex")
    dictionary["entries"][unit.id]["text"] = ""
    with pytest.raises(ValueError, match="Empty translation"):
        write_dictionary(tmp_path, "codex", dictionary)
    (tmp_path / "zh-CN" / "codex" / "runtime.json").write_text("{}")
    with pytest.raises(ValueError, match="Invalid translation dictionary"):
        read_dictionary(tmp_path, "codex")
