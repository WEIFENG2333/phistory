from phistory.registry import get_agent, parse_agent_ids


def test_parse_default_agents():
    assert parse_agent_ids(None) == ["claude-code", "codex", "hermes", "openclaw"]


def test_get_agent_has_capture_contract():
    agent = get_agent("codex")

    assert agent.package == "@openai/codex"
    assert agent.tap_client == "codex"
    assert agent.fake_chatgpt_auth
    assert "--" in agent.run_args


def test_claude_code_uses_full_prompt_surface_with_isolated_sessions():
    agent = get_agent("claude-code")

    assert "--no-session-persistence" in agent.run_args
    assert "--bare" not in agent.run_args
    assert "--exclude-dynamic-system-prompt-sections" not in agent.run_args


def test_new_agents_define_install_and_capture_profiles():
    openclaw = get_agent("openclaw")
    hermes = get_agent("hermes")

    assert openclaw.source == "npm"
    assert openclaw.home_profile == "openclaw"
    assert openclaw.node_runtime == "node@24"
    assert "agent" in openclaw.run_args

    assert hermes.source == "github-release"
    assert hermes.package == "NousResearch/hermes-agent"
    assert hermes.home_profile == "hermes"
    assert "chat" in hermes.run_args
    assert "-q" in hermes.run_args
    assert "openrouter" in hermes.run_args
