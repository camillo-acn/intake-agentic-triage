"""LLM-judge grader (Bedrock).

Calls Claude on AWS Bedrock to score the qualitative aspects of a pipeline
prediction that the rule-based grader cannot see: how well the rationale
explains the decision, and whether the proposed action fits the request.

Environment expectations (from ``CLAUDE.md``):

- Bedrock model id: ``us.anthropic.claude-sonnet-4-20250514-v1:0``
- Region: ``us-east-1``
- AWS profile: ``bootcamp``

The judge returns strict JSON ``{rationale_quality, action_appropriateness,
justification}``. Fence stripping and a single retry are implemented to
absorb the most common formatting drifts. If boto3 is missing or the
Bedrock call fails, ``grade_llm_judge`` returns a ``skipped: True`` result
with an ``error`` key — the scorecard logs the warning and keeps going.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

LOGGER = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"
AWS_PROFILE = "bootcamp"

JUDGE_SYSTEM = (
    "You are a strict evaluator for an IT Helpdesk triage system. "
    "Score the model's output on two 1-5 axes and return ONLY JSON, no prose, "
    "no markdown fences. Schema: "
    '{"rationale_quality": int (1-5), '
    '"action_appropriateness": int (1-5), '
    '"justification": str (<=200 chars)}.'
)

JUDGE_TEMPLATE = """User request:
{raw_request}

Ground truth:
- category: {expected_category}
- impact: {expected_impact}
- escalation: {expected_escalation}

Model prediction:
{prediction_json}

Score the prediction:
- rationale_quality: how well does the prediction's rationale (if any) justify the chosen category/impact?
- action_appropriateness: does the proposed action / escalation fit a real IT helpdesk response?

Return strict JSON only.
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences if present."""
    return _FENCE_RE.sub("", text).strip()


def _parse_judge_payload(text: str) -> dict[str, Any]:
    """Parse the judge's JSON, tolerating leading/trailing prose."""
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Find the first {...} block and try again.
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _invoke_bedrock(client: Any, prompt: str) -> str:
    """Call Bedrock once with the given prompt; return raw text content."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "system": JUDGE_SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(resp["body"].read())
    blocks = payload.get("content", [])
    text_chunks = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    return "".join(text_chunks).strip()


def _make_client() -> Any:
    """Build a Bedrock-runtime client; raise on import or auth failure."""
    import boto3  # local import so missing boto3 is recoverable

    session = boto3.Session(profile_name=AWS_PROFILE, region_name=BEDROCK_REGION)
    return session.client("bedrock-runtime")


def grade_llm_judge(
    case: dict[str, Any],
    prediction: dict[str, Any],
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    """Grade a single (case, prediction) pair via Bedrock-hosted Claude.

    Args:
        case: ground-truth case dict.
        prediction: pipeline output dict (any JSON-serializable shape).
        client: optional pre-built ``bedrock-runtime`` client; built lazily
            from the configured profile/region if omitted.

    Returns:
        Dict shaped either as
        ``{rationale_quality, action_appropriateness, justification}`` on
        success, or ``{skipped: True, error: "..."}`` if Bedrock or boto3
        is unavailable. Never raises to the caller — the scorecard treats
        the judge as best-effort.
    """
    try:
        bedrock = client if client is not None else _make_client()
    except Exception as exc:  # boto3 missing or auth failure
        LOGGER.warning("LLM judge unavailable, skipping: %s", exc)
        return {"skipped": True, "error": f"client_init_failed: {exc!s}"}

    prompt = JUDGE_TEMPLATE.format(
        raw_request=case.get("raw_request", ""),
        expected_category=case.get("expected_category", ""),
        expected_impact=case.get("expected_impact", ""),
        expected_escalation=case.get("expected_escalation", ""),
        prediction_json=json.dumps(prediction, ensure_ascii=False),
    )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = _invoke_bedrock(bedrock, prompt)
            parsed = _parse_judge_payload(raw)
            return {
                "rationale_quality": int(parsed.get("rationale_quality", 0)),
                "action_appropriateness": int(parsed.get("action_appropriateness", 0)),
                "justification": str(parsed.get("justification", ""))[:300],
            }
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = exc
            LOGGER.warning("LLM judge parse failure on attempt %d: %s", attempt + 1, exc)
            continue
        except Exception as exc:  # network / Bedrock / auth at call time
            LOGGER.warning("LLM judge call failed on attempt %d: %s", attempt + 1, exc)
            return {"skipped": True, "error": f"invoke_failed: {exc!s}"}

    return {"skipped": True, "error": f"parse_failed: {last_error!s}"}
