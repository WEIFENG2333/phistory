from __future__ import annotations

import json
from pathlib import Path

from phistory.models import AgentSpec, VersionInfo
from phistory.subprocesses import run


def npm_view(package: str, *fields: str) -> object:
    args = ["npm", "view", package, *fields, "--json"]
    result = run(args, timeout=120)
    text = result.stdout.strip()
    return json.loads(text) if text else None


def latest_version(agent: AgentSpec) -> VersionInfo:
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


def all_versions(agent: AgentSpec) -> list[VersionInfo]:
    data = npm_view(agent.package, "versions", "time")
    if not isinstance(data, dict) or not isinstance(data.get("versions"), list):
        raise RuntimeError(f"unexpected npm versions shape for {agent.package}: {data!r}")
    times = data.get("time") if isinstance(data.get("time"), dict) else {}
    return [
        VersionInfo(version=str(version), published_at=str(times.get(version)) if times.get(version) else None)
        for version in data["versions"]
    ]


def versions_between(agent: AgentSpec, start: str, end: str) -> list[VersionInfo]:
    versions = all_versions(agent)
    if end == "latest":
        end = versions[-1].version
    start_idx = _index_of(versions, start)
    end_idx = _index_of(versions, end)
    if start_idx > end_idx:
        raise ValueError(f"--from {start} is newer than --to {end}")
    return versions[start_idx : end_idx + 1]


def install_agent(agent: AgentSpec, version: str, install_dir: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    package_ref = f"{agent.package}@{version}"
    run([*agent.install_command, "--prefix", str(install_dir), package_ref], timeout=300)
    bin_dir = install_dir / "node_modules" / ".bin"
    if not bin_dir.exists():
        raise RuntimeError(f"npm install did not create bin dir: {bin_dir}")
    return bin_dir


def _index_of(versions: list[VersionInfo], version: str) -> int:
    for idx, item in enumerate(versions):
        if item.version == version:
            return idx
    raise ValueError(f"version not found: {version}")
