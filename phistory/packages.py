from __future__ import annotations

import json
import os
import re
import shutil
import urllib.request
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import HTTPError

from phistory.models import AgentSpec, VersionInfo
from phistory.subprocesses import run

_PLATFORM_VERSION_RE = re.compile(r"-(darwin|linux|win32)-(x64|arm64)$")
_PYPI_PRERELEASE_RE = re.compile(r"(?:a|b|rc|dev)\d*$", re.IGNORECASE)


def latest_version(agent: AgentSpec) -> VersionInfo:
    if agent.source == "npm":
        return _npm_latest(agent)
    if agent.source == "pypi":
        return _pypi_latest(agent)
    if agent.source == "github-release":
        return _github_release_latest(agent)
    raise ValueError(f"unsupported package source: {agent.source}")


def all_versions(agent: AgentSpec, *, include_prerelease: bool = False) -> list[VersionInfo]:
    if agent.source == "npm":
        return _npm_versions(agent, include_prerelease=include_prerelease)
    if agent.source == "pypi":
        return _pypi_versions(agent, include_prerelease=include_prerelease)
    if agent.source == "github-release":
        return _github_release_versions(agent, include_prerelease=include_prerelease)
    raise ValueError(f"unsupported package source: {agent.source}")


def versions_between(agent: AgentSpec, start: str, end: str, *, include_prerelease: bool = False) -> list[VersionInfo]:
    versions = all_versions(agent, include_prerelease=include_prerelease)
    if end == "latest":
        end = versions[-1].version
    start_idx = _index_of(versions, start)
    end_idx = _index_of(versions, end)
    if start_idx > end_idx:
        raise ValueError(f"--from {start} is newer than --to {end}")
    return versions[start_idx : end_idx + 1]


def install_agent(agent: AgentSpec, version: str, install_dir: Path) -> Path:
    if agent.source == "npm":
        return _install_npm(agent, version, install_dir)
    if agent.source == "pypi":
        return _install_pypi(agent, version, install_dir)
    if agent.source == "github-release":
        return _install_github_release(agent, version, install_dir)
    raise ValueError(f"unsupported package source: {agent.source}")


def npm_view(package: str, *fields: str) -> object:
    args = ["npm", "view", package, *fields, "--json"]
    result = run(args, timeout=120)
    text = result.stdout.strip()
    return json.loads(text) if text else None


def _npm_latest(agent: AgentSpec) -> VersionInfo:
    data = npm_view(agent.package, "version", "time", "dist.tarball")
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected npm view shape for {agent.package}: {data!r}")
    version = str(data["version"])
    times = data.get("time") if isinstance(data.get("time"), dict) else {}
    return VersionInfo(
        version=version,
        published_at=str(times.get(version)) if times.get(version) else None,
        tarball_url=str(data.get("dist.tarball")) if data.get("dist.tarball") else None,
    )


def _npm_versions(agent: AgentSpec, *, include_prerelease: bool) -> list[VersionInfo]:
    data = npm_view(agent.package, "versions", "time")
    if not isinstance(data, dict) or not isinstance(data.get("versions"), list):
        raise RuntimeError(f"unexpected npm versions shape for {agent.package}: {data!r}")
    times = data.get("time") if isinstance(data.get("time"), dict) else {}
    versions = [
        VersionInfo(version=str(version), published_at=str(times.get(version)) if times.get(version) else None)
        for version in data["versions"]
    ]
    return [item for item in versions if _is_archivable_version(item.version, include_prerelease=include_prerelease)]


