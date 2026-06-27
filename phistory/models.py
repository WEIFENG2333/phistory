from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PackageSource = Literal["npm", "pypi", "github-release", "github-release-asset"]
HomeProfile = Literal["none", "antigravity", "hermes", "kimi", "openclaw", "opencode", "pi"]
TapMode = Literal["auto", "reverse", "forward"]
TapTargetProfile = Literal["none", "antigravity"]


@dataclass(frozen=True)
class AgentSpec:
    id: str
    display_name: str
    package: str
    tap_client: str
    fake_env: dict[str, str]
    run_args: tuple[str, ...]
    source: PackageSource = "npm"
    install_command: tuple[str, ...] = ("npm", "install", "--no-audit", "--no-fund")
    node_runtime: str | None = None
    home_profile: HomeProfile = "none"
    tap_mode: TapMode = "auto"
    tap_target_profile: TapTargetProfile = "none"
    extra_env: dict[str, str] = field(default_factory=dict)
    fake_chatgpt_auth: bool = False
    release_asset: str | None = None
    release_asset_binary: str | None = None
    release_manifest_url: str | None = None


@dataclass(frozen=True)
class VersionInfo:
    version: str
    published_at: str | None = None
    tarball_url: str | None = None


@dataclass(frozen=True)
class CaptureTarget:
    agent: AgentSpec
    version: VersionInfo
    root: Path

    @property
    def version_dir(self) -> Path:
        return self.root / self.agent.id / self.version.version

    @property
    def prompt_path(self) -> Path:
        return self.version_dir / "prompt.md"

    @property
    def trace_path(self) -> Path:
        return self.version_dir / "trace.jsonl"

    @property
    def meta_path(self) -> Path:
        return self.version_dir / "meta.json"

    @property
    def static_prompts_path(self) -> Path:
        return self.version_dir / "static-prompts.md"

    @property
    def static_prompts_json_path(self) -> Path:
        return self.version_dir / "static-prompts.json"

    @property
    def static_candidates_json_path(self) -> Path:
        return self.version_dir / "static-candidates.json"


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
    status: CaptureStatus
    prompt_path: Path | None = None
    trace_path: Path | None = None
    meta_path: Path | None = None
    error: str | None = None
