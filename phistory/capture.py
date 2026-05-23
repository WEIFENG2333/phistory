from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from phistory import packages
from phistory.models import CaptureResult, CaptureTarget
from phistory.storage import copy_trace, is_captured, latest_trace, prepare_version_dir, remove_if_exists, write_meta
from phistory.subprocesses import run

_VOLATILE_TEXT_PATTERNS = (
    (re.compile(r"\bcch=[^;\s]+"), "cch=<normalized>"),
    (re.compile(r"(?m)^ - OS Version: .+$"), " - OS Version: $PHISTORY_OS_VERSION"),
    (re.compile(r" - OS Version: [^\\\n]*(?=\\n)"), " - OS Version: $PHISTORY_OS_VERSION"),
    (re.compile(r"Today's date is \d{4}[-/]\d{2}[-/]\d{2}\."), "Today's date is $PHISTORY_DATE."),
    (
        re.compile(r"The current date and time in ISO format is `[^`]+`\."),
        "The current date and time in ISO format is `$PHISTORY_DATETIME`.",
    ),
    (re.compile(r"<current_date>\d{4}-\d{2}-\d{2}</current_date>"), "<current_date>$PHISTORY_DATE</current_date>"),
    (re.compile(r"<timezone>[^<]+</timezone>"), "<timezone>$PHISTORY_TIMEZONE</timezone>"),
    (
        re.compile(r"\$PHISTORY_HOME/\.claude/projects/-tmp-phistory-work-[^/\s]+"),
        "$PHISTORY_HOME/.claude/projects/$PHISTORY_PROJECT",
    ),
    (re.compile(r"Bearer phistory-[A-Za-z0-9_-]+"), "Bearer <redacted>"),
)


def capture_target(
    target: CaptureTarget,
    *,
    cache_dir: Path,
    force: bool = False,
    keep_tap: bool = False,
) -> CaptureResult:
    if is_captured(target) and not force:
        return CaptureResult(
            target.agent.id, target.version.version, "skipped", target.prompt_path, target.trace_path, target.meta_path
        )

    started = time.time()
    prepare_version_dir(target, force=force)
    install_dir = (cache_dir / "installs" / target.agent.id / target.version.version).resolve()
    version_dir = target.version_dir.resolve()
    prompt_path = target.prompt_path.resolve()
    tap_output_dir = (version_dir / ".tap").resolve()

    try:
        bin_dir = packages.install_agent(target.agent, target.version.version, install_dir)
        binary_version = _binary_version(target, bin_dir)
        with (
            TemporaryDirectory(prefix="phistory-home-", ignore_cleanup_errors=True) as home_dir,
            TemporaryDirectory(prefix="phistory-work-", ignore_cleanup_errors=True) as work_dir,
        ):
            env = _capture_env(target, bin_dir, Path(home_dir))
            env["PWD"] = str(Path(work_dir))
            argv = [
                sys.executable,
                "-m",
                "claude_tap",
                "run",
                target.agent.tap_client,
                "--export-prompt",
                str(prompt_path),
                "--no-live",
                "--no-open",
                "--no-update-check",
                "-o",
                str(tap_output_dir),
                *_tap_mode_args(target),
                *target.agent.run_args,
            ]
            result = run(argv, cwd=Path(work_dir), env=env, timeout=180, check=False)
            if _needs_claude_session_persistence_retry(target, result):
                remove_if_exists(tap_output_dir)
                prompt_path.unlink(missing_ok=True)
                argv = _without_arg(argv, "--no-session-persistence")
                result = run(argv, cwd=Path(work_dir), env=env, timeout=180, check=False)
            if _needs_codex_api_key_retry(target, result):
                remove_if_exists(tap_output_dir)
                prompt_path.unlink(missing_ok=True)
                env = {**env, "OPENAI_API_KEY": "phistory-fake-api-key"}
                result = run(argv, cwd=Path(work_dir), env=env, timeout=180, check=False)
        if result.returncode != 0 or not prompt_path.exists():
            detail = (result.stderr or result.stdout).strip()[-4000:]
            raise RuntimeError(f"capture command failed ({result.returncode})\n{detail}")

        trace = latest_trace(tap_output_dir)
        copy_trace(trace, target)
        replacements = {
            str(install_dir): "$PHISTORY_INSTALL",
            str(home_dir): "$PHISTORY_HOME",
            str(work_dir): "$PHISTORY_WORKSPACE",
        }
        _sanitize_file(prompt_path, replacements)
        write_meta(
            target,
            {
                "agent_id": target.agent.id,
                "agent": target.agent.display_name,
                "package": target.agent.package,
                "version": target.version.version,
                "published_at": target.version.published_at,
                "tarball_url": target.version.tarball_url,
                "binary_version": binary_version,
                "captured_at": _iso_now(),
                "tap_client": target.agent.tap_client,
                "target": "claude-tap capture-only",
                "duration_seconds": round(time.time() - started, 3),
                "command": [_replace_many(part, replacements) for part in _portable_command(argv, version_dir)],
            },
        )
        if not keep_tap:
            remove_if_exists(tap_output_dir)
        return CaptureResult(
            target.agent.id, target.version.version, "captured", target.prompt_path, target.trace_path, target.meta_path
        )
    except Exception as exc:
        if not keep_tap:
            remove_if_exists(target.version_dir)
        return CaptureResult(target.agent.id, target.version.version, "failed", error=str(exc))


