from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from phistory.models import VersionInfo
from phistory.subprocesses import run

RELEASE_ROOT = "https://file.cdn.minimax.io/public/minimax-agent-prod/release/"
MANIFEST_URL = f"{RELEASE_ROOT}latest-mac.yml"
ASAR_PACKAGE = "@electron/asar@3.4.1"
DOWNLOAD_ATTEMPTS = 3
NETWORK_ATTEMPTS = 5
PROBE_TIMEOUT_SECONDS = 30
PROBE_WORKERS = 4
HISTORY_GAP_LIMIT = 8

_VERSION_RE = re.compile(r"^version:\s*([^\s]+)\s*$", re.MULTILINE)
_RELEASE_DATE_RE = re.compile(r"^releaseDate:\s*['\"]?([^'\"\s]+)['\"]?\s*$", re.MULTILINE)
_FILE_RE = re.compile(
    r"^\s*-\s+url:\s*(.+?)\s*$\n\s+sha512:\s*([^\s]+)\s*$",
    re.MULTILINE,
)


def latest_version() -> VersionInfo:
    manifest = _fetch_manifest()
    return VersionInfo(
        version=manifest["version"],
        published_at=manifest["release_date"],
        tarball_url=manifest["url"],
    )


def all_versions() -> list[VersionInfo]:
    latest = latest_version()
    major, minor, patch = _semver_parts(latest.version)
    candidates = [f"{major}.{minor}.{candidate_patch}" for candidate_patch in range(patch - 1, -1, -1)]
    versions = [latest]
    missing_streak = 0
    with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
        for offset in range(0, len(candidates), PROBE_WORKERS):
            for item in pool.map(_probe_version, candidates[offset : offset + PROBE_WORKERS]):
                if item is None:
                    missing_streak += 1
                    if missing_streak >= HISTORY_GAP_LIMIT:
                        return sorted(versions, key=lambda version: _semver_parts(version.version))
                    continue
                missing_streak = 0
                versions.append(item)
    return sorted(versions, key=lambda item: _semver_parts(item.version))


def install(version: str, install_dir: Path) -> Path:
    bin_dir = install_dir / "bin"
    executable = bin_dir / "minimax-code"
    if executable.exists():
        return bin_dir

    if install_dir.exists():
        shutil.rmtree(install_dir)
    bin_dir.mkdir(parents=True)

    manifest = _fetch_manifest()
    archive = install_dir / f"MiniMax-Code-{version}-arm64-mac.zip"
    url = manifest["url"] if manifest["version"] == version else _asset_url(version)
    _download(url, archive)
    if manifest["version"] == version:
        _verify_sha512(archive, manifest["sha512"])

    resources_dir = install_dir / "resources"
    _extract_app_resources(archive, resources_dir)
    app_dir = install_dir / "app"
    extraction = run(
        ["npx", "--yes", ASAR_PACKAGE, "extract", str(resources_dir / "app.asar"), str(app_dir)],
        timeout=1800,
        check=False,
    )
    package_json = app_dir / "package.json"
    sqlite_package_json = app_dir / "node_modules" / "better-sqlite3" / "package.json"
    common_required = (package_json, sqlite_package_json)
    missing = [str(path.relative_to(app_dir)) for path in common_required if not path.is_file()]
    modern_runtimes = [
        app_dir / "node_modules" / "@mavis" / package / "dist" / "index.js"
        for package in ("local-runtime-v2", "local-runtime")
    ]
    has_modern_runtime = any(path.is_file() for path in modern_runtimes)
    modern_config = app_dir / "node_modules" / "@mavis" / "config" / "dist" / "index.js"
    legacy_daemon = resources_dir / "resources" / "daemon" / "daemon.js"
    if not (has_modern_runtime and modern_config.is_file()) and not legacy_daemon.is_file():
        missing.append("a supported local runtime")
    if missing:
        detail = (extraction.stderr or extraction.stdout).strip()[-4000:]
        raise RuntimeError(f"MiniMax Code app.asar is missing required runtime files: {missing}\n{detail}")

    sqlite_package = json.loads(sqlite_package_json.read_text(encoding="utf-8"))
    sqlite_version = sqlite_package.get("version")
    if not isinstance(sqlite_version, str) or not sqlite_version:
        raise RuntimeError("MiniMax Code bundled better-sqlite3 package has no version")
    native_dir = install_dir / "linux-native"
    native_packages = [f"better-sqlite3@{sqlite_version}"]
    if legacy_daemon.is_file():
        native_packages.append(f"opencode-ai@{_legacy_opencode_version(legacy_daemon.parent)}")
    run(
        [
            "npm",
            "install",
            "--prefix",
            str(native_dir),
            "--no-audit",
            "--no-fund",
            *native_packages,
        ],
        timeout=1800,
    )
    native_package = native_dir / "node_modules" / "better-sqlite3" / "package.json"
    if not native_package.is_file():
        raise RuntimeError("npm install did not create a Linux better-sqlite3 package")
    if legacy_daemon.is_file() and not (native_dir / "node_modules" / ".bin" / "opencode").is_file():
        raise RuntimeError("npm install did not create a Linux OpenCode executable")

    launcher = Path(__file__).with_name("launchers") / "minimax_code.mjs"
    shutil.copy2(launcher, executable)
    executable.chmod(executable.stat().st_mode | 0o755)

    archive.unlink(missing_ok=True)
    if has_modern_runtime:
        shutil.rmtree(resources_dir, ignore_errors=True)
    return bin_dir


