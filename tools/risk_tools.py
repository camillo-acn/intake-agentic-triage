"""Risk-assessor tools.

Heuristics that grade the *blast radius* of an incoming request given
the classifier's category and any extracted entities. The risk
assessor is then asked to reconcile these signals with the prose of
the request and emit a single ``Impact`` level.

Each tool returns the ``ToolSuccess | ToolError`` envelope.
"""

from __future__ import annotations

import re
from typing import Any

from agents.contracts import ToolError, ToolSuccess

# Category × baseline-impact rule table.
_BASELINE_IMPACT: dict[str, str] = {
    "password_reset": "low",
    "hardware_issue": "low",
    "software_bug": "low",
    "access_request": "low",
    "security_incident": "high",
}

# Words that escalate impact when present.
_ESCALATORS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b(production|prod|customer[- ]facing|outage|down|all users|company[- ]wide)\b", re.I),
     "high", "production / customer impact"),
    (re.compile(r"\b(datacenter|rack|primary storage|payments|payroll|fail(ed|ing) over)\b", re.I),
     "critical", "core infrastructure / financial system"),
    (re.compile(r"\b(board demo|ceo|executive|presenting now|in 30 minutes|deadline today|deadline tomorrow)\b", re.I),
     "high", "executive / time-critical"),
    (re.compile(r"\b(audit|reconciliation|month[- ]end|sla breach)\b", re.I),
     "high", "compliance / audit pressure"),
    (re.compile(r"\b(exfil|exfiltration|in progress|active(ly)? leaking|stolen laptop|domain admin)\b", re.I),
     "critical", "active security event"),
]

# Words that *deflate* impact (used to push back on adversarial 'urgent!!!' framing).
_DEFLATORS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(rendering|font|1px|cosmetic|symbol is off|annoying but)\b", re.I),
     "cosmetic / non-blocking"),
    (re.compile(r"\b(no rush|low priority|when you get a chance|nice to have)\b", re.I),
     "self-described low priority"),
]

_IMPACT_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_SLA_TABLE: dict[tuple[str, str], int] = {
    ("password_reset", "low"): 8,
    ("password_reset", "medium"): 4,
    ("password_reset", "high"): 1,
    ("hardware_issue", "low"): 24,
    ("hardware_issue", "medium"): 8,
    ("hardware_issue", "high"): 2,
    ("hardware_issue", "critical"): 1,
    ("software_bug", "low"): 24,
    ("software_bug", "medium"): 8,
    ("software_bug", "high"): 2,
    ("access_request", "low"): 24,
    ("access_request", "medium"): 8,
    ("access_request", "high"): 2,
    ("security_incident", "low"): 4,
    ("security_incident", "medium"): 2,
    ("security_incident", "high"): 1,
    ("security_incident", "critical"): 1,
}


def assess_business_impact(category: str, entities: list[Any] | None = None) -> dict[str, Any]:
    """Compute a baseline impact level from a heuristic rule table.

    Use this tool once the classifier has produced a category — it
    returns the *floor* for impact (e.g. security_incident floors at
    high). Do NOT use it as the final answer: combine with
    ``check_security_signals`` and the request prose.
    """
    try:
        if category not in _BASELINE_IMPACT:
            return ToolError(error={
                "code": "unknown_category",
                "message": f"category '{category}' not in taxonomy",
                "retry_hint": "use one of: password_reset, hardware_issue, software_bug, access_request, security_incident",
            }).model_dump()
        baseline = _BASELINE_IMPACT[category]
        # If the entity list looks production-y, bump baseline by one.
        bumped = baseline
        rationale = [f"baseline for {category} = {baseline}"]
        ent_strs = [str(e).lower() for e in (entities or [])]
        joined = " ".join(ent_strs)
        if any(k in joined for k in ("prod", "production", "payments", "datacenter", "payroll")):
            new_rank = min(_IMPACT_RANK[bumped] + 1, 3)
            bumped = next(k for k, v in _IMPACT_RANK.items() if v == new_rank)
            rationale.append(f"entities mention production-like systems → bump to {bumped}")
        return ToolSuccess(data={
            "baseline_impact": baseline,
            "adjusted_impact": bumped,
            "rationale": rationale,
        }).model_dump()
    except Exception as exc:
        return ToolError(error={
            "code": "impact_failed",
            "message": str(exc),
            "retry_hint": "verify category string",
        }).model_dump()


def check_security_signals(text: str) -> dict[str, Any]:
    """Detect PII / credential / exfiltration language in the request.

    Use this tool on every request, regardless of classifier verdict —
    it's the safety-net that catches social-engineering attempts
    misclassified as access requests. Do NOT use it to set category
    directly; pair it with ``assess_business_impact``.
    """
    try:
        text_lc = text.lower()
        flags: list[str] = []
        if re.search(r"\b(domain admin|root access|sudo|full admin|grant.*admin)\b", text_lc):
            flags.append("privilege_escalation_request")
        if re.search(r"\b(stolen|lost laptop|misplaced device)\b", text_lc):
            flags.append("device_loss")
        if re.search(r"\b(exfil|exfiltration|outbound traffic|unknown ip|data leak)\b", text_lc):
            flags.append("data_exfiltration")
        if re.search(r"\b(phishing|typo[- ]?d domain|fake email|spoof(ed)?)\b", text_lc):
            flags.append("phishing")
        if re.search(r"\b(credential[- ]steal|trojan|malware|ransomware|quarantin)\b", text_lc):
            flags.append("malware")
        if re.search(r"\b(personal phone|trust me|i'?ll handle the paperwork|skip the policy|bypass)\b", text_lc):
            flags.append("possible_social_engineering")
        if re.search(r"\b(ignore previous instructions|system override|debug mode|new rules)\b", text_lc):
            flags.append("prompt_injection_attempt")
        severity = "high" if flags else "none"
        if any(f in flags for f in ("data_exfiltration", "malware", "device_loss")):
            severity = "critical"
        return ToolSuccess(data={
            "flags": flags,
            "severity": severity,
            "count": len(flags),
        }).model_dump()
    except re.error as exc:
        return ToolError(error={
            "code": "regex_error",
            "message": str(exc),
            "retry_hint": "sanitize input and retry",
        }).model_dump()


def lookup_sla_tier(category: str, impact: str) -> dict[str, Any]:
    """Return the SLA target hours for a (category, impact) pair.

    Use this tool to enrich the recommended action with a concrete
    response window. Do NOT use it for the escalation decision — that
    is the coordinator's responsibility.
    """
    try:
        key = (category, impact)
        hours = _SLA_TABLE.get(key)
        if hours is None:
            return ToolError(error={
                "code": "no_sla",
                "message": f"no SLA defined for {category} × {impact}",
                "retry_hint": "fall back to a 24h default",
            }).model_dump()
        return ToolSuccess(data={
            "category": category,
            "impact": impact,
            "sla_hours": hours,
        }).model_dump()
    except Exception as exc:
        return ToolError(error={
            "code": "sla_failed",
            "message": str(exc),
            "retry_hint": "verify (category, impact) pair",
        }).model_dump()


__all__ = ["assess_business_impact", "check_security_signals", "lookup_sla_tier"]
