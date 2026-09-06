import json

import pytest

from phistory.static_prompts.javascript import (
    extract_string_candidates,
    is_prompt_like,
    is_source_resource,
    is_static_resource,
)

PROSE = (
    "You are reviewing the following example. Your task is to explain the changes and suggest a minimal "
    "improvement. Do not execute the sample code."
)


@pytest.mark.parametrize(
    "program",
    [
        f"(()=>{{const rules={json.dumps(PROSE)};globalThis.getRules=()=>rules;}})();",
        f"globalThis.rules={json.dumps(PROSE)};",
        f"!function(){{globalThis.rules={json.dumps(PROSE)};}}();",
        f"/* Bundled resource */\n'use strict';\nvar rules={json.dumps(PROSE * 50)};",
        f"(()=>{{const rules={json.dumps(PROSE * 50)};globalThis.getRules=()=>rules;}})();",
    ],
)
def test_programs_are_resources_even_when_their_literals_contain_prompt_markers(program):
    assert is_source_resource(program)
    assert is_static_resource(program)
    assert not is_prompt_like(program)
    assert extract_string_candidates(f"const resource={json.dumps(program)};") == []


@pytest.mark.parametrize(
    "metadata",
    [
        "export const meta = { name: ${JSON.stringify(name)}, phases: ${JSON.stringify(phases)} };",
        "export const meta = { name: '${name}', description: '${description}', phases: ${} };",
    ],
)
def test_program_templates_with_value_holes_are_resources(metadata):
    text = metadata + f"\nconst instructions = {json.dumps(PROSE)};\nrun(instructions);"
    assert is_source_resource(text)
    assert is_static_resource(text)
    assert extract_string_candidates(f"const resource={json.dumps(text)};") == []
    document = f"{PROSE}\n\n```javascript\n{text}\n```"
    assert not is_static_resource(document)
    assert extract_string_candidates(f"const prompt={json.dumps(document)};")[0].content == document


@pytest.mark.parametrize(
    "example",
    [
        "```html\n<!DOCTYPE html><html><head><style>.tool { color: red; }</style></head>"
        '<body><div class="tool"><section><h1>Title</h1><p>Review this page.</p></section></div></body></html>\n```',
        "```javascript\n// Initialize the collection.\n// Select useful values.\n// Print the output.\n"
        "const values = [1, 2, 3];\nvalues.forEach(console.log);\n```",
        "~~~powershell\n$params = @{}\n$input = 1\n$output = 2\n$first = 3\n$second = 4\n~~~",
        "````markdown\n```html\n<html><head><style>.tool { color: red; }</style></head>"
        '<body><div class="tool"><section><p>Example</p></section></div></body></html>\n```\n````',
    ],
)
@pytest.mark.parametrize("example_first", [False, True])
def test_document_code_examples_do_not_turn_prose_into_a_resource(example, example_first):
    text = f"{example}\n\n{PROSE}" if example_first else f"{PROSE}\n\n{example}"
    assert not is_source_resource(text)
    assert not is_static_resource(text)
    assert is_prompt_like(text)
    assert extract_string_candidates(f"const prompt={json.dumps(text)};")[0].content == text


def test_long_document_is_not_removed_just_because_it_has_no_prompt_score():
    text = "# 参考指南\n\n" + "此文档介绍配置选项、迁移步骤和完整示例。\n\n" * 1500
    assert len(text) > 20000
    assert not is_prompt_like(text)
    assert not is_static_resource(text)
    assert extract_string_candidates(f"const guide={json.dumps(text)};")[0].content == text.strip()
