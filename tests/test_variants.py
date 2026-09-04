import json
from pathlib import Path

import pytest

from phistory.drivers import CaptureRunContext
from phistory.drivers.dsh_web import PROMPT, _create_and_prompt_session, _has_prompt_request
from phistory.models import AgentSpec, CaptureTarget, CaptureVariant, VersionInfo
from phistory.registry import AGENTS, get_agent
from phistory.site import _build_manifest
from phistory.storage import write_meta
from phistory.workflow import capture_latest, iter_backfill


def test_capture_target_keeps_variants_isolated_under_a_version(tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="agent",
        tap_client="agent",
        fake_env={},
        variants=(CaptureVariant("alternate", "Alternate", dimensions={"model": "alternate"}),),
    )

    default = CaptureTarget(agent, VersionInfo("1.0.0"), agent.default_variant, tmp_path)
    alternate = CaptureTarget(agent, VersionInfo("1.0.0"), agent.variant("alternate"), tmp_path)

    assert default.variant_dir == tmp_path / "agent/1.0.0/variants/default"
    assert alternate.variant_dir == tmp_path / "agent/1.0.0/variants/alternate"
    assert default.static_dir == alternate.static_dir == tmp_path / "agent/1.0.0/static"


def test_agent_rejects_duplicate_variant_ids():
    with pytest.raises(ValueError, match="unique"):
        AgentSpec(
            id="agent",
            display_name="Agent",
            package="agent",
            tap_client="agent",
            fake_env={},
            variants=(CaptureVariant("default", "Duplicate"),),
        )


def test_agent_rejects_active_hidden_variant_overlap():
    with pytest.raises(ValueError, match="cannot also be hidden"):
        AgentSpec(
            id="agent",
            display_name="Agent",
            package="agent",
            tap_client="agent",
            fake_env={},
            variants=(CaptureVariant("alternate", "Alternate"),),
            hidden_capture_variants=("alternate",),
        )


@pytest.mark.parametrize("variant_id", ["Not/Safe", "..", ".hidden", "trailing."])
def test_agent_rejects_invalid_variant_ids(variant_id: str):
    with pytest.raises(ValueError, match="invalid"):
        AgentSpec(
            id="agent",
            display_name="Agent",
            package="agent",
            tap_client="agent",
            fake_env={},
            variants=(CaptureVariant(variant_id, "Unsafe"),),
        )


def test_capture_latest_runs_default_and_every_configured_variant(monkeypatch, tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="agent",
        tap_client="agent",
        fake_env={},
        variants=(
            CaptureVariant("one", "One"),
            CaptureVariant("two", "Two"),
        ),
    )
    captured = []
    monkeypatch.setattr("phistory.workflow.get_agent", lambda _agent_id: agent)
    monkeypatch.setattr("phistory.workflow.packages.latest_version", lambda _agent: VersionInfo("1.0.0"))

    def fake_capture(target, **_kwargs):
        captured.append(target)
        return target.variant.id

    monkeypatch.setattr("phistory.workflow.capture_target", fake_capture)

    results = capture_latest(["agent"], root=tmp_path / "captures", cache_dir=tmp_path / "cache")

    assert results == ["default", "one", "two"]
    assert [target.variant.id for target in captured] == ["default", "one", "two"]
    assert {target.version.version for target in captured} == {"1.0.0"}


def test_capture_latest_skips_variants_before_their_minimum_version(monkeypatch, tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="agent",
        tap_client="agent",
        fake_env={},
        variants=(CaptureVariant("future", "Future", min_version="2.0.0"),),
    )
    captured = []
    monkeypatch.setattr("phistory.workflow.get_agent", lambda _agent_id: agent)
    monkeypatch.setattr("phistory.workflow.packages.latest_version", lambda _agent: VersionInfo("1.9.0"))
    monkeypatch.setattr(
        "phistory.workflow.capture_target",
        lambda target, **_kwargs: captured.append(target.variant.id) or target.variant.id,
    )

    results = capture_latest(["agent"], root=tmp_path / "captures", cache_dir=tmp_path / "cache")

    assert results == ["default"]
    assert captured == ["default"]


