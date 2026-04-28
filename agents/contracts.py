"""Pydantic v2 contracts for The Intake.

Every boundary between the user, the coordinator, the specialist agents,
and the tool layer crosses one of these models. Strict ``Literal`` types
mirror the taxonomy frozen in ``CLAUDE.md`` so a typo in a category or
impact level fails at parse time instead of hours later in the eval.

Tool I/O follows the ``ToolSuccess | ToolError`` envelope from the
project's "structured error responses" rule — see ``CLAUDE.md``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "password_reset",
    "hardware_issue",
    "software_bug",
    "access_request",
    "security_incident",
]

Impact = Literal["low", "medium", "high", "critical"]


class IntakeRequest(BaseModel):
    """Inbound helpdesk request handed to the coordinator."""

    model_config = ConfigDict(extra="forbid")

    id: str
    raw_request: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    """Classifier specialist output."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    alternatives: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """Risk-assessor specialist output."""

    model_config = ConfigDict(extra="forbid")

    impact: Impact
    risk_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class TriageDecision(BaseModel):
    """Final decision produced by the coordinator."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    category: Category
    impact: Impact
    confidence: float = Field(ge=0.0, le=1.0)
    escalate: bool
    recommended_action: str
    rationale: str
    trace: list[dict[str, Any]] = Field(default_factory=list)


class ToolError(BaseModel):
    """Failure envelope returned by every tool."""

    model_config = ConfigDict(extra="forbid")

    ok: Literal[False] = False
    error: dict[str, str]


class ToolSuccess(BaseModel):
    """Success envelope returned by every tool."""

    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = True
    data: dict[str, Any]


__all__ = [
    "Category",
    "ClassificationResult",
    "Impact",
    "IntakeRequest",
    "RiskAssessment",
    "ToolError",
    "ToolSuccess",
    "TriageDecision",
]
