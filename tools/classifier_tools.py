"""Classifier tools.

Cheap, deterministic signal extractors that the classifier specialist
consults before committing to a category. They never call out to an LLM
— they exist precisely to give the classifier *grounded* evidence the
LLM can be challenged against, especially on adversarial inputs that try
to override the verdict via prompt injection.

Each tool returns the ``ToolSuccess | ToolError`` envelope from
``agents.contracts``.
"""

from __future__ import annotations

import re
from typing import Any

from agents.contracts import ToolError, ToolSuccess

# Tiny historical-pattern KB. Each entry: (regex, category, hint).
_KNOWN_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b(password|passcode|locked out|reset link|sso reject)", re.I),
     "password_reset", "credential/login wording"),
    (re.compile(r"\b(mouse|keyboard|laptop|fan|battery|monitor|usb|chassis|rack|psu|power supply)\b", re.I),
     "hardware_issue", "physical-device wording"),
    (re.compile(r"\b(crash|exception|stack trace|null pointer|UI bug|wrong currency|throws|error code|excel|outlook crash)\b", re.I),
     "software_bug", "application-defect wording"),
    (re.compile(r"\b(access|grant|add me to|permission to|shared drive|onboard|provision|admin rights)\b", re.I),
     "access_request", "provisioning wording"),
    (re.compile(r"\b(phishing|trojan|malware|exfil|exfiltration|siem|quarantin|stolen laptop|credential[- ]steal|unauthorized)\b", re.I),
     "security_incident", "security wording"),
    (re.compile(r"\b(ignore previous instructions|system override|debug mode)\b", re.I),
     "security_incident", "prompt-injection signal — treat as suspect"),
]

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "password_reset": ["password", "reset", "locked out", "sso", "mfa", "login", "sign in"],
    "hardware_issue": ["mouse", "keyboard", "laptop", "fan", "battery", "monitor", "usb",
                        "chassis", "rack", "datacenter", "power supply", "disk", "drive failure"],
    "software_bug": ["crash", "error", "exception", "bug", "freeze", "wrong", "broken",
                      "throws", "doesn't work", "not working", "stack trace"],
    "access_request": ["access", "grant", "permission", "onboard", "provision", "shared drive",
                        "add me", "admin rights", "role"],
    "security_incident": ["phishing", "malware", "trojan", "exfiltration", "ransomware",
                           "stolen", "compromise", "breach", "siem", "quarantine",
                           "credential", "unauthorized", "data leak"],
}


def lookup_known_patterns(text: str) -> dict[str, Any]:
    """Match ``text`` against a small historical-pattern KB.

    Use this tool when you want a fast, deterministic short-list of
    categories grounded in past helpdesk tickets. Do NOT use it as the
    sole signal — patterns are intentionally narrow and can miss novel
    phrasings; combine it with ``check_keyword_signals``.
    """
    try:
        matches: list[dict[str, str]] = []
        for pattern, category, hint in _KNOWN_PATTERNS:
            m = pattern.search(text)
            if m:
                matches.append({
                    "category": category,
                    "matched": m.group(0),
                    "hint": hint,
                })
        return ToolSuccess(data={"matches": matches, "count": len(matches)}).model_dump()
    except re.error as exc:
        return ToolError(error={
            "code": "regex_error",
            "message": str(exc),
            "retry_hint": "input may contain incompatible characters; sanitize and retry",
        }).model_dump()


def extract_entities(text: str) -> dict[str, Any]:
    """Pull out structured entities (systems, accounts, error codes).

    Use this tool to ground the classifier's rationale in concrete
    artefacts mentioned by the user. Do NOT use it to *infer* category
    on its own — the entity list is descriptive, not prescriptive.
    """
    try:
        systems = re.findall(
            r"\b(Outlook|Teams|Excel|Slack|Jira|Confluence|SSO|MFA|Defender|Okta|"
            r"Active Directory|Lumen|VPN|Zoom|GitHub|GitLab|Salesforce|SAP)\b",
            text, flags=re.I,
        )
        # account / username-ish tokens
        accounts = re.findall(r"\b[a-z]{2,}-?[a-z0-9]+\b@?[a-z]*\.?[a-z]*", text)
        # error codes like HTTP-403, ERR_1234, 0x80004005
        error_codes = re.findall(r"\b(?:HTTP[- ]?\d{3}|ERR[_-]?\d+|0x[0-9a-fA-F]{4,}|E\d{3,5})\b", text)
        ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
        return ToolSuccess(data={
            "systems": sorted(set(s.lower() for s in systems)),
            "error_codes": sorted(set(error_codes)),
            "ip_candidates": sorted(set(ips)),
            "account_tokens": sorted(set(a.lower() for a in accounts))[:8],
        }).model_dump()
    except re.error as exc:
        return ToolError(error={
            "code": "regex_error",
            "message": str(exc),
            "retry_hint": "sanitize input and retry",
        }).model_dump()


def check_keyword_signals(text: str) -> dict[str, Any]:
    """Score the text against per-category keyword lexicons.

    Use this tool when ``lookup_known_patterns`` returns nothing or
    multiple competing categories. Do NOT use it for the *impact*
    decision — it only scores categorical signal strength.
    """
    try:
        text_lc = text.lower()
        scores: dict[str, int] = {}
        evidence: dict[str, list[str]] = {}
        for cat, words in _CATEGORY_KEYWORDS.items():
            hits = [w for w in words if w in text_lc]
            scores[cat] = len(hits)
            evidence[cat] = hits
        top = max(scores.items(), key=lambda kv: kv[1]) if scores else ("", 0)
        return ToolSuccess(data={
            "scores": scores,
            "evidence": evidence,
            "top_category": top[0] if top[1] > 0 else None,
            "top_score": top[1],
        }).model_dump()
    except Exception as exc:  # narrow: unexpected scoring failure
        return ToolError(error={
            "code": "scoring_failed",
            "message": str(exc),
            "retry_hint": "check input encoding",
        }).model_dump()


__all__ = ["lookup_known_patterns", "extract_entities", "check_keyword_signals"]
