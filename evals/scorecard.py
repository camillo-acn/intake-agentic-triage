"""Eval scorecard entry point.

Phase 1: loads the stratified dataset (and optionally the adversarial
set), runs each case through a stub pipeline, applies the rule-based
grader to every case, applies the LLM judge to one stratified sample
per category, and prints a Rich summary table. The full per-case run is
persisted to ``evals/runs/<UTC-timestamp>.json``.

The pipeline stub is intentionally trivial: it always returns
``password_reset / low / escalate=False``. This gives a real *floor* to
beat once the Coordinator + specialists land in Phase 2/3, and it makes
the eval delta visible in commit messages.

Usage:

    python -m evals.scorecard               # dataset only
    python -m evals.scorecard --adversarial # dataset + adversarial set

Exit code is always 0 — this is reporting, not CI gating.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from agents.contracts import IntakeRequest
from agents.coordinator import triage
from evals.graders.llm_judge import grade_llm_judge
from evals.graders.rule_based import grade_rule_based
from evals.graders.trajectory import grade_trajectory

LOGGER = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "password_reset",
    "hardware_issue",
    "software_bug",
    "access_request",
    "security_incident",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = REPO_ROOT / "evals" / "dataset" / "cases.json"
ADVERSARIAL_PATH = REPO_ROOT / "evals" / "adversarial" / "cases.json"
RUNS_DIR = REPO_ROOT / "evals" / "runs"


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load a JSON array of cases from ``path``. Missing file => empty list."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, list):
        raise ValueError(f"expected JSON array in {path}, got {type(payload).__name__}")
    return payload


async def _run_pipeline_async(case: dict[str, Any]) -> dict[str, Any]:
    """Async pipeline call routed through the real Coordinator."""
    request = IntakeRequest(id=case["id"], raw_request=case["raw_request"])
    decision = await triage(request)
    return {
        "category": decision.category,
        "impact": decision.impact,
        "escalate": decision.escalate,
        "confidence": decision.confidence,
        "rationale": decision.rationale,
        "recommended_action": decision.recommended_action,
        "trace": decision.trace,
    }


def run_pipeline(case: dict[str, Any]) -> dict[str, Any]:
    """Phase 2/3 pipeline: Coordinator + Classifier + RiskAssessor.

    Synchronous wrapper around the async coordinator; each call runs the
    classifier (with three deterministic tools) then the risk assessor
    (three more tools), applies the escalation rule, and returns a
    prediction dict carrying the full ``trace`` for the trajectory
    grader. Bedrock errors are absorbed inside the coordinator and
    surface as a safe-by-escalate verdict so a single throttled call
    cannot drag the whole run down.
    """
    return asyncio.run(_run_pipeline_async(case))


def _stratified_judge_sample(cases: list[dict[str, Any]]) -> list[int]:
    """Pick one case index per category, in dataset order, for LLM judging.

    Keeps the judge cost predictable (one Bedrock call per category) while
    still covering the taxonomy. Indices into the original ``cases`` list
    are returned so the caller can attach judge results in place.
    """
    seen: dict[str, int] = {}
    for idx, case in enumerate(cases):
        cat = case.get("expected_category")
        if cat in CATEGORIES and cat not in seen:
            seen[cat] = idx
    return [seen[c] for c in CATEGORIES if c in seen]


def _render_table(results: list[dict[str, Any]], console: Console, title: str) -> None:
    """Print the per-category accuracy table plus a totals row."""
    by_cat: dict[str, dict[str, float]] = defaultdict(
        lambda: {"n": 0, "cat": 0, "imp": 0, "esc": 0, "score": 0.0}
    )
    for row in results:
        cat = row["case"].get("expected_category", "<unset>")
        bucket = by_cat[cat]
        g = row["grade_rule_based"]
        bucket["n"] += 1
        bucket["cat"] += int(g["category_match"])
        bucket["imp"] += int(g["impact_match"])
        bucket["esc"] += int(g["escalation_match"])
        bucket["score"] += float(g["score"])

    table = Table(title=title)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("N", justify="right")
    table.add_column("Cat Acc", justify="right")
    table.add_column("Impact Acc", justify="right")
    table.add_column("Escalation Acc", justify="right")
    table.add_column("Mean Score", justify="right")

    if not by_cat:
        table.add_row("(no cases)", "0", "-", "-", "-", "-")
        console.print(table)
        return

    total_n = total_cat = total_imp = total_esc = 0
    total_score = 0.0
    for cat in sorted(by_cat):
        s = by_cat[cat]
        n = int(s["n"])
        total_n += n
        total_cat += int(s["cat"])
        total_imp += int(s["imp"])
        total_esc += int(s["esc"])
        total_score += s["score"]
        table.add_row(
            cat,
            str(n),
            f"{s['cat'] / n:.2f}",
            f"{s['imp'] / n:.2f}",
            f"{s['esc'] / n:.2f}",
            f"{s['score'] / n:.2f}",
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        str(total_n),
        f"{total_cat / total_n:.2f}",
        f"{total_imp / total_n:.2f}",
        f"{total_esc / total_n:.2f}",
        f"{total_score / total_n:.2f}",
    )
    console.print(table)


def _save_run(
    *,
    results: list[dict[str, Any]],
    suite: str,
    runs_dir: Path = RUNS_DIR,
) -> Path:
    """Persist the run payload to ``evals/runs/<UTC-timestamp>.json``."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = runs_dir / f"{stamp}.json"
    payload = {
        "generated_at": stamp,
        "suite": suite,
        "n_cases": len(results),
        "results": results,
    }
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return out_path


