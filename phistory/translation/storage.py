"""Deterministic shared dictionaries and lightweight source indexes."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .segments import EXTRACTOR_VERSION

_HASH = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")


def atomic_write_json(path: Path, data: dict, *, compact: bool = False) -> bool:
    """Replace complete JSON atomically, leaving unchanged files untouched."""
    rendered = (
        json.dumps(
            data,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
            sort_keys=True,
        )
        + "\n"
    )
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(rendered)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def dictionary_path(root: Path, agent: str, kind: str = "runtime", locale: str = "zh-CN") -> Path:
    if not all(_NAME.fullmatch(value) for value in (agent, locale)) or kind not in {"runtime", "static"}:
        raise ValueError("Invalid translation dictionary name")
    return root / locale / agent / f"{kind}.json"


def _validate_dictionary(data: Any, locale: str):
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("locale") != locale:
        raise ValueError("Unsupported translation dictionary")
    entries = data.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("Translation dictionary entries must be an object")
    for key, entry in entries.items():
        if not isinstance(key, str) or not _HASH.fullmatch(key) or not isinstance(entry, dict):
            raise ValueError("Invalid translation entry identity")
        if not isinstance(entry.get("text"), str) or not entry["text"].strip():
            raise ValueError(f"Empty translation entry: {key}")
        if not all(isinstance(entry.get(field), str) and entry[field] for field in ("model", "prompt_version")):
            raise ValueError(f"Missing translation provenance: {key}")


def read_dictionary(root: Path, agent: str, kind: str = "runtime", locale: str = "zh-CN") -> dict:
    path = dictionary_path(root, agent, kind, locale)
    if not path.exists():
        return {"schema_version": 1, "locale": locale, "entries": {}}
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
        _validate_dictionary(data, locale)
    except (ValueError, UnicodeError) as error:
        raise ValueError(f"Invalid translation dictionary {path}: {error}") from error
    return data


def write_dictionary(root: Path, agent: str, dictionary: dict, kind: str = "runtime", locale: str = "zh-CN") -> bool:
    _validate_dictionary(dictionary, locale)
    return atomic_write_json(dictionary_path(root, agent, kind, locale), dictionary)


def _validate_refs(refs: Any):
    if not isinstance(refs, list):
        raise ValueError("Source spans must be a list")
    end = 0
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("id"), str) or not _HASH.fullmatch(ref["id"]):
            raise ValueError("Invalid source span identity")
        if type(ref.get("start")) is not int or type(ref.get("end")) is not int:
            raise ValueError("Source span offsets must be integers")
        if (
            ref["start"] < end
            or ref["end"] <= ref["start"]
            or ref.get("kind") not in {"text", "json-string", "json-string-part"}
        ):
            raise ValueError("Invalid or overlapping source spans")
        depth = ref.get("escape_depth", 1)
        if type(depth) is not int or not 1 <= depth <= 8:
            raise ValueError("Invalid JSON escaping depth")
        end = ref["end"]


def _validate_source(data: Any, expected_hash: str | None = None):
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or data.get("extractor_version") != EXTRACTOR_VERSION
    ):
        raise ValueError("Unsupported source index")
    digest = data.get("source_hash")
    if (
        not isinstance(digest, str)
        or not _HASH.fullmatch(digest)
        or (expected_hash is not None and expected_hash != digest)
    ):
        raise ValueError("Source hash mismatch")
    if data.get("kind") == "markdown":
        _validate_refs(data.get("segments"))
    elif data.get("kind") == "trace":
        fields = data.get("fields")
        selected = data.get("selected_record")
        if not isinstance(fields, list) or (selected is not None and (type(selected) is not int or selected < 0)):
            raise ValueError("Invalid trace source index")
        visited = set()
        for field in fields:
            if not isinstance(field, dict) or type(field.get("record")) is not int or field["record"] != selected:
                raise ValueError("Invalid trace record reference")
            pointer = field.get("pointer")
            if (
                not isinstance(pointer, str)
                or not pointer.startswith("/")
                or re.search(r"~(?![01])", pointer)
                or pointer in visited
            ):
                raise ValueError("Invalid or duplicate trace field pointer")
            visited.add(pointer)
            _validate_refs(field.get("segments"))
    else:
        raise ValueError("Unknown translation source kind")


def source_path(index: dict) -> str:
    _validate_source(index)
    return f"sources/{index['source_hash']}-v{index['extractor_version']}.json"


def write_source(root: Path, index: dict) -> str:
    path = source_path(index)
    atomic_write_json(root / path, index, compact=True)
    return path


def read_source(path: Path, expected_hash: str | None = None) -> dict | None:
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
        _validate_source(data, expected_hash)
    except (OSError, ValueError, UnicodeError):
        return None
    return data
