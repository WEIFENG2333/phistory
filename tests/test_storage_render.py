import json
from pathlib import Path

from phistory.models import AgentSpec, CaptureTarget, VersionInfo
from phistory.render import render_index
from phistory.site import _change_summary, render_site
from phistory.storage import is_captured, write_meta


def test_capture_paths_and_index(tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="pkg",
        tap_client="agent",
        fake_env={},
        run_args=(),
    )
    target = CaptureTarget(agent, VersionInfo("1.0.0", "2026-05-22T00:00:00Z"), tmp_path / "captures")
    target.version_dir.mkdir(parents=True)
    target.prompt_path.write_text("# Prompt\n", encoding="utf-8")
    target.trace_path.write_text("{}\n", encoding="utf-8")
    write_meta(
        target,
        {
            "agent_id": "agent",
            "agent": "Agent",
            "version": "1.0.0",
            "published_at": "2026-05-22T00:00:00Z",
            "captured_at": "2026-05-22T01:00:00Z",
        },
    )

    assert is_captured(target)
    assert json.loads(target.meta_path.read_text(encoding="utf-8"))["version"] == "1.0.0"

    out = tmp_path / "INDEX.md"
    render_index(tmp_path / "captures", out)
    text = out.read_text(encoding="utf-8")
    zh_text = (tmp_path / "README_zh.md").read_text(encoding="utf-8")
    assert "Agent" in text
    assert "[中文](README_zh.md)" in text
    assert "archives versioned system prompt snapshots" in text
    assert "claude-tap" in text
    assert "GitHub Actions checks supported CLI releases every hour" in text
    assert "## Capture Status" in text
    assert "| Agent | Latest | Captures | Last Captured |" in text
    assert "captures/agent/1.0.0/prompt.md" in text
    assert "[1.0.0 - 2026-05-22]" in text
    assert "2026-05-22 01:00 UTC" in text
    assert "| Agent | Version | Published | Captured | Snapshot | Raw Trace |" not in text
    assert "[English](README.md)" in zh_text
    assert "自动归档 Claude Code" in zh_text
    assert "每小时检查一次支持的 CLI 版本" in zh_text
    assert "## 抓取状态" in zh_text
    assert "| Agent | 最新版本 | 快照数 | 最近抓取 |" in zh_text
    assert "[1.0.0 - 2026-05-22]" in zh_text
    assert "## License" not in zh_text

    capture_doc = tmp_path / "docs/captures.md"
    capture_index = tmp_path / "captures/index.json"
    capture_doc_text = capture_doc.read_text(encoding="utf-8")
    capture_index_json = json.loads(capture_index.read_text(encoding="utf-8"))
    assert "| Agent | Version | Published | Captured | Snapshot | Raw Trace |" in capture_doc_text
    assert "[agent 1.0.0, published 2026-05-22 00:00 UTC]" in capture_doc_text
    assert capture_index_json["agents"][0]["latest_version"] == "1.0.0"
    assert capture_index_json["captures"][0]["prompt"] == "captures/agent/1.0.0/prompt.md"


def test_capture_is_incomplete_without_trace(tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="pkg",
        tap_client="agent",
        fake_env={},
        run_args=(),
    )
    target = CaptureTarget(agent, VersionInfo("1.0.0"), tmp_path / "captures")
    target.version_dir.mkdir(parents=True)
    target.prompt_path.write_text("# Prompt\n", encoding="utf-8")
    write_meta(target, {"version": "1.0.0"})

    assert not is_captured(target)


def test_render_index_sorts_versions_numerically(tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="pkg",
        tap_client="agent",
        fake_env={},
        run_args=(),
    )
    for version in ("2.1.99", "2.1.146"):
        target = CaptureTarget(agent, VersionInfo(version), tmp_path / "captures")
        target.version_dir.mkdir(parents=True)
        target.prompt_path.write_text("# Prompt\n", encoding="utf-8")
        target.trace_path.write_text("{}\n", encoding="utf-8")
        write_meta(target, {"agent_id": "agent", "agent": "Agent", "version": version})

    out = tmp_path / "INDEX.md"
    render_index(tmp_path / "captures", out)
    text = out.read_text(encoding="utf-8")

    assert "[2.1.146]" in text
    assert "[2.1.99]" not in text
    capture_doc_text = (tmp_path / "docs/captures.md").read_text(encoding="utf-8")
    assert capture_doc_text.index("`2.1.146`") < capture_doc_text.index("`2.1.99`")


def test_render_site_writes_static_html_manifest(tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="pkg",
        tap_client="agent",
        fake_env={},
        run_args=(),
    )
    for version in ("1.0.0", "1.1.0"):
        target = CaptureTarget(agent, VersionInfo(version, "2026-05-22T00:00:00Z"), tmp_path / "captures")
        target.version_dir.mkdir(parents=True)
        target.prompt_path.write_text(f"# Prompt {version}\n", encoding="utf-8")
        target.trace_path.write_text("{}\n", encoding="utf-8")
        write_meta(
            target,
            {
                "agent_id": "agent",
                "agent": "Agent",
                "package": "pkg",
                "version": version,
                "published_at": "2026-05-22T00:00:00Z",
                "captured_at": "2026-05-22T01:00:00Z",
            },
        )

    out = tmp_path / "index.html"
    render_site(tmp_path / "captures", out)
    text = out.read_text(encoding="utf-8")

    assert "<!doctype html>" in text
    assert "Phistory" in text
    assert "OpenClaw" in text
    assert "application/ld+json" in text
    assert "captures/agent/1.1.0/prompt.md" in text
    assert "2026-05-22" in text
    assert "monaco-editor" in text
    assert "createDiffEditor" in text
    assert "range: 'latest'" in text
    assert "mini-diffstat" in text
    assert '"trace":"' in text
    assert "captures/agent/1.1.0/trace.jsonl" in text
    assert "Trace detail" in text
    assert "Raw Request Body" in text
    assert "toolDeclarations" in text
    assert "schemaParameters" in text
    assert "trace-jumpbar" in text
    assert '"published_display":"2026-05-22 00:00 UTC"' in text
    assert '"captured_display":"2026-05-22 01:00 UTC"' in text
    assert '"previous_version":"1.0.0"' in text
    assert '"changed_lines":2' in text
    assert '"level":1' in text
    assert '"scale":100' in text
    assert "URLSearchParams" in text
    assert "# Prompt 1.1.0" not in text
    assert "captured_at" not in text
    assert "is_latest" not in text
    assert "_compared_line_count" not in text


def test_change_summary_keeps_repeated_prompt_lines_matchable(tmp_path: Path):
    old_prompt = tmp_path / "old.md"
    new_prompt = tmp_path / "new.md"
    old_lines = ["- shared instruction", "", "common"] * 220
    new_lines = old_lines.copy()
    new_lines[len(new_lines) // 2] = "- updated instruction"
    old_prompt.write_text("\n".join(old_lines), encoding="utf-8")
    new_prompt.write_text("\n".join(new_lines), encoding="utf-8")

    change = _change_summary(
        {"version": "1.1.0", "prompt": new_prompt},
        {"version": "1.0.0", "prompt": old_prompt},
    )

    assert change["added_lines"] == 1
    assert change["removed_lines"] == 1
    assert change["changed_lines"] == 2
