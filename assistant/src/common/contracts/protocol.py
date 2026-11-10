"""Coordinator/specialist communication boundary (routing.py stays canonical).

A2ARequest/A2AResponse are *application payloads* inside an authenticated A2A
transport. They are NOT replacements for the A2A SDK wire protocol or auth.
"""

from typing import Literal

from pydantic import model_validator

from .base import StrictContract
from .routing import Specialist, SpecialistReport, SpecialistTask


class ProtocolViolation(ValueError):
    pass


def verify_report(task: SpecialistTask, report: SpecialistReport) -> SpecialistReport:
    """Call after every specialist returns, before using findings to compose a reply."""
    if report.task_id != task.task_id:
        raise ProtocolViolation("task_id mismatch")
    if report.specialist != task.specialist:
        raise ProtocolViolation("specialist mismatch")
    return report


class ActionA2ARequest(StrictContract):
    protocol_version: Literal["1.0"] = "1.0"
    task: SpecialistTask

    @model_validator(mode="after")
    def action_only(self):
        if self.task.specialist is not Specialist.ACTION:
            raise ValueError("A2A Action endpoint only accepts Action tasks")
        return self


class ActionA2AResponse(StrictContract):
    protocol_version: Literal["1.0"] = "1.0"
    report: SpecialistReport

    @model_validator(mode="after")
    def action_only(self):
        if self.report.specialist is not Specialist.ACTION:
            raise ValueError("A2A Action endpoint only returns Action reports")
        return self
