# The Intake — agentic IT Helpdesk triage

![status](https://img.shields.io/badge/status-v0%20skeleton-lightgrey)

Anthropic Hackathon — Scenario 5 entry. Built on the Claude Agent SDK and
AWS Bedrock. This README is a v0 skeleton; sections are filled in as each
phase lands.

## Problem

IT Helpdesk teams drown in unstructured intake. Tickets arrive miscategorized,
under-prioritized, or missing context, and humans triage them inconsistently.
This project asks whether an agentic system can produce reliable, auditable
triage decisions.

## Solution

A coordinator agent dispatches each request to specialist sub-agents
(classifier, risk assessor, action planner). Decisions are graded against an
eval scorecard before any prompt is shipped. See `CLAUDE.md` for the working
contract and `docs/adr/` for the binding architectural decisions.

## Architecture

`<mermaid diagram lands in Phase 2 alongside ADR-003>`

## Domain & Taxonomy

- Categories: `password_reset`, `hardware_issue`, `software_bug`,
  `access_request`, `security_incident`.
- Impact: `low`, `medium`, `high`, `critical`.
- Escalation: `security_incident` OR `confidence < 0.6` OR `impact in {high, critical}`.

## Evals

`<scorecard table lands in Phase 1 once the dataset is seeded>`

Run locally: `python -m evals.scorecard`.

## ADR Index

See [`docs/adr/README.md`](docs/adr/README.md) for the running list of
architectural decisions.

## Quickstart

```
pip install -e .
python -m evals.scorecard
```

## Demo Scenarios

`<3 canonical demo flows land alongside the Phase 3 implementation>`

## Roadmap

Phase 0 bootstrap → Phase 1 evals → Phase 2 architecture → Phase 3
implementation → Phase 4 hardening → submission. Tags track each milestone.

## Acknowledgements

Anthropic Claude Agent SDK, Claude Code, AWS Bedrock.
