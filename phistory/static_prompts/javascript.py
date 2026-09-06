from __future__ import annotations

import hashlib
import re

import tree_sitter_javascript
from tree_sitter import Language, Node, Parser

from phistory.static_prompts.catalog import normalize_for_match
from phistory.static_prompts.models import StaticPromptCandidate

_VARIABLE_RE = re.compile(r"\$\{([^{}]{1,120})\}")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_TOKEN_RE = re.compile(r"\S+")
_HTML_TAG_RE = re.compile(r"</?(?:html|head|body|style|script|div|span|section|h[1-6]|p|a)\b", re.IGNORECASE)
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_TEMPLATE_HOLE_RE = re.compile(r"\$\{[^{}]*\}")
_PROGRAM_START_RE = re.compile(
    r"^(?:[\"'();!]|/\*|//|"
    r"(?:const|let|var|function|class|import|export|await|void|new)\b|async\s+function\b|"
    r"[A-Za-z_$][\w$]*\s*(?:[.\[(=]|\?\.))"
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "not",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "use",
    "when",
    "with",
    "you",
    "your",
}
_PROMPT_MARKERS = (
    "You are",
    "Your task",
    "You must",
    "IMPORTANT",
    "ONLY return",
    "Do not",
    "Never",
    "Claude Code",
    "system prompt",
    "system reminder",
    "tool",
    "instructions",
    "permission",
    "<policy_spec>",
)
_CODE_MARKERS = (
    "async function",
    "function ",
    "=>",
    "Object.defineProperty",
    "__webpack",
    "sourceMappingURL",
    "node_modules/",
)
_LANGUAGE = Language(tree_sitter_javascript.language())
_PARSER = Parser(_LANGUAGE)


def extract_string_candidates(source: str, *, min_length: int = 80) -> list[StaticPromptCandidate]:
    source_bytes = source.encode("utf-8", errors="surrogatepass")
    tree = _PARSER.parse(source_bytes)
    candidates: list[StaticPromptCandidate] = []
    seen: set[str] = set()
    for order, (kind, content) in enumerate(_iter_literals(tree.root_node, source_bytes)):
        content = content.strip()
        normalized = normalize_for_match(content)
        if len(normalized) < min_length:
            continue
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        score = _prompt_score(content)
        if is_static_resource(content):
            continue
        candidates.append(
            StaticPromptCandidate(
                id=digest[:16],
                content=content,
                kind=kind,
                score=score,
                order=order,
                variables=tuple(sorted(set(_variables(content)))),
            )
        )
    return candidates


def extract_prompt_candidates(source: str, *, min_score: int = 5) -> list[StaticPromptCandidate]:
    candidates = [
        candidate
        for candidate in extract_string_candidates(source)
        if is_prompt_like(candidate.content, min_score=min_score)
    ]
    return sorted(candidates, key=lambda item: (-item.score, item.order))


def is_prompt_like(text: str, *, min_score: int = 5) -> bool:
    return _prompt_score(text) >= min_score


def is_static_resource(text: str) -> bool:
    """Apply the same resource boundary to fresh literals and archived candidates."""
    stripped = _without_fenced_code(text).strip()
    lower_head = stripped[:1200].lower()
    return (
        _looks_like_encoded_blob(stripped)
        or _looks_like_regex_resource(stripped)
        or is_source_resource(stripped)
        or _looks_like_html_resource(stripped, lower_head)
        or _looks_like_script_resource(stripped, lower_head)
        or _looks_like_token_vocabulary(stripped, _WORD_RE.findall(stripped))
    )


def _without_fenced_code(text: str) -> str:
    # Code examples are part of a document, not evidence that the document is a program.
    if "```" not in text and "~~~" not in text:
        return text
    lines = []
    fence = ""
    for line in text.splitlines(keepends=True):
        match = _FENCE_RE.match(line.rstrip("\r\n"))
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = ""
            continue
        if match:
            fence = match[1]
        else:
            lines.append(line)
    return "".join(lines)


