from phistory.registry import get_agent, parse_agent_ids


def test_parse_default_agents():
    assert parse_agent_ids(None) == [
        "claude-code",
        "codex",
        "antigravity",
        "kimi-code",
        "mimo",
        "openclaw",
        "hermes",
        "kimi",
        "opencode",
        "pi",
        "omp",
    ]


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
    antigravity = get_agent("antigravity")
    kimi_code = get_agent("kimi-code")
    mimo = get_agent("mimo")
    openclaw = get_agent("openclaw")
    hermes = get_agent("hermes")
    kimi = get_agent("kimi")
    opencode = get_agent("opencode")
    pi = get_agent("pi")
    omp = get_agent("omp")

    assert antigravity.source == "github-release-asset"
    assert antigravity.package == "google-antigravity/antigravity-cli"
    assert antigravity.release_asset == "agy_cli_linux_x64.tar.gz"
    assert antigravity.release_asset_binary == "antigravity"
    assert antigravity.release_manifest_url
    assert antigravity.tap_client == "agy"
    assert antigravity.home_profile == "antigravity"
    assert antigravity.tap_target_profile == "antigravity"
    assert "--print" in antigravity.run_args

    assert kimi_code.source == "npm"
    assert kimi_code.package == "@moonshot-ai/kimi-code"
    assert kimi_code.tap_client == "kimi-code"
    assert kimi_code.executable == "kimi"
    assert kimi_code.home_profile == "kimi-code"
    assert "--prompt" in kimi_code.run_args

    assert mimo.source == "npm"
    assert mimo.package == "@mimo-ai/cli"
    assert mimo.tap_client == "mimo"
    assert mimo.home_profile == "mimo"
    assert mimo.tap_mode == "reverse"
    assert "run" in mimo.run_args
    assert "--dangerously-skip-permissions" in mimo.run_args

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

    assert kimi.source == "github-release"
    assert kimi.package == "MoonshotAI/kimi-cli"
    assert kimi.home_profile == "kimi"
    assert "--print" in kimi.run_args

    assert opencode.source == "npm"
    assert opencode.package == "opencode-ai"
    assert opencode.home_profile == "opencode"
    assert opencode.tap_mode == "reverse"
    assert "run" in opencode.run_args
    assert "--dir" in opencode.run_args

    assert pi.source == "npm"
    assert pi.package == "@earendil-works/pi-coding-agent"
    assert pi.home_profile == "pi"
    assert pi.node_runtime is None

    assert omp.source == "npm"
    assert omp.package == "@oh-my-pi/pi-coding-agent"
    assert omp.tap_client == "omp"
    assert omp.executable == "omp"
    assert omp.home_profile == "omp"
    assert omp.binary_release_repo == "can1357/oh-my-pi"
    assert omp.binary_release_asset == "omp-linux-x64"
    assert omp.binary_release_tag == "v{version}"
    assert "--print" in omp.run_args
