"""Eval scorecard entry point.

Phase 0 stub: loads JSON cases from ``evals/dataset/``, runs them through a
placeholder pipeline, applies a rule-based grader (exact match on category
and impact), prints a Rich summary table, and persists the run as JSON in
``evals/runs/``.

The pipeline stub is intentionally trivial: Phase 2 wires in the real
Coordinator. The shape of the run output is the contract the grader and
later analyses will rely on, so it is stable from this commit forward.

Invoke either of:

    python -m evals.scorecard
    python evals/scorecard.py
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

CATEGORIES: tuple[str, ...] = (
    "password_reset",
    "hardware_issue",
    "software_bug",
    "access_request",
    "security_incident",
)
IMPACTS: tuple[str, ...] = ("low", "medium", "high", "critical")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "evals" / "dataset"
RUNS_DIR = REPO_ROOT / "evals" / "runs"


def load_cases(dataset_dir: Path = DATASET_DIR) -> list[dict[str, Any]]:
    """Load every ``*.json`` case file under ``dataset_dir``.

    Empty or missing directory yields zero cases without raising.
    """
    if not dataset_dir.exists():
        return []
    cases: list[dict[str, Any]] = []
    for path in sorted(dataset_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path}: {exc}") from exc
        if isinstance(payload, list):
            cases.extend(payload)
        elif isinstance(payload, dict):
            cases.append(payload)
        else:
            raise ValueError(f"unexpected JSON root in {path}: {type(payload).__name__}")
    return cases


def run_pipeline(case: dict[str, Any]) -> dict[str, Any]:
    """Phase 0 placeholder pipeline.

    Returns a deterministic-ish prediction seeded by the case id, so re-runs
    are reproducible across invocations. Replaced wholesale in Phase 2 by
    the real Coordinator.
    """
    seed = str(case.get("id", "")) or json.dumps(case, sort_keys=True)
    rng = random.Random(seed)
    return {
        "category": rng.choice(CATEGORIES),
        "impact": rng.choice(IMPACTS),
        "confidence": round(rng.uniform(0.3, 0.95), 2),
    }


def grade(case: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    """Rule-based grader: exact match on category and impact."""
    category_ok = prediction.get("category") == case.get("expected_category")
    impact_ok = prediction.get("impact") == case.get("expected_impact")
    return {
        "category_correct": bool(category_ok),
        "impact_correct": bool(impact_ok),
        "both_correct": bool(category_ok and impact_ok),
    }


def render_table(results: list[dict[str, Any]], console: Console) -> None:
    """Print per-category counts and accuracy."""
    by_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "cat_ok": 0, "imp_ok": 0})
    for row in results:
        bucket = by_cat[row["case"].get("expected_category", "<unset>")]
        bucket["n"] += 1
        bucket["cat_ok"] += int(row["grade"]["category_correct"])
        bucket["imp_ok"] += int(row["grade"]["impact_correct"])

    table = Table(title="Intake scorecard")
    table.add_column("Category", style="cyan")
    table.add_column("N", justify="right")
    table.add_column("Category acc.", justify="right")
    table.add_column("Impact acc.", justify="right")

    if not by_cat:
        table.add_row("(no cases)", "0", "-", "-")
    else:
        for cat in sorted(by_cat):
            stats = by_cat[cat]
            n = stats["n"]
            cat_acc = f"{stats['cat_ok'] / n:.2f}" if n else "-"
            imp_acc = f"{stats['imp_ok'] / n:.2f}" if n else "-"
            table.add_row(cat, str(n), cat_acc, imp_acc)

    console.print(table)


def save_run(results: list[dict[str, Any]], runs_dir: Path = RUNS_DIR) -> Path:
    """Persist the full run as ``evals/runs/<UTC-timestamp>.json``."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = runs_dir / f"{stamp}.json"
    payload = {
        "generated_at": stamp,
        "n_cases": len(results),
        "results": results,
    }
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return out_path


def main() -> int:
    console = Console()
    cases = load_cases()
    results: list[dict[str, Any]] = []
    for case in cases:
        prediction = run_pipeline(case)
        results.append({"case": case, "prediction": prediction, "grade": grade(case, prediction)})

    render_table(results, console)
    out_path = save_run(results)
    console.print(f"[dim]run saved to {out_path.relative_to(REPO_ROOT)}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
