import hashlib
import json
from pathlib import Path

import pytest

from phistory.build import BUILD_MARKER, build_site
from phistory.cli import main
from phistory.render import read_capture_rows, render_index
from phistory.translation.segments import extract_markdown
from phistory.translation.storage import write_dictionary


def archive(base: Path, version: str) -> Path:
    directory = base / "captures" / "agent" / version / "variants" / "default"
    directory.mkdir(parents=True)
    (directory / "meta.json").write_text(json.dumps({"agent_id": "agent", "version": version}))
    (directory / "prompt.md").write_text("Read the file.\n", encoding="utf-8")
    (directory / "trace.jsonl").write_text(
        json.dumps({"request": {"body": {"instructions": "Read the file."}}}) + "\n", encoding="utf-8"
    )
    return directory


def dictionary(base: Path, text: str = "读取文件。") -> Path:
    segment = extract_markdown("Read the file.").segments[0]
    write_dictionary(
        base / "translations",
        "agent",
        {
            "schema_version": 1,
            "locale": "zh-CN",
            "entries": {segment.id: {"text": text, "model": "test", "prompt_version": "test"}},
        },
    )
    return base / "translations/zh-CN/agent/runtime.json"


def manifest(public: Path) -> dict:
    html = (public / "index.html").read_text(encoding="utf-8")
    return json.loads(html.split('<script id="manifest" type="application/json">')[1].split("</script>")[0])


