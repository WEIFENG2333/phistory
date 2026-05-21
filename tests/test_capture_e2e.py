import json
import stat
from pathlib import Path

from phistory.capture import _capture_env, _sanitize_text, capture_target
from phistory.models import AgentSpec, CaptureTarget, VersionInfo


def test_capture_target_runs_local_cli_through_tap(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_codex = bin_dir / "codex"
    fake_codex.write_text(_FAKE_CODEX, encoding="utf-8")
    fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setattr("phistory.npm.install_agent", lambda *_args, **_kwargs: bin_dir)

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
    assert meta["target"] == "local dummy upstream"

    trace_records = [json.loads(line) for line in target.trace_path.read_text(encoding="utf-8").splitlines()]
    assert trace_records
    assert {record["response"]["status"] for record in trace_records} == {200}
    assert all(record["upstream_base_url"].startswith("http://127.0.0.1:") for record in trace_records)

    prompt = target.prompt_path.read_text(encoding="utf-8")
    assert "Fake system prompt" in prompt
    assert str(tmp_path) not in prompt


def test_sanitize_text_normalizes_volatile_claude_headers():
    text = (
        "x-anthropic-billing-header: cc_version=2.1.146.6c9; cc_entrypoint=sdk-cli; cch=abc123;\n"
        " - OS Version: Linux 6.17.0-1013-azure\n"
        "Today's date is 2026-05-21.\n"
        "<current_date>2026-05-21</current_date>\n"
        "<timezone>Etc/UTC</timezone>\n"
        "$PHISTORY_HOME/.claude/projects/-tmp-phistory-work-abc123/memory/\n"
        "Authorization: Bearer phistory-fake-access-token"
    )

    assert _sanitize_text(text, {}) == (
        "x-anthropic-billing-header: cc_version=2.1.146.6c9; cc_entrypoint=sdk-cli; cch=<normalized>;\n"
        " - OS Version: $PHISTORY_OS_VERSION\n"
        "Today's date is $PHISTORY_DATE.\n"
        "<current_date>$PHISTORY_DATE</current_date>\n"
        "<timezone>$PHISTORY_TIMEZONE</timezone>\n"
        "$PHISTORY_HOME/.claude/projects/$PHISTORY_PROJECT/memory/\n"
        "Authorization: Bearer <redacted>"
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


def test_capture_failure_removes_partial_version_dir(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_codex = bin_dir / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    fake_codex.chmod(fake_codex.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setattr("phistory.npm.install_agent", lambda *_args, **_kwargs: bin_dir)

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

    monkeypatch.setattr("phistory.npm.install_agent", lambda *_args, **_kwargs: bin_dir)

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

    monkeypatch.setattr("phistory.npm.install_agent", lambda *_args, **_kwargs: bin_dir)

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
