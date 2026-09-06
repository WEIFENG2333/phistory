from __future__ import annotations

import hashlib
from pathlib import Path

from phistory.translation.segments import EXTRACTOR_VERSION
from phistory.translation.storage import dictionary_path, read_dictionary, read_source
from phistory.translation.templates import restore_template


class TranslationIndex:
    """Join immutable capture files with optional dictionaries for the static manifest."""

    def __init__(self, capture_root: Path):
        self.base = capture_root.parent
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
            source_path = self.root / "sources" / f"{digest}-v{EXTRACTOR_VERSION}.json"
            if source_path not in self.sources:
                self.sources[source_path] = read_source(source_path, digest)
            source = self.sources[source_path]
            if source is None:
                continue
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
                "index": self._path(source_path),
                "fingerprint": self._fingerprint(source_path)[:16],
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
