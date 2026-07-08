from __future__ import annotations

from phistory.models import AgentSpec

CLAUDE_CODE = AgentSpec(
    id="claude-code",
    display_name="Claude Code",
    package="@anthropic-ai/claude-code",
    tap_client="claude",
    fake_env={"ANTHROPIC_API_KEY": "fake"},
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    run_args=(
        "--no-yolo",
        "--",
        "--no-session-persistence",
        "-p",
        "Reply with one short sentence.",
    ),
)

CODEX = AgentSpec(
    id="codex",
    display_name="Codex CLI",
    package="@openai/codex",
    tap_client="codex",
    fake_env={},
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    fake_chatgpt_auth=True,
    run_args=(
        "--no-yolo",
        "--",
        "exec",
        "Reply with one short sentence.",
        "--skip-git-repo-check",
        "--json",
    ),
)

ANTIGRAVITY = AgentSpec(
    id="antigravity",
    display_name="Antigravity CLI",
    package="google-antigravity/antigravity-cli",
    source="github-release-asset",
    release_asset="agy_cli_linux_x64.tar.gz",
    release_asset_binary="antigravity",
    release_manifest_url="https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/linux_amd64.json",
    tap_client="agy",
    fake_env={},
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    home_profile="antigravity",
    tap_target_profile="antigravity",
    run_args=(
        "--no-yolo",
        "--",
        "--print",
        "Reply with one short sentence.",
        "--print-timeout",
        "1s",
        "--dangerously-skip-permissions",
        "--model",
        "MODEL_GOOGLE_GEMINI_2_5_FLASH",
    ),
)

KIMI_CODE = AgentSpec(
    id="kimi-code",
    display_name="Kimi Code",
    package="@moonshot-ai/kimi-code",
    tap_client="kimi-code",
    executable="kimi",
    fake_env={
        "KIMI_API_KEY": "phistory-fake-api-key",
        "MOONSHOT_API_KEY": "phistory-fake-api-key",
    },
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "KIMI_TELEMETRY_DISABLED": "1",
        "CI": "1",
    },
    home_profile="kimi-code",
    run_args=(
        "--no-yolo",
        "--",
        "--prompt",
        "Reply with one short sentence.",
        "--output-format",
        "text",
    ),
)

MIMO = AgentSpec(
    id="mimo",
    display_name="MiMo Code",
    package="@mimo-ai/cli",
    tap_client="mimo",
    fake_env={
        "OPENAI_API_KEY": "phistory-fake-api-key",
        "ANTHROPIC_API_KEY": "phistory-fake-api-key",
    },
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    home_profile="mimo",
    tap_mode="reverse",
    run_args=(
        "--no-yolo",
        "--",
        "run",
        "Reply with one short sentence.",
        "--model",
        "openai/gpt-4.1",
        "--format",
        "json",
        "--dir",
        ".",
        "--dangerously-skip-permissions",
    ),
)

OPENCLAW = AgentSpec(
    id="openclaw",
    display_name="OpenClaw",
    package="openclaw",
    tap_client="openclaw",
    fake_env={"OPENAI_API_KEY": "phistory-fake-api-key"},
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    node_runtime="node@24",
    home_profile="openclaw",
    run_args=(
        "--no-yolo",
        "--",
        "agent",
        "--local",
        "--agent",
        "main",
        "--message",
        "Reply with one short sentence.",
        "--json",
        "--timeout",
        "20",
    ),
)

HERMES = AgentSpec(
    id="hermes",
    display_name="Hermes Agent",
    package="NousResearch/hermes-agent",
    source="github-release",
    tap_client="hermes",
    fake_env={
        "OPENAI_API_KEY": "phistory-fake-api-key",
        "OPENROUTER_API_KEY": "phistory-fake-api-key",
    },
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "HERMES_ACCEPT_HOOKS": "1",
    },
    home_profile="hermes",
    tap_mode="reverse",
    run_args=(
        "--no-yolo",
        "--",
        "chat",
        "-q",
        "Reply with one short sentence.",
        "--yolo",
        "-Q",
        "--provider",
        "openrouter",
        "--model",
        "phistory-dummy",
    ),
)

KIMI = AgentSpec(
    id="kimi",
    display_name="Kimi CLI",
    package="MoonshotAI/kimi-cli",
    source="github-release",
    tap_client="kimi",
    fake_env={
        "OPENAI_API_KEY": "phistory-fake-api-key",
        "KIMI_API_KEY": "phistory-fake-api-key",
        "MOONSHOT_API_KEY": "phistory-fake-api-key",
    },
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "KIMI_TELEMETRY_DISABLED": "1",
    },
    home_profile="kimi",
    run_args=(
        "--no-yolo",
        "--",
        "--print",
        "--prompt",
        "Reply with one short sentence.",
        "--model",
        "phistory-dummy",
        "--output-format",
        "text",
    ),
)

OPENCODE = AgentSpec(
    id="opencode",
    display_name="opencode",
    package="opencode-ai",
    tap_client="opencode",
    fake_env={"OPENAI_API_KEY": "phistory-fake-api-key"},
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    home_profile="opencode",
    tap_mode="reverse",
    run_args=(
        "--no-yolo",
        "--",
        "run",
        "Reply with one short sentence.",
        "--model",
        "openai/gpt-4.1",
        "--format",
        "json",
        "--dir",
        ".",
    ),
)

PI = AgentSpec(
    id="pi",
    display_name="Pi",
    package="@earendil-works/pi-coding-agent",
    tap_client="pi",
    fake_env={"OPENAI_API_KEY": "phistory-fake-api-key"},
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    home_profile="pi",
    run_args=(
        "--no-yolo",
        "--",
        "--provider",
        "phistory",
        "--model",
        "gpt-4.1",
        "--print",
        "--mode",
        "text",
        "--no-session",
        "Reply with one short sentence.",
    ),
)

OMP = AgentSpec(
    id="omp",
    display_name="Oh My Pi",
    package="@oh-my-pi/pi-coding-agent",
    tap_client="omp",
    executable="omp",
    fake_env={"OPENAI_API_KEY": "phistory-fake-api-key"},
    extra_env={
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "CI": "1",
    },
    binary_release_repo="can1357/oh-my-pi",
    binary_release_asset="omp-linux-x64",
    binary_release_tag="v{version}",
    home_profile="omp",
    run_args=(
        "--no-yolo",
        "--",
        "--print",
        "--mode",
        "text",
        "--no-session",
        "--approval-mode",
        "yolo",
        "--model",
        "phistory/gpt-4.1",
        "Reply with one short sentence.",
    ),
)

AGENTS: dict[str, AgentSpec] = {
    agent.id: agent
    for agent in (CLAUDE_CODE, CODEX, ANTIGRAVITY, KIMI_CODE, MIMO, OPENCLAW, HERMES, KIMI, OPENCODE, PI, OMP)
}
AGENT_ORDER = tuple(AGENTS)


def agent_sort_key(agent_id: str) -> tuple[int, str]:
    try:
        return (AGENT_ORDER.index(agent_id), "")
    except ValueError:
        return (len(AGENT_ORDER), agent_id)


def get_agent(agent_id: str) -> AgentSpec:
    try:
        return AGENTS[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(AGENTS))
        raise ValueError(f"unknown agent {agent_id!r}; known agents: {known}") from exc


def parse_agent_ids(value: str | None) -> list[str]:
    if not value:
        return list(AGENT_ORDER)
    ids = [item.strip() for item in value.split(",") if item.strip()]
    for agent_id in ids:
        get_agent(agent_id)
    return ids
