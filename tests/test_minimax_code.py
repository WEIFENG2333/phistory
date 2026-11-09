import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from phistory import minimax_code
from phistory.models import AgentSpec, VersionInfo
from phistory.packages import all_versions, install_agent, latest_version

MANIFEST = """\
version: 3.0.57
files:
  - url: MiniMax Code-3.0.57-mac.zip
    sha512: ignored
    size: 1
  - url: MiniMax Code-3.0.57-arm64-mac.zip
    sha512: YXJtNjQ=
    size: 2
releaseDate: '2026-07-30T09:39:06.016Z'
"""


def test_parse_manifest_selects_arm64_zip():
    assert minimax_code._parse_manifest(MANIFEST) == {
        "version": "3.0.57",
        "release_date": "2026-07-30T09:39:06.016Z",
        "url": ("https://file.cdn.minimax.io/public/minimax-agent-prod/release/MiniMax%20Code-3.0.57-arm64-mac.zip"),
        "sha512": "YXJtNjQ=",
    }


def test_parse_manifest_rejects_missing_arm64_asset():
    with pytest.raises(RuntimeError, match="unexpected MiniMax Code updater manifest"):
        minimax_code._parse_manifest("version: 3.0.57\nreleaseDate: '2026-07-30T09:39:06.016Z'\n")


def test_version_discovery_uses_manifest_and_official_assets(monkeypatch):
    monkeypatch.setattr(
        minimax_code,
        "latest_version",
        lambda: VersionInfo(
            "3.0.3",
            "2026-07-30T09:39:06.016Z",
            "https://example.invalid/MiniMax%20Code-3.0.3-arm64-mac.zip",
        ),
    )
    available = {"3.0.1", "3.0.3"}
    monkeypatch.setattr(
        minimax_code,
        "_probe_version",
        lambda version: (
            VersionInfo(version, "2026-07-01T00:00:00Z", minimax_code._asset_url(version))
            if version in available
            else None
        ),
    )

    versions = minimax_code.all_versions()

    assert [item.version for item in versions] == ["3.0.1", "3.0.3"]
    assert versions[-1].published_at == "2026-07-30T09:39:06.016Z"


def test_package_dispatches_minimax_code_source(monkeypatch, tmp_path):
    agent = AgentSpec(
        id="minimax-code",
        display_name="MiniMax Code",
        package="MiniMax Code desktop app",
        source="minimax-code",
        tap_client="minimax-code",
        fake_env={},
    )
    version = VersionInfo("3.0.57")
    monkeypatch.setattr(minimax_code, "latest_version", lambda: version)
    monkeypatch.setattr(minimax_code, "all_versions", lambda: [version])
    monkeypatch.setattr(minimax_code, "install", lambda _version, install_dir: install_dir / "bin")

    assert latest_version(agent) == version
    assert all_versions(agent) == [version]
    assert install_agent(agent, version.version, tmp_path) == tmp_path / "bin"


