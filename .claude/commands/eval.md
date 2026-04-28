---
description: Run the Intake scorecard against the stratified dataset and report the results.
---

# /eval

Runs the eval scorecard against the canonical dataset
(`evals/dataset/cases.json`), prints the Rich summary table, and points at
the saved run JSON under `evals/runs/`.

Use this command whenever you make a change that could move pipeline
behavior (new specialist, tool, prompt change, model swap). Capture the
delta in the commit body as required by `CONTRIBUTING.md`.

```bash
python -m evals.scorecard
```

After it finishes:

1. Read the `Cat Acc / Impact Acc / Escalation Acc / Mean Score` totals
   row and report it back to the user.
2. Quote the `run saved to evals/runs/<timestamp>.json` line so the run
   is traceable.
3. If any per-category accuracy dropped vs. the previous run, flag it
   explicitly and ask whether to investigate before committing.
