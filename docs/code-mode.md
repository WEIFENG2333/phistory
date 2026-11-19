# Claude Code Code Mode

The `code-mode` variant runs the interactive terminal with
`CLAUDE_CODE_EXPERIMENTAL_CODE_MODE=1` and a forward capture proxy. Phistory owns
`phistory/bootstrap/claude-code-mode.json`, which supplies synthetic organization
settings, policy and feature configuration. The isolated HOME records acceptance
of the experimental-mode prompts. Capture uses fake credentials and local model
responses.

`claude-tap --bootstrap-responses` supplies the transport-independent response
mechanism. The exact configuration and canonical SHA-256 are recorded in each
trace's `capture_environment` and in `meta.json`. Prompt and Trace views identify
these as simulated-startup captures. A successful archive requires an observed
`REPL` tool and matching bootstrap provenance; fallback to ordinary tools fails
the capture. The hourly workflow automatically captures this variant alongside
Terminal and Headless (-p). Future upstream changes to the startup endpoints or
feature flag require updating this fixture and repeating the real local smoke.
