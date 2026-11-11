"""Support-specific evidence contract; uses the existing SpecialistReport as the handoff.

No separate SupportTask/SupportReport wire type: Coordinator's routing.py remains canonical.
Citation fields are derived from retrieved KB metadata; never invented by the model.
"""
from typing import Literal
from pydantic import Field
from .base import StrictContract
from .routing import Finding, NonBlank


class KBCitation(StrictContract):
    document_title: NonBlank
    version: NonBlank  # e.g. 3.2 for policies, 2026-01 for dated FAQs
    section: NonBlank | None = None
    document_type: Literal["policy", "faq"]

    def as_source(self) -> str:
        if self.document_type == "policy":
            head = f"{self.document_title} v{self.version}"
        else:
            head = f"{self.document_title}, {self.version}"
        return f"{head}, s.{self.section}" if self.section else head


class CitedClaim(StrictContract):
    claim: NonBlank
    citation: KBCitation

    def as_finding(self) -> Finding:
        return Finding(claim=self.claim, source=self.citation.as_source())


SUPPORT_GAP_REPLY = (
    "I don't have that information in my documents. "
    "Would you like me to open a ticket?"
)
