# ADR-001 — Eval primitives: task, grader, trajectory, outcome

- **Status**: Accepted
- **Date**: 2026-04-28
- **Deciders**: The Intake team

## Context

The hackathon brief weights *engineering process* as heavily as the final
artifact. Our `CLAUDE.md` working contract codifies an "evals-first"
principle: no production code lands before a measurable scorecard exists.
That commitment is only credible if the eval harness has well-defined
primitives — otherwise every later change debates what to measure rather
than what to build.

We need to fix the vocabulary now, in Phase 1, so that:

1. The Coordinator + specialists added in later phases plug into stable
   grader contracts without retrofitting.
2. Every commit body can cite a metric delta in the same units as the
   previous commit.
3. Adversarial robustness, qualitative response quality, and process
   correctness are tracked as independent signals — none of them is
   subsumed by the others.

Three forces shape the choice:

- **Cheap-but-deterministic floor.** A fast, exact-match grader must run
  on every case in every run; without it, regressions go silent during
  iteration.
- **Qualitative signal we cannot fake with rules.** Rationale quality
  and action appropriateness are real review criteria for a human
  triager, and rule matching cannot see them.
- **Process correctness, not just outcome.** The Coordinator topology
  this project commits to (per ADR-003 in Phase 2) is only useful if we
  can grade *how* the system reached an answer, not only *what* it
  answered.

## Decision

We will adopt four eval primitives — **task**, **grader**, **trajectory**,
**outcome** — and implement a 3-grader stack on top of them:

1. **Task** — a single case in `evals/dataset/cases.json` (or
   `evals/adversarial/cases.json`) with a stable JSON schema:
   `id`, `raw_request`, `expected_category`, `expected_impact`,
   `expected_escalation`, `tags`. The dataset is stratified across the
   five categories with explicit ambiguous and multilingual coverage.
2. **Grader** — a pure function `(case, prediction) -> dict` returning a
   contract-shaped result. We ship three:
   - `rule_based.grade_rule_based` — exact match on category/impact/
     escalation, mean of three booleans as `score`. Runs on every case.
   - `llm_judge.grade_llm_judge` — Claude on Bedrock
     (`us.anthropic.claude-sonnet-4-20250514-v1:0`,
     region `us-east-1`, profile `bootcamp`) returning strict JSON
     `{rationale_quality, action_appropriateness, justification}` on a
     1-5 scale. Runs on a stratified one-per-category sample to keep
     cost predictable.
   - `trajectory.grade_trajectory` — stub today, returns
     `{steps_count, escalation_path_correct}`. Wired in Phase 2 once the
     Coordinator emits a `trace` payload.
3. **Trajectory** — the structured `trace` the Coordinator will emit:
   ordered specialist invocations and their structured outputs. Phase 1
   reserves the contract; Phase 2 fills it in.
4. **Outcome** — the persisted run JSON in `evals/runs/<UTC-stamp>.json`.
   It contains all per-case rows (case + prediction + every grader
   result) so any later analysis can be done offline against the file
   without rerunning Bedrock.

The scorecard CLI (`python -m evals.scorecard [--adversarial]`) is the
single entry point. Exit code is always 0 — this is reporting, not CI
gating; CI gating is a separate decision that only makes sense once the
real pipeline replaces the stub.

## Consequences

**Easier:**

- Every behavior change has an unambiguous "before/after" pair of
  numbers in the same units, satisfying the commit-body requirement in
  `CONTRIBUTING.md`.
- The three graders fail independently: a rule-based regression and a
  judge-quality regression surface separately, instead of being averaged
  away into a single number.
- Phase 2 can land the Coordinator without changing grader signatures —
  only the trajectory grader's body needs to start consuming the trace
  it receives.
- Cost is bounded: even if the dataset triples, the LLM judge fans out
  to one call per category per run.

**Harder:**

- The judge introduces a Bedrock dependency on every full run. Mitigated
  by the `skipped: True` fallback path in `llm_judge.py` so a missing
  `boto3` or auth failure never crashes the scorecard.
- Three graders means three places to keep schema-aligned with the
  Coordinator's prediction contract once it lands. Followed up by an
  ADR pinning the `Prediction` Pydantic model in Phase 2.
- The `trajectory` grader is a known stub right now; we accept the small
  amount of dead-shape code in exchange for a stable contract surface.

**Follow-ups:**

- ADR-003 (Phase 2): Coordinator topology + Pydantic `Prediction` /
  `Trace` contracts.
- ADR-004 (Phase 4): pin a CI gate against a concrete dataset/adversarial
  threshold once the v1 numbers are known.

## Alternatives Considered

- **Single rule-based grader, no LLM judge.** Rejected: rationale
  quality is a top-three reason a real triager would override the
  system, and it is invisible to exact match. The hackathon submission
  also benefits from showing a multi-grader stack as part of the process
  story.
- **Single LLM judge, no rule-based floor.** Rejected: every
  iteration would need a Bedrock round-trip just to know whether
  category/impact regressed, which is both slow and noisy. Determinism
  on the cheap part of the stack is non-negotiable.
- **Pytest-only assertions on a fixture set.** Rejected: gives binary
  pass/fail per case but loses the per-category accuracy table that the
  commit-body delta requires, and offers no path for qualitative
  scoring. Pytest will still cover unit-level invariants on graders
  themselves, but is not the scorecard.
- **External eval framework (e.g., DeepEval / OpenAI evals harness).**
  Rejected for the hackathon: the integration cost competes with the
  agent work itself, and the tooling adds opaque dependencies that
  contradict the "no MCP, native tools only" stance in `CLAUDE.md`.
