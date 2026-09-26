"""Replace capture-run noise in rendered Markdown with stable placeholders.

Rules are pattern-driven rather than bound to one run's directories, so a
snapshot rendered today and the same snapshot re-rendered from its archived
trace years later normalize identically.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Capture scaffolding first: later rules match against the placeholder paths.
_CAPTURE_PATHS = (
    (re.compile(r"(?:/[\w.@+-]+)+/installs/[\w.@+-]+/[\w.@+-]+"), "$PHISTORY_INSTALL"),
    (re.compile(r"(?:/[\w.@+-]+)*/phistory-home-[A-Za-z0-9_]+"), "$PHISTORY_HOME"),
    (re.compile(r"(?:/[\w.@+-]+)*/phistory-work-[A-Za-z0-9_]+"), "$PHISTORY_WORKSPACE"),
    # Some releases print the capture machine's own paths (extra working dirs, tool locations).
    (re.compile(r"(?:/[\w.-]+)*/home/[A-Za-z0-9_][\w.-]*"), "$PHISTORY_USER_HOME"),
)

_VOLATILE = (
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
    (re.compile(r"\bcch=[^;\s]+"), "cch=<normalized>"),
    # Local service URLs carry a per-run port; the scheme marks them as live endpoints.
    (re.compile(r"http://(?:127\.0\.0\.1|localhost):\d+"), "http://127.0.0.1:$PHISTORY_PORT"),
    (re.compile(r"(?m)^ - OS Version: .+$"), " - OS Version: $PHISTORY_OS_VERSION"),
    (re.compile(r" - OS Version: [^\\\n]*(?=\\n)"), " - OS Version: $PHISTORY_OS_VERSION"),
    (re.compile(r"Today's date is \d{4}[-/]\d{2}[-/]\d{2}\."), "Today's date is $PHISTORY_DATE."),
    (re.compile(r"(?m)^Today's date: \d{4}[-/]\d{2}[-/]\d{2}$"), "Today's date: $PHISTORY_DATE"),
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
        re.compile(r"\$PHISTORY_HOME/\.claude/projects/-[\w-]*phistory-work-[^/\s]+"),
        "$PHISTORY_HOME/.claude/projects/$PHISTORY_PROJECT",
    ),
    (
        re.compile(r"\$PHISTORY_HOME/\.local/share/mimocode/memory/sessions/ses_[A-Za-z0-9_]+"),
        "$PHISTORY_HOME/.local/share/mimocode/memory/sessions/$PHISTORY_SESSION",
    ),
    (re.compile(r"Bearer phistory-[A-Za-z0-9_-]+"), "Bearer <redacted>"),
    (re.compile(r"claude --resume [0-9a-f-]{36}"), "claude --resume $PHISTORY_SESSION"),
    (re.compile(r"(?m)^(\s*\"session_?[iI]d\":\s*\")[0-9a-f-]{36}"), r"\1$PHISTORY_SESSION"),
)

_TRAILING_SPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_FENCE_GAP = re.compile(r"\n{3,}(```json)")


def sanitize(text: str, *, ports: Iterable[int] = ()) -> str:
    """`ports` are the run's own proxy ports; documented example ports stay intact."""
    for port in sorted(set(ports)):
        text = re.sub(rf"\b(127\.0\.0\.1|localhost):{port}\b", r"\1:$PHISTORY_PORT", text)
    for pattern, replacement in _CAPTURE_PATHS + _VOLATILE:
        text = pattern.sub(replacement, text)
    text = _TRAILING_SPACE.sub("", text)
    return _FENCE_GAP.sub(r"\n\n\1", text)