def _capture_env(target: CaptureTarget, bin_dir: Path, home_dir: Path | None = None) -> dict[str, str]:
    home = home_dir or target.version_dir / ".home"
    for path in (home, home / ".config", home / ".cache", home / ".local" / "share", home / ".codex", home / ".claude"):
        path.mkdir(parents=True, exist_ok=True)
    if target.agent.fake_chatgpt_auth:
        _write_fake_chatgpt_auth(home)
    if target.agent.home_profile == "hermes":
        _write_hermes_config(home)
    if target.agent.home_profile == "kimi":
        _write_kimi_config(home)
    if target.agent.home_profile == "openclaw":
        _write_openclaw_config(home)
    if target.agent.home_profile == "opencode":
        _write_opencode_config(home)
    if target.agent.home_profile == "pi":
        _write_pi_config(home)
    env = {
        **target.agent.fake_env,
        **target.agent.extra_env,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "CODEX_HOME": str(home / ".codex"),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "TZ": "Etc/UTC",
    }
    if target.agent.home_profile == "hermes":
        env["HERMES_HOME"] = str(home / ".hermes")
    if target.agent.home_profile == "kimi":
        env["KIMI_SHARE_DIR"] = str(home / ".kimi")
    if target.agent.home_profile == "openclaw":
        env.update(
            {
                "OPENCLAW_STATE_DIR": str(home / ".openclaw"),
                "OPENCLAW_CONFIG_PATH": str(home / ".openclaw" / "openclaw.json"),
            }
        )
    if target.agent.home_profile == "opencode":
        env["OPENCODE_CONFIG"] = str(home / ".config" / "opencode" / "opencode.json")
    if target.agent.home_profile == "pi":
        env["PI_CODING_AGENT_DIR"] = str(home / ".pi" / "agent")
    if target.agent.fake_chatgpt_auth:
        env.update({"OPENAI_API_KEY": "", "CODEX_API_KEY": "", "CODEX_ACCESS_TOKEN": ""})
    return env


def _needs_claude_session_persistence_retry(target: CaptureTarget, result) -> bool:
    if target.agent.id != "claude-code" or result.returncode == 0:
        return False
    output = f"{result.stderr}\n{result.stdout}"
    return "unknown option '--no-session-persistence'" in output


def _needs_codex_api_key_retry(target: CaptureTarget, result) -> bool:
    if target.agent.id != "codex" or result.returncode == 0:
        return False
    output = f"{result.stderr}\n{result.stdout}"
    return "Missing OpenAI API key" in output


def _tap_mode_args(target: CaptureTarget) -> list[str]:
    if target.agent.tap_mode == "auto":
        return []
    return ["-m", target.agent.tap_mode]


def _without_arg(argv: list[str], value: str) -> list[str]:
    return [arg for arg in argv if arg != value]


def _write_fake_chatgpt_auth(home: Path) -> None:
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    auth = {
        "auth_mode": "chatgpt",
        "tokens": {
            "id_token": _fake_chatgpt_jwt(),
            "access_token": "phistory-fake-access-token",
            "refresh_token": "phistory-fake-refresh-token",
            "account_id": "phistory-account",
        },
        "last_refresh": "2026-01-01T00:00:00Z",
    }
    (codex_home / "auth.json").write_text(json.dumps(auth, separators=(",", ":")), encoding="utf-8")


