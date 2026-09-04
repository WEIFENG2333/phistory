from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PackageSource = Literal["npm", "pypi", "github-release", "github-release-asset", "minimax-code"]
GitHubReleaseInstall = Literal["wheel", "editable"]
CaptureDriver = Literal["oneshot", "dsh-web"]
HomeProfile = Literal[
    "none",
    "antigravity",
    "dsh",
    "grok",
    "hermes",
    "kimi",
    "kimi-code",
    "mimo",
    "omp",
    "openclaw",
    "opencode",
    "pi",
]
TapMode = Literal["auto", "reverse", "forward"]
_VARIANT_ID_RE = re.compile(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\Z")
_VERSION_PART_RE = re.compile(r"\d+|[A-Za-z]+")
_SEMVER_RE = re.compile(
    r"[vV]?(?P<release>\d+(?:\.\d+)*)"
    r"(?:(?:-(?P<semver_prerelease>[0-9A-Za-z][0-9A-Za-z.-]*))|"
    r"(?P<compact_prerelease>[A-Za-z][0-9A-Za-z.-]*))?"
    r"(?:\+[0-9A-Za-z.-]+)?\Z"
)


def _version_key(version: str) -> tuple:
    match = _SEMVER_RE.fullmatch(version)
    if match is None:
        natural = tuple(
            (1, int(part)) if part.isdigit() else (0, part.casefold()) for part in _VERSION_PART_RE.findall(version)
        )
        return (0, natural)

    release = tuple(int(part) for part in match.group("release").split("."))
    prerelease = match.group("semver_prerelease") or match.group("compact_prerelease")
    if prerelease is None:
        return (1, release, 1, ())

    prerelease_key = tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"[.-]", prerelease)
    )
    return (1, release, 0, prerelease_key)


@dataclass(frozen=True)
class CaptureVariant:
    id: str
    label: str
    run_args: tuple[str, ...] = ()
    dimensions: dict[str, str] = field(default_factory=dict)
    driver: CaptureDriver = "oneshot"
    extra_env: dict[str, str] = field(default_factory=dict)
    min_version: str | None = None

    def supports_version(self, version: str) -> bool:
        return self.min_version is None or _version_key(version) >= _version_key(self.min_version)


@dataclass(frozen=True)
class AgentSpec:
    id: str
    display_name: str
    package: str
    tap_client: str
    fake_env: dict[str, str]
    default_variant: CaptureVariant = field(default_factory=lambda: CaptureVariant("default", "Default"))
    variants: tuple[CaptureVariant, ...] = ()
    hidden_capture_variants: tuple[str, ...] = ()
    executable: str | None = None
    source: PackageSource = "npm"
    install_command: tuple[str, ...] = ("npm", "install", "--no-audit", "--no-fund")
    node_runtime: str | None = None
    binary_release_repo: str | None = None
    binary_release_asset: str | None = None
    binary_release_tag: str = "{version}"
    home_profile: HomeProfile = "none"
    tap_mode: TapMode = "auto"
    extra_env: dict[str, str] = field(default_factory=dict)
    fake_chatgpt_auth: bool = False
    release_asset: str | None = None
    release_asset_binary: str | None = None
    release_manifest_url: str | None = None
    github_release_install: GitHubReleaseInstall = "wheel"

    def __post_init__(self) -> None:
        all_variants = self.capture_variants
        ids = [variant.id for variant in all_variants]
        if self.default_variant.id != "default":
            raise ValueError(f"{self.id}: default variant id must be 'default'")
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: capture variant ids must be unique")
        for variant_id in ids:
            if _VARIANT_ID_RE.fullmatch(variant_id) is None:
                raise ValueError(f"{self.id}: invalid capture variant id {variant_id!r}")
        for variant_id in self.hidden_capture_variants:
            if _VARIANT_ID_RE.fullmatch(variant_id) is None:
                raise ValueError(f"{self.id}: invalid hidden capture variant id {variant_id!r}")
        overlapping_variants = sorted(set(ids) & set(self.hidden_capture_variants))
        if overlapping_variants:
            names = ", ".join(overlapping_variants)
            raise ValueError(f"{self.id}: active capture variants cannot also be hidden: {names}")

    @property
    def capture_variants(self) -> tuple[CaptureVariant, ...]:
        return (self.default_variant, *self.variants)

    def variant(self, variant_id: str) -> CaptureVariant:
        for variant in self.capture_variants:
            if variant.id == variant_id:
                return variant
        known = ", ".join(item.id for item in self.capture_variants)
        raise ValueError(f"{self.id}: unknown capture variant {variant_id!r}; known variants: {known}")


@dataclass(frozen=True)
class VersionInfo:
    version: str
    published_at: str | None = None
    tarball_url: str | None = None


@dataclass(frozen=True)
class CaptureTarget:
    agent: AgentSpec
    version: VersionInfo
    variant: CaptureVariant
    root: Path

    @property
    def version_dir(self) -> Path:
        return self.root / self.agent.id / self.version.version

    @property
    def variant_dir(self) -> Path:
        return self.version_dir / "variants" / self.variant.id

    @property
    def prompt_path(self) -> Path:
        return self.variant_dir / "prompt.md"

    @property
    def trace_path(self) -> Path:
        return self.variant_dir / "trace.jsonl"

    @property
    def meta_path(self) -> Path:
        return self.variant_dir / "meta.json"

    @property
    def static_dir(self) -> Path:
        return self.version_dir / "static"

    @property
    def static_prompts_path(self) -> Path:
        return self.static_dir / "prompts.md"

    @property
    def static_prompts_json_path(self) -> Path:
        return self.static_dir / "prompts.json"

    @property
    def static_candidates_json_path(self) -> Path:
        return self.static_dir / "candidates.json"


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


CaptureStatus = Literal["captured", "skipped", "failed"]


@dataclass(frozen=True)
class CaptureResult:
    agent_id: str
    version: str
    variant_id: str
    status: CaptureStatus
    prompt_path: Path | None = None
    trace_path: Path | None = None
    meta_path: Path | None = None
    error: str | None = None
