from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp

from phistory import packages
from phistory.drivers import CaptureRunContext, run_capture
from phistory.models import CaptureResult, CaptureTarget
from phistory.packages import agent_executable
from phistory.static_prompts.extract import extract_static_prompts
from phistory.storage import copy_trace, is_captured, latest_trace, prepare_version_dir, remove_if_exists, write_meta
from phistory.subprocesses import run

_VOLATILE_TEXT_PATTERNS = (
    (re.compile(r"\bcch=[^;\s]+"), "cch=<normalized>"),
    (re.compile(r"(?m)^ - OS Version: .+$"), " - OS Version: $PHISTORY_OS_VERSION"),
    (re.compile(r" - OS Version: [^\\\n]*(?=\\n)"), " - OS Version: $PHISTORY_OS_VERSION"),
    (re.compile(r"Today's date is \d{4}[-/]\d{2}[-/]\d{2}\."), "Today's date is $PHISTORY_DATE."),
    (re.compile(r"Today's date: \d{4}[-/]\d{2}[-/]\d{2}"), "Today's date: $PHISTORY_DATE"),
    (re.compile(r"Today's date is [A-Z][a-z]+, [A-Z][a-z]+ \d{1,2}, \d{4}\."), "Today's date is $PHISTORY_DATE."),
    (
        re.compile(r"The current date is: [A-Z][a-z]+, [A-Z][a-z]+ \d{1,2}, \d{4}\."),
        "The current date is: $PHISTORY_DATE.",
    ),
    (re.compile(r"(?m)^My operating system is: \w+$"), "My operating system is: $PHISTORY_OS"),
    (
        re.compile(r"(?:\.\./|\.\.)+\$PHISTORY_HOME/\.qwen/output-language\.md"),
        "$PHISTORY_HOME/.qwen/output-language.md",
    ),
    (
        re.compile(r"(?:\.\./)+phistory-home-[A-Za-z0-9_-]+/\.qwen/output-language\.md"),
        "$PHISTORY_HOME/.qwen/output-language.md",
    ),
    (
        re.compile(r"\$PHISTORY_HOME/\.qwen/projects/[^/\s]+"),
        "$PHISTORY_HOME/.qwen/projects/$PHISTORY_PROJECT",
    ),
    (re.compile(r"http://(?:127\.0\.0\.1|localhost):\d+"), "http://127.0.0.1:$PHISTORY_PORT"),
    (
        re.compile(r"The current date and time in ISO format is `[^`]+`\."),
        "The current date and time in ISO format is `$PHISTORY_DATETIME`.",
    ),
    (re.compile(r"The current local time is: [^\n]+"), "The current local time is: $PHISTORY_DATETIME."),
    (re.compile(r"(?m)^Conversation started: .+$"), "Conversation started: $PHISTORY_DATETIME"),
    (re.compile(r"Conversation ID: [0-9a-f-]{36}"), "Conversation ID: $PHISTORY_CONVERSATION"),
    (re.compile(r"(?m)^(  YOUR SESSION ID:) mvs_[A-Za-z0-9_]+$"), r"\1 $PHISTORY_SESSION"),
    (
        re.compile(r"(?m)^(  YOUR SCRATCHPAD: .*/scratchpads/)mvs_[A-Za-z0-9_]+(/scratchpad\.md)$"),
        r"\1$PHISTORY_SESSION\2",
    ),
    (re.compile(r"(?m)^(  daemonPort:) \d+$"), r"\1 $PHISTORY_PORT"),
    (
        re.compile(
            r"(?m)^(  date:) (?:\d{4}-\d{2}-\d{2} .+ \(UTC, UTC[+-]\d+(?::\d+)?\)|"
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) .+ GMT[+-]\d{4} \([^)]+\))$"
        ),
        r"\1 $PHISTORY_DATETIME",
    ),
    (re.compile(r"<current_date>\d{4}-\d{2}-\d{2}</current_date>"), "<current_date>$PHISTORY_DATE</current_date>"),
    (re.compile(r"<timezone>[^<]+</timezone>"), "<timezone>$PHISTORY_TIMEZONE</timezone>"),
    (
        re.compile(r"\$PHISTORY_HOME/\.gemini/antigravity-cli/brain/[0-9a-f-]{36}"),
        "$PHISTORY_HOME/.gemini/antigravity-cli/brain/$PHISTORY_CONVERSATION",
    ),
    (
        re.compile(r"\$PHISTORY_HOME/\.claude/projects/-tmp-phistory-work-[^/\s]+"),
        "$PHISTORY_HOME/.claude/projects/$PHISTORY_PROJECT",
    ),
    (
        re.compile(r"\$PHISTORY_HOME/\.local/share/mimocode/memory/sessions/ses_[A-Za-z0-9_]+"),
        "$PHISTORY_HOME/.local/share/mimocode/memory/sessions/$PHISTORY_SESSION",
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
            target.agent.id,
            target.version.version,
            target.variant.id,
            "skipped",
            target.prompt_path,
            target.trace_path,
            target.meta_path,
        )

    staging_root: Path | None = None
    working_target = target
    if force and target.variant_dir.exists():
        target.root.mkdir(parents=True, exist_ok=True)
        staging_root = Path(mkdtemp(prefix=".phistory-capture-", dir=target.root))
        working_target = CaptureTarget(target.agent, target.version, target.variant, staging_root)

    started = time.time()
    prepare_version_dir(working_target)
    install_dir = (cache_dir / "installs" / target.agent.id / target.version.version).resolve()
    variant_dir = working_target.variant_dir.resolve()
    prompt_path = working_target.prompt_path.resolve()
    tap_output_dir = (variant_dir / ".tap").resolve()

    try:
        bin_dir = packages.install_agent(target.agent, target.version.version, install_dir)
        binary_version = _binary_version(target, bin_dir)
        with (
            TemporaryDirectory(prefix="phistory-home-", ignore_cleanup_errors=True) as home_dir,
            TemporaryDirectory(prefix="phistory-work-", ignore_cleanup_errors=True) as work_dir,
        ):
            env = _capture_env(working_target, bin_dir, Path(home_dir))
            env["PWD"] = str(Path(work_dir))
            execution = run_capture(
                CaptureRunContext(
                    target=working_target,
                    prompt_path=prompt_path,
                    tap_output_dir=tap_output_dir,
                    work_dir=Path(work_dir),
                    env=env,
                )
            )
            argv = list(execution.command)
            result = execution.result
        if not prompt_path.exists():
            detail = (result.stderr or result.stdout).strip()[-4000:]
            raise RuntimeError(f"capture command failed ({result.returncode})\n{detail}")

        if not working_target.trace_path.exists():
            trace = latest_trace(tap_output_dir)
            copy_trace(trace, working_target)
        replacements = {
            str(install_dir): "$PHISTORY_INSTALL",
            # Resolved forms first: macOS symlinks /tmp and /var, so clients may
            # print realpath'd paths that contain the unresolved dir as a suffix.
            str(Path(home_dir).resolve()): "$PHISTORY_HOME",
            str(Path(work_dir).resolve()): "$PHISTORY_WORKSPACE",
            str(home_dir): "$PHISTORY_HOME",
            str(work_dir): "$PHISTORY_WORKSPACE",
        }
        _sanitize_file(prompt_path, replacements)
        write_meta(
            working_target,
            {
                "agent_id": target.agent.id,
                "agent": target.agent.display_name,
                "package": target.agent.package,
                "version": target.version.version,
                "variant": {
                    "id": target.variant.id,
                    "label": target.variant.label,
                    "dimensions": target.variant.dimensions,
                },
                "requested": target.variant.dimensions,
                "observed": _trace_observation(working_target.trace_path),
                "published_at": target.version.published_at,
                "tarball_url": target.version.tarball_url,
                "binary_version": binary_version,
                "captured_at": _iso_now(),
                "tap_client": target.agent.tap_client,
                "target": "claude-tap capture-only",
                "client_exit_code": result.returncode,
                "duration_seconds": round(time.time() - started, 3),
                "command": [_replace_many(part, replacements) for part in _portable_command(argv, variant_dir)],
            },
        )
        if not keep_tap:
            remove_if_exists(tap_output_dir)
        if staging_root is not None:
            _promote_staged_capture(working_target.variant_dir, target.variant_dir, staging_root)
        if target.variant.id == "default":
            _extract_static_best_effort(target, install_dir)
        return CaptureResult(
            target.agent.id,
            target.version.version,
            target.variant.id,
            "captured",
            target.prompt_path,
            target.trace_path,
            target.meta_path,
        )
    except Exception as exc:
        if not keep_tap:
            remove_if_exists(working_target.variant_dir)
            if staging_root is not None:
                remove_if_exists(staging_root)
            else:
                _remove_empty_capture_parents(working_target)
        elif staging_root is not None:
            exc = RuntimeError(f"{exc}\nfailed capture kept under {staging_root}")
        return CaptureResult(target.agent.id, target.version.version, target.variant.id, "failed", error=str(exc))


