# ADR-002 — Domain selection: IT Helpdesk triage

- **Status**: Accepted
- **Date**: 2026-04-28
- **Deciders**: The Intake team

## Context

Anthropic Hackathon Scenario 5 — "The Intake" — asks for an agentic
system that triages an unstructured user request into a structured
decision. The brief leaves the *domain* open. The domain choice has
outsized leverage on the final submission because it determines:

- Whether the eval scorecard can show meaningful, defensible deltas
  (taxonomies that are too crisp give no headroom; taxonomies that are
  too fuzzy never converge).
- Whether tool-use credibly extends the agent (a domain with no real
  side effects collapses to a classifier demo).
- Whether adversarial testing has natural targets (categories must be
  worth attacking — e.g. a security route that an attacker would try to
  bypass).
- Whether the safety story is real (PreToolUse hooks need *something*
  to gate).

Three domains were live candidates: IT Helpdesk triage, customer-support
triage for an e-commerce site, and clinical pre-screening intake. The
team chose IT Helpdesk before any code was written; this ADR records why
so the choice doesn't get re-litigated mid-implementation.

## Decision

We will fix the domain to **IT Helpdesk triage** with the following
binding taxonomy:

- **Categories** (5):
  `password_reset`, `hardware_issue`, `software_bug`,
  `access_request`, `security_incident`.
- **Impact** (4):
  `low`, `medium`, `high`, `critical`.
- **Escalation rule**:
  `category == security_incident` **OR**
  `confidence < 0.6` **OR**
  `impact in {high, critical}`.

The taxonomy is the binding contract between the dataset, the graders,
the Coordinator, and the demo scenarios. It does not change for the
duration of the hackathon. Refinements (new categories, threshold
tweaks) must go through a new ADR that supersedes this one in the same
commit as the code change.

The taxonomy is mirrored in `CLAUDE.md` under "Domain spec — IT Helpdesk
triage" and in the README; this ADR is the source of truth those files
reference.

## Consequences

**Easier:**

- Multi-category ambiguity is built in: a phishing report disguised as
  a password reset, or a permission-denied error that could be a
  software bug or an access request, are realistic *and* exercised by
  the Phase 1 dataset (cases 009 and 013). This gives the LLM judge and
  the rule-based grader genuinely different signals on the same case.
- The escalation rule has three independent triggers, so the
  RiskAssessor specialist (Phase 2) has non-trivial logic to encode and
  the trajectory grader has non-trivial paths to verify.
- The domain has credible *write* operations: opening a ticket,
  resetting a password, granting access — all natural targets for a
  PreToolUse hook (Phase 4) that blocks side effects on adversarial
  inputs without any artificial scaffolding.
- The taxonomy is small enough (5×4 = 20 cells) that 15 stratified
  cases meaningfully cover it, keeping the dataset legible in a code
  review.

**Harder:**

- We commit to *not* adding categories like `network_outage` or
  `compliance_request` even when they would be plausible. Some
  borderline cases will be tagged ambiguous rather than getting their
  own bucket. We accept this loss of nuance for taxonomy stability.
- The escalation rule's `confidence < 0.6` clause is a property of the
  pipeline's *prediction*, not of the ground truth. This means the
  rule-based grader can only check the category/impact triggers
  directly; mismatches caused solely by confidence will surface as
  rationale-quality issues for the LLM judge. Acceptable, but worth
  flagging.
- Multilingual coverage in Phase 1 is light (one English+Italian case).
  If multilingual robustness becomes a metric we want to move, that's a
  Phase 4 dataset extension, not a domain change.

**Follow-ups:**

- ADR-003 (Phase 2): Coordinator + 3 specialists topology binds the
  three categories of decision (classify, assess risk, plan action) to
  this taxonomy.
- Phase 4 hardening: the PreToolUse hook policy that blocks credential-
  granting side effects on `security_incident` and on any case where
  the prompt-injection adversarial fingerprint is detected.

## Alternatives Considered

- **Customer-support triage for e-commerce.** Rejected: the natural
  taxonomy (refund / return / shipping / technical / other) has weak
  security stakes, so the adversarial set would feel synthetic and the
  PreToolUse safety story would be about cosmetic guardrails rather
  than real risk.
- **Clinical pre-screening intake.** Rejected for the hackathon
  timebox: medical taxonomies require domain expertise we cannot
  source-check inside the project, and the misclassification risk
  during demos outweighs the upside. The architecture we are building
  could be re-pointed at this domain later, but not now.
- **Generic "free-form ticket" with a learned taxonomy.** Rejected:
  evals-first requires a fixed taxonomy at t=0; a learned taxonomy
  defers measurement. Our entire submission narrative depends on
  showing the eval delta from commit to commit, which a moving target
  would obliterate.
- **Larger taxonomy (8-10 categories).** Rejected: the dataset would
  need to grow proportionally to keep statistical power per category,
  and the labelling-by-hand cost in Phase 1 is real. 5 categories at 3
  cases each is the minimum viable stratification we can justify and
  still review carefully.
