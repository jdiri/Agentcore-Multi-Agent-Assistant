"""Baseline Action agent and write-tool schemas.

Only code can update persisted state, with conditional writes and audit records.
These models do not themselves enforce authorization or execute any writes.
"""
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from pydantic import Field, model_validator
from .base import StrictContract, ToolResult
from .routing import NonBlank


class ActionState(StrEnum):
    DRAFTED = "DRAFTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class TicketCategory(StrEnum):
    ACCOUNT_ACCESS = "Account Access"
    STATEMENTS = "Statements & Documents"
    TRANSFERS = "Transfers"
    TRANSACTIONS = "Transactions"
    FEES = "Fees"
    PROFILE_CHANGES = "Profile Changes"
    OTHER = "Other"


class DraftEmailInput(StrictContract):
    to_role: Literal["advisor"]  # address resolved server-side, never tool-provided
    subject: NonBlank = Field(max_length=200)
    body: NonBlank = Field(max_length=10000)


class SendApprovedEmailInput(StrictContract):
    request_id: NonBlank


class CreateTicketInput(StrictContract):
    summary: NonBlank = Field(max_length=200)
    description: NonBlank = Field(max_length=10000)
    category: TicketCategory
    # masking must occur in server code before storing/logging this text


class ActionRequestReceipt(StrictContract):
    request_id: NonBlank
    state: ActionState
    # In the normal email draft path, state is PENDING_APPROVAL


class TicketReceipt(StrictContract):
    ticket_number: NonBlank
    category: TicketCategory
    status: Literal["Open"] = "Open"


class AuditActor(StrEnum):
    AGENT = "agent"
    CLIENT = "client"
    APPROVER = "approver"
    SYSTEM = "system"  # e.g. expiry from scheduled backend code


class ActionAuditEntry(StrictContract):
    request_id: NonBlank
    from_state: ActionState | None
    to_state: ActionState
    actor: AuditActor
    occurred_at: datetime
    reason: NonBlank | None = None

    @model_validator(mode="after")
    def aware_timestamp(self) -> Self:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("audit timestamps must carry a UTC offset")
        return self


DraftEmailOutput = ToolResult[ActionRequestReceipt]
SendApprovedEmailOutput = ToolResult[ActionRequestReceipt]
CreateTicketOutput = ToolResult[TicketReceipt]