def _remove_empty_capture_parents(target: CaptureTarget) -> None:
    for path in (target.variant_dir.parent, target.version_dir, target.version_dir.parent):
        try:
            path.rmdir()
        except OSError:
            break


def _promote_staged_capture(staged: Path, destination: Path, staging_root: Path) -> None:
    backup = staging_root / "previous"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.rename(backup)
    try:
        staged.rename(destination)
    except Exception:
        if backup.exists():
            backup.rename(destination)
        raise
    remove_if_exists(backup)
    remove_if_exists(staging_root)


def _capture_env(target: CaptureTarget, bin_dir: Path, home_dir: Path | None = None) -> dict[str, str]:
    home = home_dir or target.version_dir / ".home"
    for path in (home, home / ".config", home / ".cache", home / ".local" / "share", home / ".codex", home / ".claude"):
        path.mkdir(parents=True, exist_ok=True)
    if target.agent.fake_chatgpt_auth:
        _write_fake_chatgpt_auth(home)
    if target.agent.home_profile == "antigravity":
        _write_antigravity_config(home)
    if target.agent.home_profile == "hermes":
        _write_hermes_config(home)
    if target.agent.home_profile == "kimi":
        _write_kimi_config(home)
    if target.agent.home_profile == "kimi-code":
        _write_kimi_code_config(home)
    if target.agent.home_profile == "mimo":
        _write_mimo_config(home)
    if target.agent.home_profile == "omp":
        _write_omp_config(home)
    if target.agent.home_profile == "openclaw":
        _write_openclaw_config(home)
    if target.agent.home_profile == "opencode":
        _write_opencode_config(home)
    if target.agent.home_profile == "pi":
        _write_pi_config(home)
    env = {
        **target.agent.fake_env,
        **target.agent.extra_env,
        **target.variant.extra_env,
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
    if target.agent.home_profile == "dsh":
        env["DSH_HOME"] = str(home / ".dsh")
    if target.agent.home_profile == "grok":
        grok_home = home / ".grok"
        grok_home.mkdir(parents=True, exist_ok=True)
        env["GROK_HOME"] = str(grok_home)
    if target.agent.home_profile == "kimi":
        env["KIMI_SHARE_DIR"] = str(home / ".kimi")
    if target.agent.home_profile == "kimi-code":
        env["KIMI_CODE_HOME"] = str(home / ".kimi-code")
    if target.agent.home_profile == "mimo":
        env.update(
            {
                "MIMOCODE_CONFIG": str(home / ".config" / "mimocode" / "mimocode.json"),
                "MIMOCODE_MIMO_ONLY": "false",
            }
        )
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
    if target.agent.home_profile == "omp":
        env["PI_CODING_AGENT_DIR"] = str(home / ".omp" / "agent")
    if target.agent.fake_chatgpt_auth:
        env.update({"OPENAI_API_KEY": "", "CODEX_API_KEY": "", "CODEX_ACCESS_TOKEN": ""})
    return env


def _extract_static_best_effort(target: CaptureTarget, install_dir: Path) -> None:
    if target.agent.id != "claude-code":
        return
    target.static_dir.mkdir(parents=True, exist_ok=True)
    try:
        extract_static_prompts(target, install_dir)
    except Exception:
        return


def _trace_observation(trace_path: Path) -> dict[str, object]:
    best: tuple[int, dict] | None = None
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        body = (record.get("request") or {}).get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                continue
        if not isinstance(body, dict):
            continue
        score = _prompt_request_score(body)
        if best is None or score > best[0]:
            best = (score, body)
    if best is None:
        return {}
    body = best[1]
    observed: dict[str, object] = {}
    if isinstance(body.get("model"), str):
        observed["model"] = body["model"]
    tool_count = _observed_tool_count(body)
    if tool_count:
        observed["tool_count"] = tool_count
    return observed


def _observed_tool_count(body: dict) -> int:
    count = len(body["tools"]) if isinstance(body.get("tools"), list) else 0
    inputs = body.get("input")
    if not isinstance(inputs, list):
        return count
    for item in inputs:
        if not isinstance(item, dict) or item.get("type") != "additional_tools":
            continue
        tools = item.get("tools")
        if isinstance(tools, list):
            count += len(tools)
    return count


def _prompt_request_score(body: dict) -> int:
    score = 0
    if body.get("system"):
        score += 4
    if body.get("instructions"):
        score += 4
    if body.get("tools"):
        score += 4
    if _observed_tool_count(body):
        score += 4
    if body.get("messages"):
        score += 1
    if body.get("input"):
        score += 1
    return score


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


def _write_antigravity_config(home: Path) -> None:
    agy_home = home / ".gemini" / "antigravity-cli"
    agy_home.mkdir(parents=True, exist_ok=True)
    token = {
        "auth_method": "consumer",
        "token": {
            "access_token": "phistory-fake-access-token",
            "token_type": "Bearer",
            "refresh_token": "phistory-fake-refresh-token",
            "expiry": "2099-01-01T00:00:00Z",
            "is_gcp_tos": False,
        },
    }
    (agy_home / "antigravity-oauth-token").write_text(json.dumps(token, separators=(",", ":")), encoding="utf-8")


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


def _write_kimi_code_config(home: Path) -> None:
    kimi_home = home / ".kimi-code"
    kimi_home.mkdir(parents=True, exist_ok=True)
    (kimi_home / ".skip-migration-from-kimi-cli").write_text("", encoding="utf-8")
    (kimi_home / "config.toml").write_text(
        "\n".join(
            [
                'default_model = "kimi-code/kimi-for-coding"',
                "",
                '[providers."phistory"]',
                'type = "kimi"',
                'base_url = "https://api.kimi.com/coding/v1"',
                'api_key = "phistory-fake-api-key"',
                "",
                '[models."kimi-code/kimi-for-coding"]',
                'provider = "phistory"',
                'model = "kimi-for-coding"',
                "max_context_size = 262144",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_mimo_config(home: Path) -> None:
    config_dir = home / ".config" / "mimocode"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "$schema": "https://mimo.xiaomi.com/mimocode/config.json",
        "model": "openai/gpt-4.1",
        "provider": {
            "openai": {
                "options": {
                    "apiKey": "phistory-fake-api-key",
                }
            }
        },
    }
    (config_dir / "mimocode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


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


def _write_omp_config(home: Path) -> None:
    omp_home = home / ".omp" / "agent"
    omp_home.mkdir(parents=True, exist_ok=True)
    models = {
        "providers": {
            "phistory": {
                "api": "openai-responses",
                "baseUrl": "https://api.openai.com/v1",
                "apiKey": "phistory-fake-api-key",
                "models": [
                    {
                        "id": "gpt-4.1",
                        "name": "gpt-4.1",
                        "contextWindow": 200000,
                        "maxTokens": 32768,
                    }
                ],
            }
        }
    }
    (omp_home / "models.json").write_text(json.dumps(models, indent=2), encoding="utf-8")
    (omp_home / "settings.json").write_text(
        json.dumps({"defaultProvider": "phistory", "defaultModelId": "gpt-4.1"}, indent=2),
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
    executable = bin_dir / agent_executable(target.agent)
    if not executable.exists():
        return None
    with TemporaryDirectory(prefix="phistory-version-home-") as home_dir:
        try:
            env = _capture_env(target, bin_dir, Path(home_dir))
            result = run([str(executable), "--version"], env=env, timeout=30, check=False)
        except Exception:
            return target.version.version
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
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}(```json)", r"\n\n\1", text)
    return text


def _replace_many(text: str, replacements: dict[str, str]) -> str:
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
