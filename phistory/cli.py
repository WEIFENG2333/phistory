from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from phistory import __version__, packages
from phistory.models import CaptureTarget
from phistory.registry import AGENT_ORDER, AGENTS, parse_agent_ids
from phistory.render import render_index
from phistory.site import render_site
from phistory.static_prompts.extract import extract_static_prompts, static_prompts_meta
from phistory.workflow import capture_latest, iter_backfill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phistory", description="Capture versioned prompt snapshots from agent CLIs.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", default="captures", help="capture root directory")
    parser.add_argument("--cache-dir", default=".phistory-cache", help="install/cache directory")

    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="capture current versions")
    capture.add_argument("--latest", action="store_true", help="capture latest package version for each agent")
    capture.add_argument("--agents", default=None, help=f"comma-separated agent ids (default: {','.join(AGENT_ORDER)})")
    capture.add_argument("--force", action="store_true", help="recapture existing versions")
    capture.add_argument("--keep-tap", action="store_true", help="keep raw claude-tap output directories")
    capture.add_argument("--summary-title", default="Capture results", help="GitHub Actions summary title")

    fill = sub.add_parser("backfill", help="capture historical package versions")
    fill.add_argument("agent", choices=sorted(AGENTS), help="agent id")
    fill.add_argument("--from", dest="start", required=True, help="first package version to capture")
    fill.add_argument("--to", dest="end", default="latest", help="last package version to capture")
    fill.add_argument("--limit", type=int, default=None, help="capture at most N versions from the range")
    fill.add_argument("--newest-first", action="store_true", help="capture the selected range from newest to oldest")
    fill.add_argument("--include-prerelease", action="store_true", help="include prerelease package versions")
    fill.add_argument("--force", action="store_true", help="recapture existing versions")
    fill.add_argument("--keep-tap", action="store_true", help="keep raw claude-tap output directories")
    fill.add_argument("--summary-title", default="Backfill results", help="GitHub Actions summary title")

    index = sub.add_parser("render-index", help="render capture index")
    index.add_argument("-o", "--output", default="README.md", help="index markdown path")

    site = sub.add_parser("render-site", help="render static HTML site")
    site.add_argument("-o", "--output", default="index.html", help="site HTML path")

    static = sub.add_parser("extract-static", help="extract static prompts from installed agent packages")
    static.add_argument("agent", choices=sorted(AGENTS), help="agent id")
    static.add_argument("versions", nargs="*", help="package versions to extract")
    static.add_argument(
        "--latest-captured",
        type=int,
        default=None,
        metavar="N",
        help="extract the latest N versions already present under the capture root",
    )
    static.add_argument(
        "--refresh-candidates",
        action="store_true",
        help="reinstall packages and regenerate static-candidates.json instead of replaying the archived candidates",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    cache_dir = Path(args.cache_dir)

    if args.command == "capture":
        if not args.latest:
            raise SystemExit("capture currently requires --latest")
        results = capture_latest(
            parse_agent_ids(args.agents),
            root=root,
            cache_dir=cache_dir,
            force=args.force,
            keep_tap=args.keep_tap,
        )
        return _print_results(results, args.summary_title)

    if args.command == "backfill":
        failed = False
        for result in iter_backfill(
            args.agent,
            start=args.start,
            end=args.end,
            root=root,
            cache_dir=cache_dir,
            force=args.force,
            keep_tap=args.keep_tap,
            limit=args.limit,
            newest_first=args.newest_first,
            include_prerelease=args.include_prerelease,
        ):
            failed = _print_result(result) or failed
            _write_github_summary([result], args.summary_title)
        return 1 if failed else 0

    if args.command == "render-index":
        render_index(root, Path(args.output))
        print(f"wrote {args.output}")
        return 0

    if args.command == "render-site":
        render_site(root, Path(args.output))
        print(f"wrote {args.output}")
        return 0

    if args.command == "extract-static":
        versions = _resolve_static_versions(args.agent, args.versions, args.latest_captured, root=root)
        return _extract_static(
            args.agent,
            versions,
            root=root,
            cache_dir=cache_dir,
            refresh_candidates=args.refresh_candidates,
        )

    return 2


def _resolve_static_versions(
    agent_id: str, versions: list[str], latest_captured: int | None, *, root: Path
) -> list[str]:
    if latest_captured is not None:
        if latest_captured < 1:
            raise SystemExit("--latest-captured must be greater than zero")
        if versions:
            raise SystemExit("pass explicit versions or --latest-captured, not both")
        versions = _latest_captured_versions(root, agent_id, latest_captured)
    if not versions:
        raise SystemExit("extract-static requires at least one version or --latest-captured N")
    return versions


def _latest_captured_versions(root: Path, agent_id: str, limit: int) -> list[str]:
    agent_dir = root / agent_id
    if not agent_dir.exists():
        raise SystemExit(f"no captured versions found for {agent_id}: {agent_dir}")
    versions = [
        path.name
        for path in agent_dir.iterdir()
        if path.is_dir() and (path / "prompt.md").exists() and (path / "trace.jsonl").exists()
    ]
    versions.sort(key=_version_sort_key, reverse=True)
    if not versions:
        raise SystemExit(f"no complete captured versions found for {agent_id}: {agent_dir}")
    return versions[:limit]


def _version_sort_key(version: str) -> tuple[object, ...]:
    parts: list[object] = []
    for part in version.replace("-", ".").split("."):
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts)


