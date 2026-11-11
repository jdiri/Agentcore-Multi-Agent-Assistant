"""Trusted execution context for backend use only, NOT model-visible agent messages.

Construct this only AFTER platform-side JWT, caller and session checks.
Parsing this model does not verify a JWT. Do not trust user-provided JSON.
"""

from enum import StrEnum

from .base import StrictContract
from .routing import NonBlank


class WorkloadRole(StrEnum):
    COORDINATOR = "coordinator"
    SUPPORT = "support"
    RESEARCH = "research"
    ACTION = "action"


class VerifiedIdentityContext(StrictContract):
    user_id: NonBlank
    cognito_subject: NonBlank
    caller_workload: WorkloadRole
    session_id: NonBlank
