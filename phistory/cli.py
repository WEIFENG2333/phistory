from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phistory import __version__
from phistory.registry import AGENTS, parse_agent_ids
from phistory.render import render_index
from phistory.workflow import capture_latest, iter_backfill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phistory", description="Capture versioned prompt snapshots from agent CLIs.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", default="captures", help="capture root directory")
    parser.add_argument("--cache-dir", default=".phistory-cache", help="install/cache directory")

    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="capture current versions")
    capture.add_argument("--latest", action="store_true", help="capture latest npm version for each agent")
    capture.add_argument(
        "--agents", default=None, help=f"comma-separated agent ids (default: {','.join(sorted(AGENTS))})"
    )
    capture.add_argument("--force", action="store_true", help="recapture existing versions")
    capture.add_argument("--keep-tap", action="store_true", help="keep raw claude-tap output directories")

    fill = sub.add_parser("backfill", help="capture historical npm versions")
    fill.add_argument("agent", choices=sorted(AGENTS), help="agent id")
    fill.add_argument("--from", dest="start", required=True, help="first npm version to capture")
    fill.add_argument("--to", dest="end", default="latest", help="last npm version to capture")
    fill.add_argument("--limit", type=int, default=None, help="capture at most N versions from the range")
    fill.add_argument("--include-prerelease", action="store_true", help="include prerelease npm versions")
    fill.add_argument("--force", action="store_true", help="recapture existing versions")
    fill.add_argument("--keep-tap", action="store_true", help="keep raw claude-tap output directories")

    index = sub.add_parser("render-index", help="render capture index")
    index.add_argument("-o", "--output", default="README.md", help="index markdown path")

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
        return _print_results(results)

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
            include_prerelease=args.include_prerelease,
        ):
            failed = _print_result(result) or failed
        return 1 if failed else 0

    if args.command == "render-index":
        render_index(root, Path(args.output))
        print(f"wrote {args.output}")
        return 0

    return 2


def _print_results(results) -> int:
    failed = False
    for result in results:
        failed = _print_result(result) or failed
    return 1 if failed else 0


def _print_result(result) -> bool:
    print(f"{result.agent_id} {result.version}: {result.status}", flush=True)
    if result.prompt_path:
        print(f"  prompt: {result.prompt_path}", flush=True)
    if result.trace_path:
        print(f"  trace:  {result.trace_path}", flush=True)
    if result.error:
        print(f"  error:  {result.error}", file=sys.stderr, flush=True)
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
