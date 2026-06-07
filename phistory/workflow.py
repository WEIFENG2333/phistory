from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from phistory import packages
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
        try:
            agent = get_agent(agent_id)
            version = packages.latest_version(agent)
            result = capture_target(
                CaptureTarget(agent, version, root), cache_dir=cache_dir, force=force, keep_tap=keep_tap
            )
        except Exception as exc:
            result = CaptureResult(agent_id, "unknown", "failed", error=str(exc))
        results.append(result)
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
    newest_first: bool = False,
    include_prerelease: bool = False,
) -> list[CaptureResult]:
    agent = get_agent(agent_id)
    versions: list[VersionInfo] = packages.versions_between(agent, start, end, include_prerelease=include_prerelease)
    if newest_first:
        versions = list(reversed(versions))
    if limit is not None:
        versions = versions[:limit]
    return [
        capture_target(CaptureTarget(agent, version, root), cache_dir=cache_dir, force=force, keep_tap=keep_tap)
        for version in versions
    ]


def iter_backfill(
    agent_id: str,
    *,
    start: str,
    end: str,
    root: Path,
    cache_dir: Path,
    force: bool = False,
    keep_tap: bool = False,
    limit: int | None = None,
    newest_first: bool = False,
    include_prerelease: bool = False,
) -> Iterator[CaptureResult]:
    agent = get_agent(agent_id)
    versions: list[VersionInfo] = packages.versions_between(agent, start, end, include_prerelease=include_prerelease)
    if newest_first:
        versions = list(reversed(versions))
    if limit is not None:
        versions = versions[:limit]
    for version in versions:
        yield capture_target(CaptureTarget(agent, version, root), cache_dir=cache_dir, force=force, keep_tap=keep_tap)
