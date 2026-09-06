function storedLanguage() {
  try { return localStorage.getItem('phistory-language') === 'zh-CN' ? 'zh-CN' : 'original'; }
  catch { return 'original'; }
}

function setLanguage(language) {
  if (state.view === 'static' || !['original', 'zh-CN'].includes(language) || state.language === language) return;
  saveTraceState();
  rememberTranslationPosition();
  state.language = language;
  try { localStorage.setItem('phistory-language', state.language); } catch {}
  renderControls();
  if (state.view !== 'trace' && state.translationComparison?.ready) {
    renderComparisonLanguage();
  } else {
    refreshView();
  }
}

function translationAssetUrl(path, fingerprint) {
  const url = new URL(path, location.href);
  if (url.origin !== location.origin) throw new Error('Invalid translation asset origin.');
  if (fingerprint) url.searchParams.set('v', fingerprint);
  return url.pathname + url.search;
}

async function loadTranslationJson(path, fingerprint) {
  const url = translationAssetUrl(path, fingerprint);
  if (!state.translationCache.has(url)) {
    const pending = fetch(url).then(response => {
      if (!response.ok) throw new Error('Translation unavailable.');
      return response.json();
    }).catch(error => {
      state.translationCache.delete(url);
      throw error;
    });
    state.translationCache.set(url, pending);
  }
  return state.translationCache.get(url);
}

async function sourceHashMatches(source, expected) {
  if (!/^[a-f0-9]{64}$/.test(expected || '') || !globalThis.crypto?.subtle) return false;
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(source));
  return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('') === expected;
}

async function loadTranslation(item, kind, source) {
  // A source index references shared dictionary entries; stale indexes must never rewrite new source text.
  if (!['prompt', 'trace'].includes(kind)) return null;
  const metadata = item.translations?.['zh-CN'];
  const descriptor = metadata?.[kind];
  const dictionary = metadata?.runtime;
  if (!descriptor?.index || !dictionary?.path) return null;
  try {
    const [index, words] = await Promise.all([
      loadTranslationJson(descriptor.index, descriptor.fingerprint),
      loadTranslationJson(dictionary.path, dictionary.fingerprint)
    ]);
    if (index.schema_version !== 1 || words.schema_version !== 1 || words.locale !== 'zh-CN') return null;
    if (!words.entries || typeof words.entries !== 'object' || Array.isArray(words.entries)) return null;
    if (index.kind !== (kind === 'trace' ? 'trace' : 'markdown')) return null;
    if (kind === 'trace' && (!Array.isArray(index.fields) || !index.fields.every(field => field
      && Number.isInteger(field.record) && field.record >= 0 && typeof field.pointer === 'string'
      && field.pointer.startsWith('/') && Array.isArray(field.segments)))) return null;
    if (!await sourceHashMatches(source, index.source_hash)) return null;
    return { index, entries: words.entries };
  } catch { return null; }
}

function validTranslationBindings(bindings) {
  return bindings === undefined || (bindings && typeof bindings === 'object' && !Array.isArray(bindings)
    && Object.entries(bindings).every(([token, binding]) => /^\$PHISTORY_[A-Z_]+$/.test(token)
      && binding && typeof binding === 'object' && !Array.isArray(binding)
      && typeof binding.value === 'string' && binding.value.length > 0 && !/[\r\n]/.test(binding.value)
      && Number.isSafeInteger(binding.count) && binding.count > 0));
}

function restoreTranslationBindings(text, bindings) {
  if (!bindings) return text;
  const tokens = text.match(/\$PHISTORY_[A-Z_]+(?![A-Za-z0-9_])/g) || [];
  if (Object.entries(bindings).some(([token, binding]) => tokens.filter(value => value === token).length !== binding.count)) return null;
  // Restore each occurrence's literals once, before JSON escaping; values may contain dollars and backslashes.
  return text.replace(/\$PHISTORY_[A-Z_]+(?![A-Za-z0-9_])/g,
    token => Object.hasOwn(bindings, token) ? bindings[token].value : token);
}

function translationDocument(source, segments, entries = {}) {
  // Python records Unicode code-point offsets, whereas JavaScript string offsets count UTF-16 units.
  const points = Array.from(source);
  let end = 0;
  const valid = Array.isArray(segments) && segments.every(segment => {
    if (!segment || typeof segment !== 'object') return false;
    const ok = typeof segment.id === 'string' && Number.isInteger(segment.start) && Number.isInteger(segment.end)
      && segment.start >= end && segment.end > segment.start && segment.end <= points.length
      && ['text', 'json-string', 'json-string-part'].includes(segment.kind)
      && validTranslationBindings(segment.bindings)
      && (segment.escape_depth === undefined || (Number.isInteger(segment.escape_depth) && segment.escape_depth > 0 && segment.escape_depth <= 16));
    end = segment.end;
    return ok;
  });
  return { source, points, segments: valid ? segments : null, entries };
}