def _fetch_manifest() -> dict[str, str]:
    request = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": "phistory"})
    for attempt in range(NETWORK_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
                return _parse_manifest(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code < 500 or attempt + 1 == NETWORK_ATTEMPTS:
                raise
        except (TimeoutError, URLError, OSError):
            if attempt + 1 == NETWORK_ATTEMPTS:
                raise
        time.sleep(attempt + 1)
    raise RuntimeError("MiniMax Code updater manifest request exhausted retries")


def _parse_manifest(text: str) -> dict[str, str]:
    version_match = _VERSION_RE.search(text)
    date_match = _RELEASE_DATE_RE.search(text)
    files = [(url.strip(), sha512) for url, sha512 in _FILE_RE.findall(text)]
    asset = next((item for item in files if item[0].endswith("-arm64-mac.zip")), None)
    if not version_match or not date_match or asset is None:
        raise RuntimeError("unexpected MiniMax Code updater manifest")
    return {
        "version": version_match.group(1),
        "release_date": date_match.group(1),
        "url": f"{RELEASE_ROOT}{quote(asset[0])}",
        "sha512": asset[1],
    }


def _asset_url(version: str) -> str:
    return f"{RELEASE_ROOT}{quote(f'MiniMax Code-{version}-arm64-mac.zip')}"


def _probe_version(version: str) -> VersionInfo | None:
    url = _asset_url(version)
    request = urllib.request.Request(url, headers={"User-Agent": "phistory"}, method="HEAD")
    for attempt in range(NETWORK_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
                published_at = _http_date_to_iso(response.headers.get("Last-Modified"))
                return VersionInfo(version=version, published_at=published_at, tarball_url=url)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code < 500 or attempt + 1 == NETWORK_ATTEMPTS:
                raise
        except (TimeoutError, URLError, OSError):
            if attempt + 1 == NETWORK_ATTEMPTS:
                raise
        time.sleep(attempt + 1)
    return None


def _download(url: str, output: Path) -> None:
    partial = output.with_suffix(f"{output.suffix}.part")
    for attempt in range(DOWNLOAD_ATTEMPTS):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "phistory"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                mode = "ab" if offset and response.status == 206 else "wb"
                with partial.open(mode) as file:
                    shutil.copyfileobj(response, file)
            partial.replace(output)
            return
        except HTTPError as exc:
            if exc.code == 416 and partial.exists():
                partial.replace(output)
                return
            if exc.code < 500 or attempt + 1 == DOWNLOAD_ATTEMPTS:
                raise
            time.sleep(attempt + 1)
        except (TimeoutError, URLError, OSError):
            if attempt + 1 == DOWNLOAD_ATTEMPTS:
                raise
            time.sleep(attempt + 1)


def _extract_app_resources(archive: Path, output: Path) -> None:
    prefix = "MiniMax Code.app/Contents/Resources/"
    output.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zip_file:
        names = [
            name
            for name in zip_file.namelist()
            if name == f"{prefix}app.asar"
            or name.startswith(f"{prefix}app.asar.unpacked/")
            or name.startswith(f"{prefix}resources/daemon/")
        ]
        if f"{prefix}app.asar" not in names:
            raise RuntimeError("MiniMax Code archive does not contain app.asar")
        for name in names:
            relative = Path(name.removeprefix(prefix))
            target = (output / relative).resolve()
            if not target.is_relative_to(output.resolve()):
                raise RuntimeError(f"unsafe MiniMax Code archive path: {name}")
            if name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(name) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def _verify_sha512(path: Path, expected_base64: str) -> None:
    expected = base64.b64decode(expected_base64, validate=True)
    digest = hashlib.sha512()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.digest() != expected:
        raise RuntimeError(f"sha512 mismatch for {path.name}")


def _legacy_opencode_version(daemon_dir: Path) -> str:
    sdk_dir = daemon_dir / ".opencode-plugin-sdk"
    versions = sorted(
        (path.name for path in sdk_dir.iterdir() if path.is_dir()),
        key=_semver_parts,
    )
    if len(versions) != 1:
        raise RuntimeError(f"expected one bundled OpenCode SDK version, found: {versions}")
    return versions[0]


def _http_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _semver_parts(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise RuntimeError(f"unexpected MiniMax Code version: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])
