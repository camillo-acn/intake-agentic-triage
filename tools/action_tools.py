"""Action tools — the high-risk write ops the PreToolUse hook gates.

Both ``create_ticket`` and ``notify_oncall`` are mocked: they never
actually write to a real ITSM or paging system. They exist for two
reasons:

1. To exercise the PreToolUse hook contract end-to-end. The hook reads
   the tool name + input args and decides whether the call may proceed.
2. To give the coordinator a realistic write-side surface for the
   trace, so that the trajectory grader and the LLM judge can reason
   about what *would* have been done.
"""

from __future__ import annotations

import uuid
from typing import Any

from agents.contracts import ToolError, ToolSuccess


def create_ticket(category: str, impact: str, summary: str,
                   human_approved: bool = False) -> dict[str, Any]:
    """Create a (mock) ITSM ticket.

    Use this tool only after the classifier and risk assessor have both
    produced a verdict and the coordinator has decided whether to
    escalate. Do NOT use it before classification — without a category
    the ticket would land in an unrouteable queue.

    The ``human_approved`` flag is forwarded through the PreToolUse
    hook: ``security_incident`` writes are blocked unless the flag is
    explicitly true.
    """
    try:
        ticket_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        return ToolSuccess(data={
            "ticket_id": ticket_id,
            "category": category,
            "impact": impact,
            "summary": summary[:200],
            "human_approved": bool(human_approved),
            "mocked": True,
        }).model_dump()
    except Exception as exc:
        return ToolError(error={
            "code": "ticket_failed",
            "message": str(exc),
            "retry_hint": "retry once; if it fails again, escalate to L2",
        }).model_dump()


def notify_oncall(severity: str, human_approved: bool = False) -> dict[str, Any]:
    """Page the on-call rotation (mock).

    Use this tool only when the coordinator has decided to escalate
    *and* the impact is high or critical. Do NOT use it for routine
    auto-handle paths — paging on low-impact tickets is the fastest
    way to lose oncall trust.
    """
    try:
        page_id = f"PAGE-{uuid.uuid4().hex[:8].upper()}"
        return ToolSuccess(data={
            "page_id": page_id,
            "severity": severity,
            "human_approved": bool(human_approved),
            "mocked": True,
        }).model_dump()
    except Exception as exc:
        return ToolError(error={
            "code": "notify_failed",
            "message": str(exc),
            "retry_hint": "retry once; if it fails again, fall back to email",
        }).model_dump()


__all__ = ["create_ticket", "notify_oncall"]
