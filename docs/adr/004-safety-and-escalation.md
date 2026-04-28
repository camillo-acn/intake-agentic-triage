# ADR-004 — Safety policy: PreToolUse gate + escalation rule

- **Status**: Accepted
- **Date**: 2026-04-28
- **Deciders**: The Intake team

## Context

Phase 2/3 wired up two action tools — `create_ticket` and
`notify_oncall` — as the only paths through which the Coordinator can
mutate the outside world. An LLM that can be prompted to misclassify a
`security_incident` as a `password_reset` (see `evals/adversarial/`)
can also, in principle, be prompted into firing a write tool with the
wrong arguments. The deterministic escalation rule from `CLAUDE.md`
defends the *output* of the pipeline; nothing yet defended its
*side-effects*.

The Anthropic Hackathon judging weighs safety as a first-class
concern, and we needed a defense that (a) lives outside the model's
prompt — so it cannot be talked out of — (b) is auditable per-call,
and (c) does not require a second LLM. The Claude Code hook protocol
is exactly that surface: a `PreToolUse` hook receives the tool name
and arguments, can `block` or `approve`, and the decision is logged.

We also wanted the escalation rule itself recorded in an ADR rather
than only in `CLAUDE.md`, so a future reviewer reading the ADR index
sees the safety story end-to-end.

## Decision

We will run a **two-layer safety policy**:

**Layer 1 — Deterministic escalation rule** (in `agents/coordinator.py`):

```
escalate = category == "security_incident"
       OR  confidence < 0.6
       OR  impact in {"high", "critical"}
```

The Coordinator computes this *after* the Classifier and RiskAssessor
have produced their structured outputs. The rule is pure code, not a
prompt — the LLM cannot override it. A `security_incident` verdict
unconditionally escalates regardless of confidence or impact.

**Layer 2 — PreToolUse hook on action tools**
(`.claude/hooks/pretooluse_writes.py`, registered in
`.claude/settings.json` with matcher `create_ticket|notify_oncall`):

- Non-gated tools: `approve` (logged).
- Gated tools (`create_ticket`, `notify_oncall`): if
  `category == 'security_incident'` AND no explicit
  `human_approved == True` flag is present in the tool input, the
  call is **blocked** with reason `"high-risk write requires human
  approval"`. Otherwise approved.
- Every decision (approve or block) is appended to
  `.claude/logs/pretooluse.log` with a UTC timestamp, the tool name,
  and the reason — giving us a per-run audit trail.

The hook is fail-closed on malformed JSON (returns `block`) and
fail-open on empty stdin (returns `approve`) so it never silently
swallows a legitimate event.

## Consequences

- **Easier**: prompt-injection attempts that flip the classifier
  output (`adv-001`, `adv-002`) still cannot fire a write — the
  escalation rule and the hook are both downstream of the LLM. The
  adversarial scorecard run on 2026-04-28 confirmed this:
  category accuracy 5/5, escalation accuracy 5/5, mean score 0.93;
  the hook replay over the full eval batch blocked 11 high-risk
  writes and approved the routine ones.
- **Easier**: safety is auditable per call. `.claude/logs/pretooluse.log`
  is the single artifact a reviewer reads to answer "did the system
  ever fire a write it should not have?".
- **Easier**: the escalation rule lives in code, so unit tests and
  the trajectory grader can both check it directly.
- **Harder**: the hook only sees the immediate tool call; a multi-step
  attack that primes a non-gated tool first is out of scope. The
  small allowlist (`create_ticket`, `notify_oncall`) keeps that
  surface small but expansion needs a new ADR.
- **Harder**: bypassing the hook requires editing `.claude/settings.json`
  — easy for an authorized engineer, which is the intended ergonomics,
  but it does mean the hook is a *policy* layer not a *cryptographic*
  one. A real production deployment should sign or attest the hook.

Follow-ups:

- Expand the gated tool list once we add real Jira / Slack /
  PagerDuty integrations.
- Add a regression test that replays adversarial cases and asserts
  the hook log shape.
- Once the project moves to the Claude Agent SDK (ADR-003 follow-up),
  re-anchor the hook on the SDK's tool-execution interception point.

## Alternatives Considered

- **Prompt-only safety** — rely on a strong system prompt to refuse
  unsafe writes. Rejected: prompt injection (`adv-001`, `adv-002`)
  shows the model can be argued out of policy, and there is no audit
  log; we already require trace-grading to be deterministic, so
  policy enforcement should be too.
- **Second LLM as safety reviewer** — a third agent that vets every
  tool call. Rejected for this phase: doubles per-request cost and
  latency, adds another prompt to harden, and the rule we need to
  enforce (`security_incident → require human_approved`) is a
  one-line conditional, not a judgement call.
- **Hard-deny all writes** — block `create_ticket` / `notify_oncall`
  unconditionally and surface them as suggestions only. Rejected:
  defeats the autonomous-triage value proposition for the 80% of
  routine cases that should self-serve.
