from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from phistory import __version__
from phistory.registry import AGENTS, parse_agent_ids
from phistory.render import render_index
from phistory.site import render_site
from phistory.workflow import capture_latest, iter_backfill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phistory", description="Capture versioned prompt snapshots from agent CLIs.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", default="captures", help="capture root directory")
    parser.add_argument("--cache-dir", default=".phistory-cache", help="install/cache directory")

    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="capture current versions")
    capture.add_argument("--latest", action="store_true", help="capture latest package version for each agent")
    capture.add_argument(
        "--agents", default=None, help=f"comma-separated agent ids (default: {','.join(sorted(AGENTS))})"
    )
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

    return 2


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
