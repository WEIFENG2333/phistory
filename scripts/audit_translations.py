"""Read-only release checks for source maps, translated dictionaries and deployment size."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from phistory.render import read_capture_rows
from phistory.translation.client import protect
from phistory.translation.segments import EXTRACTOR_VERSION, SEGMENT_VERSION, extract_markdown, extract_trace
from phistory.translation.storage import read_dictionary, read_source
from phistory.translation.templates import TOKEN, restore_template, trace_template

REPO = Path(__file__).resolve().parents[1]

SNAKE_CASE = re.compile(r"\b[a-z][a-z0-9]*(?:_+[a-z0-9]+)+\b")
STYLE_WORDS = {"snake_case", "lower_case", "upper_case", "kebab_case"}


def git_paths(*args: str) -> list[str]:
    result = subprocess.run(["git", args[0], "-z", *args[1:]], cwd=REPO, capture_output=True, check=True)
    return [item.decode() for item in result.stdout.split(b"\0") if item]


def resolve_pointer(record: dict, pointer: str):
    value = record
    for part in pointer.split("/")[1:]:
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def span_text(source: str, ref: dict) -> str:
    value = source[ref["start"] : ref["end"]]
    if ref["kind"] == "json-string":
        value = json.loads(value)
    elif ref["kind"] == "json-string-part":
        for _ in range(ref.get("escape_depth", 1)):
            value = json.loads('"' + value + '"')
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-complete", action="store_true", help="fail when source maps or translations are missing"
    )
    parser.add_argument(
        "--expected-prompt-version", help="optionally require this provenance on every stored translation"
    )
    parser.add_argument("--expected-model", help="optionally require this model on every stored translation")
    parser.add_argument("--verify-source", action="append", default=[], help="deep-check all spans for this source")
    parser.add_argument(
        "--preserved-samples",
        type=int,
        default=5,
        help="Preserved samples per agent and dictionary for semantic review.",
    )
    parser.add_argument("--size-limit", type=int, default=1_000_000_000)
    parser.add_argument("--report", type=Path, default=REPO / ".phistory-cache/translation-audit.json")
    args = parser.parse_args()
    if args.preserved_samples < 0:
        parser.error("--preserved-samples must be nonnegative")
    deep_sources = {(REPO / path).resolve() for path in args.verify_source}
    capture_root, translation_root = REPO / "captures", REPO / "translations"
    rows = read_capture_rows(capture_root)
    documents = {}
    for row in rows:
        for surface, kind in (("prompt", "runtime"), ("trace", "runtime")):
            if path := row.get(surface):
                documents[path] = (row["agent_id"], kind)
    unknown_sources = deep_sources - {path.resolve() for path in documents}
    if unknown_sources:
        parser.error("--verify-source is not an archived source: " + ", ".join(map(str, sorted(unknown_sources))))
    errors, missing_maps = [], []
    needed = defaultdict(set)
    origins, unit_texts, index_cache = {}, {}, {}
    bound_templates = set()
    deep_checked, references = 0, 0

    for path, (agent, kind) in sorted(documents.items()):
        relative = str(path.relative_to(REPO))
        try:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            index_path = translation_root / "sources" / f"{digest}-v{EXTRACTOR_VERSION}.json"
            if index_path not in index_cache:
                index_cache[index_path] = read_source(index_path, digest)
            index = index_cache[index_path]
            text = raw.decode("utf-8")
            is_trace = path.suffix == ".jsonl"
            if index is None:
                if index_path.exists():
                    raise ValueError("source index is malformed or has a mismatched hash")
                missing_maps.append(relative)
                index = (extract_trace if is_trace else extract_markdown)(text).index
            if index["kind"] != ("trace" if is_trace else "markdown"):
                raise ValueError("source index has the wrong document kind")
            records = [json.loads(line) for line in text.splitlines() if line.strip()] if is_trace else []
            fields = index["fields"] if is_trace else [{"segments": index["segments"]}]
            check_every_span = path.resolve() in deep_sources
            if check_every_span:
                expected = (extract_trace if is_trace else extract_markdown)(text)
                if expected.index != index:
                    raise ValueError("source index differs from current extraction")
                deep_checked += 1
            for field in fields:
                original = resolve_pointer(records[field["record"]], field["pointer"]) if is_trace else text
                if not isinstance(original, str):
                    raise ValueError("source field pointer does not address text")
                for ref in field["segments"]:
                    references += 1
                    key = ref["id"]
                    if ref["end"] > len(original):
                        raise ValueError(f"span outside source field: {key}")
                    # Verify content identity once per unique paragraph, plus all explicitly selected new sources.
                    if key not in unit_texts or check_every_span or ref.get("bindings"):
                        value = span_text(original, ref)
                        if ref.get("bindings"):
                            template, bindings = trace_template(value)
                            if bindings != ref["bindings"] or restore_template(template, bindings) != value:
                                raise ValueError("capture template does not restore its original source")
                            value = template
                            bound_templates.add(key)
                        expected_id = hashlib.sha256(f"{SEGMENT_VERSION}\0{value}".encode()).hexdigest()
                        if expected_id != key:
                            raise ValueError(f"span content does not match its text-only identity: {key}")
                        unit_texts[key] = value
                    needed[agent, kind].add(key)
                    origins.setdefault((agent, kind, key), relative)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            errors.append({"source": relative, "error": str(exc)})

    coverage, harness_review, identifier_review, preserved_review = [], [], [], []
    dictionaries = {}
    for (agent, kind), keys in sorted(needed.items()):
        try:
            entries = read_dictionary(translation_root, agent)["entries"]
        except (OSError, ValueError) as exc:
            errors.append({"dictionary": f"{agent}/{kind}", "error": str(exc)})
            entries = {}
        dictionaries[agent, kind] = entries
        models, prompt_versions, statuses = Counter(), Counter(), Counter()
        for key, entry in entries.items():
            models[entry["model"]] += 1
            prompt_versions[entry["prompt_version"]] += 1
            status = entry.get("status", "legacy")
            if "status" in entry and status not in ("translated", "preserved"):
                errors.append({"dictionary": f"{agent}/{kind}", "id": key, "error": "invalid translation status"})
                status = "invalid"
            statuses[status] += 1
            if args.expected_prompt_version and entry["prompt_version"] != args.expected_prompt_version:
                errors.append({"dictionary": f"{agent}/{kind}", "id": key, "error": "unexpected prompt version"})
            if args.expected_model and entry["model"] != args.expected_model:
                errors.append({"dictionary": f"{agent}/{kind}", "id": key, "error": "unexpected model"})
        available = keys & entries.keys()
        for key in sorted(available & bound_templates):
            if Counter(TOKEN.findall(unit_texts[key])) != Counter(TOKEN.findall(entries[key]["text"])):
                errors.append(
                    {"agent": agent, "kind": kind, "id": key, "error": "translation changed capture placeholders"}
                )
                available.remove(key)
        coverage.append(
            {
                "agent": agent,
                "kind": kind,
                "total": len(keys),
                "translated": len(available),
                "missing": len(keys - available),
                "source_chars": sum(len(unit_texts[key]) for key in keys),
                "models": dict(models),
                "prompt_versions": dict(prompt_versions),
                "statuses": dict(statuses),
            }
        )
        preserved_samples = 0
        for key in sorted(available):
            original, translated = unit_texts[key], entries[key]["text"]
            comparison = {
                "agent": agent,
                "kind": kind,
                "id": key,
                "source": origins[agent, kind, key],
                "original": original,
                "translated": translated,
                "status": entries[key].get("status", "legacy"),
                "model": entries[key]["model"],
                "prompt_version": entries[key]["prompt_version"],
            }
            if entries[key].get("status") == "preserved":
                if translated != original:
                    errors.append(
                        {"agent": agent, "kind": kind, "id": key, "error": "preserved text differs from source"}
                    )
                # Stable hash order samples the model's decisions without guessing whether prose is code.
                if preserved_samples < args.preserved_samples:
                    preserved_review.append(comparison)
                    preserved_samples += 1
            if re.search(r"\bharness\b", original, re.IGNORECASE):
                harness_review.append(
                    {
                        **comparison,
                        "preserved": bool(re.search(r"\bharness\b", translated, re.IGNORECASE)),
                        "framework_terms": [
                            word for word in ("运行框架", "测试框架", "执行框架", "评测框架") if word in translated
                        ],
                    }
                )
            bare, _ = protect(original)
            lost = sorted(token for token in set(SNAKE_CASE.findall(bare)) - STYLE_WORDS if token not in translated)
            if lost:
                identifier_review.append({**comparison, "missing_identifiers": lost})
    # New captures are expected during incremental runs, including after git add.
    changed = set(git_paths("diff", "--name-only", "--diff-filter=DMRTUXB", "--", "captures")) | set(
        git_paths("diff", "--cached", "--name-only", "--diff-filter=DMRTUXB", "--", "captures")
    )
    raw_changes = sorted(path for path in changed if path != "captures/index.json")
    if raw_changes:
        errors.append({"error": "existing raw captures changed", "files": raw_changes})
    deploy_paths = set(git_paths("ls-files", "--cached", "--others", "--exclude-standard"))
    sizes = Counter()
    for name in sorted(deploy_paths):
        path = REPO / name
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            # A concurrent atomic checkpoint may have just removed its temporary file.
            continue
        category = (
            "source_maps"
            if name.startswith("translations/sources/")
            else "dictionaries"
            if name.startswith("translations/zh-CN/")
            else "captures"
            if name.startswith("captures/")
            else "other"
        )
        sizes[category] += size
    total_bytes = sum(sizes.values())
    if total_bytes >= args.size_limit:
        errors.append({"error": "deployment size exceeds the configured limit", "bytes": total_bytes})
    missing = sum(item["missing"] for item in coverage)
    report = {
        "snapshots": len(rows),
        "documents": len(documents),
        "source_maps": len(index_cache),
        "source_references_checked": references,
        "unique_source_identities_checked": len(unit_texts),
        "deep_verified_documents": deep_checked,
        "missing_source_maps": missing_maps,
        "coverage": coverage,
        "missing_dictionary_entries_by_surface": missing,
        "deployment_bytes": dict(sizes),
        "deployment_total_bytes": total_bytes,
        "deployment_limit_bytes": args.size_limit,
        "raw_capture_changes": raw_changes,
        "errors": errors,
        "harness_review": harness_review,
        "bare_identifier_review": identifier_review,
        "preserved_review": preserved_review,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"snapshots={len(rows)} documents={len(documents)} source_maps={len(index_cache)} deep_verified={deep_checked}"
    )
    for row in coverage:
        print(
            f"{row['agent']}/{row['kind']}: {row['translated']}/{row['total']}; missing {row['missing']}; statuses {row['statuses']}"
        )
    print(
        f"structure_errors={len(errors)} missing_maps={len(missing_maps)} missing_dictionary_entries_by_surface={missing}"
    )
    print(f"deployment={total_bytes:,}/{args.size_limit:,} bytes {dict(sizes)}")
    print(
        f"review_only: harness={len(harness_review)} bare_identifiers={len(identifier_review)} preserved_samples={len(preserved_review)}"
    )
    print(f"report={args.report}")
    return int(bool(errors) or (args.require_complete and bool(missing or missing_maps)))


if __name__ == "__main__":
    raise SystemExit(main())