function translatedRange(document, start = 0, end = document.points.length) {
  const source = document.points.slice(start, end).join('');
  if (!document.segments) return { source, text: source, missing: source.trim() ? 1 : 0, total: source.trim() ? 1 : 0 };
  const result = [];
  let cursor = start;
  let missing = 0;
  let total = 0;
  for (const segment of document.segments) {
    if (segment.end <= start) continue;
    if (segment.start >= end) break;
    total++;
    let text = Object.hasOwn(document.entries, segment.id) ? document.entries[segment.id]?.text : null;
    if (typeof text === 'string') text = restoreTranslationBindings(text, segment.bindings);
    if (typeof text !== 'string' || !text.trim() || segment.start < start || segment.end > end) {
      missing++;
      continue;
    }
    result.push(document.points.slice(cursor, segment.start).join(''));
    let replacement = segment.kind === 'json-string' ? JSON.stringify(text) : text;
    if (segment.kind === 'json-string-part') {
      for (let depth = 0; depth < (segment.escape_depth || 1); depth++) replacement = JSON.stringify(replacement).slice(1, -1);
    }
    result.push(replacement);
    cursor = segment.end;
  }
  result.push(document.points.slice(cursor, end).join(''));
  return { source, text: result.join(''), missing, total };
}

async function prepareTranslationComparison(from, to, original, modified, sequence) {
  if (state.language !== 'zh-CN') return;
  const translations = await Promise.all([
    loadTranslation(from, 'prompt', original), loadTranslation(to, 'prompt', modified)
  ]);
  if (!isCurrentRender(sequence)) return;
  const documents = [original, modified].map((source, index) => {
    const data = translations[index];
    return translationDocument(source, data?.index.segments, data?.entries);
  });
  state.translationComparison = { documents, sequence };
  renderTranslationComparison();
}

function documentLines(document) {
  const lines = document.source.split('\n');
  const offsets = [0];
  for (let i = 0; i < lines.length; i++) {
    offsets.push(offsets.at(-1) + Array.from(lines[i]).length + (i < lines.length - 1 ? 1 : 0));
  }
  let segmentIndex = 0;
  const segments = document.segments || [];
  const safe = offsets.map(offset => {
    while (segmentIndex < segments.length && segments[segmentIndex].end <= offset) segmentIndex++;
    const segment = segments[segmentIndex];
    return !segment || offset <= segment.start || offset >= segment.end;
  });
  let fence = null;
  for (let index = 0; index < lines.length; index++) {
    const marker = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(lines[index]);
    if (fence) {
      safe[index] = false;
      if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && !marker[2].trim()) fence = null;
    } else if (marker) {
      fence = marker[1];
    }
    if (index > 0 && lines[index].includes('|') && lines[index - 1].includes('|')) safe[index] = false;
  }
  return { lines, offsets, safe };
}

function sourceChangeRange(change, side) {
  const start = change[`${side}StartLineNumber`];
  const end = change[`${side}EndLineNumber`];
  return end === 0 ? [start, start] : [start - 1, end];
}

