from phistory.registry import AGENT_ORDER, get_agent, parse_agent_ids


def test_display_order_starts_with_dsh_in_third_position():
    assert AGENT_ORDER[:3] == ("claude-code", "codex", "dsh")


def test_parse_default_agents():
    assert parse_agent_ids(None) == [
        "claude-code",
        "codex",
        "dsh",
        "antigravity",
        "grok",
        "minimax-code",
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
    assert agent.hidden_capture_variants == ("gpt-5.6",)
    assert agent.default_variant.label == "Default"
    assert "--" in agent.default_variant.run_args
    assert "--model" not in agent.default_variant.run_args
    assert [(variant.id, variant.dimensions) for variant in agent.variants] == [
        ("gpt-5.6-sol", {"model": "gpt-5.6-sol"}),
        ("gpt-5.6-terra", {"model": "gpt-5.6-terra"}),
        ("gpt-5.6-luna", {"model": "gpt-5.6-luna"}),
        ("gpt-5.5", {"model": "gpt-5.5"}),
    ]
    assert {variant.id: variant.min_version for variant in agent.variants} == {
        "gpt-5.6-sol": "0.144.0",
        "gpt-5.6-terra": "0.144.0",
        "gpt-5.6-luna": "0.144.0",
        "gpt-5.5": "0.125.0",
    }
    for variant in agent.variants:
        model_index = variant.run_args.index("--model")
        assert variant.run_args[model_index + 1] == variant.dimensions["model"]


def test_claude_code_uses_full_prompt_surface_with_isolated_sessions():
    agent = get_agent("claude-code")

    assert "--no-session-persistence" in agent.default_variant.run_args
    assert "--bare" not in agent.default_variant.run_args
    assert "--exclude-dynamic-system-prompt-sections" not in agent.default_variant.run_args


def test_new_agents_define_install_and_capture_profiles():
    antigravity = get_agent("antigravity")
    dsh = get_agent("dsh")
    grok = get_agent("grok")
    minimax_code = get_agent("minimax-code")
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
    assert antigravity.tap_mode == "forward"
    assert "--print" in antigravity.default_variant.run_args

    assert dsh.source == "npm"
    assert dsh.package == "@deepseek-ai/dsh"
    assert dsh.tap_client == "dsh"
    assert dsh.home_profile == "dsh"
    assert dsh.tap_mode == "forward"
    assert dsh.default_variant.id == "default"
    assert dsh.default_variant.driver == "dsh-web"
    assert dsh.default_variant.dimensions == {"surface": "web"}
    assert [variant.id for variant in dsh.variants] == ["headless", "standard", "code", "minimal", "cordis"]

    assert grok.source == "npm"
    assert grok.package == "@xai-official/grok"
    assert grok.tap_client == "grok"
    assert grok.fake_env == {
        "XAI_API_KEY": "phistory-fake-api-key",
        "GROK_CODE_XAI_API_KEY": "phistory-fake-api-key",
    }
    assert grok.home_profile == "grok"
    assert "--no-auto-update" in grok.default_variant.run_args
    assert "--single" in grok.default_variant.run_args

    assert minimax_code.source == "minimax-code"
    assert minimax_code.package == "MiniMax Code desktop app"
    assert minimax_code.tap_client == "minimax-code"
    assert minimax_code.tap_mode == "reverse"
    assert minimax_code.default_variant.run_args == ()

    assert kimi_code.source == "npm"
    assert kimi_code.package == "@moonshot-ai/kimi-code"
    assert kimi_code.tap_client == "kimi-code"
    assert kimi_code.executable == "kimi"
    assert kimi_code.home_profile == "kimi-code"
    assert "--prompt" in kimi_code.default_variant.run_args

    assert mimo.source == "npm"
    assert mimo.package == "@mimo-ai/cli"
    assert mimo.tap_client == "mimo"
    assert mimo.home_profile == "mimo"
    assert mimo.tap_mode == "reverse"
    assert "run" in mimo.default_variant.run_args
    assert "--dangerously-skip-permissions" in mimo.default_variant.run_args

    assert openclaw.source == "npm"
    assert openclaw.home_profile == "openclaw"
    assert openclaw.node_runtime == "node@24"
    assert "agent" in openclaw.default_variant.run_args

    assert hermes.source == "github-release"
    assert hermes.package == "NousResearch/hermes-agent"
    assert hermes.home_profile == "hermes"
    assert "chat" in hermes.default_variant.run_args
    assert "-q" in hermes.default_variant.run_args
    assert "openrouter" in hermes.default_variant.run_args

    assert kimi.source == "github-release"
    assert kimi.package == "MoonshotAI/kimi-cli"
    assert kimi.home_profile == "kimi"
    assert "--print" in kimi.default_variant.run_args

    assert opencode.source == "npm"
    assert opencode.package == "opencode-ai"
    assert opencode.home_profile == "opencode"
    assert opencode.tap_mode == "reverse"
    assert "run" in opencode.default_variant.run_args
    assert "--dir" in opencode.default_variant.run_args

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
    assert "--print" in omp.default_variant.run_args
