# CLAUDE.md — Working contract for Claude Code sessions

This file is the durable handshake between this repository and any future
Claude Code session. Read it first, follow it, and update it in the same
commit as any change that invalidates it.

## Project context

We are building **The Intake**, an agentic triage system for **IT Helpdesk**
requests, submitted to the **Anthropic Hackathon — Scenario 5**. The system
is built with the **Claude Agent SDK** and runs Claude on **AWS Bedrock**.
The submission is judged on the engineering process as much as on the
final result, so the asset library under `.claude/` and the eval scorecard
are first-class deliverables.

## Working principles

1. **Evals-first** — no production code lands before a measurable scorecard
   exists. Every behavior change re-runs `evals/scorecard.py` and reports
   the delta in the commit body.
2. **Living documentation** — `README.md`, this file, and `docs/adr/` are
   updated in the same commit as the code they describe.
3. **Claude Code as a multiplier** — anything done twice becomes a slash
   command, subagent, or skill under `.claude/`.
4. **English everywhere** — all commits, code, comments, prompts, ADRs,
   docs, and eval cases are in English. Mirrors `CONTRIBUTING.md`.

## Domain spec — IT Helpdesk triage

- **Categories**: `password_reset`, `hardware_issue`, `software_bug`,
  `access_request`, `security_incident`.
- **Impact levels**: `low`, `medium`, `high`, `critical`.
- **Escalation rule**: escalate if
  `category == security_incident` **or** `confidence < 0.6` **or**
  `impact in {high, critical}`.

This taxonomy is fixed for the hackathon. Do not propose alternatives;
propose refinements via an ADR if needed.

## Bedrock config

- **Model id**: `us.anthropic.claude-sonnet-4-20250514-v1:0`
- **Region**: `us-east-1`
- **AWS profile**: `bootcamp`

Minimal Python invocation pattern:

```python
import boto3, json

session = boto3.Session(profile_name="bootcamp", region_name="us-east-1")
bedrock = session.client("bedrock-runtime")

resp = bedrock.invoke_model(
    modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "ping"}],
    }),
)
print(json.loads(resp["body"].read()))
```

For agent-style usage prefer the `anthropic[bedrock]` client or the
`claude-agent-sdk`, both wired to the same profile/region.

## Code conventions

- **Python 3.14** (the project supports `>=3.12`, but new code targets 3.14).
- **Pydantic v2** models for every agent input/output, every tool input/output,
  and every inter-agent context contract. No untyped dicts on boundaries.
- **Structured error responses**, shape:
  `{"ok": false, "error": {"code": "...", "message": "...", "retry_hint": "..."}}`.
  Successful responses use `{"ok": true, "data": ...}`.
- **No bare `except`** — catch specific exception classes; re-raise with
  context if you cannot handle them.
- **Type hints everywhere**, including private helpers and test fixtures.

## Definition of Done

A change is not done until **all** of the following are true:

1. Code is updated.
2. Documentation impacted by the change (`README.md`, `CLAUDE.md`,
   relevant ADR) is updated **in the same commit**.
3. If behavior changed, `evals/scorecard.py` was re-run and the
   resulting JSON is referenced.
4. The commit message follows Conventional Commits (see
   `CONTRIBUTING.md`) and the body states the eval delta with numbers.

## No MCP

Enterprise policy forbids MCP servers. Do not add MCP configuration.
Use Python scripts and the native Claude Code tools (`Bash`, `Read`,
`Write`, `Edit`, `Grep`, `Glob`, `WebFetch`) plus the Claude Agent SDK
to integrate external systems.

## Asset library policy

If a workflow is performed twice, lift it into `.claude/`:

- Repeated multi-step actions → `.claude/commands/<name>.md`.
- Repeated specialist reasoning tasks → `.claude/agents/<name>.md`.
- Repeated procedures with structured outputs → `.claude/skills/<name>/SKILL.md`.
- Repeated automated reactions to events → hook in `.claude/settings.json`.

The asset library is part of the submission narrative.

## Pointers

- Process and commit conventions: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Architecture decisions: [`docs/adr/`](docs/adr/)
- Eval scorecard: [`evals/scorecard.py`](evals/scorecard.py)
- Top-level overview: [`README.md`](README.md)
- Working log: [`docs/worklog.md`](docs/worklog.md)
