from phistory.models import AgentSpec, VersionInfo
from phistory.npm import versions_between


def test_versions_between_uses_registry_order(monkeypatch):
    agent = AgentSpec(
        id="x",
        display_name="X",
        package="x",
        tap_client="x",
        fake_env={},
        run_args=(),
    )
    monkeypatch.setattr(
        "phistory.npm.all_versions",
        lambda _agent: [VersionInfo("1.0.0"), VersionInfo("1.1.0"), VersionInfo("2.0.0")],
    )

    assert [item.version for item in versions_between(agent, "1.1.0", "latest")] == ["1.1.0", "2.0.0"]
