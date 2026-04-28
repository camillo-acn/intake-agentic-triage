---
name: adr-writer
description: Author a new Architecture Decision Record using the Nygard template, assign the next progressive number, and update the ADR index in the same operation.
---

# adr-writer

Keeps `docs/adr/` self-consistent: every new ADR uses the Nygard format,
gets the next number, and shows up in the index immediately.

## When to use

- The user says "let's record this decision", "write an ADR for X",
  or accepts a non-trivial architectural choice.
- A binding change has been made (topology, contract shape, escalation
  policy, eval methodology) that is not already an ADR.
- A previous ADR is being superseded — create the new ADR and update the
  old one's Status in the same step.

Do **not** use this skill for stylistic preferences, code conventions
(those go in `CLAUDE.md`), or one-off notes (those go in `docs/worklog.md`).

## Steps

1. **Read the template**: `docs/adr/000-template.md`.
2. **Find the next number**: list `docs/adr/NNN-*.md` files, take the
   highest `NNN`, add 1, zero-pad to 3 digits. If none exist, start at `001`.
3. **Pick the slug**: short, hyphenated, lowercase, ≤5 words
   (e.g. `coordinator-and-three-specialists`).
4. **Create** `docs/adr/<NNN>-<slug>.md` from the template. Set Status
   to `Proposed` (or `Accepted` if the team has already greenlit it),
   Date to today (UTC, `YYYY-MM-DD`), and fill all four sections.
   Alternatives Considered must list at least two rejected options
   with the dominant reason for rejection.
5. **Update the index** in `docs/adr/README.md`: append a row
   `| ADR-<NNN> | <Title> | <Status> | <YYYY-MM-DD> |`.
6. **If superseding** an earlier ADR: edit the old file's Status to
   `Superseded by ADR-<NNN>` and update the index row accordingly.
7. **Stage** all touched ADR files together so the commit is atomic.

## Worked example

Request: "Record the decision to use a coordinator with three specialists."

- Inspect `docs/adr/`: only `000-template.md` and `README.md` exist.
- Next number is `001`. Slug: `coordinator-and-three-specialists`.
- Create `docs/adr/001-coordinator-and-three-specialists.md` with:
  - Status: `Accepted`, Date: `2026-04-28`.
  - Context: orchestration burden of a single mega-prompt; need for
    independently graded specialists; eval scorecard requires per-step
    contracts.
  - Decision: "We will run a Coordinator that dispatches each request to
    three specialists — Classifier, RiskAssessor, ActionPlanner —
    communicating via Pydantic context contracts."
  - Consequences: easier per-specialist evals; more boilerplate;
    follow-up ADR needed on inter-agent context shape.
  - Alternatives Considered: single-agent monolith (rejected: opaque
    eval surface); five-specialist mesh (rejected: combinatorial
    coordination cost without measured benefit).
- Append to `docs/adr/README.md`:
  `| ADR-001 | Coordinator and three specialists | Accepted | 2026-04-28 |`.
- Done. The user gets two file changes ready to commit together.
