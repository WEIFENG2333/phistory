import json
from pathlib import Path

from phistory.models import AgentSpec, CaptureTarget, VersionInfo
from phistory.render import render_index
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
    assert "captures/agent/1.0.0/prompt.md" in text


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
