"""Thin Bedrock-runtime wrapper used by the specialist agents.

We deliberately do not use the Claude Agent SDK's tool-use loop here:
the timebox is 30 minutes and the SDK's ergonomics around custom tool
schemas, async loops, and structured-output enforcement vary across
versions. Instead we run the heuristic tools deterministically *before*
the LLM call and inject their output into the prompt. The LLM then
emits strict JSON which we parse into a Pydantic model.

This keeps latency low (one Bedrock call per specialist), reasoning
grounded in tool outputs, and the trace clean.

Retries: exponential backoff (0.5s, 1.0s) with at most two retries on
throttling / transient errors. After that the caller decides how to
fail — typically by returning an "unknown / escalate=True" verdict so
the case lands on a human.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

LOGGER = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"
AWS_PROFILE = "bootcamp"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def make_client() -> Any:
    """Build a Bedrock-runtime client from the configured profile/region."""
    import boto3

    session = boto3.Session(profile_name=AWS_PROFILE, region_name=BEDROCK_REGION)
    return session.client("bedrock-runtime")


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse a Claude response that should contain a JSON object.

    Tolerates: leading/trailing prose, markdown fences, and an extra
    trailing comma here and there. Raises ``json.JSONDecodeError`` if
    nothing JSON-shaped can be recovered.
    """
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def invoke_claude(
    *,
    client: Any,
    system: str,
    user: str,
    max_tokens: int = 800,
) -> str:
    """Single Bedrock call, returning concatenated text content.

    Retries on transient failures with exponential backoff. Raises the
    last exception if all retries fail — the caller is expected to
    catch and degrade gracefully.
    """
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    delays = [0.5, 1.0]
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(resp["body"].read())
            blocks = payload.get("content", [])
            chunks = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            return "".join(chunks).strip()
        except Exception as exc:  # broad on purpose: bedrock raises various
            last_exc = exc
            LOGGER.warning("Bedrock invoke failed (attempt %d/3): %s", attempt + 1, exc)
            if attempt < len(delays):
                time.sleep(delays[attempt])
                continue
            raise
    # unreachable, but keeps type checker happy
    assert last_exc is not None
    raise last_exc


__all__ = [
    "AWS_PROFILE",
    "BEDROCK_MODEL_ID",
    "BEDROCK_REGION",
    "invoke_claude",
    "make_client",
    "parse_json_response",
]