def test_backfill_starts_a_variant_at_its_minimum_version(monkeypatch, tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="agent",
        tap_client="agent",
        fake_env={},
        variants=(CaptureVariant("future", "Future", min_version="1.1.0"),),
    )
    versions = [
        VersionInfo("1.0.0"),
        VersionInfo("1.1.0-alpha.1"),
        VersionInfo("1.1.0"),
        VersionInfo("1.2.0"),
    ]
    monkeypatch.setattr("phistory.workflow.get_agent", lambda _agent_id: agent)
    monkeypatch.setattr("phistory.workflow.packages.versions_between", lambda *_args, **_kwargs: versions)
    monkeypatch.setattr(
        "phistory.workflow.capture_target",
        lambda target, **_kwargs: (target.version.version, target.variant.id),
    )

    results = list(
        iter_backfill(
            "agent",
            start="1.0.0",
            end="1.2.0",
            root=tmp_path / "captures",
            cache_dir=tmp_path / "cache",
        )
    )

    assert results == [
        ("1.0.0", "default"),
        ("1.1.0-alpha.1", "default"),
        ("1.1.0", "default"),
        ("1.1.0", "future"),
        ("1.2.0", "default"),
        ("1.2.0", "future"),
    ]


def test_dsh_web_default_does_not_override_mode(monkeypatch, tmp_path: Path):
    agent = get_agent("dsh")
    payloads = []
    monkeypatch.setattr(
        "phistory.drivers.dsh_web._rpc_when_ready",
        lambda _port, _method, payload, _process: payloads.append(payload) or {"sessionId": "session"},
    )
    monkeypatch.setattr("phistory.drivers.dsh_web._rpc", lambda *_args: {})

    for variant_id in ("default", "code"):
        target = CaptureTarget(agent, VersionInfo("1.0.0"), agent.variant(variant_id), tmp_path)
        context = CaptureRunContext(target, target.prompt_path, target.variant_dir / ".tap", tmp_path, {})
        _create_and_prompt_session(context, 1234, object())

    assert "agentPreset" not in payloads[0]
    assert payloads[1]["agentPreset"] == "code"


def test_dsh_web_accepts_a_prompt_request_without_tools(tmp_path: Path):
    trace_dir = tmp_path / "session"
    trace_dir.mkdir()
    (trace_dir / "trace_1.jsonl").write_text(
        json.dumps({"request": {"body": {"messages": [{"role": "user", "content": PROMPT}]}}}) + "\n",
        encoding="utf-8",
    )

    assert _has_prompt_request(tmp_path)


def test_site_manifest_builds_independent_variant_version_lanes(tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="agent",
        tap_client="agent",
        fake_env={},
        variants=(CaptureVariant("model-b", "Model B", dimensions={"model": "model-b"}),),
    )
    captures = (
        ("1.0.0", "default", "old default"),
        ("1.1.0", "default", "new default"),
        ("1.0.0", "model-b", "only model b"),
    )
    for version, variant_id, prompt in captures:
        variant = agent.variant(variant_id)
        target = CaptureTarget(agent, VersionInfo(version), variant, tmp_path)
        target.variant_dir.mkdir(parents=True)
        target.prompt_path.write_text(prompt + "\n", encoding="utf-8")
        target.trace_path.write_text("{}\n", encoding="utf-8")
        write_meta(
            target,
            {
                "agent_id": agent.id,
                "agent": agent.display_name,
                "version": version,
                "variant": {
                    "id": variant.id,
                    "label": variant.label,
                    "dimensions": variant.dimensions,
                },
            },
        )

    manifest = _build_manifest(tmp_path)
    site_agent = manifest["agents"][0]
    lanes = {variant["id"]: variant for variant in site_agent["variants"]}

    assert site_agent["default_variant"] == "default"
    assert [variant["id"] for variant in site_agent["variants"]] == ["default", "model-b"]
    assert [item["version"] for item in lanes["default"]["versions"]] == ["1.1.0", "1.0.0"]
    assert lanes["default"]["versions"][0]["change"]["previous_version"] == "1.0.0"
    assert lanes["model-b"]["versions"][0]["change"]["previous_version"] is None
    assert lanes["model-b"]["versions"][0]["variant_dimensions"] == {"model": "model-b"}


