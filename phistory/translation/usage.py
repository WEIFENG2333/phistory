from __future__ import annotations

import json
import threading
import warnings
from datetime import datetime, timezone
from pathlib import Path

_WRITE_LOCK = threading.Lock()
_CONTEXT_FIELDS = {"agent", "surface", "purpose", "run_id"}


class UsageLog:
    """Append provider accounting without storing request text or credentials."""

    def __init__(self, path: Path, context: dict | None = None):
        self.path = path
        self.context = {key: value for key, value in (context or {}).items() if key in _CONTEXT_FIELDS}
        # Fail before the first paid request if the log destination is unavailable.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)

    def write(self, record: dict) -> None:
        entry = {
            "schema": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **self.context,
            **record,
        }
        try:
            # Several worker threads, and possibly several clients, share this JSONL file.
            with _WRITE_LOCK, self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            # A logging failure must not discard a paid-for, usable model response.
            warnings.warn("Unable to append translation usage log", RuntimeWarning, stacklevel=2)
