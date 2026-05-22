import json
from pathlib import Path

from phistory.models import AgentSpec, CaptureTarget, VersionInfo
from phistory.render import render_index
from phistory.site import render_site
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
    assert "Agent" in text
    assert "archives versioned system prompt snapshots" in text
    assert "claude-tap" in text
    assert "GitHub Actions checks for new supported CLI versions every hour" in text
    assert "## Latest Captures" in text
    assert "- Agent: `1.0.0` published 2026-05-22 00:00 UTC, captured 2026-05-22 01:00 UTC" in text
    assert "captures/agent/1.0.0/prompt.md" in text
    assert "[agent 1.0.0, published 2026-05-22 00:00 UTC]" in text
    assert "2026-05-22 01:00 UTC" in text


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

    assert text.index("`2.1.146`") < text.index("`2.1.99`")


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
    assert "captures/agent/1.1.0/prompt.md" in text
    assert "2026-05-22" in text
    assert "monaco-editor" in text
    assert "createDiffEditor" in text
    assert "URLSearchParams" in text
    assert "# Prompt 1.1.0" not in text
    assert "captured_at" not in text
    assert "is_latest" not in text
    assert "published_display" not in text