def hashes(directory: Path) -> dict:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_build_from_clean_archive_reuses_history_and_only_publishes_public_assets(tmp_path, monkeypatch):
    for version in ("1.0", "2.0"):
        archive(tmp_path, version)
    original_dictionary = dictionary(tmp_path)
    for name in (
        ".env",
        "translation.toml",
        ".phistory-cache/private.json",
        "captures/agent/2.0/variants/default/.home/private.json",
        "translations/zh-CN/agent/static.json",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private or obsolete")
    for name in (
        "CNAME",
        "robots.txt",
        "sitemap.xml",
        "docs/screenshot.png",
        "docs/agent-icons/agent.svg",
        "docs/translations.md",
        "captures/agent/1.0/static/prompts.md",
        "captures/agent/1.0/static/prompts.json",
        "captures/agent/1.0/static/candidates.json",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public")
    before = hashes(tmp_path / "captures")

    def forbidden(*args, **kwargs):
        pytest.fail("site building must not load translation credentials or call a provider")

    monkeypatch.setattr("phistory.translation.config.load_config", forbidden)
    monkeypatch.setattr("phistory.translation.client.TranslationClient.translate", forbidden)
    public = tmp_path / ".phistory-cache/site"
    assert (
        main(["--root", str(tmp_path / "captures"), "--cache-dir", str(tmp_path / ".phistory-cache"), "build-site"])
        == 0
    )
    assert not (tmp_path / "translations/sources").exists()
    assert hashes(tmp_path / "captures") == before
    assert (public / "translations/zh-CN/agent/runtime.json").read_bytes() == original_dictionary.read_bytes()
    data = manifest(public)
    assert data["count"] == 2
    versions = data["agents"][0]["variants"][0]["versions"]
    for item in versions:
        for kind in ("prompt", "trace"):
            assert item[kind].startswith("captures/agent/")
            assert (public / item[kind]).is_file()
            descriptor = item["translations"]["zh-CN"][kind]
            index = public / descriptor["index"]
            assert descriptor["translated"] == descriptor["total"] == 1
            assert descriptor["fingerprint"] == hashlib.sha256(index.read_bytes()).hexdigest()[:16]
            assert descriptor["source_hash"] == hashlib.sha256((public / item[kind]).read_bytes()).hexdigest()
    assert versions[0]["translations"] == versions[1]["translations"]
    assert len(list((public / "translations/sources").glob("*.json"))) == 2
    assert "static" not in versions[1]["translations"]["zh-CN"]
    for name in (
        "index.html",
        "README.md",
        "README_zh.md",
        "llms.txt",
        ".nojekyll",
        "CNAME",
        "robots.txt",
        "sitemap.xml",
        "docs/screenshot.png",
        "docs/agent-icons/agent.svg",
        "docs/translations.md",
        "captures/agent/1.0/static/prompts.md",
        "captures/agent/1.0/static/candidates.json",
    ):
        assert (public / name).is_file(), name
    for name in (
        ".env",
        "translation.toml",
        ".phistory-cache",
        "captures/agent/2.0/variants/default/.home",
        "translations/zh-CN/agent/static.json",
    ):
        assert not (public / name).exists(), name
    assert "translations" not in json.loads((public / "captures/index.json").read_text())["captures"][0]
    first_build = hashes(public)
    build_site(tmp_path / "captures", public)
    assert hashes(public) == first_build


@pytest.mark.parametrize("contents", [None, "broken JSON"])
def test_build_without_usable_dictionary_falls_back_to_original(tmp_path, contents):
    archive(tmp_path, "1.0")
    if contents is not None:
        dictionary(tmp_path).write_text(contents)
    public = tmp_path / "public"
    build_site(tmp_path / "captures", public)
    assert manifest(public)["agents"][0]["latest"]["translations"] == {}
    assert not (public / "translations/sources").exists()
    assert (public / "captures/agent/1.0/variants/default/prompt.md").read_text() == "Read the file.\n"


def test_rebuild_removes_obsolete_assets_and_refreshes_dictionary_fingerprint(tmp_path):
    source = archive(tmp_path, "1.0")
    dictionary(tmp_path)
    public = tmp_path / "public"
    build_site(tmp_path / "captures", public)
    previous = manifest(public)["agents"][0]["latest"]["translations"]["zh-CN"]
    old_prompt_index = public / previous["prompt"]["index"]
    (source / "prompt.md").write_text("Read the file.\n\nA new paragraph.\n")
    dictionary(tmp_path, "请读取文件。")
    build_site(tmp_path / "captures", public)
    latest = manifest(public)["agents"][0]["latest"]["translations"]["zh-CN"]
    assert not old_prompt_index.exists()
    assert latest["prompt"]["translated"] == 1
    assert latest["prompt"]["total"] == 2
    assert latest["runtime"]["fingerprint"] != previous["runtime"]["fingerprint"]


@pytest.mark.parametrize("newline", [b"\r\n", b"\r"])
def test_build_indexes_exact_archived_bytes_including_line_endings(tmp_path, newline):
    source = archive(tmp_path, "1.0")
    dictionary(tmp_path)
    for name in ("prompt.md", "trace.jsonl"):
        path = source / name
        path.write_bytes(path.read_bytes().replace(b"\n", newline))
    public = tmp_path / "public"
    build_site(tmp_path / "captures", public)
    latest = manifest(public)["agents"][0]["latest"]
    for kind in ("prompt", "trace"):
        raw = (public / latest[kind]).read_bytes()
        descriptor = latest["translations"]["zh-CN"][kind]
        index = json.loads((public / descriptor["index"]).read_text())
        assert descriptor["source_hash"] == index["source_hash"] == hashlib.sha256(raw).hexdigest()


def test_failed_build_preserves_previous_preview(tmp_path, monkeypatch):
    archive(tmp_path, "1.0")
    public = tmp_path / "public"
    build_site(tmp_path / "captures", public)
    before = hashes(public)

    def fail(*args, **kwargs):
        raise ValueError("bad source")

    monkeypatch.setattr("phistory.build.render_site", fail)
    assert main(["--root", str(tmp_path / "captures"), "build-site", "-o", str(public)]) == 1
    assert hashes(public) == before


@pytest.mark.parametrize("output", [".", "captures", "captures/site", "translations", "docs", "private"])
def test_build_refuses_to_replace_source_or_unrelated_directory(tmp_path, output):
    archive(tmp_path, "1.0")
    destination = tmp_path / output
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "keep.txt").write_text("keep")
    # Even a previous-build marker must not allow removal of an input directory.
    if output != "private":
        (destination / BUILD_MARKER).touch()
    with pytest.raises(ValueError):
        build_site(tmp_path / "captures", destination)
    assert (destination / "keep.txt").read_text() == "keep"


def test_archive_index_is_independent_of_translation_assets(tmp_path):
    archive(tmp_path, "1.0")
    render_index(tmp_path / "captures", tmp_path / "README.md")
    before = (tmp_path / "captures/index.json").read_bytes()
    dictionary(tmp_path)
    render_index(tmp_path / "captures", tmp_path / "README.md")
    assert (tmp_path / "captures/index.json").read_bytes() == before
    assert "translations" not in read_capture_rows(tmp_path / "captures")[0]
