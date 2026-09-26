from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from phistory import packages
from phistory.capture import capture_target
from phistory.models import AgentSpec, CaptureResult, CaptureTarget, CaptureVariant, VersionInfo
from phistory.prompt import render_archive_markdown, snapshot_from_trace
from phistory.registry import get_agent


@dataclass(frozen=True)
class RerenderResult:
    agent_id: str
    version: str
    variant_id: str
    status: str
    error: str | None = None


def capture_latest(
    agent_ids: Iterable[str],
    *,
    root: Path,
    cache_dir: Path,
    variant_ids: Iterable[str] | None = None,
    force: bool = False,
    keep_tap: bool = False,
) -> list[CaptureResult]:
    results: list[CaptureResult] = []
    selected_ids = tuple(variant_ids) if variant_ids is not None else None
    for agent_id in agent_ids:
        try:
            agent = get_agent(agent_id)
            version = packages.latest_version(agent)
            variants = _selected_variants(agent, selected_ids)
        except Exception as exc:
            results.append(CaptureResult(agent_id, "unknown", "default", "failed", error=str(exc)))
            continue
        for variant in _variants_for_version(variants, version):
            try:
                result = capture_target(
                    CaptureTarget(agent, version, variant, root),
                    cache_dir=cache_dir,
                    force=force,
                    keep_tap=keep_tap,
                )
            except Exception as exc:
                result = CaptureResult(agent_id, version.version, variant.id, "failed", error=str(exc))
            results.append(result)
    return results


def backfill(
    agent_id: str,
    *,
    start: str,
    end: str,
    root: Path,
    cache_dir: Path,
    variant_ids: Iterable[str] | None = None,
    force: bool = False,
    keep_tap: bool = False,
    limit: int | None = None,
    newest_first: bool = False,
    include_prerelease: bool = False,
    captured_only: bool = False,
) -> list[CaptureResult]:
    return list(
        iter_backfill(
            agent_id,
            start=start,
            end=end,
            root=root,
            cache_dir=cache_dir,
            variant_ids=variant_ids,
            force=force,
            keep_tap=keep_tap,
            limit=limit,
            newest_first=newest_first,
            include_prerelease=include_prerelease,
            captured_only=captured_only,
        )
    )


def iter_backfill(
    agent_id: str,
    *,
    start: str,
    end: str,
    root: Path,
    cache_dir: Path,
    variant_ids: Iterable[str] | None = None,
    force: bool = False,
    keep_tap: bool = False,
    limit: int | None = None,
    newest_first: bool = False,
    include_prerelease: bool = False,
    captured_only: bool = False,
) -> Iterator[CaptureResult]:
    agent = get_agent(agent_id)
    versions: list[VersionInfo] = packages.versions_between(agent, start, end, include_prerelease=include_prerelease)
    if captured_only:
        # Adding a variant to an existing archive: skip releases that never captured at all.
        archived = {path.name for path in (root / agent_id).glob("*") if path.is_dir()}
        versions = [version for version in versions if version.version in archived]
    if newest_first:
        versions = list(reversed(versions))
    if limit is not None:
        versions = versions[:limit]
    variants = _selected_variants(agent, tuple(variant_ids) if variant_ids is not None else None)
    for version in versions:
        for variant in _variants_for_version(variants, version):
            yield capture_target(
                CaptureTarget(agent, version, variant, root),
                cache_dir=cache_dir,
                force=force,
                keep_tap=keep_tap,
            )


def _selected_variants(agent: AgentSpec, variant_ids: tuple[str, ...] | None) -> tuple[CaptureVariant, ...]:
    if variant_ids is None:
        return agent.capture_variants
    return tuple(agent.variant(variant_id) for variant_id in variant_ids)


def _variants_for_version(variants: tuple[CaptureVariant, ...], version: VersionInfo) -> tuple[CaptureVariant, ...]:
    return tuple(variant for variant in variants if variant.supports_version(version.version))


def rerender_archive(root: Path, agent_ids: Iterable[str] | None = None) -> list[RerenderResult]:
    """Rebuild archived Markdown from stored traces, without reinstalling anything."""
    selected = set(agent_ids) if agent_ids is not None else None
    results: list[RerenderResult] = []
    for trace in sorted(root.glob("*/*/variants/*/trace.jsonl")):
        agent_id, version, _, variant_id = trace.relative_to(root).parts[:4]
        if selected is not None and agent_id not in selected:
            continue
        try:
            markdown = render_archive_markdown(trace)
        except (ValueError, OSError) as exc:
            results.append(RerenderResult(agent_id, version, variant_id, "failed", str(exc)))
            continue
        prompt_path = trace.parent / "prompt.md"
        changed = not prompt_path.exists() or prompt_path.read_text(encoding="utf-8") != markdown
        if changed:
            prompt_path.write_text(markdown, encoding="utf-8")
        _refresh_observed(trace)
        results.append(RerenderResult(agent_id, version, variant_id, "updated" if changed else "unchanged"))
    return results


def _refresh_observed(trace: Path) -> None:
    meta_path = trace.parent / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    observed = meta.get("observed")
    meta["observed"] = {**(observed if isinstance(observed, dict) else {}), **snapshot_from_trace(trace).observation}
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
