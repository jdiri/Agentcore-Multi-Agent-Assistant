"""Support-specific evidence contract; uses the existing SpecialistReport as the handoff.

No separate SupportTask/SupportReport wire type: Coordinator's routing.py remains canonical.
Citation fields are derived from retrieved KB metadata; never invented by the model.
"""

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import Field, model_validator

from .base import StrictContract
from .routing import (
    Finding,
    NonBlank,
    ReportStatus,
    Specialist,
    SpecialistReport,
    SpecialistTask,
)

# e.g. POL-TRF: a type prefix, then three capital letters. Shared by every version of a document.
DocumentId = Annotated[str, Field(pattern=r"^(POL|FAQ|GDE|OVR|NTC)-[A-Z]{3}$")]

# 3.2 (numbered), 2026-01 (year-month) or 2026 (year only).
DocumentVersion = Annotated[str, Field(pattern=r"^(\d+\.\d+|\d{4}-\d{2}|\d{4})$")]


class DocumentType(StrEnum):
    """Kind of KB document, set by the prefix of its Document ID."""

    POLICY = "policy"
    FAQ = "faq"
    GUIDE = "guide"
    OVERVIEW = "overview"
    NOTICE = "notice"


_TYPE_BY_PREFIX = {
    "POL": DocumentType.POLICY,
    "FAQ": DocumentType.FAQ,
    "GDE": DocumentType.GUIDE,
    "OVR": DocumentType.OVERVIEW,
    "NTC": DocumentType.NOTICE,
}


class KBDocument(StrictContract):
    """One version of one KB document, from its header block.

    `document_id` is shared across versions (both transfer policies are POL-TRF), so a document
    is identified by `document_id` plus `version`. `superseded` is set by the loader after
    comparing the whole corpus; no header states it. `document_type` is a stored field so a
    dumped document loads back, but it must always match the `document_id` prefix.
    """

    document_id: DocumentId
    title: NonBlank
    version: DocumentVersion
    supersedes: DocumentVersion | None = None
    owner: NonBlank
    superseded: bool = False
    document_type: DocumentType  # filled from the document_id prefix when not given

    @model_validator(mode="before")
    @classmethod
    def _fill_document_type(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("document_type") is None:
            document_id = data.get("document_id")
            if isinstance(document_id, str) and document_id[:3] in _TYPE_BY_PREFIX:
                data = {**data, "document_type": _TYPE_BY_PREFIX[document_id[:3]]}
        return data

    @model_validator(mode="after")
    def _check_document_type(self) -> Self:
        expected = _TYPE_BY_PREFIX[self.document_id[:3]]
        if self.document_type is not expected:
            raise ValueError(
                f"document_type {self.document_type} does not match {self.document_id}"
                f" (expected {expected})"
            )
        return self


# 4, 4.1 or a range such as 2-3.
SectionNumber = Annotated[str, Field(pattern=r"^\d+(\.\d+)*(-\d+(\.\d+)*)?$")]


class KBCitation(StrictContract):
    """Where one claim came from: a retrieved chunk of a current KB document.

    Build it with `from_document`, from the retrieval result's metadata, never from model text.
    """

    document_id: DocumentId
    document_title: NonBlank
    version: DocumentVersion
    document_type: DocumentType
    section: SectionNumber | None = None
    chunk_id: NonBlank  # the retrieved chunk this claim rests on
    score: float = Field(ge=0)  # retrieval relevance score, kept for the trace

    @model_validator(mode="after")
    def _check_section(self) -> Self:
        if self.document_type is DocumentType.POLICY and self.section is None:
            raise ValueError("a policy citation needs a section")
        if self.document_type is DocumentType.FAQ and self.section is not None:
            raise ValueError("an FAQ citation has no section")
        return self

    @classmethod
    def from_document(
        cls, document: KBDocument, *, chunk_id: str, score: float, section: str | None = None
    ) -> "KBCitation":
        """The only way Support should make a citation. Refuses superseded documents."""
        if document.superseded:
            raise ValueError(f"{document.title} v{document.version} is superseded")
        return cls(
            document_id=document.document_id,
            document_title=document.title,
            version=document.version,
            document_type=document.document_type,
            section=section,
            chunk_id=chunk_id,
            score=score,
        )

    def as_source(self) -> str:
        """The brief's format: `Title v3.2, s.4.1` or `Title, 2026-01`."""
        if "." in self.version:  # numbered, e.g. 3.2
            head = f"{self.document_title} v{self.version}"
        else:  # dated, e.g. 2026-01 or 2026
            head = f"{self.document_title}, {self.version}"
        return f"{head}, s.{self.section}" if self.section else head


class CitedClaim(StrictContract):
    claim: NonBlank
    citation: KBCitation

    def as_finding(self) -> Finding:
        return Finding(claim=self.claim, source=self.citation.as_source())


SUPPORT_GAP_REPLY = (
    "I don't have that information in my documents. Would you like me to open a ticket?"
)


def gap_report(task: SpecialistTask, *, tool_rounds_used: int = 0) -> SpecialistReport:
    """Support's only answer when retrieval is below the relevance threshold.

    No findings, so the Coordinator adds no `Sources:` line and shows `detail` as written.
    Deciding that it is a gap, and logging it, are the caller's job.
    """
    if task.specialist is not Specialist.SUPPORT:
        raise ValueError(f"gap_report is for Support tasks, got {task.specialist}")
    return SpecialistReport(
        task_id=task.task_id,
        specialist=Specialist.SUPPORT,
        status=ReportStatus.NO_INFORMATION,
        detail=SUPPORT_GAP_REPLY,
        tool_rounds_used=tool_rounds_used,
    )