def test_site_manifest_hides_captures_before_a_registered_variant_minimum(monkeypatch, tmp_path: Path):
    agent = AgentSpec(
        id="gated-agent",
        display_name="Gated Agent",
        package="agent",
        tap_client="agent",
        fake_env={},
        variants=(CaptureVariant("future", "Future", min_version="1.1.0"),),
    )
    monkeypatch.setitem(AGENTS, agent.id, agent)
    for version in ("1.0.0", "1.1.0"):
        target = CaptureTarget(agent, VersionInfo(version), agent.variant("future"), tmp_path)
        target.variant_dir.mkdir(parents=True)
        target.prompt_path.write_text(f"prompt {version}\n", encoding="utf-8")
        target.trace_path.write_text("{}\n", encoding="utf-8")
        write_meta(
            target,
            {
                "agent_id": agent.id,
                "agent": agent.display_name,
                "version": version,
                "variant": {"id": "future", "label": "Future", "dimensions": {}},
            },
        )

    lanes = {lane["id"]: lane for lane in _build_manifest(tmp_path)["agents"][0]["variants"]}

    assert [item["version"] for item in lanes["future"]["versions"]] == ["1.1.0"]
    assert lanes["future"]["versions"][0]["change"]["previous_version"] is None


def test_site_manifest_hides_archived_variants(monkeypatch, tmp_path: Path):
    agent = AgentSpec(
        id="agent",
        display_name="Agent",
        package="agent",
        tap_client="agent",
        fake_env={},
        hidden_capture_variants=("retired",),
    )
    monkeypatch.setitem(AGENTS, agent.id, agent)
    for variant in (agent.default_variant, CaptureVariant("retired", "Retired")):
        target = CaptureTarget(agent, VersionInfo("1.0.0"), variant, tmp_path)
        target.variant_dir.mkdir(parents=True)
        target.prompt_path.write_text(f"{variant.id}\n", encoding="utf-8")
        target.trace_path.write_text("{}\n", encoding="utf-8")
        write_meta(
            target,
            {
                "agent_id": agent.id,
                "agent": agent.display_name,
                "version": "1.0.0",
                "variant": {"id": variant.id, "label": variant.label, "dimensions": {}},
            },
        )

    lanes = {lane["id"] for lane in _build_manifest(tmp_path)["agents"][0]["variants"]}

    assert lanes == {"default"}


def test_site_does_not_read_the_removed_flat_capture_layout(tmp_path: Path):
    version_dir = tmp_path / "agent/1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "prompt.md").write_text("legacy\n", encoding="utf-8")
    (version_dir / "trace.jsonl").write_text("{}\n", encoding="utf-8")
    (version_dir / "meta.json").write_text(json.dumps({"agent_id": "agent", "version": "1.0.0"}), encoding="utf-8")

    assert _build_manifest(tmp_path) == {"agents": [], "count": 0}


def test_capture_workflow_commits_successful_outputs_before_reporting_failures():
    workflow = Path(".github/workflows/capture.yml").read_text(encoding="utf-8")

    assert "group: capture-prompts-${{ github.ref }}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert workflow.index("git add README.md") < workflow.index("git diff --cached --quiet")
    assert workflow.index("name: Commit capture updates") < workflow.index("name: Report capture failures")