def evaluate(
    cases: list[dict[str, Any]],
    *,
    judge_indices: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Run pipeline + graders over ``cases``.

    Args:
        cases: list of case dicts.
        judge_indices: subset of indices to also score with the LLM judge.
            ``None`` defaults to a stratified one-per-category sample.

    Returns:
        List of result rows ready to be saved/rendered.
    """
    if judge_indices is None:
        judge_indices = _stratified_judge_sample(cases)
    judge_set = set(judge_indices)

    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        prediction = run_pipeline(case)
        trace_payload = {
            "steps": prediction.get("trace", []),
            "final_escalation": prediction.get("escalate", False),
        }
        row: dict[str, Any] = {
            "case": case,
            "prediction": prediction,
            "grade_rule_based": grade_rule_based(case, prediction),
            "grade_trajectory": grade_trajectory(case, trace=trace_payload),
        }
        if idx in judge_set:
            row["grade_llm_judge"] = grade_llm_judge(case, prediction)
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Intake eval scorecard.")
    parser.add_argument(
        "--adversarial",
        action="store_true",
        help="Also run the adversarial set (evals/adversarial/cases.json).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    console = Console()

    dataset_cases = load_cases(DATASET_PATH)
    console.print(f"[dim]loaded {len(dataset_cases)} dataset cases from {DATASET_PATH.name}[/dim]")
    dataset_results = evaluate(dataset_cases)
    _render_table(dataset_results, console, title="Intake scorecard — dataset")

    all_results: list[dict[str, Any]] = list(dataset_results)
    suite = "dataset"

    if args.adversarial:
        adv_cases = load_cases(ADVERSARIAL_PATH)
        console.print(
            f"[dim]loaded {len(adv_cases)} adversarial cases from {ADVERSARIAL_PATH.name}[/dim]"
        )
        # Adversarial set is small; judge every case.
        adv_results = evaluate(adv_cases, judge_indices=list(range(len(adv_cases))))
        _render_table(adv_results, console, title="Intake scorecard — adversarial")
        all_results.extend(adv_results)
        suite = "dataset+adversarial"

    out_path = _save_run(results=all_results, suite=suite)
    console.print(f"[dim]run saved to {out_path.relative_to(REPO_ROOT)}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
