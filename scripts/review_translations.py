"""Export stratified archived source/translation pairs for read-only review; never call an API."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from phistory.render import _version_key, read_capture_rows
from phistory.translation.segments import extract_markdown, extract_trace
from phistory.translation.storage import read_dictionary

ROOT = Path(__file__).resolve().parents[1]


def candidates(rows, dictionary):
    versions = sorted({row["version"] for row in rows}, key=_version_key)
    selected_versions = {versions[0], versions[-1], versions[len(versions) // 2]} if versions else set()
    found = {}
    for row in rows:
        for path in (row["prompt"], row["trace"]):
            if not path or row["version"] not in selected_versions:
                continue
            text = path.read_bytes().decode("utf-8")
            source = extract_trace(text) if path.suffix == ".jsonl" else extract_markdown(text)
            metadata = defaultdict(set)
            pointers = {}
            fields = source.index.get("fields", [{"segments": source.index.get("segments", [])}])
            for field in fields:
                pointer = field.get("pointer", "")
                for ref in field["segments"]:
                    if "json-string" in ref["kind"] or "/properties/" in pointer:
                        metadata[ref["id"]].add("schema")
                    if pointer:
                        pointers[ref["id"]] = pointer
            for segment in source.segments:
                entry = dictionary["entries"].get(segment.id)
                preserved = entry is not None and entry.get("status") == "preserved"
                if len(segment.text) < 80 and not preserved:
                    continue
                strata = metadata[segment.id]
                if preserved:
                    strata.add("preserved")
                if row["version"] == versions[0]:
                    strata.add("old")
                if row["version"] == versions[-1]:
                    strata.add("latest")
                if len(segment.text) >= 500:
                    strata.add("long")
                if "Tool:" in segment.context and "schema" not in strata:
                    strata.add("tool")
                identity = (segment.id, row["version"])
                if identity in found:
                    found[identity]["strata"] = sorted(set(found[identity]["strata"]) | strata)
                    continue
                found[identity] = {
                    "id": segment.id,
                    "version": row["version"],
                    "source": str(path),
                    "pointer": pointers.get(segment.id),
                    "strata": sorted(strata),
                    "context": segment.context,
                    "text": segment.text,
                    "translation": entry["text"] if entry else None,
                    "status": entry.get("status", "legacy") if entry else None,
                    "provenance": {key: value for key, value in entry.items() if key != "text"} if entry else None,
                }
    return list(found.values())


def select(rows, count, seed):
    chosen, seen, coverage = [], set(), {}
    for stratum in ("preserved", "old", "latest", "long", "tool", "schema"):
        available = [row for row in rows if stratum in row["strata"]]
        translated = [row for row in available if row["translation"] and row["id"] not in seen]
        if stratum == "long":
            translated.sort(key=lambda row: (-len(row["text"]), row["id"]))
        else:
            translated.sort(key=lambda row: hashlib.sha256((seed + stratum + row["id"]).encode()).hexdigest())
        picked = []
        for row in translated:
            if row["id"] in seen:
                continue
            picked.append(row)
            seen.add(row["id"])
            if len(picked) == count:
                break
        chosen.extend({**row, "selected_for": stratum} for row in picked)
        coverage[stratum] = {"source_candidates": len(available), "selected": len(picked)}
    return chosen, coverage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--agents", help="Comma-separated agents; defaults to all archived agents.")
    parser.add_argument("--count", type=int, default=1, help="Distinct samples per stratum and agent.")
    parser.add_argument("--seed", default="translation-review-v9")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("count must be positive")
    wanted = set(args.agents.split(",")) if args.agents else None
    grouped = defaultdict(list)
    for row in read_capture_rows(args.root / "captures"):
        if wanted is None or row["agent_id"] in wanted:
            grouped[row["agent_id"]].append(row)
    if wanted and wanted - grouped.keys():
        parser.error("unknown agents: " + ", ".join(sorted(wanted - grouped.keys())))
    output = args.output or args.root / ".phistory-cache/translation-eval" / datetime.now(timezone.utc).strftime(
        "bulk-review-%Y%m%dT%H%M%SZ"
    )
    output.mkdir(parents=True, exist_ok=True)
    for agent, rows in sorted(grouped.items()):
        dictionary = read_dictionary(args.root / "translations", agent)
        selected, coverage = select(candidates(rows, dictionary), args.count, args.seed)
        report = {"agent": agent, "seed": args.seed, "coverage": coverage, "pairs": selected}
        (output / f"{agent}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        review = "\n\n".join(
            f"## {row['selected_for']} / {row['version']} / {row['id']}\n\n{row['source']}\n\n"
            f"状态：{row['status']}\n\n"
            f"原文：\n\n{row['text']}\n\n译文：\n\n{row['translation']}"
            for row in selected
        )
        (output / f"{agent}.md").write_text(review + "\n", encoding="utf-8")
        print(f"{agent}: {len(selected)} pairs; read {output / (agent + '.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