function alignSourceBlocks(documents, changes) {
  // Expand source hunks to safe prose/code boundaries before applying translations or paired fallback.
  const [oldLines, newLines] = documents.map(documentLines);
  const boundaries = [[0, 0]];
  const appendEqual = (oldStart, oldEnd, newStart, newEnd) => {
    if (oldEnd - oldStart !== newEnd - newStart) return;
    for (let offset = 0; offset <= oldEnd - oldStart; offset++) {
      const oldLine = oldStart + offset;
      const newLine = newStart + offset;
      const edge = offset === 0 || oldLine === oldEnd;
      if ((edge || !oldLines.lines[oldLine - 1]?.trim() || /^#{1,6} /.test(oldLines.lines[oldLine] || ''))
          && oldLines.safe[oldLine] && newLines.safe[newLine]) boundaries.push([oldLine, newLine]);
    }
  };
  let oldCursor = 0;
  let newCursor = 0;
  for (const change of changes) {
    const [oldStart, oldEnd] = sourceChangeRange(change, 'original');
    const [newStart, newEnd] = sourceChangeRange(change, 'modified');
    appendEqual(oldCursor, oldStart, newCursor, newStart);
    oldCursor = oldEnd;
    newCursor = newEnd;
  }
  appendEqual(oldCursor, oldLines.lines.length, newCursor, newLines.lines.length);
  boundaries.push([oldLines.lines.length, newLines.lines.length]);
  const unique = boundaries.filter((value, index) => index === 0 || value.some((line, side) => line !== boundaries[index - 1][side]));
  const rows = [];
  for (let index = 1; index < unique.length; index++) {
    const start = unique[index - 1];
    const end = unique[index];
    const sides = documents.map((document, side) => {
      const lines = side === 0 ? oldLines : newLines;
      return translatedRange(document, lines.offsets[start[side]], lines.offsets[end[side]]);
    });
    const changed = sides[0].source !== sides[1].source;
    if (!changed) {
      const preferred = sides[0].missing <= sides[1].missing ? sides[0] : sides[1];
      sides[0] = preferred;
      sides[1] = preferred;
    }
    if (sides.every(side => !side.source.trim()) && rows.length) {
      const previous = rows.at(-1);
      previous.end = end;
      previous.sides = previous.sides.map((item, side) => ({
        ...item, source: item.source + sides[side].source, text: item.text + sides[side].text
      }));
      continue;
    }
    rows.push({ start, end, sides, changed, fallback: changed && sides.some(side => side.missing > 0) });
  }
  return rows;
}

function assembleTranslationComparison(documents, changes) {
  // Equal source blocks share one translation. Chinese wording must not create changes on its own.
  const blocks = alignSourceBlocks(documents, changes);
  const texts = ['', ''];
  const maps = [[], []];
  const positions = [1, 1];
  const hiddenChanges = [];
  for (const block of blocks) {
    const translated = block.sides.map(item => block.fallback ? item.source : item.text);
    const starts = [...positions];
    translated.forEach((text, side) => {
      texts[side] += text;
      positions[side] += (text.match(/\n/g) || []).length;
      maps[side].push({
        sourceStart: block.start[side] + 1, sourceEnd: block.end[side] + 1,
        translatedStart: starts[side], translatedEnd: positions[side]
      });
    });
    if (block.changed && translated[0] === translated[1]) {
      hiddenChanges.push(starts.map((start, side) => [start, Math.max(start, positions[side] - 1)]));
    }
  }
  const totals = documents.map(document => translatedRange(document));
  return {
    texts, maps, hiddenChanges,
    total: totals.reduce((sum, item) => sum + item.total, 0),
    missing: totals.reduce((sum, item) => sum + item.missing, 0)
  };
}

function mapTranslationLine(mapping, line, reverse = false) {
  // Line counts may change during translation; preserve the logical reading position within each block.
  const from = reverse ? 'translated' : 'source';
  const to = reverse ? 'source' : 'translated';
  const entry = mapping.find(item => line >= item[`${from}Start`] && line < item[`${from}End`]) || mapping.at(-1);
  if (!entry) return Math.max(1, line);
  const fromLength = Math.max(1, entry[`${from}End`] - entry[`${from}Start`]);
  const toLength = Math.max(1, entry[`${to}End`] - entry[`${to}Start`]);
  const offset = Math.floor(Math.max(0, line - entry[`${from}Start`]) * toLength / fromLength);
  return entry[`${to}Start`] + Math.min(toLength - 1, offset);
}

function rememberTranslationPosition() {
  if (!state.editor || state.view === 'trace') return;
  const editor = state.editor.getModifiedEditor();
  const line = editor.getVisibleRanges()[0]?.startLineNumber || editor.getPosition()?.lineNumber || 1;
  state.translationPosition = state.language === 'zh-CN' && state.translationComparison?.ready
    ? mapTranslationLine(state.translationComparison.maps[1], line, true) : line;
}

function restoreTranslationPosition() {
  if (!state.translationPosition || !state.editor) return;
  const ready = state.translationComparison?.ready;
  const line = state.language === 'zh-CN' && ready
    ? mapTranslationLine(state.translationComparison.maps[1], state.translationPosition)
    : state.translationPosition;
  const editor = state.editor.getModifiedEditor();
  editor.setScrollTop(editor.getTopForLineNumber(Math.min(line, editor.getModel().getLineCount())));
  if (state.language !== 'zh-CN' || ready) state.translationPosition = null;
}

function renderTranslationComparison() {
  // Read Monaco's original-source hunks once, then keep the same editor UI for the assembled Chinese text.
  const comparison = state.translationComparison;
  if (!comparison || comparison.ready || comparison.preparing || !isCurrentRender(comparison.sequence) || state.language !== 'zh-CN' || !state.editor || state.monacoDiffReady === false) return;
  const changes = state.editor.getLineChanges();
  if (!changes) return;
  comparison.preparing = true;
  const assembled = assembleTranslationComparison(comparison.documents, changes);
  // Let Monaco finish notifying its listeners before replacing either source model.
  queueMicrotask(() => {
    if (!isCurrentRender(comparison.sequence) || state.translationComparison !== comparison) return;
    Object.assign(comparison, assembled, { ready: true });
    renderComparisonLanguage();
  });
}

function renderComparisonLanguage() {
  const comparison = state.translationComparison;
  if (!comparison?.ready) return;
  const translated = state.language === 'zh-CN';
  const texts = translated ? comparison.texts : comparison.documents.map(document => document.source);
  const models = state.editor?.getModel();
  if (models?.original.getValue() !== texts[0] || models?.modified.getValue() !== texts[1]) {
    renderMonacoDiff(...texts);
  } else {
    restoreTranslationPosition();
  }
  if (!translated) {
    state.translationDecorations?.forEach(collection => collection.clear());
    return;
  }
  const available = comparison.total - comparison.missing;
  const coverage = comparison.total ? Math.round(100 * available / comparison.total) : 100;
  const status = comparison.missing ? (available ? `译文就绪 ${coverage}%，缺译的变更段落整段显示原文。` : '暂无中文译文，显示原文。') : '当前显示中文翻译。';
  els.language.title = `${status} 版本变更统计依据原文。`;
  if (comparison.hiddenChanges.length) els.language.title += ' 黄色行标记表示原文有修改、中文相同。';
  state.translationDecorations.forEach((collection, side) => {
    collection.set(comparison.hiddenChanges.map(ranges => ({
      range: new state.monaco.Range(ranges[side][0], 1, ranges[side][1], 1),
      options: {
        isWholeLine: true,
        className: 'source-only-change',
        linesDecorationsClassName: 'source-change-marker',
        hoverMessage: { value: '原文有修改，中文译文相同。切换「原文」查看具体变化。' },
        overviewRuler: { color: '#c69026', position: 7 }
      }
    })));
  });
}

function translationNoticeHtml(status) {
  const available = Math.max(0, status.total - status.missing);
  const coverage = status.total ? Math.round(100 * available / status.total) : 100;
  const label = status.missing ? (available ? `中文 ${coverage}% · 未完成部分显示原文` : '暂无可用中文翻译，显示原文') : '中文翻译';
  return `<div class="translation-notice" role="status"><span>${label}</span><small>原始请求与工具定义保留原文</small></div>`;
}

function originalTextHtml(text, original, label = '查看原文') {
  if (typeof original !== 'string' || text === original) return '';
  return `<details class="translation-original"><summary>${escapeHtml(label)}</summary><pre>${escapeHtml(original)}</pre></details>`;
}

function pointerTarget(record, pointer) {
  if (typeof pointer !== 'string' || !pointer.startsWith('/')) return null;
  const parts = pointer.slice(1).split('/').map(part => part.replace(/~1/g, '/').replace(/~0/g, '~'));
  let parent = record;
  for (const part of parts.slice(0, -1)) {
    if (['__proto__', 'prototype', 'constructor'].includes(part) || !parent || !Object.hasOwn(parent, part)) return null;
    parent = parent[part];
  }
  const key = parts.at(-1);
  return parent && !['__proto__', 'prototype', 'constructor'].includes(key) && Object.hasOwn(parent, key) ? { parent, key } : null;
}

async function translateTraceDetail(item, records, selected, original) {
  const source = state.cache.get(captureAssetUrl(item, item.trace));
  const data = typeof source === 'string' ? await loadTranslation(item, 'trace', source) : null;
  if (!data || !Array.isArray(data.index.fields)) return { ...original, translation: { total: 1, missing: 1 } };
  const record = JSON.parse(JSON.stringify(selected.record));
  const status = { total: 0, missing: 0 };
  const seen = new Set();
  for (const field of data.index.fields) {
    if (field.record !== selected.index) continue;
    const target = pointerTarget(record, field.pointer);
    if (!target || typeof target.parent[target.key] !== 'string' || seen.has(field.pointer)) {
      return { ...original, translation: { total: 1, missing: 1 } };
    }
    seen.add(field.pointer);
    const result = translatedRange(translationDocument(target.parent[target.key], field.segments, data.entries));
    status.total += result.total;
    status.missing += result.missing;
    target.parent[target.key] = result.text;
  }
  const detail = normalizeTraceRecord(record, selected.index, records.length);
  for (const key of ['systemBlocks', 'developerBlocks', 'messages']) {
    detail[key].forEach((block, index) => { block.originalText = original[key][index]?.text; });
  }
  detail.tools.forEach((tool, index) => {
    tool.raw = original.tools[index]?.raw;
    tool.originalDescription = original.tools[index]?.description;
    tool.originalParameters = schemaParameters(original.tools[index]?.schema);
  });
  detail.rawBody = original.rawBody;
  detail.translation = status;
  return detail;
}
