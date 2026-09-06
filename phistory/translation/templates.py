"""Reuse capture-normalized prose while retaining each trace's literal values."""

from __future__ import annotations

import re
from functools import lru_cache

TOKEN = re.compile(r"\$PHISTORY_[A-Z_]+(?![A-Za-z0-9_])")
_TEMP_ROOT = re.compile(r"/(?:[\w.-]+/)*phistory-(home|work)-[A-Za-z0-9_-]+")


def restore_template(text: str, bindings: dict) -> str:
    """Restore once: literal values may themselves contain dollar signs or tokens."""
    tokens = TOKEN.findall(text)
    if any(tokens.count(name) != binding["count"] for name, binding in bindings.items()):
        raise ValueError("Translation changed capture placeholders")
    return TOKEN.sub(lambda match: bindings.get(match.group(), {"value": match.group()})["value"], text)


@lru_cache(maxsize=4096)
def trace_template(text: str) -> tuple[str, dict]:
    from phistory.capture import _sanitize_text

    replacements = {
        match.group(): "$PHISTORY_HOME" if match.group(1) == "home" else "$PHISTORY_WORKSPACE"
        for match in _TEMP_ROOT.finditer(text)
    }
    template = _sanitize_text(text, replacements)
    if template == text:
        return text, {}

    # The capture sanitizer also cleans presentation. Share only changes that can
    # be reversed exactly through its existing placeholders, with no prose edits.
    parts, names, end = [], [], 0
    for token in TOKEN.finditer(template):
        name = token.group()[1:]
        parts.append(re.escape(template[end : token.start()]))
        parts.append(f"(?P={name})" if name in names else f"(?P<{name}>[^\r\n]+?)")
        names.append(name)
        end = token.end()
    if not names:
        return text, {}
    parts.append(re.escape(template[end:]))
    match = re.fullmatch("".join(parts), text)
    if not match:
        return text, {}
    bindings = {
        "$" + name: {"value": value, "count": names.count(name)}
        for name, value in match.groupdict().items()
        if value != "$" + name
    }
    if restore_template(template, bindings) != text:
        return text, {}
    return template, bindings