def _write_openclaw_config(home: Path) -> None:
    state_dir = home / ".openclaw"
    state_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "agents": {
            "defaults": {
                "workspace": str(state_dir / "workspace"),
                "model": {"primary": "phistory/phistory-dummy"},
            }
        },
        "models": {
            "providers": {
                "phistory": {
                    "api": "openai-responses",
                    "baseUrl": "http://127.0.0.1:9/v1",
                    "apiKey": "phistory-fake-api-key",
                    "models": [{"id": "phistory-dummy", "name": "Phistory Dummy"}],
                }
            }
        },
    }
    (state_dir / "openclaw.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _write_hermes_config(home: Path) -> None:
    hermes_home = home / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / "config.yaml").write_text(
        "\n".join(
            [
                "model:",
                "  provider: openrouter",
                "  default: phistory-dummy",
                "agent:",
                "  max_turns: 1",
                "display:",
                "  streaming: false",
                "  persistent_output: false",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_kimi_config(home: Path) -> None:
    kimi_home = home / ".kimi"
    kimi_home.mkdir(parents=True, exist_ok=True)
    (kimi_home / "config.toml").write_text(
        "\n".join(
            [
                'default_model = "phistory-dummy"',
                "default_yolo = true",
                "skip_afk_prompt_injection = true",
                "",
                "[providers.phistory]",
                'type = "openai_responses"',
                'base_url = "https://api.openai.com/v1"',
                'api_key = "phistory-fake-api-key"',
                "",
                "[models.phistory-dummy]",
                'provider = "phistory"',
                'model = "gpt-4.1"',
                "max_context_size = 200000",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_opencode_config(home: Path) -> None:
    config_dir = home / ".config" / "opencode"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": "openai/gpt-4.1",
        "provider": {
            "openai": {
                "options": {
                    "apiKey": "phistory-fake-api-key",
                }
            }
        },
    }
    (config_dir / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _write_pi_config(home: Path) -> None:
    pi_home = home / ".pi" / "agent"
    pi_home.mkdir(parents=True, exist_ok=True)
    models = {
        "providers": {
            "phistory": {
                "api": "openai-responses",
                "baseUrl": "https://api.openai.com/v1",
                "apiKey": "phistory-fake-api-key",
                "models": [{"id": "gpt-4.1", "name": "gpt-4.1"}],
            }
        }
    }
    (pi_home / "models.json").write_text(json.dumps(models, indent=2), encoding="utf-8")
    (pi_home / "settings.json").write_text(
        json.dumps({"defaultProvider": "phistory"}, indent=2),
        encoding="utf-8",
    )


def _fake_chatgpt_jwt() -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "exp": 4102444800,
        "email": "phistory@example.invalid",
        "https://api.openai.com/auth": {
            "chatgpt_plan_type": "plus",
            "chatgpt_user_id": "phistory-user",
            "chatgpt_account_id": "phistory-account",
            "chatgpt_account_is_fedramp": False,
        },
    }
    return f"{_b64url_json(header)}.{_b64url_json(payload)}.phistory-signature"


def _b64url_json(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _binary_version(target: CaptureTarget, bin_dir: Path) -> str | None:
    executable = bin_dir / target.agent.tap_client
    if not executable.exists():
        return None
    with TemporaryDirectory(prefix="phistory-version-home-") as home_dir:
        env = _capture_env(target, bin_dir, Path(home_dir))
        result = run([str(executable), "--version"], env=env, timeout=30, check=False)
    text = (result.stdout or result.stderr).strip()
    return text or None


def _portable_command(argv: list[str], version_dir: Path) -> list[str]:
    out: list[str] = []
    for index, arg in enumerate(argv):
        if index == 0:
            out.append("python")
            continue
        path = Path(arg)
        if path.is_absolute():
            try:
                out.append(path.relative_to(version_dir).as_posix())
                continue
            except ValueError:
                pass
        out.append(arg)
    return out


def _sanitize_file(path: Path, replacements: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(_sanitize_text(text, replacements), encoding="utf-8")


def _sanitize_text(text: str, replacements: dict[str, str]) -> str:
    text = _replace_many(text, replacements)
    for pattern, replacement in _VOLATILE_TEXT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _replace_many(text: str, replacements: dict[str, str]) -> str:
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
