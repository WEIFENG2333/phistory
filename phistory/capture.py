from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from phistory import npm
from phistory.dummy_upstream import dummy_upstream
from phistory.models import CaptureResult, CaptureTarget
from phistory.storage import copy_trace, is_captured, latest_trace, prepare_version_dir, remove_if_exists, write_meta
from phistory.subprocesses import run


def capture_target(
    target: CaptureTarget,
    *,
    cache_dir: Path,
    force: bool = False,
    keep_tap: bool = False,
) -> CaptureResult:
    if is_captured(target) and not force:
        return CaptureResult(
            target.agent.id, target.version.version, "skipped", target.prompt_path, target.trace_path, target.meta_path
        )

    started = time.time()
    prepare_version_dir(target, force=force)
    install_dir = (cache_dir / "installs" / target.agent.id / target.version.version).resolve()
    version_dir = target.version_dir.resolve()
    prompt_path = target.prompt_path.resolve()
    tap_output_dir = (version_dir / ".tap").resolve()

    try:
        bin_dir = npm.install_agent(target.agent, target.version.version, install_dir)
        binary_version = _binary_version(target, bin_dir)
        env = _capture_env(target, bin_dir)
        with dummy_upstream() as upstream:
            argv = [
                sys.executable,
                "-m",
                "claude_tap",
                "run",
                target.agent.tap_client,
                "-t",
                upstream,
                "--export-prompt",
                str(prompt_path),
                "--no-live",
                "--no-open",
                "--no-update-check",
                "-o",
                str(tap_output_dir),
                *target.agent.run_args,
            ]
            result = run(argv, cwd=version_dir, env=env, timeout=180, check=False)
        if result.returncode != 0 or not prompt_path.exists():
            detail = (result.stderr or result.stdout).strip()[-4000:]
            raise RuntimeError(f"capture command failed ({result.returncode})\n{detail}")

        trace = latest_trace(tap_output_dir)
        copy_trace(trace, target)
        write_meta(
            target,
            {
                "agent_id": target.agent.id,
                "agent": target.agent.display_name,
                "package": target.agent.package,
                "version": target.version.version,
                "published_at": target.version.published_at,
                "tarball_url": target.version.tarball_url,
                "binary_version": binary_version,
                "captured_at": _iso_now(),
                "tap_client": target.agent.tap_client,
                "target": upstream,
                "duration_seconds": round(time.time() - started, 3),
                "command": argv,
            },
        )
        if not keep_tap:
            remove_if_exists(tap_output_dir)
        return CaptureResult(
            target.agent.id, target.version.version, "captured", target.prompt_path, target.trace_path, target.meta_path
        )
    except Exception as exc:
        return CaptureResult(target.agent.id, target.version.version, "failed", error=str(exc))


def _capture_env(target: CaptureTarget, bin_dir: Path) -> dict[str, str]:
    env = {
        **target.agent.fake_env,
        **target.agent.extra_env,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    return env


def _binary_version(target: CaptureTarget, bin_dir: Path) -> str | None:
    executable = bin_dir / target.agent.tap_client
    if not executable.exists():
        return None
    result = run([str(executable), "--version"], env=_capture_env(target, bin_dir), timeout=30, check=False)
    text = (result.stdout or result.stderr).strip()
    return text or None


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
