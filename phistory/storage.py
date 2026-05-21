from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from phistory.models import CaptureTarget


def is_captured(target: CaptureTarget) -> bool:
    return target.prompt_path.exists() and target.trace_path.exists() and target.meta_path.exists()


def prepare_version_dir(target: CaptureTarget, *, force: bool) -> None:
    if force and target.version_dir.exists():
        shutil.rmtree(target.version_dir)
    target.version_dir.mkdir(parents=True, exist_ok=True)


def latest_trace(tap_output_dir: Path) -> Path:
    traces = sorted(tap_output_dir.glob("*/trace_*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not traces:
        raise RuntimeError(f"no trace file found under {tap_output_dir}")
    return traces[0]


def write_meta(target: CaptureTarget, data: dict[str, Any]) -> None:
    target.meta_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_trace(src: Path, target: CaptureTarget) -> None:
    shutil.copyfile(src, target.trace_path)


def remove_if_exists(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
