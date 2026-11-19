import json
from pathlib import Path

import pytest
from claude_tap.bootstrap import BootstrapResponses

from phistory.capture import _capture_env, capture_target
from phistory.drivers import CaptureExecution
from phistory.drivers.common import bootstrap_path, tap_command
from phistory.models import CaptureTarget, CommandResult, VersionInfo
from phistory.registry import get_agent
from phistory.render import read_capture_rows
from phistory.site import _build_manifest


@pytest.mark.parametrize(
    "tool,provenance,success", [("REPL", True, True), ("Read", True, False), ("REPL", False, False)]
)
def test_code_mode_verifies_observed_tools_and_preserves_previous_capture(
    tmp_path, monkeypatch, tool, provenance, success
):
    agent = get_agent("claude-code")
    target = CaptureTarget(agent, VersionInfo("2.1.328"), agent.variant("code-mode"), tmp_path / "captures")
    target.variant_dir.mkdir(parents=True)
    target.prompt_path.write_text("previous prompt")
    target.trace_path.write_text("previous trace")
    target.meta_path.write_text("{}")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setattr("phistory.packages.install_agent", lambda *args: bin_dir)
    monkeypatch.setattr("phistory.capture._binary_version", lambda *args: "2.1.328")

    def run(context):
        record = {"request": {"body": {"system": "system instructions", "model": "test", "tools": [{"name": tool}]}}}
        if provenance:
            record["capture_environment"] = BootstrapResponses.load(bootstrap_path(target)).provenance()
        context.target.trace_path.write_text(json.dumps(record) + "\n")
        return CaptureExecution(CommandResult(("claude",), 0, "", ""), {"surface": "interactive-tty"})

    monkeypatch.setattr("phistory.capture.run_capture", run)
    result = capture_target(target, cache_dir=tmp_path / "cache", force=True)
    assert (result.status == "captured") == success
    if success:
        assert "locally simulated startup settings" in target.prompt_path.read_text()
        meta = json.loads(target.meta_path.read_text())
        assert meta["observed"]["tool_count"] == 1
        assert meta["capture_environment"]["kind"] == "mocked-bootstrap"
        rows = read_capture_rows(target.root)
        assert rows[0]["mocked_bootstrap"] is True
        manifest = _build_manifest(target.root)
        assert manifest["agents"][0]["variants"][0]["versions"][0]["mocked_bootstrap"] is True
    else:
        assert target.prompt_path.read_text() == "previous prompt"
        assert target.trace_path.read_text() == "previous trace"


def test_code_mode_configuration_is_variant_scoped(tmp_path):
    agent = get_agent("claude-code")
    for variant in agent.capture_variants:
        target = CaptureTarget(agent, VersionInfo("2.1.328"), variant, tmp_path)
        home = tmp_path / variant.id
        env = _capture_env(target, tmp_path / "bin", home, tmp_path / "work")
        command = tap_command(target, tmp_path / variant.id / "tap")
        config = json.loads((home / ".claude.json").read_text())
        if variant.id == "code-mode":
            assert env["ANTHROPIC_API_KEY"] == "fake"
            assert env["CLAUDE_CODE_EXPERIMENTAL_CODE_MODE"] == "1"
            assert config["codeModeCaveatsAcceptedV1"] is True
            assert config["codeModeAutoModeCaveatAcceptedV1"] is True
            assert command[command.index("--mode") + 1] == "forward"
            assert Path(command[command.index("--bootstrap-responses") + 1]).is_file()
            assert variant.required_tools == ("REPL",)
        else:
            assert "CLAUDE_CODE_EXPERIMENTAL_CODE_MODE" not in env
            assert "codeModeCaveatsAcceptedV1" not in config
            assert "--bootstrap-responses" not in command


def test_code_mode_prompt_ids_do_not_create_diff_noise():
    from phistory.sanitize import sanitize

    assert sanitize("cc_prompt_id=one; cch=abc;") == sanitize("cc_prompt_id=two; cch=def;")
