"""Trajectory grader (stub).

In Phase 2 the Coordinator will emit a structured ``trace`` describing the
specialists it invoked and their outcomes. This grader scores that path
rather than the final answer: it answers "did the system reach the right
escalation through the right route?".

For Phase 1 the pipeline does not yet emit a trace, so this is a stub: it
accepts an optional ``trace`` dict and returns zeros when the trace is
empty. The shape of the return value is the contract the scorecard relies
on, so it is stable from this commit forward.
"""

from __future__ import annotations

from typing import Any


def grade_trajectory(case: dict[str, Any], trace: dict[str, Any] | None) -> dict[str, Any]:
    """Score a pipeline trace against the case's expected escalation path.

    Args:
        case: ground-truth case dict.
        trace: pipeline trace dict, or ``None``/``{}`` when the pipeline
            does not emit one yet (Phase 1 baseline).

    Returns:
        Dict ``{steps_count, escalation_path_correct}``. With an empty
        trace both fields are zero/false.
    """
    if not trace:
        return {"steps_count": 0, "escalation_path_correct": False}

    steps = trace.get("steps") or []
    steps_count = len(steps)

    expected_escalation = bool(case.get("expected_escalation"))
    final_escalation = bool(trace.get("final_escalation", trace.get("escalation", False)))
    escalation_path_correct = expected_escalation == final_escalation

    return {
        "steps_count": int(steps_count),
        "escalation_path_correct": bool(escalation_path_correct),
    }
