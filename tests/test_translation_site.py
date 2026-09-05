import json
import shutil
import subprocess
from pathlib import Path

import pytest

from phistory.site import render_site

SCRIPT = Path(__file__).parents[1] / "phistory/web/translation.js"


def run_javascript(body: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for frontend behavior tests")
    script = "const assert = require('node:assert/strict');\n" + SCRIPT.read_text() + "\n" + body
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_unicode_offsets_and_schema_strings_preserve_json_structure():
    run_javascript(r"""
const source = '🚀 {"name":"read_file","description":"Read a file."}';
const points = Array.from(source);
const start = points.join('').indexOf('"Read') - 1;
const end = start + Array.from('"Read a file."').length;
const document = translationDocument(source, [{id:'read',start,end,kind:'json-string'}],
  {read:{text:'读取文件，保留 "path" 参数。'}});
const result = translatedRange(document);
assert.equal(result.missing, 0);
assert.deepEqual(JSON.parse(result.text.slice(3)), {
  name:'read_file', description:'读取文件，保留 "path" 参数。'
});
assert.equal(document.source, source);
""")


def test_diff_aligns_whole_paragraphs_and_falls_back_as_a_pair():
    run_javascript(r"""
const oldText = '# Rules\n\nAlways inspect files.\nThen ask the user.\n\nDone.\n';
const newText = '# Rules\n\nAlways inspect files.\nThen ask only if needed.\n\nDone.\n';
const make = (source, translated) => translationDocument(source,
  [{id:'rules',start:9,end:source.indexOf('\n\nDone'),kind:'text'}], translated ? {rules:{text:'始终检查文件，然后按需询问用户。'}} : {});
const changes = [{originalStartLineNumber:4, originalEndLineNumber:4, modifiedStartLineNumber:4, modifiedEndLineNumber:4}];
const rows = alignSourceBlocks([make(oldText,true),make(newText,false)], changes);
const changed = rows.filter(row=>row.changed);
assert.equal(changed.length, 1);
assert.equal(changed[0].start[0], 2);
assert.equal(changed[0].end[0], 5);
assert.equal(changed[0].fallback, true);
assert.match(changed[0].sides[0].source, /Always inspect files/);
assert.equal(rows.map(row=>row.sides[0].source).join(''),oldText);
assert.equal(rows.map(row=>row.sides[1].source).join(''),newText);
""")


def test_nested_json_description_parts_escape_without_changing_code():
    run_javascript(r"""
const description = 'Read "path".\nKeep `read_file` unchanged.';
const nested = JSON.stringify({description});
const source = JSON.stringify({description:nested});
const encoded = value => JSON.stringify(JSON.stringify(value).slice(1,-1)).slice(1,-1);
const oldPart = encoded('Read "path".');
const start = source.indexOf(oldPart);
const document = translationDocument(source,
  [{id:'a',start,end:start+oldPart.length,kind:'json-string-part',escape_depth:2}],
  {a:{text:'读取 "path"。'}});
const translated = JSON.parse(JSON.parse(translatedRange(document).text).description);
assert.equal(translated.description,'读取 "path"。\nKeep `read_file` unchanged.');
""")


def test_changed_json_description_keeps_its_markdown_fence_intact():
    run_javascript(r"""
const original='# Tool\n\n```json\n{\n  "description": "Read a file."\n}\n```\n\nDone.\n';
const modified=original.replace('Read a file.','Read files.');
const make=source=>translationDocument(source,[]);
const change={originalStartLineNumber:5,originalEndLineNumber:5,modifiedStartLineNumber:5,modifiedEndLineNumber:5};
const changed=alignSourceBlocks([make(original),make(modified)],[change]).filter(row=>row.changed);
assert.equal(changed.length,1);
assert.match(changed[0].sides[0].source,/^```json\n/);
assert.match(changed[0].sides[0].source,/\n```\n/);
assert.equal(changed[0].start[0],2);
""")


def test_equal_original_shares_translation_without_false_changes():
    run_javascript(r"""
const source = 'Read the file.\n';
const complete = translationDocument(source,[{id:'a',start:0,end:14,kind:'text'}],{a:{text:'读取文件。'}});
const missing = translationDocument(source,undefined);
const rows = alignSourceBlocks([missing,complete],[]);
assert.equal(rows.length,1);
assert.equal(rows[0].changed,false);
assert.equal(rows[0].fallback,false);
assert.equal(rows[0].sides[0].text,rows[0].sides[1].text);
assert.match(rows[0].sides[0].text,/读取文件/);
""")


def test_native_diff_assembly_preserves_source_changes_and_line_mapping():
    run_javascript(r"""
const original='Read the file.\n\nThen ask the user.\n';
const modified='Read this file.\n\nThen ask the user.\n';
const make=source=>translationDocument(source,
  [{id:'a',start:0,end:source.indexOf('\n'),kind:'text'}], {a:{text:'读取文件。'}});
const change={originalStartLineNumber:1,originalEndLineNumber:1,modifiedStartLineNumber:1,modifiedEndLineNumber:1};
const result=assembleTranslationComparison([make(original),make(modified)],[change]);
assert.equal(result.texts[0],result.texts[1]);
assert.equal(result.hiddenChanges.length,1);
assert.equal(result.texts[0],'读取文件。\n\nThen ask the user.\n');
assert.equal(mapTranslationLine(result.maps[1],3),3);
assert.equal(mapTranslationLine(result.maps[1],3,true),3);
const expanded=translationDocument(original,
  [{id:'a',start:0,end:14,kind:'text'}],{a:{text:'先阅读\n文件。'}});
const result2=assembleTranslationComparison([expanded,expanded],[]);
assert.equal(mapTranslationLine(result2.maps[1],3),4);
assert.equal(mapTranslationLine(result2.maps[1],4,true),3);
""")


def test_monaco_source_models_are_not_replaced_inside_its_diff_callback():
    run_javascript(r"""
const document=translationDocument('Read the file.\n',[]);
const comparison={documents:[document,document],sequence:1};
const state={language:'zh-CN',translationComparison:comparison,editor:{getLineChanges:()=>[]}};
const isCurrentRender=sequence=>sequence===1;
let callbackActive=true;
let rendered=false;
renderComparisonLanguage=()=>{assert.equal(callbackActive,false);rendered=true;};
renderTranslationComparison();
assert.equal(rendered,false);
callbackActive=false;
queueMicrotask(()=>{assert.equal(rendered,true);assert.equal(comparison.ready,true);});
""")


def test_translation_waits_for_current_monaco_diff_after_model_updates():
    run_javascript(r"""
const document=translationDocument('Read the file.\n',[]);
const comparison={documents:[document,document],sequence:1};
const state={language:'zh-CN',translationComparison:comparison,monacoDiffReady:false,
  editor:{getLineChanges:()=>[]}};
const isCurrentRender=sequence=>sequence===1;
let rendered=false;
renderComparisonLanguage=()=>{rendered=true;};
renderTranslationComparison();
assert.equal(comparison.preparing,undefined);
assert.equal(rendered,false);
state.monacoDiffReady=true;
renderTranslationComparison();
queueMicrotask(()=>assert.equal(rendered,true));
""")


def test_source_change_markers_are_cleared_when_switching_back_to_original():
    run_javascript(r"""
const collections=[0,1].map(()=>({items:[],set(items){this.items=items;},clear(){this.items=[];}}));
const comparison={ready:true,texts:['中文','中文'],documents:[{source:'A'},{source:'B'}],
  total:2,missing:0,hiddenChanges:[[[1,1],[1,1]]]};
const state={language:'zh-CN',translationComparison:comparison,translationDecorations:collections,
  monaco:{Range:class {}}};
state.editor={getModel:()=>Object.fromEntries(['original','modified'].map((key,side)=>
  [key,{getValue:()=>state.language==='zh-CN'?comparison.texts[side]:comparison.documents[side].source}]))};
const els={language:{}};
restoreTranslationPosition=()=>{};
for(let index=0;index<10;index++){
  state.language='zh-CN';renderComparisonLanguage();
  assert.ok(collections.every(collection=>collection.items.length===1));
  state.language='original';renderComparisonLanguage();
  assert.ok(collections.every(collection=>collection.items.length===0));
}
assert.equal(state.translationDecorations,collections);
""")


def test_insertions_deletions_and_empty_snapshots_preserve_alignment():
    run_javascript(r"""
const make = source => translationDocument(source,[]);
for (const [oldText,newText,change] of [
  ['A\n\nC','A\n\nB\n\nC',{originalStartLineNumber:2,originalEndLineNumber:0,modifiedStartLineNumber:3,modifiedEndLineNumber:4}],
  ['A\n\nB\n\nC','A\n\nC',{originalStartLineNumber:3,originalEndLineNumber:4,modifiedStartLineNumber:2,modifiedEndLineNumber:0}],
  ['','New',{originalStartLineNumber:1,originalEndLineNumber:1,modifiedStartLineNumber:1,modifiedEndLineNumber:1}]
]) {
  const rows = alignSourceBlocks([make(oldText),make(newText)],[change]);
  assert.equal(rows.map(row=>row.sides[0].source).join(''),oldText);
  assert.equal(rows.map(row=>row.sides[1].source).join(''),newText);
  assert.ok(rows.some(row=>row.changed));
}
""")


def test_invalid_segments_and_missing_words_leave_original_intact():
    run_javascript(r"""
const source = 'Keep the source.';
for (const segments of [undefined,[null],[{id:'x',start:0,end:99,kind:'text'}],
  [{id:'x',start:0,end:4,kind:'text'},{id:'y',start:2,end:5,kind:'text'}]]) {
  const result = translatedRange(translationDocument(source,segments,{x:{text:'bad'}}));
  assert.equal(result.text,source);
  assert.equal(result.missing,1);
}
const document=translationDocument(source,[{id:'x',start:0,end:16,kind:'text'}],{x:{text:''}});
assert.equal(translatedRange(document).text,source);
""")


def test_trace_pointer_validation_and_original_data_are_preserved():
    run_javascript(r"""
const source = {request:{body:{'a/b':{'~text':'Read a file.'},tools:[{description:'Run a command.'}]}}};
const record = JSON.parse(JSON.stringify(source));
const target = pointerTarget(record,'/request/body/a~1b/~0text');
target.parent[target.key]='读取文件。';
assert.equal(source.request.body['a/b']['~text'],'Read a file.');
assert.equal(record.request.body['a/b']['~text'],'读取文件。');
assert.equal(pointerTarget(record,'/request/body/__proto__/polluted'),null);
assert.equal(pointerTarget(record,'/request/body/missing'),null);
assert.equal(pointerTarget(record,'not-a-pointer'),null);
""")


def test_translation_loader_rejects_stale_and_unavailable_assets():
    run_javascript(r"""
const state = {translationCache:new Map()};
const location = {href:'https://example.test/index.html',origin:'https://example.test'};
globalThis.crypto = require('node:crypto').webcrypto;
const source='Read a file.';
const hash=require('node:crypto').createHash('sha256').update(source).digest('hex');
const item={translations:{'zh-CN':{prompt:{index:'index.json',fingerprint:'a'},runtime:{path:'words.json',fingerprint:'b'}}}};
const index={schema_version:1,kind:'markdown',source_hash:hash,segments:[]};
let calls=0;
globalThis.fetch=async url=>{calls++;return {ok:true,json:async()=>url.includes('words')
  ? {schema_version:1,locale:'zh-CN',entries:{}}:index};};
(async()=>{
  assert.ok(await loadTranslation(item,'prompt',source));
  assert.ok(await loadTranslation(item,'prompt',source));
  assert.equal(calls,2);
  assert.equal(await loadTranslation(item,'prompt','Changed.'),null);
  assert.equal(await loadTranslation({},'prompt',source),null);
  state.translationCache.clear();
  globalThis.fetch=async()=>{throw new Error('offline');};
  assert.equal(await loadTranslation(item,'prompt',source),null);
  assert.equal(state.translationCache.size,0);
})().catch(error=>{console.error(error);process.exitCode=1;});
""")


def test_site_embeds_translation_assets_without_language_query_parameters(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for frontend syntax checks")
    captures = tmp_path / "captures"
    captures.mkdir()
    output = tmp_path / "index.html"
    render_site(captures, output)
    html = output.read_text()
    assert "__TRANSLATION_" not in html
    assert 'id="language"' in html
    assert "localStorage.setItem('phistory-language'" in html
    assert 'class="translation-view"' not in html
    assert 'class="translation-row' not in html
    script = html.split("<script>")[-1].split("</script>")[0]
    script_path = tmp_path / "site.js"
    script_path.write_text(script)
    result = subprocess.run([node, "--check", str(script_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    query_code = script.split("function writeQuery()")[1].split("function ensureAvailableView()")[0]
    assert "language" not in query_code and "zh-CN" not in query_code
    manifest = json.loads(html.split('<script id="manifest" type="application/json">')[1].split("</script>")[0])
    assert manifest["agents"] == []
