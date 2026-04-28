"""Rule-based grader.

Exact-match comparison of a pipeline ``prediction`` against the ground-truth
fields on a ``case``. The score is the unweighted mean of three booleans
(category, impact, escalation), so a perfectly correct prediction scores 1.0
and a fully wrong one scores 0.0.

This grader is the cheap, deterministic floor that runs on every case in
every run. The LLM-judge grader (``llm_judge.py``) layers qualitative
signals on top of this on a sampled subset.
"""

from __future__ import annotations

from typing import Any


def grade_rule_based(case: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    """Compare a single prediction against expected fields.

    Args:
        case: ground-truth case record with ``expected_category``,
            ``expected_impact``, ``expected_escalation``.
        prediction: pipeline output with ``category``, ``impact``,
            ``escalate`` (or ``escalation``) keys. Missing keys count as
            mismatches rather than raising — the scorecard must keep going.

    Returns:
        Dict with three boolean ``*_match`` fields and a float ``score``
        (mean of the three booleans).
    """
    category_match = prediction.get("category") == case.get("expected_category")
    impact_match = prediction.get("impact") == case.get("expected_impact")

    pred_esc = prediction.get("escalate", prediction.get("escalation"))
    expected_esc = case.get("expected_escalation")
    escalation_match = bool(pred_esc) == bool(expected_esc)

    score = (int(category_match) + int(impact_match) + int(escalation_match)) / 3.0

    return {
        "category_match": bool(category_match),
        "impact_match": bool(impact_match),
        "escalation_match": bool(escalation_match),
        "score": round(score, 4),
    }
