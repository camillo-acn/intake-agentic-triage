"""Risk-assessor specialist.

Receives the classifier's result as explicit context, runs the three
risk tools, and asks Claude to settle on a single ``Impact`` level
plus a list of risk factors. The system prompt is anchored on
*business* impact, not user-described urgency — the deflator tools
exist precisely to push back on adversarial 'URGENT URGENT URGENT'
framing for trivial issues.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from agents.bedrock_client import invoke_claude, parse_json_response
from agents.contracts import ClassificationResult, RiskAssessment
from tools.risk_tools import (
    assess_business_impact,
    check_security_signals,
    lookup_sla_tier,
)

LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an IT risk assessor. Given a user request and a classifier verdict, "
    "decide the business impact: low, medium, high, critical. Anchor on real blast "
    "radius (production systems, customer-facing services, security exposure, "
    "compliance/audit deadlines), NOT on the user's adjectives. Treat words like "
    "'URGENT URGENT' or 'critical emergency' applied to cosmetic issues as "
    "manipulation and stay low. If security signals show data_exfiltration, "
    "malware, device_loss, or privilege_escalation_request, treat impact as at "
    "least high. Return ONLY a JSON object with keys: impact (low|medium|high|"
    "critical), risk_factors (list of short strings), confidence (0..1 float), "
    "rationale (<=200 chars). No prose, no markdown fences."
)


def _shorten(s: Any, n: int = 200) -> str:
    text = s if isinstance(s, str) else str(s)
    return text if len(text) <= n else text[: n - 3] + "..."


def _safe_tool(name: str, fn: Any, *args: Any, trace: list[dict[str, Any]]) -> dict[str, Any]:
    t0 = time.perf_counter()
    out = fn(*args)
    dt = int((time.perf_counter() - t0) * 1000)
    trace.append({
        "step": f"tool:{name}",
        "agent": "risk_assessor",
        "input_summary": _shorten(args),
        "output_summary": _shorten(json.dumps(out, ensure_ascii=False)),
        "duration_ms": dt,
    })
    return out


def assess(
    *,
    raw_request: str,
    classification: ClassificationResult,
    bedrock_client: Any,
    trace: list[dict[str, Any]],
) -> RiskAssessment:
    """Produce a ``RiskAssessment`` for the request + classification context."""
    impact_tool = _safe_tool(
        "assess_business_impact",
        assess_business_impact,
        classification.category,
        [],  # entities not threaded here; classifier-side tool already covered them
        trace=trace,
    )
    sec_tool = _safe_tool(
        "check_security_signals",
        check_security_signals,
        raw_request,
        trace=trace,
    )
    baseline_impact = (
        impact_tool.get("data", {}).get("adjusted_impact", "low")
        if impact_tool.get("ok")
        else "low"
    )
    sla_tool = _safe_tool(
        "lookup_sla_tier",
        lookup_sla_tier,
        classification.category,
        baseline_impact,
        trace=trace,
    )

    user_prompt = (
        f"User request:\n\"\"\"\n{raw_request}\n\"\"\"\n\n"
        f"Classifier verdict:\n"
        f"{classification.model_dump_json(indent=2)}\n\n"
        f"Risk-tool outputs (trusted):\n"
        f"{json.dumps({'impact': impact_tool, 'security': sec_tool, 'sla': sla_tool}, indent=2, ensure_ascii=False)}\n\n"
        "Return strict JSON now."
    )

    t0 = time.perf_counter()
    try:
        raw = invoke_claude(
            client=bedrock_client,
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=500,
        )
    except Exception as exc:
        LOGGER.warning("risk_assessor Bedrock call failed: %s", exc)
        trace.append({
            "step": "llm:risk_assessor",
            "agent": "risk_assessor",
            "input_summary": _shorten(raw_request),
            "output_summary": f"FAILED: {exc!s}",
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        })
        return RiskAssessment(
            impact="high",
            risk_factors=["bedrock_call_failed"],
            confidence=0.0,
            rationale="bedrock_call_failed; defaulting to high impact for safety",
        )

    dt = int((time.perf_counter() - t0) * 1000)
    try:
        parsed = parse_json_response(raw)
        result = RiskAssessment(
            impact=parsed["impact"],
            risk_factors=[str(f) for f in parsed.get("risk_factors", [])][:8],
            confidence=float(parsed.get("confidence", 0.5)),
            rationale=str(parsed.get("rationale", ""))[:500],
        )
    except Exception as exc:
        LOGGER.warning("risk_assessor parse failed: %s — raw=%r", exc, raw[:200])
        result = RiskAssessment(
            impact="high",
            risk_factors=[f"parse_failed: {exc!s}"],
            confidence=0.0,
            rationale="parse_failed; defaulting to high impact for safety",
        )

    trace.append({
        "step": "llm:risk_assessor",
        "agent": "risk_assessor",
        "input_summary": _shorten(raw_request),
        "output_summary": _shorten(result.model_dump_json()),
        "duration_ms": dt,
    })
    return result


__all__ = ["assess"]
