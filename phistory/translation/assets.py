from __future__ import annotations

import hashlib
from pathlib import Path

from phistory.translation.segments import extract_markdown, extract_trace
from phistory.translation.storage import dictionary_path, read_dictionary, source_path, write_source
from phistory.translation.templates import restore_template


class TranslationAssets:
    """Build disposable source indexes and page metadata from published archives and dictionaries."""

    def __init__(self, public_root: Path):
        self.base = public_root
        self.root = self.base / "translations"
        self.dictionaries = {}
        self.sources = {}
        self.fingerprints = {}

    def _fingerprint(self, path: Path) -> str:
        if path not in self.fingerprints:
            self.fingerprints[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        return self.fingerprints[path]

    def _path(self, path: Path) -> str:
        return path.relative_to(self.base).as_posix()

    def for_row(self, row: dict) -> dict:
        if not self.root.exists():
            return {}
        dictionary = dictionary_path(self.root, row["agent_id"])
        if not dictionary.exists():
            return {}
        if dictionary not in self.dictionaries:
            try:
                self.dictionaries[dictionary] = read_dictionary(self.root, row["agent_id"])
            except (OSError, ValueError):
                self.dictionaries[dictionary] = None
        data = self.dictionaries[dictionary]
        if data is None:
            return {}
        result = {}
        for surface in ("prompt", "trace"):
            path = row.get(surface)
            if not path:
                continue
            digest = self._fingerprint(path)
            if digest not in self.sources:
                extract = extract_markdown if surface == "prompt" else extract_trace
                source = extract(path.read_bytes().decode("utf-8")).index
                write_source(self.root, source)
                self.sources[digest] = source
            source = self.sources[digest]
            index_path = self.root / source_path(source)
            refs = (
                source.get("segments", [])
                if source["kind"] == "markdown"
                else [ref for field in source["fields"] for ref in field["segments"]]
            )
            available = []
            for ref in refs:
                entry = data["entries"].get(ref["id"])
                if entry is None:
                    continue
                if ref.get("bindings"):
                    try:
                        restore_template(entry["text"], ref["bindings"])
                    except ValueError:
                        # Match the browser: an unusable template falls back to its original source.
                        continue
                available.append(ref)
            result[surface] = {
                "index": self._path(index_path),
                "fingerprint": self._fingerprint(index_path)[:16],
                "source_hash": digest,
                "total": len(refs),
                "translated": len(available),
                "source_chars": sum(ref["end"] - ref["start"] for ref in refs),
                "translated_chars": sum(ref["end"] - ref["start"] for ref in available),
            }
        if result:
            result["runtime"] = {
                "path": self._path(dictionary),
                "fingerprint": self._fingerprint(dictionary)[:16],
            }
        return {"zh-CN": result} if result else {}