def _install_npm(agent: AgentSpec, version: str, install_dir: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    package_ref = f"{agent.package}@{version}"
    run([*agent.install_command, "--prefix", str(install_dir), package_ref], timeout=300)
    bin_dir = install_dir / "node_modules" / ".bin"
    if not bin_dir.exists():
        raise RuntimeError(f"npm install did not create bin dir: {bin_dir}")
    if agent.node_runtime:
        _wrap_node_bin(bin_dir / agent.tap_client, agent.node_runtime)
    return bin_dir


def _pypi_latest(agent: AgentSpec) -> VersionInfo:
    data = _pypi_json(agent.package)
    info = data.get("info")
    if not isinstance(info, dict) or not info.get("version"):
        raise RuntimeError(f"unexpected PyPI package shape for {agent.package}: {data!r}")
    version = str(info["version"])
    return _pypi_version_from_release(version, data.get("releases", {}).get(version))


def _pypi_versions(agent: AgentSpec, *, include_prerelease: bool) -> list[VersionInfo]:
    data = _pypi_json(agent.package)
    releases = data.get("releases")
    if not isinstance(releases, dict):
        raise RuntimeError(f"unexpected PyPI releases shape for {agent.package}: {data!r}")
    versions = [
        _pypi_version_from_release(str(version), files)
        for version, files in releases.items()
        if _is_archivable_version(str(version), include_prerelease=include_prerelease)
    ]
    return sorted(versions, key=lambda item: (item.published_at or "", item.version))


def _install_pypi(agent: AgentSpec, version: str, install_dir: Path) -> Path:
    bin_dir = install_dir / "bin"
    if (bin_dir / agent.tap_client).exists():
        return bin_dir
    if install_dir.exists():
        shutil.rmtree(install_dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    run(["uv", "venv", str(install_dir)], timeout=120)
    run(["uv", "pip", "install", "--python", str(bin_dir / "python"), f"{agent.package}=={version}"], timeout=300)
    if not (bin_dir / agent.tap_client).exists():
        raise RuntimeError(f"PyPI install did not create executable: {bin_dir / agent.tap_client}")
    return bin_dir


def _github_release_latest(agent: AgentSpec) -> VersionInfo:
    releases = _github_releases(agent.package)
    for release in releases:
        if not release.get("draft") and not release.get("prerelease"):
            return _github_release_version(release)
    raise RuntimeError(f"no stable GitHub releases found for {agent.package}")


def _github_release_versions(agent: AgentSpec, *, include_prerelease: bool) -> list[VersionInfo]:
    releases = [
        _github_release_version(release)
        for release in _github_releases(agent.package)
        if not release.get("draft") and (include_prerelease or not release.get("prerelease"))
    ]
    return sorted(releases, key=lambda item: (item.published_at or "", item.version))


def _install_github_release(agent: AgentSpec, version: str, install_dir: Path) -> Path:
    bin_dir = install_dir / "bin"
    if (bin_dir / agent.tap_client).exists():
        return bin_dir
    if install_dir.exists():
        shutil.rmtree(install_dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    run(["uv", "venv", str(install_dir)], timeout=120)
    package_ref = f"https://github.com/{agent.package}/archive/refs/tags/{version}.tar.gz"
    run(["uv", "pip", "install", "--python", str(bin_dir / "python"), package_ref], timeout=600)
    if not (bin_dir / agent.tap_client).exists():
        raise RuntimeError(f"GitHub release install did not create executable: {bin_dir / agent.tap_client}")
    return bin_dir


def _pypi_json(package: str) -> dict:
    url = f"https://pypi.org/pypi/{package}/json"
    with urllib.request.urlopen(url, timeout=120) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected PyPI response for {package}: {data!r}")
    return data


def _github_releases(repo: str) -> list[dict]:
    page = 1
    releases: list[dict] = []
    while True:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
        request = urllib.request.Request(url, headers=_github_headers())
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.load(response)
        except (HTTPError, IncompleteRead) as exc:
            if isinstance(exc, IncompleteRead) or exc.code == 403:
                return _github_releases_via_gh(repo)
            raise
        if not isinstance(data, list):
            raise RuntimeError(f"unexpected GitHub releases response for {repo}: {data!r}")
        if not data:
            return releases
        releases.extend(item for item in data if isinstance(item, dict))
        page += 1


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "phistory",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_releases_via_gh(repo: str) -> list[dict]:
    result = run(["gh", "api", f"repos/{repo}/releases", "--paginate", "--slurp"], timeout=120)
    pages = json.loads(result.stdout)
    if not isinstance(pages, list):
        raise RuntimeError(f"unexpected gh releases response for {repo}: {pages!r}")
    releases: list[dict] = []
    for page in pages:
        if isinstance(page, list):
            releases.extend(item for item in page if isinstance(item, dict))
    return releases


def _github_release_version(release: dict) -> VersionInfo:
    tag = release.get("tag_name")
    if not tag:
        raise RuntimeError(f"GitHub release without tag_name: {release!r}")
    return VersionInfo(
        version=str(tag),
        published_at=str(release.get("published_at")) if release.get("published_at") else None,
        tarball_url=str(release.get("html_url")) if release.get("html_url") else None,
    )


def _pypi_version_from_release(version: str, files: object) -> VersionInfo:
    release_files = files if isinstance(files, list) else []
    preferred = next((item for item in release_files if item.get("packagetype") == "bdist_wheel"), None)
    preferred = preferred or next((item for item in release_files if isinstance(item, dict)), None)
    return VersionInfo(
        version=version,
        published_at=str(preferred.get("upload_time_iso_8601"))
        if preferred and preferred.get("upload_time_iso_8601")
        else None,
        tarball_url=str(preferred.get("url")) if preferred and preferred.get("url") else None,
    )


def _index_of(versions: list[VersionInfo], version: str) -> int:
    for idx, item in enumerate(versions):
        if item.version == version:
            return idx
    raise ValueError(f"version not found: {version}")


def _is_archivable_version(version: str, *, include_prerelease: bool) -> bool:
    if _PLATFORM_VERSION_RE.search(version):
        return False
    if include_prerelease:
        return True
    return "-" not in version and _PYPI_PRERELEASE_RE.search(version) is None


def _wrap_node_bin(executable: Path, node_runtime: str) -> None:
    if not executable.exists():
        raise RuntimeError(f"cannot wrap missing executable: {executable}")
    if not executable.is_symlink():
        try:
            if "PHISTORY_NODE_RUNTIME_WRAPPER" in executable.read_text(encoding="utf-8", errors="ignore"):
                return
        except OSError:
            pass
    if executable.is_symlink():
        real_executable = executable.resolve()
        executable.unlink()
    else:
        real_executable = executable.with_name(f"{executable.name}.real")
        if not real_executable.exists():
            executable.rename(real_executable)
    executable.write_text(
        f'#!/bin/sh\n# PHISTORY_NODE_RUNTIME_WRAPPER\nexec npx -y "{node_runtime}" "{real_executable}" "$@"\n',
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | 0o755)