@pytest.mark.parametrize("runtime", ["local-runtime", "local-runtime-v2"])
def test_install_builds_headless_launcher_and_linux_native_module(monkeypatch, tmp_path, runtime):
    version = "3.0.56"
    monkeypatch.setattr(
        minimax_code,
        "_fetch_manifest",
        lambda: {
            "version": "3.0.57",
            "release_date": "2026-07-30T09:39:06.016Z",
            "url": "https://example.invalid/latest.zip",
            "sha512": "unused",
        },
    )

    def fake_download(_url: str, output: Path) -> None:
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("MiniMax Code.app/Contents/Resources/app.asar", b"asar")
            archive.writestr(
                "MiniMax Code.app/Contents/Resources/app.asar.unpacked/example.txt",
                b"sidecar",
            )

    def fake_run(argv, **_kwargs):
        install_dir = tmp_path / "install"
        if argv[0] == "npx":
            app = install_dir / "app"
            files = {
                "package.json": {"version": version},
                "node_modules/@mavis/config/dist/index.js": {},
                f"node_modules/@mavis/{runtime}/dist/index.js": {},
                "node_modules/better-sqlite3/package.json": {"version": "12.11.1"},
            }
            for name, content in files.items():
                path = app / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(content), encoding="utf-8")
        if argv[0] == "npm":
            package = install_dir / "linux-native/node_modules/better-sqlite3/package.json"
            package.parent.mkdir(parents=True, exist_ok=True)
            package.write_text(json.dumps({"version": "12.11.1"}), encoding="utf-8")
        return type("Result", (), {"stdout": "", "stderr": ""})()

    monkeypatch.setattr(minimax_code, "_download", fake_download)
    monkeypatch.setattr(minimax_code, "run", fake_run)

    install_dir = tmp_path / "install"
    bin_dir = minimax_code.install(version, install_dir)

    executable = bin_dir / "minimax-code"
    assert executable.is_file()
    assert executable.stat().st_mode & 0o111
    assert "createLocalRuntimeHost" in executable.read_text(encoding="utf-8")
    assert "modernRuntimeV2Path" in executable.read_text(encoding="utf-8")
    assert "await createLocalRuntimeHost" in executable.read_text(encoding="utf-8")
    assert "/minimax-desktop/api/v1/session/" in executable.read_text(encoding="utf-8")
    assert "process.env.MAVIS_DATA_DIR = dataDir" in executable.read_text(encoding="utf-8")
    assert 'npm: "@ai-sdk/anthropic"' in executable.read_text(encoding="utf-8")
    assert not (install_dir / f"MiniMax-Code-{version}-arm64-mac.zip").exists()
    assert not (install_dir / "resources").exists()


def test_install_supports_bundled_legacy_daemon(monkeypatch, tmp_path):
    version = "3.0.47"
    monkeypatch.setattr(
        minimax_code,
        "_fetch_manifest",
        lambda: {
            "version": "3.0.57",
            "release_date": "2026-07-30T09:39:06.016Z",
            "url": "https://example.invalid/latest.zip",
            "sha512": "unused",
        },
    )

    def fake_download(_url: str, output: Path) -> None:
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("MiniMax Code.app/Contents/Resources/app.asar", b"asar")
            archive.writestr(
                "MiniMax Code.app/Contents/Resources/resources/daemon/daemon.js",
                b"daemon",
            )
            archive.writestr(
                "MiniMax Code.app/Contents/Resources/resources/daemon/.opencode-plugin-sdk/1.14.28/package.json",
                b"{}",
            )

    def fake_run(argv, **_kwargs):
        install_dir = tmp_path / "install"
        if argv[0] == "npx":
            app = install_dir / "app"
            files = {
                "package.json": {"version": version},
                "node_modules/better-sqlite3/package.json": {"version": "12.11.1"},
            }
            for name, content in files.items():
                path = app / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(content), encoding="utf-8")
        if argv[0] == "npm":
            assert "better-sqlite3@12.11.1" in argv
            assert "opencode-ai@1.14.28" in argv
            native = install_dir / "linux-native/node_modules"
            package = native / "better-sqlite3/package.json"
            package.parent.mkdir(parents=True, exist_ok=True)
            package.write_text(json.dumps({"version": "12.11.1"}), encoding="utf-8")
            opencode = native / ".bin/opencode"
            opencode.parent.mkdir(parents=True, exist_ok=True)
            opencode.write_text("#!/bin/sh\n", encoding="utf-8")
        return type("Result", (), {"stdout": "", "stderr": ""})()

    monkeypatch.setattr(minimax_code, "_download", fake_download)
    monkeypatch.setattr(minimax_code, "run", fake_run)

    install_dir = tmp_path / "install"
    bin_dir = minimax_code.install(version, install_dir)

    assert (bin_dir / "minimax-code").is_file()
    assert (install_dir / "resources/resources/daemon/daemon.js").is_file()
    assert "captureWithLegacyDaemon" in (bin_dir / "minimax-code").read_text(encoding="utf-8")


def test_verify_sha512_accepts_electron_updater_base64(tmp_path):
    payload = b"official updater artifact"
    artifact = tmp_path / "artifact.zip"
    artifact.write_bytes(payload)
    expected = base64.b64encode(hashlib.sha512(payload).digest()).decode("ascii")

    minimax_code._verify_sha512(artifact, expected)


def test_http_date_is_normalized_to_utc():
    assert minimax_code._http_date_to_iso("Thu, 30 Jul 2026 09:54:09 GMT") == "2026-07-30T09:54:09Z"
