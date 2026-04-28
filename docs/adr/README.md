# Architecture Decision Records

We use the **Nygard format** (Status / Context / Decision / Consequences /
Alternatives Considered). Start every new ADR by copying
[`000-template.md`](000-template.md), giving it the next progressive
number and a short slug, and adding a row to the table below.

The `adr-writer` skill (`.claude/skills/adr-writer/SKILL.md`) automates
this; prefer invoking it over editing by hand.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](001-eval-primitives.md) | Eval primitives: task, grader, trajectory, outcome | Accepted | 2026-04-28 |
| [ADR-002](002-domain-it-helpdesk.md) | Domain selection: IT Helpdesk triage | Accepted | 2026-04-28 |
| [ADR-003](003-topology.md) | Multi-agent topology: Coordinator + Classifier + RiskAssessor | Accepted | 2026-04-28 |

## Status values

- `Proposed` — drafted, not yet adopted.
- `Accepted` — current binding decision.
- `Superseded by ADR-NNN` — replaced; keep file for history.
- `Deprecated` — no longer applies, no replacement.
