from __future__ import annotations

import hashlib
from pathlib import Path

from phistory.translation.segments import EXTRACTOR_VERSION
from phistory.translation.storage import dictionary_path, read_dictionary, read_source


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
        result = {}
        for surface, kind in (("prompt", "runtime"), ("trace", "runtime"), ("static_prompts", "static")):
            path = row.get(surface)
            dictionary = dictionary_path(self.root, row["agent_id"], kind)
            if not path or not dictionary.exists():
                continue
            if dictionary not in self.dictionaries:
                try:
                    self.dictionaries[dictionary] = read_dictionary(self.root, row["agent_id"], kind)
                except (OSError, ValueError):
                    self.dictionaries[dictionary] = None
            data = self.dictionaries[dictionary]
            if data is None:
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
            available = [ref for ref in refs if ref["id"] in data["entries"]]
            name = "static" if surface == "static_prompts" else surface
            result[name] = {
                "index": self._path(source_path),
                "fingerprint": self._fingerprint(source_path)[:16],
                "source_hash": digest,
                "total": len(refs),
                "translated": len(available),
                "source_chars": sum(ref["end"] - ref["start"] for ref in refs),
                "translated_chars": sum(ref["end"] - ref["start"] for ref in available),
            }
            result["runtime" if kind == "runtime" else "static_dictionary"] = {
                "path": self._path(dictionary),
                "fingerprint": self._fingerprint(dictionary)[:16],
            }
        return {"zh-CN": result} if result else {}
