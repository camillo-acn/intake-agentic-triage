"""Trajectory grader.

Scores the *path* the system took, not the final answer. We look for
two things in the coordinator's emitted trace:

1. ``steps_count`` — how many specialist (LLM) steps fired. The
   target topology has two specialists (classifier + risk_assessor)
   plus the coordinator decision, so a healthy trace contains roughly
   2-3 LLM-level steps. Tool steps are excluded from this count to
   keep the metric stable as we add more heuristic tools.
2. ``escalation_path_correct`` — whether the coordinator's final
   ``escalate`` flag matches the case's ``expected_escalation``. This
   is a duplicate signal vs. the rule-based grader, but kept here
   because the trajectory view is what the LLM judge consumes when
   reasoning about *how* the system arrived at the answer.

For backward compatibility with the Phase 1 stub the grader still
accepts ``trace=None`` / ``trace={}`` and returns zeros.
"""

from __future__ import annotations

from typing import Any

# Steps we treat as "specialist work" for the steps_count metric.
_LLM_STEP_PREFIXES: tuple[str, ...] = ("llm:", "decision:")


def _count_llm_steps(steps: list[dict[str, Any]]) -> int:
    return sum(
        1
        for s in steps
        if isinstance(s, dict)
        and any(str(s.get("step", "")).startswith(p) for p in _LLM_STEP_PREFIXES)
    )


def grade_trajectory(case: dict[str, Any], trace: dict[str, Any] | None) -> dict[str, Any]:
    """Score a pipeline trace against the case's expected escalation path.

    Args:
        case: ground-truth case dict.
        trace: pipeline trace dict ``{steps, final_escalation}`` or
            ``None``/``{}`` when no trace is available.

    Returns:
        Dict ``{steps_count, escalation_path_correct}``.
    """
    if not trace:
        return {"steps_count": 0, "escalation_path_correct": False}

    steps = trace.get("steps") or []
    steps_count = _count_llm_steps(steps) if isinstance(steps, list) else 0

    expected_escalation = bool(case.get("expected_escalation"))
    final_escalation = bool(trace.get("final_escalation", trace.get("escalation", False)))
    escalation_path_correct = expected_escalation == final_escalation

    return {
        "steps_count": int(steps_count),
        "escalation_path_correct": bool(escalation_path_correct),
    }
