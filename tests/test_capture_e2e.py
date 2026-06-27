import json
import stat
from pathlib import Path

from phistory.capture import (
    _capture_command,
    _capture_env,
    _needs_antigravity_model_retry,
    _needs_antigravity_prompt_retry,
    _sanitize_text,
    _without_arg_and_value,
    capture_target,
)
from phistory.models import AgentSpec, CaptureTarget, VersionInfo


def test_capture_target_runs_local_cli_through_tap(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_codex = bin_dir / "codex"
    fake_codex.write_text(_FAKE_CODEX, encoding="utf-8")
    fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setattr("phistory.packages.install_agent", lambda *_args, **_kwargs: bin_dir)

    agent = AgentSpec(
        id="fake-codex",
        display_name="Fake Codex",
        package="fake-codex",
        tap_client="codex",
        fake_env={"OPENAI_API_KEY": "fake"},
        run_args=("--no-yolo", "--", "exec", "hello", "--json"),
    )
    target = CaptureTarget(agent, VersionInfo("1.0.0", "2026-05-22T00:00:00Z"), tmp_path / "captures")

    result = capture_target(target, cache_dir=tmp_path / "cache", force=True)

    assert result.status == "captured"
    assert target.prompt_path.exists()
    assert target.trace_path.exists()
    assert target.meta_path.exists()
    assert not (target.version_dir / ".home").exists()

    meta = json.loads(target.meta_path.read_text(encoding="utf-8"))
    assert meta["binary_version"] == "fake-codex 1.0.0"
    assert meta["target"] == "claude-tap capture-only"
    assert "-t" not in meta["command"]

    trace_records = [json.loads(line) for line in target.trace_path.read_text(encoding="utf-8").splitlines()]
    assert trace_records
    assert {record["response"]["status"] for record in trace_records} == {200}
    assert all(record["response"]["body"]["id"].startswith("resp_claude_tap_capture") for record in trace_records)

    prompt = target.prompt_path.read_text(encoding="utf-8")
    assert "Fake system prompt" in prompt
    assert str(tmp_path) not in prompt


def test_sanitize_text_normalizes_volatile_claude_headers():
    text = (
        "x-anthropic-billing-header: cc_version=2.1.146.6c9; cc_entrypoint=sdk-cli; cch=abc123;\n"
        " - OS Version: Linux 6.17.0-1013-azure\n"
        "Today's date is 2026-05-21.\n"
        "The current date and time in ISO format is `2026-05-23T07:26:17.532901+00:00`.\n"
        "The current local time is: 2026-06-27T13:47:31+08:00.\n"
        "Conversation started: Friday, June 05, 2026 08:07 PM\n"
        "Conversation ID: d6609428-853a-4f4d-80e5-229becf1fff5\n"
        "<current_date>2026-05-21</current_date>\n"
        "<timezone>Etc/UTC</timezone>\n"
        "$PHISTORY_HOME/.gemini/antigravity-cli/brain/d6609428-853a-4f4d-80e5-229becf1fff5\n"
        "$PHISTORY_HOME/.claude/projects/-tmp-phistory-work-abc123/memory/\n"
        "Authorization: Bearer phistory-fake-access-token\n"
        "\n"
        "\n"
        "```json"
    )

    assert _sanitize_text(text, {}) == (
        "x-anthropic-billing-header: cc_version=2.1.146.6c9; cc_entrypoint=sdk-cli; cch=<normalized>;\n"
        " - OS Version: $PHISTORY_OS_VERSION\n"
        "Today's date is $PHISTORY_DATE.\n"
        "The current date and time in ISO format is `$PHISTORY_DATETIME`.\n"
        "The current local time is: $PHISTORY_DATETIME.\n"
        "Conversation started: $PHISTORY_DATETIME\n"
        "Conversation ID: $PHISTORY_CONVERSATION\n"
        "<current_date>$PHISTORY_DATE</current_date>\n"
        "<timezone>$PHISTORY_TIMEZONE</timezone>\n"
        "$PHISTORY_HOME/.gemini/antigravity-cli/brain/$PHISTORY_CONVERSATION\n"
        "$PHISTORY_HOME/.claude/projects/$PHISTORY_PROJECT/memory/\n"
        "Authorization: Bearer <redacted>\n"
        "\n"
        "```json"
    )


def test_capture_env_writes_fake_chatgpt_auth(tmp_path: Path):
    agent = AgentSpec(
        id="codex",
        display_name="Codex",
        package="@openai/codex",
        tap_client="codex",
        fake_env={},
        run_args=(),
        fake_chatgpt_auth=True,
    )
    target = CaptureTarget(agent, VersionInfo("1.0.0"), tmp_path / "captures")

    env = _capture_env(target, tmp_path / "bin", tmp_path / "home")

    auth = json.loads((tmp_path / "home" / ".codex" / "auth.json").read_text(encoding="utf-8"))
    assert auth["auth_mode"] == "chatgpt"
    assert auth["tokens"]["access_token"] == "phistory-fake-access-token"
    assert env["OPENAI_API_KEY"] == ""
    assert env["CI"] == "true"
    assert env["GITHUB_ACTIONS"] == "true"
    assert env["TZ"] == "Etc/UTC"


def test_capture_env_writes_agent_profile_configs(tmp_path: Path):
    antigravity = AgentSpec(
        id="antigravity",
        display_name="Antigravity",
        package="antigravity",
        tap_client="agy",
        fake_env={},
        run_args=(),
        home_profile="antigravity",
    )
    openclaw = AgentSpec(
        id="openclaw",
        display_name="OpenClaw",
        package="openclaw",
        tap_client="openclaw",
        fake_env={},
        run_args=(),
        home_profile="openclaw",
    )
    hermes = AgentSpec(
        id="hermes",
        display_name="Hermes",
        package="hermes-agent",
        tap_client="hermes",
        fake_env={},
        run_args=(),
        home_profile="hermes",
    )
    kimi = AgentSpec(
        id="kimi",
        display_name="Kimi",
        package="kimi-cli",
        tap_client="kimi",
        fake_env={},
        run_args=(),
        home_profile="kimi",
    )
    opencode = AgentSpec(
        id="opencode",
        display_name="opencode",
        package="opencode-ai",
        tap_client="opencode",
        fake_env={},
        run_args=(),
        home_profile="opencode",
    )
    pi = AgentSpec(
        id="pi",
        display_name="Pi",
        package="pi",
        tap_client="pi",
        fake_env={},
        run_args=(),
        home_profile="pi",
    )

    antigravity_env = _capture_env(
        CaptureTarget(antigravity, VersionInfo("1.0.0"), tmp_path), tmp_path / "bin", tmp_path / "ag"
    )
    openclaw_env = _capture_env(
        CaptureTarget(openclaw, VersionInfo("1.0.0"), tmp_path), tmp_path / "bin", tmp_path / "oc"
    )
    hermes_env = _capture_env(CaptureTarget(hermes, VersionInfo("1.0.0"), tmp_path), tmp_path / "bin", tmp_path / "hm")
    kimi_env = _capture_env(CaptureTarget(kimi, VersionInfo("1.0.0"), tmp_path), tmp_path / "bin", tmp_path / "km")
    opencode_env = _capture_env(
        CaptureTarget(opencode, VersionInfo("1.0.0"), tmp_path), tmp_path / "bin", tmp_path / "op"
    )
    pi_env = _capture_env(CaptureTarget(pi, VersionInfo("1.0.0"), tmp_path), tmp_path / "bin", tmp_path / "pi")

    agy_token = json.loads(
        (Path(antigravity_env["HOME"]) / ".gemini" / "antigravity-cli" / "antigravity-oauth-token").read_text(
            encoding="utf-8"
        )
    )
    openclaw_config = json.loads(Path(openclaw_env["OPENCLAW_CONFIG_PATH"]).read_text(encoding="utf-8"))
    kimi_config = (Path(kimi_env["KIMI_SHARE_DIR"]) / "config.toml").read_text(encoding="utf-8")
    opencode_config = json.loads(Path(opencode_env["OPENCODE_CONFIG"]).read_text(encoding="utf-8"))
    pi_models = json.loads((Path(pi_env["PI_CODING_AGENT_DIR"]) / "models.json").read_text(encoding="utf-8"))
    assert agy_token["auth_method"] == "consumer"
    assert agy_token["token"]["access_token"] == "phistory-fake-access-token"
    assert openclaw_config["models"]["providers"]["phistory"]["api"] == "openai-responses"
    assert (Path(hermes_env["HERMES_HOME"]) / "config.yaml").read_text(encoding="utf-8").startswith("model:")
    assert 'type = "openai_responses"' in kimi_config
    assert opencode_config["model"] == "openai/gpt-4.1"
    assert pi_models["providers"]["phistory"]["api"] == "openai-responses"


def test_capture_command_can_use_tap_target(tmp_path: Path):
    agent = AgentSpec(
        id="antigravity",
        display_name="Antigravity",
        package="antigravity",
        tap_client="agy",
        fake_env={},
        run_args=("--no-yolo", "--", "--print", "hello"),
        tap_target_profile="antigravity",
    )
    target = CaptureTarget(agent, VersionInfo("1.0.0"), tmp_path)

    argv = _capture_command(target, tmp_path / "prompt.md", tmp_path / ".tap", tap_target="http://127.0.0.1:1234")

    assert "--tap-target" in argv
    assert argv[argv.index("--tap-target") + 1] == "http://127.0.0.1:1234"
    assert argv[-2:] == ["--print", "hello"]


def test_antigravity_model_flag_retry_removes_model_value():
    agent = AgentSpec(
        id="antigravity",
        display_name="Antigravity",
        package="antigravity",
        tap_client="agy",
        fake_env={},
        run_args=(),
    )
    target = CaptureTarget(agent, VersionInfo("1.0.4"), Path("captures"))
    result = type("Result", (), {"returncode": 1, "stderr": "flags provided but not defined: -model", "stdout": ""})()

    assert _needs_antigravity_model_retry(target, result)
    assert _without_arg_and_value(["agy", "--print", "hello", "--model", "flash"], "--model") == [
        "agy",
        "--print",
        "hello",
    ]


def test_antigravity_no_prompt_retry_only_when_prompt_missing(tmp_path: Path):
    agent = AgentSpec(
        id="antigravity",
        display_name="Antigravity",
        package="antigravity",
        tap_client="agy",
        fake_env={},
        run_args=(),
    )
    target = CaptureTarget(agent, VersionInfo("1.0.13"), tmp_path)
    result = type(
        "Result", (), {"returncode": 1, "stderr": "Error: no prompt-bearing request found in trace", "stdout": ""}
    )()

    assert _needs_antigravity_prompt_retry(target, result, tmp_path / "missing.md")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# Prompt\n", encoding="utf-8")
    assert not _needs_antigravity_prompt_retry(target, result, prompt)


def test_capture_failure_removes_partial_version_dir(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_codex = bin_dir / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setattr("phistory.packages.install_agent", lambda *_args, **_kwargs: bin_dir)

    agent = AgentSpec(
        id="broken-codex",
        display_name="Broken Codex",
        package="broken-codex",
        tap_client="codex",
        fake_env={"OPENAI_API_KEY": "fake"},
        run_args=("--no-yolo", "--", "exec", "hello", "--json"),
    )
    target = CaptureTarget(agent, VersionInfo("1.0.0"), tmp_path / "captures")

    result = capture_target(target, cache_dir=tmp_path / "cache", force=True)

    assert result.status == "failed"
    assert not target.version_dir.exists()


def test_capture_retries_old_claude_without_session_persistence(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_claude = bin_dir / "claude"
    fake_claude.write_text(_FAKE_OLD_CLAUDE, encoding="utf-8")
    fake_claude.chmod(fake_claude.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setattr("phistory.packages.install_agent", lambda *_args, **_kwargs: bin_dir)

    agent = AgentSpec(
        id="claude-code",
        display_name="Claude Code",
        package="@anthropic-ai/claude-code",
        tap_client="claude",
        fake_env={"ANTHROPIC_API_KEY": "fake"},
        run_args=("--no-yolo", "--", "--no-session-persistence", "-p", "hello"),
    )
    target = CaptureTarget(agent, VersionInfo("0.2.9"), tmp_path / "captures")

    result = capture_target(target, cache_dir=tmp_path / "cache", force=True)

    assert result.status == "captured"
    meta = json.loads(target.meta_path.read_text(encoding="utf-8"))
    assert "--no-session-persistence" not in meta["command"]


def test_capture_retries_old_codex_with_api_key(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_codex = bin_dir / "codex"
    fake_codex.write_text(_FAKE_OLD_CODEX, encoding="utf-8")
    fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setattr("phistory.packages.install_agent", lambda *_args, **_kwargs: bin_dir)

    agent = AgentSpec(
        id="codex",
        display_name="Codex",
        package="@openai/codex",
        tap_client="codex",
        fake_env={},
        run_args=("--no-yolo", "--", "exec", "hello", "--json"),
        fake_chatgpt_auth=True,
    )
    target = CaptureTarget(agent, VersionInfo("0.1.0"), tmp_path / "captures")

    result = capture_target(target, cache_dir=tmp_path / "cache", force=True)

    assert result.status == "captured"
    assert "Old Codex system prompt" in target.prompt_path.read_text(encoding="utf-8")


_FAKE_CODEX = """#!/usr/bin/env python3
import json
import re
import sys
import urllib.request

if "--version" in sys.argv:
    print("fake-codex 1.0.0")
    raise SystemExit(0)

base_url = None
for arg in sys.argv:
    match = re.search(r'base_url="([^"]+)"', arg)
    if match:
        base_url = match.group(1)
        break

if not base_url:
    print("missing base_url override", file=sys.stderr)
    raise SystemExit(2)

payload = {
    "model": "fake-model",
    "instructions": "Fake system prompt",
    "input": "hello",
    "tools": [
        {
            "type": "function",
            "name": "shell",
            "description": "run a command",
            "parameters": {"type": "object", "properties": {}},
        }
    ],
}
request = urllib.request.Request(
    base_url.rstrip("/") + "/responses",
    data=json.dumps(payload).encode("utf-8"),
    headers={"content-type": "application/json", "authorization": "Bearer fake"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=10) as response:
    response.read()
"""


_FAKE_OLD_CODEX = """#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.request

if "--version" in sys.argv:
    print("codex-cli 0.1.0")
    raise SystemExit(0)

if not os.environ.get("OPENAI_API_KEY"):
    print("Missing OpenAI API key.", file=sys.stderr)
    raise SystemExit(1)

base_url = None
for arg in sys.argv:
    match = re.search(r'base_url="([^"]+)"', arg)
    if match:
        base_url = match.group(1)
        break

if not base_url:
    print("missing base_url override", file=sys.stderr)
    raise SystemExit(2)

payload = {"model": "fake-model", "instructions": "Old Codex system prompt", "input": "hello", "tools": []}
request = urllib.request.Request(
    base_url.rstrip("/") + "/responses",
    data=json.dumps(payload).encode("utf-8"),
    headers={"content-type": "application/json", "authorization": "Bearer fake"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=10) as response:
    response.read()
"""


_FAKE_OLD_CLAUDE = """#!/usr/bin/env python3
import json
import os
import sys
import urllib.request

if "--version" in sys.argv:
    print("0.2.9 (Claude Code)")
    raise SystemExit(0)

if "--no-session-persistence" in sys.argv:
    print("error: unknown option '--no-session-persistence'", file=sys.stderr)
    raise SystemExit(1)

base_url = os.environ.get("ANTHROPIC_BASE_URL")
if not base_url:
    print("missing ANTHROPIC_BASE_URL", file=sys.stderr)
    raise SystemExit(2)

payload = {
    "model": "fake-claude",
    "messages": [{"role": "user", "content": "hello"}],
    "system": [{"type": "text", "text": "Old Claude system prompt"}],
    "tools": [],
}
request = urllib.request.Request(
    base_url.rstrip("/") + "/v1/messages",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json", "x-api-key": "fake", "anthropic-version": "2023-06-01"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=10) as response:
    response.read()
"""
