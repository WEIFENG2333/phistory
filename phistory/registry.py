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

AGENTS: dict[str, AgentSpec] = {agent.id: agent for agent in (CLAUDE_CODE, CODEX, HERMES, OPENCLAW)}


def get_agent(agent_id: str) -> AgentSpec:
    try:
        return AGENTS[agent_id]
    except KeyError as exc:
        known = ", ".join(sorted(AGENTS))
        raise ValueError(f"unknown agent {agent_id!r}; known agents: {known}") from exc


def parse_agent_ids(value: str | None) -> list[str]:
    if not value:
        return sorted(AGENTS)
    ids = [item.strip() for item in value.split(",") if item.strip()]
    for agent_id in ids:
        get_agent(agent_id)
    return ids