def _extract_static(
    agent_id: str,
    versions: list[str],
    *,
    root: Path,
    cache_dir: Path,
    refresh_candidates: bool = False,
) -> int:
    agent = AGENTS[agent_id]
    failed = False
    for version in versions:
        install_dir = (cache_dir / "installs" / agent.id / version).resolve()
        target = CaptureTarget(agent=agent, version=packages.version_info(agent, version), root=root)
        target.version_dir.mkdir(parents=True, exist_ok=True)
        if refresh_candidates and target.static_candidates_json_path.exists():
            target.static_candidates_json_path.unlink()
        if not target.static_candidates_json_path.exists():
            packages.install_agent(agent, version, install_dir)
        try:
            result = extract_static_prompts(target, install_dir)
        except Exception as exc:
            failed = True
            print(f"{agent_id} {version}: failed static extraction: {exc}", file=sys.stderr, flush=True)
            continue
        if result is None:
            print(f"{agent_id} {version}: static extraction unsupported", flush=True)
            continue
        _update_meta_static_prompts(target, static_prompts_meta(target, result))
        print(
            f"{agent_id} {version}: {len(result.matches)} static prompts ({result.known_count} known, {result.unknown_count} unknown)",
            flush=True,
        )
    return 1 if failed else 0


def _update_meta_static_prompts(target: CaptureTarget, payload: dict[str, object]) -> None:
    if not target.meta_path.exists():
        return
    try:
        meta = json.loads(target.meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(meta, dict):
        return
    meta["static_prompts"] = payload
    target.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _print_results(results, summary_title: str = "Capture results") -> int:
    failed = False
    for result in results:
        failed = _print_result(result) or failed
    _write_github_summary(results, summary_title)
    return 1 if failed else 0


def _print_result(result) -> bool:
    print(f"{result.agent_id} {result.version}: {result.status}", flush=True)
    if result.prompt_path:
        print(f"  prompt: {result.prompt_path}", flush=True)
    if result.trace_path:
        print(f"  trace:  {result.trace_path}", flush=True)
    if result.error:
        print(f"  error:  {result.error}", file=sys.stderr, flush=True)
        _print_github_error(result)
        return True
    return False


def _write_github_summary(results, title: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    counts = {
        status: sum(1 for result in results if result.status == status) for status in ("captured", "skipped", "failed")
    }
    lines = [
        f"## {_md_escape(title)}",
        "",
        f"Captured: **{counts['captured']}** · Skipped: **{counts['skipped']}** · Failed: **{counts['failed']}**",
        "",
        "| Agent | Version | Status | Prompt | Trace | Error |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        cells = [
            f"`{_md_escape(result.agent_id)}`",
            f"`{_md_escape(result.version)}`",
            _status_label(result.status),
            _path_link(result.prompt_path),
            _path_link(result.trace_path),
            _md_escape(_error_summary(result.error)),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    summary_path = Path(path)
    existing = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    summary_path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")


def _print_github_error(result) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    title = f"{result.agent_id} {result.version} capture failed"
    print(
        f"::error title={_annotation_escape(title)}::{_annotation_escape(_error_summary(result.error))}",
        file=sys.stderr,
    )


def _status_label(status: str) -> str:
    return {"captured": "captured", "skipped": "skipped", "failed": "failed"}.get(status, status)


def _path_link(path: Path | None) -> str:
    if path is None:
        return ""
    value = path.as_posix()
    return f"[`{_md_escape(value)}`]({_md_escape(value)})"


def _error_summary(error: str | None) -> str:
    if not error:
        return ""
    line = " ".join(error.strip().splitlines())
    return line[:500] + ("..." if len(line) > 500 else "")


def _md_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _annotation_escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


if __name__ == "__main__":
    raise SystemExit(main())
