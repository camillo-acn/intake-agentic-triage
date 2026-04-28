---
description: Run the Intake scorecard against the dataset plus the adversarial set.
---

# /eval-adv

Runs the eval scorecard with the `--adversarial` flag, which appends the
five adversarial cases (`evals/adversarial/cases.json`) — prompt
injection, contradictory signals, category override, social engineering —
to the standard dataset run.

Use this command after any change that touches: agent prompts, tool
permissions, hooks, escalation logic, or anything that could regress
adversarial robustness.

```bash
python -m evals.scorecard --adversarial
```

After it finishes:

1. Report both the dataset totals row and the adversarial totals row
   separately. They should be tracked as distinct metrics in the commit
   body.
2. Quote the `run saved to evals/runs/<timestamp>.json` line.
3. If the adversarial mean score is lower than dataset (it usually is),
   that is expected; only flag a regression if it dropped vs. the
   previous adversarial run.
