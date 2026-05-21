from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from phistory.models import CommandResult


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int = 120,
    check: bool = True,
) -> CommandResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    proc = subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    result = CommandResult(tuple(argv), proc.returncode, proc.stdout, proc.stderr)
    if check and proc.returncode != 0:
        command = " ".join(argv)
        tail = (proc.stderr or proc.stdout).strip()[-4000:]
        raise RuntimeError(f"command failed ({proc.returncode}): {command}\n{tail}")
    return result
