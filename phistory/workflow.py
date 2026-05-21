from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from phistory import npm
from phistory.capture import capture_target
from phistory.models import CaptureResult, CaptureTarget, VersionInfo
from phistory.registry import get_agent


def capture_latest(
    agent_ids: Iterable[str],
    *,
    root: Path,
    cache_dir: Path,
    force: bool = False,
    keep_tap: bool = False,
) -> list[CaptureResult]:
    results: list[CaptureResult] = []
    for agent_id in agent_ids:
        agent = get_agent(agent_id)
        version = npm.latest_version(agent)
        results.append(
            capture_target(CaptureTarget(agent, version, root), cache_dir=cache_dir, force=force, keep_tap=keep_tap)
        )
    return results


def backfill(
    agent_id: str,
    *,
    start: str,
    end: str,
    root: Path,
    cache_dir: Path,
    force: bool = False,
    keep_tap: bool = False,
    limit: int | None = None,
) -> list[CaptureResult]:
    agent = get_agent(agent_id)
    versions: list[VersionInfo] = npm.versions_between(agent, start, end)
    if limit is not None:
        versions = versions[:limit]
    return [
        capture_target(CaptureTarget(agent, version, root), cache_dir=cache_dir, force=force, keep_tap=keep_tap)
        for version in versions
    ]
