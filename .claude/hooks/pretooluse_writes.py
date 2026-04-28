"""PreToolUse hook gating high-risk write operations.

Reads a JSON event from stdin (Claude Code hook protocol), inspects the
tool name and its input arguments, and emits a JSON decision back to
stdout: ``{"decision": "approve"|"block", "reason": "..."}``.

Policy:
- Tools other than ``create_ticket`` / ``notify_oncall`` are allowed
  through untouched.
- For those two tools, if ``category == 'security_incident'`` AND no
  explicit ``human_approved == True`` flag is present in the tool
  input, the call is blocked with reason "high-risk write requires
  human approval".
- Otherwise the call is approved with a logged reason.

Every decision (approve or block) is appended to
``.claude/logs/pretooluse.log`` so the run can be audited.

The hook is wired up in ``.claude/settings.json`` on the ``PreToolUse``
event with a matcher that targets the two gated tool names.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

GATED_TOOLS: set[str] = {"create_ticket", "notify_oncall"}
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "pretooluse.log"


def _log(decision: str, tool: str, reason: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp}\t{decision}\t{tool}\t{reason}\n"
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line)


def decide(event: dict) -> dict:
    """Return the hook decision dict for a parsed event payload."""
    tool_name = (
        event.get("tool_name")
        or event.get("toolName")
        or event.get("name")
        or ""
    )
    tool_input = (
        event.get("tool_input")
        or event.get("toolInput")
        or event.get("input")
        or {}
    )
    if tool_name not in GATED_TOOLS:
        reason = f"tool '{tool_name}' is not gated"
        _log("approve", tool_name or "<unknown>", reason)
        return {"decision": "approve", "reason": reason}

    category = str(tool_input.get("category", "")).lower()
    human_approved = bool(tool_input.get("human_approved", False))

    if category == "security_incident" and not human_approved:
        reason = "high-risk write requires human approval"
        _log("block", tool_name, reason)
        return {"decision": "block", "reason": reason}

    reason = (
        f"approved: category={category or 'n/a'}, "
        f"human_approved={human_approved}"
    )
    _log("approve", tool_name, reason)
    return {"decision": "approve", "reason": reason}


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        # Treat empty stdin as a no-op approve so we never block silently.
        out = {"decision": "approve", "reason": "empty event"}
        sys.stdout.write(json.dumps(out))
        return 0
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        out = {"decision": "block", "reason": f"invalid JSON event: {exc!s}"}
        sys.stdout.write(json.dumps(out))
        return 0

    decision = decide(event if isinstance(event, dict) else {})
    sys.stdout.write(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
