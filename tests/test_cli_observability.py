from pathlib import Path

from phistory.cli import _print_results, main
from phistory.models import AgentSpec, CaptureResult
from phistory.workflow import capture_latest


def test_print_results_writes_github_summary_and_annotations(tmp_path: Path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    code = _print_results(
        [
            CaptureResult("codex", "1.0.0", "captured", tmp_path / "prompt.md", tmp_path / "trace.jsonl"),
            CaptureResult("claude-code", "unknown", "failed", error="first line\nsecond line"),
        ],
        "Observed capture",
    )

    assert code == 1
    text = summary.read_text(encoding="utf-8")
    assert "## Observed capture" in text
    assert "Captured: **1** · Skipped: **0** · Failed: **1**" in text
    assert "`codex`" in text
    assert "`claude-code`" in text
    assert "first line second line" in text
    assert "::error title=claude-code unknown capture failed::first line second line" in capsys.readouterr().err


def test_capture_allow_failures_reports_but_exits_zero(tmp_path: Path, monkeypatch):
    def fake_capture_latest(agent_ids, *, root, cache_dir, force, keep_tap):
        assert agent_ids == ["claude-code"]
        assert root == tmp_path / "captures"
        assert cache_dir == tmp_path / "cache"
        assert force is True
        assert keep_tap is False
        return [CaptureResult("claude-code", "2.1.204", "failed", error="tap failed")]

    monkeypatch.setattr("phistory.cli.capture_latest", fake_capture_latest)

    code = main(
        [
            "--root",
            str(tmp_path / "captures"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "capture",
            "--latest",
            "--agents",
            "claude-code",
            "--force",
            "--allow-failures",
        ]
    )

    assert code == 0


def test_capture_latest_reports_version_lookup_failure(monkeypatch, tmp_path: Path):
    agent = AgentSpec(
        id="broken",
        display_name="Broken",
        package="broken",
        tap_client="broken",
        fake_env={},
        run_args=(),
    )
    monkeypatch.setattr("phistory.workflow.get_agent", lambda _agent_id: agent)
    monkeypatch.setattr(
        "phistory.workflow.packages.latest_version", lambda _agent: (_ for _ in ()).throw(RuntimeError("registry down"))
    )

    results = capture_latest(["broken"], root=tmp_path / "captures", cache_dir=tmp_path / "cache")

    assert len(results) == 1
    assert results[0].agent_id == "broken"
    assert results[0].version == "unknown"
    assert results[0].status == "failed"
    assert results[0].error == "registry down"
