"""Coordinator — public entry point for the triage pipeline.

Orchestrates Classifier → RiskAssessor → escalation rule, and emits a
single ``TriageDecision`` with a step-by-step ``trace`` ready for the
trajectory grader.

The coordinator owns three things the specialists do not:

1. The escalation rule from ``CLAUDE.md``:
   ``escalate = (category == 'security_incident') or (confidence < 0.6)
                  or (impact in {'high', 'critical'})``.
2. The recommended-action string (auto-handle vs L2 escalation).
3. Graceful degradation: if either specialist's Bedrock call fails
   permanently, the case is flagged with low confidence so the
   escalation rule routes it to a human.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from agents.bedrock_client import make_client
from agents.classifier import classify
from agents.contracts import (
    Category,
    Impact,
    IntakeRequest,
    TriageDecision,
)
from agents.risk_assessor import assess

LOGGER = logging.getLogger(__name__)

_AUTO_HANDLE_HINT: dict[str, str] = {
    "password_reset": "Trigger self-service password reset flow and email recovery link",
    "hardware_issue": "Open hardware ticket; ship spare from local depot if applicable",
    "software_bug": "Log defect with repro steps; assign to owning app team",
    "access_request": "Route to access-management workflow for approval",
    "security_incident": "Escalate to L2 on-call",  # never used (always escalates)
}


def _should_escalate(category: str, confidence: float, impact: str) -> bool:
    return (
        category == "security_incident"
        or confidence < 0.6
        or impact in {"high", "critical"}
    )


def _recommended_action(*, escalate: bool, category: str, impact: str) -> str:
    if escalate:
        return f"Escalate to L2 on-call ({category}, impact={impact})"
    return f"Auto-handle: {_AUTO_HANDLE_HINT.get(category, 'route to L1 queue')}"


async def triage(request: IntakeRequest) -> TriageDecision:
    """Run the full pipeline asynchronously and return a ``TriageDecision``.

    The Bedrock client is built lazily; if construction fails (missing
    boto3, missing creds), the case is recorded as
    ``unknown / unknown / escalate=True`` so it lands on a human.
    """
    trace: list[dict[str, Any]] = []
    pipeline_start = time.perf_counter()

    # Build the Bedrock client up-front. This is the only network-y bit
    # that can blow up before any specialist runs.
    try:
        bedrock = await asyncio.to_thread(make_client)
    except Exception as exc:
        LOGGER.error("could not build Bedrock client: %s", exc)
        trace.append({
            "step": "init:bedrock",
            "agent": "coordinator",
            "input_summary": "make_client()",
            "output_summary": f"FAILED: {exc!s}",
            "duration_ms": int((time.perf_counter() - pipeline_start) * 1000),
        })
        # Degrade gracefully: route to a human.
        return TriageDecision(
            request_id=request.id,
            category="security_incident",
            impact="high",
            confidence=0.0,
            escalate=True,
            recommended_action="Escalate to L2 on-call (Bedrock unavailable; safe-by-escalate)",
            rationale=f"bedrock_init_failed: {exc!s}",
            trace=trace,
        )

    classification = await asyncio.to_thread(
        classify,
        raw_request=request.raw_request,
        bedrock_client=bedrock,
        trace=trace,
    )
    risk = await asyncio.to_thread(
        assess,
        raw_request=request.raw_request,
        classification=classification,
        bedrock_client=bedrock,
        trace=trace,
    )

    # Combined confidence: floor of the two specialists.
    combined_conf = min(classification.confidence, risk.confidence)

    escalate = _should_escalate(
        category=classification.category,
        confidence=combined_conf,
        impact=risk.impact,
    )
    action = _recommended_action(
        escalate=escalate,
        category=classification.category,
        impact=risk.impact,
    )
    rationale = (
        f"category={classification.category} (conf={classification.confidence:.2f}: "
        f"{classification.rationale}); impact={risk.impact} "
        f"(conf={risk.confidence:.2f}: {risk.rationale}); "
        f"escalate={escalate} per rule "
        f"(security_incident={classification.category == 'security_incident'}, "
        f"conf<0.6={combined_conf < 0.6}, "
        f"impact_high_or_critical={risk.impact in {'high', 'critical'}})"
    )

    trace.append({
        "step": "decision:coordinator",
        "agent": "coordinator",
        "input_summary": (
            f"category={classification.category}, impact={risk.impact}, "
            f"combined_conf={combined_conf:.2f}"
        ),
        "output_summary": f"escalate={escalate}, action={action}",
        "duration_ms": int((time.perf_counter() - pipeline_start) * 1000),
    })

    return TriageDecision(
        request_id=request.id,
        category=classification.category,
        impact=risk.impact,
        confidence=round(combined_conf, 4),
        escalate=escalate,
        recommended_action=action,
        rationale=rationale[:600],
        trace=trace,
    )


def triage_sync(request: IntakeRequest) -> TriageDecision:
    """Synchronous helper for callers that don't run an event loop."""
    return asyncio.run(triage(request))


__all__ = ["triage", "triage_sync"]
