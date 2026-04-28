# Contributing to *intake-agentic-triage*

This repository is the entry for **Anthropic Hackathon — Scenario 5 "The Intake"**.
It will be evaluated on the **process** as much as on the result, so the conventions
below are not optional cosmetics: they are the contract between the codebase, the
commit history, and the human reading them.

## Working principles

1. **Evals-first.** No production code is added before the task is defined and a
   measurable scorecard exists. Every meaningful change should reference the
   metric it impacts.
2. **Living documentation.** `README.md`, `CLAUDE.md`, and `docs/adr/` are
   updated in the same commit as the code they describe. There is no
   "end-of-project documentation pass".
3. **Claude Code as a multiplier.** Anything we do more than once becomes a
   slash command (`.claude/commands/`), a subagent (`.claude/agents/`), or a
   skill (`.claude/skills/`). The asset library is itself part of the
   submission.
4. **English everywhere.** All commits, code, comments, prompts, ADRs, and
   docs are written in English.

## Commit conventions — Conventional Commits

Every commit follows this shape:

    <type>(<optional scope>): <imperative subject, lowercase, no trailing period>

    <body explaining WHAT changed, WHY, and — from Phase 1 onward — which eval
    metric was impacted, with numbers when available.>

### Allowed types

| Type       | Use for                                                              |
|------------|----------------------------------------------------------------------|
| `feat`     | New user-visible capability (new agent, new tool, new command).      |
| `fix`      | Bug fix in existing behavior.                                        |
| `chore`    | Tooling, config, repo setup, dependencies — no behavior change.      |
| `docs`     | Documentation-only change (README, ADR, CLAUDE.md, comments).        |
| `test`     | Adding or modifying tests / eval cases / graders.                    |
| `refactor` | Code restructure with no behavior change and no new feature.         |
| `perf`     | Performance improvement with no behavior change.                     |
| `eval`     | Eval-related changes: dataset, scorecard, graders, adversarial set.  |

### Scope (optional but encouraged)

Use the top-level area as scope: `agents`, `tools`, `hooks`, `evals`, `docs`,
`claude` (for `.claude/` assets), `bedrock`, `adr`.

### Examples

    feat(agents): add classifier specialist with structured context contract

    Implements the Classifier specialist following ADR-003. Receives the raw
    intake payload, returns category + confidence + rationale per the Pydantic
    contract in agents/contracts.py. Coordinator now routes through it before
    RiskAssessor.

    Eval impact: category accuracy 0.42 -> 0.71 on the stratified dev set
    (see evals/runs/2025-XX-XX-classifier-v1.json).

----

    eval(adversarial): add 12 prompt-injection cases to adversarial set

    Targets the Classifier and ActionPlanner with payloads that try to
    override category, exfiltrate the system prompt, or coerce a non-escalation
    on a clearly high-impact request.

    Coverage delta: adversarial set 18 -> 30 cases, all currently failing on
    the v1 pipeline. Tracked in docs/adr/006-safety-hooks.md as the motivation
    for the PreToolUse policy.

----

    docs(adr): record decision on coordinator + 3 specialists topology

    ADR-003 fixes the topology used from this commit forward:
    Coordinator -> {Classifier, RiskAssessor, ActionPlanner}, with explicit
    Pydantic context contracts. Alternatives considered: single-agent,
    five-specialist mesh. See ADR for trade-offs.

## Branching

For the hackathon timebox we work directly on `main`. The history must read
linearly. If a change is risky (e.g. refactor of the coordinator), use a
short-lived branch `wip/<topic>` and merge with `--no-ff` to keep the merge
visible in the log.

## Tags

Each phase ends with an annotated tag, used as evidence in the final
submission narrative:

| Tag                | Meaning                                                  |
|--------------------|----------------------------------------------------------|
| `v0-init`          | Empty repo initialized.                                  |
| `v0-bootstrap`     | Phase 0 complete — production-shaped layout exists.      |
| `v1-evals`         | Phase 1 complete — task defined, scorecard runnable.     |
| `v2-architecture`  | Phase 2 complete — ADRs, contracts, dummy pipeline OK.   |
| `v3-implementation`| Phase 3 complete — agents above target metrics.          |
| `v4-hardening`     | Phase 4 complete — adversarial set passes.               |
| `v1.0-submission`  | Final submission.                                        |

Tag with:

    git tag -a <tag> -m "<short description of what this milestone proves>"
    git push origin <tag>

## Worklog

`docs/worklog.md` is an append-only log. At the end of each working session
add a short entry: what was done, which Claude Code asset was used or
created, what was learned. The git log shows the *what*; the worklog shows
the *how*.
