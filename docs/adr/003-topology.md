# ADR-003 — Multi-agent topology: Coordinator + Classifier + RiskAssessor

- **Status**: Accepted
- **Date**: 2026-04-28
- **Deciders**: The Intake team

## Context

Phase 1 left us with a stub pipeline that returned the modal class for
every input (mean score 0.36 against the stratified dataset). Phase 2/3
needed a real implementation that (a) demonstrably beat the floor, (b)
emitted a structured trace the trajectory grader could score, and (c)
fit inside a 30-minute timebox.

The Claude Agent SDK is the project's preferred surface, but its
tool-use loop, response-format hints, and async ergonomics vary across
versions and would have eaten most of the budget. At the same time,
Bedrock's `invoke_model` is well-understood, fully async-friendly via
`asyncio.to_thread`, and lets us treat the LLM as a *structured-output
function* over deterministic tool outputs — which is exactly what the
classifier/risk-assessor pattern needs.

The hackathon judging weighs the engineering process: separation of
concerns, explicit Pydantic contracts between agents, and a trace that
the trajectory grader can read are first-class deliverables, not just
internal niceties.

## Decision

We will run the pipeline as **Coordinator → Classifier → RiskAssessor**
with explicit Pydantic context passing between stages:

- **Coordinator** (`agents/coordinator.py`) — the only public entry
  point. Owns the escalation rule from `CLAUDE.md`
  (`escalate = security_incident OR confidence < 0.6 OR impact in
  {high, critical}`), the recommended-action string, and graceful
  degradation when Bedrock is unavailable.
- **Classifier** (`agents/classifier.py`) — runs three deterministic
  tools (`lookup_known_patterns`, `extract_entities`,
  `check_keyword_signals`), packs their output into the prompt, asks
  Claude on Bedrock for a strict `ClassificationResult` JSON.
- **RiskAssessor** (`agents/risk_assessor.py`) — receives the
  `ClassificationResult` as explicit input, runs three risk tools
  (`assess_business_impact`, `check_security_signals`,
  `lookup_sla_tier`), asks Claude for a `RiskAssessment` JSON.

Tools live in `tools/` and return the `ToolSuccess | ToolError`
envelope from `agents/contracts.py`. Action tools (`create_ticket`,
`notify_oncall`) are mocked and gated by the PreToolUse hook in
`.claude/hooks/pretooluse_writes.py`.

## Consequences

- **Easier**: trace-driven grading (each tool + LLM call is one trace
  step with timing); adding a new tool is a one-file change; swapping
  Bedrock for the SDK later is local to `agents/bedrock_client.py`.
- **Easier**: prompt-injection defense is layered — tool outputs ground
  the classifier's verdict, and the system prompt explicitly instructs
  the model to ignore in-message override attempts.
- **Harder**: two LLM calls per request (classifier + risk_assessor)
  doubles latency vs. a single-agent path. Acceptable for the
  hackathon dataset; would warrant caching or a batch path in
  production.
- **Harder**: trace ordering is now part of the contract — adding
  steps in a different order breaks `grade_trajectory.steps_count`
  expectations.

Follow-ups:

- ADR-004 candidate: lift Bedrock client into the Claude Agent SDK
  once the timebox allows.
- Eval expansion: more multilingual cases; more compound (security +
  hardware) cases.

## Alternatives Considered

- **Single-agent pipeline** — one Claude call producing the entire
  TriageDecision JSON. Rejected: no specialization, no useful
  trajectory grading, harder to defend against prompt injection
  because all reasoning happens in one prompt.
- **Four-plus specialists** (e.g. separate Action-Recommender,
  PromptInjectionDetector, MultilingualNormalizer). Rejected: timebox;
  the marginal gain over two specialists is small for the 15-case
  dataset, and each extra hop is another Bedrock call to audit.
- **Claude Agent SDK with full tool-use loop** — strictly the
  project's stated preference. Rejected for *this* phase: unfamiliar
  ergonomics under the 30-minute budget. Same contract, different
  client; revisit in a follow-up ADR.
