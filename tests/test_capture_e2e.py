import json
import stat
from pathlib import Path

from phistory.capture import capture_target
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
    assert {record["upstream_base_url"] for record in trace_records} == {"http://127.0.0.1:<dummy>"}

    prompt = target.prompt_path.read_text(encoding="utf-8")
    assert "Fake system prompt" in prompt
    assert str(tmp_path) not in prompt


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
