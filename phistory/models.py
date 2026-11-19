from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PackageSource = Literal["npm", "pypi", "github-release", "github-release-asset", "minimax-code"]
GitHubReleaseInstall = Literal["wheel", "editable"]
CaptureDriver = Literal["oneshot", "dsh-web", "pty"]
HomeProfile = Literal[
    "none",
    "antigravity",
    "claude",
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


@dataclass(frozen=True)
class CaptureVariant:
    id: str
    label: str
    run_args: tuple[str, ...] = ()
    dimensions: dict[str, str] = field(default_factory=dict)
    driver: CaptureDriver = "oneshot"
    extra_env: dict[str, str] = field(default_factory=dict)
    # Text typed into an interactive TUI to make it issue one prompt-bearing request.
    pty_message: str = ""
    tap_mode: TapMode | None = None
    bootstrap_responses: str | None = None
    required_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentSpec:
    id: str
    display_name: str
    package: str
    tap_client: str
    fake_env: dict[str, str]
    default_variant: CaptureVariant = field(default_factory=lambda: CaptureVariant("default", "Default"))
    variants: tuple[CaptureVariant, ...] = ()
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
    python_version: str | None = None
    last_supported_version: str | None = None

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
