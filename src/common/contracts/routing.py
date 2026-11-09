"""Coordinator <-> specialist contract: routing enum, tasks and reports.

Owner: Dev A. Consumers: Support, Research and Action (roadmap section 3).

`RoutingDecision` is the only model the Coordinator LLM fills in. `SpecialistTask` is built by
code and `SpecialistReport` is returned by each specialist. These models carry no client identity
on purpose: identity comes from the sign-in and travels separately, never through model-visible
fields.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX_HANDOFFS_PER_TURN = 4
MAX_TOOL_ROUNDS = 3
COORDINATOR_MAX_TOKENS = 1024
SPECIALIST_MAX_TOKENS = 2048

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Specialist(StrEnum):
    """The only destinations the Coordinator can route to."""

    SUPPORT = "support"
    RESEARCH = "research"
    ACTION = "action"


class RefusalReason(StrEnum):
    """Why a message was handled by nobody."""

    OFF_TOPIC = "off_topic"
    INVESTMENT_ADVICE = "investment_advice"
    PROMPT_ATTACK = "prompt_attack"
    CROSS_CLIENT = "cross_client"


class ReportStatus(StrEnum):
    """How a specialist's task ended."""

    COMPLETED = "completed"
    NO_INFORMATION = "no_information"  # the documents do not cover the question
    TOOL_FAILED = "tool_failed"  # report the failure; never fill in missing data
    POLICY_DENIED = "policy_denied"  # final; do not retry with different arguments
    UNAVAILABLE = "unavailable"  # e.g. the Action runtime is unreachable
    LIMIT_REACHED = "limit_reached"  # stopped at a tool-round limit; findings may be partial
    AWAITING_APPROVAL = "awaiting_approval"  # the turn ends and the outcome is reported later


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Delegation(_Contract):
    """One piece of work the Coordinator assigns to a specialist."""

    specialist: Specialist
    task: NonBlank
    repeat_justification: NonBlank | None = Field(
        default=None,
        description="Required only when this specialist already appears earlier in the plan.",
    )


class RoutingDecision(_Contract):
    """The Coordinator's plan for a turn: ordered delegations, or a refusal."""

    delegations: tuple[Delegation, ...] = Field(default=(), max_length=MAX_HANDOFFS_PER_TURN)
    refusal: RefusalReason | None = None

    @model_validator(mode="after")
    def _check_plan(self) -> Self:
        if bool(self.delegations) == (self.refusal is not None):
            raise ValueError("provide either delegations or a refusal, not both or neither")

        seen: set[Specialist] = set()
        for delegation in self.delegations:
            if delegation.specialist in seen and delegation.repeat_justification is None:
                raise ValueError(f"repeating {delegation.specialist} requires a justification")
            seen.add(delegation.specialist)
        return self


class Finding(_Contract):
    """One claim from a specialist and where it came from."""

    claim: NonBlank
    source: NonBlank


class SpecialistTask(_Contract):
    """Everything a specialist is told. Built by code from a `Delegation`."""

    task_id: NonBlank
    session_id: NonBlank
    turn_id: NonBlank
    specialist: Specialist
    instruction: NonBlank
    prior_findings: tuple[Finding, ...] = ()


class SpecialistReport(_Contract):
    """What a specialist returns. Every claim in the client's reply must come from one of these."""

    task_id: NonBlank
    specialist: Specialist
    status: ReportStatus
    findings: tuple[Finding, ...] = ()
    detail: NonBlank | None = None
    action_request_id: NonBlank | None = None
    tool_rounds_used: int = Field(default=0, ge=0, le=MAX_TOOL_ROUNDS)

    @model_validator(mode="after")
    def _check_status(self) -> Self:
        if self.status is ReportStatus.COMPLETED:
            if not self.findings:
                raise ValueError("a completed report needs at least one finding")
        elif self.detail is None:
            raise ValueError(f"status {self.status} requires detail")

        if self.status is ReportStatus.AWAITING_APPROVAL and self.action_request_id is None:
            raise ValueError("awaiting_approval requires action_request_id")
        return self
