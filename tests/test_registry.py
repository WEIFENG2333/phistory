from phistory.registry import get_agent, parse_agent_ids


def test_parse_default_agents():
    assert parse_agent_ids(None) == ["claude-code", "codex"]


def test_get_agent_has_capture_contract():
    agent = get_agent("codex")

    assert agent.package == "@openai/codex"
    assert agent.tap_client == "codex"
    assert "OPENAI_API_KEY" in agent.fake_env
    assert "--" in agent.run_args
