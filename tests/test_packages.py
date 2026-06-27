import io
import tarfile

from phistory.models import AgentSpec, VersionInfo
from phistory.packages import _github_headers, all_versions, install_agent, latest_version, versions_between
from phistory.workflow import iter_backfill


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
        "phistory.packages.all_versions",
        lambda _agent, **_kwargs: [VersionInfo("1.0.0"), VersionInfo("1.1.0"), VersionInfo("2.0.0")],
    )

    assert [item.version for item in versions_between(agent, "1.1.0", "latest")] == ["1.1.0", "2.0.0"]


def test_all_versions_filters_platform_and_prerelease_versions(monkeypatch):
    agent = AgentSpec(
        id="x",
        display_name="X",
        package="x",
        tap_client="x",
        fake_env={},
        run_args=(),
    )
    monkeypatch.setattr(
        "phistory.packages.npm_view",
        lambda *_args: {
            "versions": ["1.0.0", "1.1.0-alpha.1", "1.1.0-linux-x64", "1.1.0"],
            "time": {},
        },
    )

    assert [item.version for item in all_versions(agent)] == ["1.0.0", "1.1.0"]
    assert [item.version for item in all_versions(agent, include_prerelease=True)] == [
        "1.0.0",
        "1.1.0-alpha.1",
        "1.1.0",
    ]


def test_pypi_versions_are_sorted_by_upload_time(monkeypatch):
    agent = AgentSpec(
        id="x",
        display_name="X",
        package="x",
        source="pypi",
        tap_client="x",
        fake_env={},
        run_args=(),
    )
    monkeypatch.setattr(
        "phistory.packages._pypi_json",
        lambda _package: {
            "info": {"version": "0.2.0"},
            "releases": {
                "0.2.0": [
                    {
                        "packagetype": "bdist_wheel",
                        "upload_time_iso_8601": "2026-05-02T00:00:00Z",
                        "url": "https://example.invalid/0.2.whl",
                    }
                ],
                "0.1.0": [
                    {
                        "packagetype": "bdist_wheel",
                        "upload_time_iso_8601": "2026-05-01T00:00:00Z",
                        "url": "https://example.invalid/0.1.whl",
                    }
                ],
                "0.3.0rc1": [
                    {
                        "packagetype": "bdist_wheel",
                        "upload_time_iso_8601": "2026-05-03T00:00:00Z",
                        "url": "https://example.invalid/0.3.whl",
                    }
                ],
            },
        },
    )

    assert latest_version(agent).version == "0.2.0"
    assert [item.version for item in all_versions(agent)] == ["0.1.0", "0.2.0"]
    assert [item.version for item in all_versions(agent, include_prerelease=True)] == ["0.1.0", "0.2.0", "0.3.0rc1"]


def test_github_release_versions_are_sorted_by_publish_time(monkeypatch):
    agent = AgentSpec(
        id="x",
        display_name="X",
        package="owner/repo",
        source="github-release",
        tap_client="x",
        fake_env={},
        run_args=(),
    )
    monkeypatch.setattr(
        "phistory.packages._github_releases",
        lambda _repo: [
            {
                "tag_name": "v2",
                "published_at": "2026-05-02T00:00:00Z",
                "html_url": "https://example.invalid/v2",
                "draft": False,
                "prerelease": False,
            },
            {
                "tag_name": "v1",
                "published_at": "2026-05-01T00:00:00Z",
                "html_url": "https://example.invalid/v1",
                "draft": False,
                "prerelease": False,
            },
            {
                "tag_name": "v3-beta",
                "published_at": "2026-05-03T00:00:00Z",
                "html_url": "https://example.invalid/v3-beta",
                "draft": False,
                "prerelease": True,
            },
        ],
    )

    assert latest_version(agent).version == "v2"
    assert [item.version for item in all_versions(agent)] == ["v1", "v2"]
    assert [item.version for item in all_versions(agent, include_prerelease=True)] == ["v1", "v2", "v3-beta"]


def test_github_release_asset_versions_use_matching_asset(monkeypatch):
    agent = AgentSpec(
        id="x",
        display_name="X",
        package="owner/repo",
        source="github-release-asset",
        release_asset="tool-linux-x64.tar.gz",
        release_asset_binary="tool",
        tap_client="x",
        fake_env={},
        run_args=(),
    )
    monkeypatch.setattr(
        "phistory.packages._github_releases",
        lambda _repo: [
            {
                "tag_name": "1.0.1",
                "published_at": "2026-05-02T00:00:00Z",
                "html_url": "https://example.invalid/1.0.1",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {"name": "tool-linux-x64.tar.gz", "browser_download_url": "https://example.invalid/tool.tgz"}
                ],
            },
            {
                "tag_name": "1.0.0",
                "published_at": "2026-05-01T00:00:00Z",
                "html_url": "https://example.invalid/1.0.0",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {"name": "tool-linux-x64.tar.gz", "browser_download_url": "https://example.invalid/old.tgz"}
                ],
            },
        ],
    )

    assert latest_version(agent) == VersionInfo(
        version="1.0.1", published_at="2026-05-02T00:00:00Z", tarball_url="https://example.invalid/tool.tgz"
    )
    assert [item.version for item in all_versions(agent)] == ["1.0.0", "1.0.1"]


def test_install_github_release_asset_extracts_binary(monkeypatch, tmp_path):
    agent = AgentSpec(
        id="x",
        display_name="X",
        package="owner/repo",
        source="github-release-asset",
        release_asset="tool-linux-x64.tar.gz",
        release_asset_binary="tool",
        tap_client="x",
        fake_env={},
        run_args=(),
    )

    def fake_download(_url, output):
        info = tarfile.TarInfo("package/tool")
        payload = b"#!/bin/sh\nprintf tool\n"
        info.size = len(payload)
        info.mode = 0o755
        with tarfile.open(output, "w:gz") as archive:
            archive.addfile(info, io.BytesIO(payload))

    monkeypatch.setattr(
        "phistory.packages._github_release_asset_info",
        lambda *_args: {"name": "tool-linux-x64.tar.gz", "url": "https://example.invalid/tool.tgz"},
    )
    monkeypatch.setattr("phistory.packages._download", fake_download)

    bin_dir = install_agent(agent, "1.0.0", tmp_path / "install")

    assert (bin_dir / "x").exists()
    assert (bin_dir / "x").read_text(encoding="utf-8") == "#!/bin/sh\nprintf tool\n"


def test_github_headers_can_skip_auth(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "bad-token")

    assert "Authorization" in _github_headers()
    assert "Authorization" not in _github_headers(use_auth=False)


def test_iter_backfill_can_walk_newest_first(monkeypatch, tmp_path):
    agent = AgentSpec(
        id="x",
        display_name="X",
        package="x",
        tap_client="x",
        fake_env={},
        run_args=(),
    )
    monkeypatch.setattr("phistory.workflow.get_agent", lambda _agent_id: agent)
    monkeypatch.setattr(
        "phistory.workflow.packages.versions_between",
        lambda *_args, **_kwargs: [VersionInfo("1.0.0"), VersionInfo("1.1.0"), VersionInfo("2.0.0")],
    )
    monkeypatch.setattr(
        "phistory.workflow.capture_target",
        lambda target, **_kwargs: target.version.version,
    )

    assert list(
        iter_backfill(
            "x",
            start="1.0.0",
            end="2.0.0",
            root=tmp_path,
            cache_dir=tmp_path / "cache",
            newest_first=True,
            limit=2,
        )
    ) == ["2.0.0", "1.1.0"]