def is_source_resource(text: str) -> bool:
    """Recognize standalone programs and web resources before extracting their prose."""
    stripped = _without_fenced_code(text).strip()
    if stripped.startswith("#!"):
        return True
    # Resource metadata may precede the HTML; prose merely quoting tags is kept.
    html = re.sub(r"^(?:<!--.*?-->\s*)+", "", stripped, flags=re.DOTALL)
    if re.match(
        r"^(?:<!doctype\s+html(?:\s|>)|<(?:html|head|style|script)(?:\s|>)|"
        r"<title(?:\s[^>]*)?>.*?</title>\s*<(?:style|script)(?:\s|>))",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        return True
    if not _PROGRAM_START_RE.match(stripped):
        return False
    # Inspect the program opening: prompt words inside bundled strings are not evidence of prose.
    # Parse the complete text so a long first declaration or IIFE is not cut into an ERROR node.
    # Resource templates can contain value holes; substitute only in this disposable parsing copy.
    program = _TEMPLATE_HOLE_RE.sub("__phistory_value__", stripped)
    opening = _PARSER.parse(program.encode("utf-8", errors="surrogatepass"))
    for node in opening.root_node.named_children:
        if node.type in {"comment", "empty_statement"}:
            continue
        if node.has_error:
            return False
        if node.type == "expression_statement" and len(node.named_children) == 1:
            expression = node.named_children[0]
            if expression.type == "string":
                continue
            while expression.type in {"parenthesized_expression", "unary_expression", "await_expression"}:
                expression = expression.named_children[-1]
            return expression.type in {"call_expression", "assignment_expression"}
        return node.type in {
            "variable_declaration",
            "lexical_declaration",
            "function_declaration",
            "generator_function_declaration",
            "class_declaration",
            "import_statement",
            "export_statement",
        }
    return False


def _iter_literals(root: Node, source: bytes):
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "string":
            yield "string", _string_text(node, source)
            continue
        if node.type == "template_string":
            yield "template", _template_text(node, source)
            continue
        stack.extend(reversed(node.children))


def _string_text(node: Node, source: bytes) -> str:
    fragments = []
    for child in node.children:
        if child.type == "string_fragment":
            fragments.append(_decode_js_fragment(_slice(child, source)))
        elif child.type == "escape_sequence":
            fragments.append(_decode_escape_text(_slice(child, source)))
    if fragments:
        return "".join(fragments)
    raw = _slice(node, source)
    return _decode_js_fragment(raw[1:-1] if len(raw) >= 2 else raw)


def _template_text(node: Node, source: bytes) -> str:
    raw = _slice(node, source)
    body = raw[1:-1] if raw.startswith("`") and raw.endswith("`") else raw
    return _decode_js_fragment(body)


def _template_substitution(node: Node, source: bytes) -> str:
    raw = _slice(node, source).strip()
    if raw.startswith("${") and raw.endswith("}"):
        expression = raw[2:-1].strip()
    else:
        expression = raw
    expression = " ".join(expression.split())
    return "${" + expression[:160] + "}"


def _slice(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _decode_js_fragment(text: str) -> str:
    if "\\" not in text:
        return text
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "\\":
            out.append(text[index])
            index += 1
            continue
        decoded, index = _decode_escape(text, index)
        out.append(decoded)
    return "".join(out)


def _decode_escape_text(text: str) -> str:
    if not text.startswith("\\"):
        return text
    decoded, _ = _decode_escape(text, 0)
    return decoded


def _decode_escape(source: str, index: int) -> tuple[str, int]:
    if index + 1 >= len(source):
        return "\\", index + 1
    esc = source[index + 1]
    mapping = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
    if esc in mapping:
        return mapping[esc], index + 2
    if esc == "\n":
        return "", index + 2
    if esc == "u":
        if index + 2 < len(source) and source[index + 2] == "{":
            end = source.find("}", index + 3, index + 12)
            if end != -1:
                return _decode_codepoint(source[index + 3 : end]), end + 1
        value = source[index + 2 : index + 6]
        if len(value) == 4:
            return _decode_codepoint(value), index + 6
    if esc == "x":
        value = source[index + 2 : index + 4]
        if len(value) == 2:
            return _decode_codepoint(value), index + 4
    return esc, index + 2


def _decode_codepoint(value: str) -> str:
    try:
        codepoint = int(value, 16)
    except ValueError:
        return ""
    if 0xD800 <= codepoint <= 0xDFFF:
        return "\ufffd"
    try:
        return chr(codepoint)
    except ValueError:
        return "\ufffd"


def _prompt_score(text: str) -> int:
    compact = text.strip()
    if len(compact) < 120:
        return 0
    words = _WORD_RE.findall(compact)
    if len(words) < 24:
        return 0
    marker_hits = sum(1 for marker in _PROMPT_MARKERS if marker.lower() in compact.lower())
    natural_language = _natural_language_score(compact, words)
    if marker_hits == 0 and natural_language < 5:
        return 0
    if is_static_resource(compact):
        return 0
    if _looks_like_code(_without_fenced_code(compact), marker_hits):
        return 0

    score = marker_hits * 3 + natural_language
    if len(compact) >= 1000:
        score += 1
    if len(compact) >= 4000:
        score += 1
    if compact.count("\n") >= 3:
        score += 1
    return score


def _natural_language_score(text: str, words: list[str]) -> int:
    score = 0
    word_ratio = sum(len(word) for word in words) / max(len(text), 1)
    if word_ratio >= 0.42:
        score += 2
    if len(words) >= 60:
        score += 1
    if len(words) >= 140:
        score += 1
    sentence_marks = sum(text.count(char) for char in ".?!")
    if sentence_marks >= 3:
        score += 2
    if any(text.lstrip().startswith(prefix) for prefix in ("#", "-", "*", "1.", "<")):
        score += 1
    return score


def _looks_like_code(text: str, marker_hits: int) -> bool:
    stripped = text.lstrip()
    if stripped.startswith((";", "}", ")", "const ", "let ", "var ", "function ", "async function ")):
        return True
    lower = text.lower()
    if any(marker.lower() in lower[:600] for marker in _CODE_MARKERS) and marker_hits < 2:
        return True
    semicolons = text.count(";")
    newlines = text.count("\n")
    if semicolons > max(8, newlines * 2) and marker_hits < 3:
        return True
    operator_count = sum(text.count(token) for token in ("=>", "===", "!==", "&&", "||", "++", "--"))
    if operator_count > max(6, newlines + 2) and marker_hits < 3:
        return True
    brace_ratio = sum(text.count(char) for char in "{}[]();=") / max(len(text), 1)
    whitespace_ratio = sum(1 for char in text if char.isspace()) / max(len(text), 1)
    if brace_ratio > 0.10 and whitespace_ratio < 0.18 and marker_hits < 3:
        return True
    return False


def _looks_like_encoded_blob(text: str) -> bool:
    compact = text.strip()
    if len(compact) < 4096:
        return False
    whitespace_ratio = sum(1 for char in compact if char.isspace()) / len(compact)
    if whitespace_ratio > 0.02:
        return False
    allowed = sum(1 for char in compact if char.isalnum() or char in "+/=_-")
    if allowed / len(compact) < 0.96:
        return False
    return len(set(compact)) <= 80


def _looks_like_html_resource(stripped: str, lower_head: str) -> bool:
    if stripped.startswith("<!DOCTYPE html>") or stripped.startswith("<html"):
        return True
    html_tags = len(_HTML_TAG_RE.findall(stripped[:5000]))
    if html_tags >= 6 and (" class=" in lower_head or "<style" in lower_head or "<script" in lower_head):
        return True
    if html_tags >= 4 and stripped.count("${") >= 2:
        return True
    return False


def _looks_like_regex_resource(stripped: str) -> bool:
    head = stripped[:200]
    if not head.startswith("\\"):
        return False
    regex_tokens = ("\\b", "\\d", "\\s", "\\w", "(?:", "(?=", "[", "]", "|")
    return sum(head.count(token) for token in regex_tokens) >= 3


def _looks_like_script_resource(stripped: str, lower_head: str) -> bool:
    if "import-module az.accounts" in lower_head or "$params = @{" in lower_head:
        return True
    script_lines = 0
    for line in stripped.splitlines()[:30]:
        value = line.strip()
        if not value:
            continue
        if value.startswith(("$", "if ", "for ", "while ", "function ", "param(")):
            script_lines += 1
    return script_lines >= 5


def _looks_like_token_vocabulary(text: str, words: list[str]) -> bool:
    tokens = _TOKEN_RE.findall(text)
    if len(tokens) < 50:
        return False
    lines = [line for line in text.splitlines() if line.strip()]
    compact_block = len(lines) <= 4
    stopword_count = sum(1 for word in words if word.lower() in _STOPWORDS)
    stopword_ratio = stopword_count / max(len(words), 1)
    punct_token_count = sum(1 for token in tokens if any(char in token for char in ".!?|_<>+-=*/"))
    uppercase_count = sum(1 for token in tokens if token.isupper() and any(char.isalpha() for char in token))
    short_token_count = sum(1 for token in tokens if len(token.strip("!?|_<>+-=*/.")) <= 4)

    if compact_block and stopword_ratio < 0.035:
        return True
    if compact_block and punct_token_count / len(tokens) > 0.28 and stopword_ratio < 0.06:
        return True
    if compact_block and uppercase_count / len(tokens) > 0.55:
        return True
    if compact_block and short_token_count / len(tokens) > 0.58 and stopword_ratio < 0.07:
        return True
    return False


def _variables(text: str) -> list[str]:
    variables = []
    for match in _VARIABLE_RE.finditer(text):
        expression = " ".join(match.group(1).split())
        if expression:
            variables.append(expression)
    return variables
