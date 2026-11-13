"""Search the Bedrock Knowledge Base for Support (D6: called directly, not through the Gateway).

Every search applies `CURRENT_ONLY_FILTER`, so superseded versions are never returned; a result
that is superseded anyway is treated as an error, not dropped silently. The question text is
never logged: only the result count and top score.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from common.contracts.support import KBCitation, KBDocument

from .kb_metadata import CURRENT_ONLY_FILTER, document_from_sidecar

log = logging.getLogger(__name__)

CHUNK_ID_KEY = "x-amz-bedrock-kb-chunk-id"
# Our KB is a Bedrock *managed* knowledge base, which rejects `vectorSearchConfiguration`.
# The managed form takes the same `filter` and `numberOfResults`.
SEARCH_CONFIGURATION = "managedSearchConfiguration"
DEFAULT_TOP_K = 5
MAX_TOP_K = 20


class RetrievalError(ValueError):
    """A retrieval result is unusable: missing metadata, chunk ID or score, or superseded."""


class RetrieveClient(Protocol):
    """The one boto3 `bedrock-agent-runtime` call this module uses."""

    def retrieve(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class RetrievedChunk:
    """One search result, with everything needed to cite it."""

    text: str
    document: KBDocument
    section: str | None
    chunk_id: str
    score: float

    def citation(self, subsection: str | None = None) -> KBCitation:
        """Cite this chunk; optionally narrow `4` to `4.1` when 4.1 is in this chunk's text.

        The subsection must belong to this chunk's section and a paragraph must start with it,
        so a model can suggest `4.1` but code decides whether the citation may say so.
        """
        section = self.section
        if subsection is not None:
            if self.section is None or not subsection.startswith(f"{self.section}."):
                raise ValueError(f"{subsection} is not inside section {self.section}")
            if not re.search(rf"^{re.escape(subsection)} ", self.text, re.MULTILINE):
                raise ValueError(f"section {subsection} is not in the retrieved text")
            section = subsection
        return KBCitation.from_document(
            self.document, chunk_id=self.chunk_id, score=self.score, section=section
        )


def knowledge_base_id() -> str:
    """The KB ID from `P3_KB_ID`. An ID, never an ARN."""
    kb_id = os.environ.get("P3_KB_ID", "").strip()
    if not kb_id:
        raise RuntimeError("P3_KB_ID is not set")
    return kb_id


def _parse(result: dict[str, Any]) -> RetrievedChunk:
    metadata = result.get("metadata") or {}
    try:
        document = document_from_sidecar(metadata)
    except ValueError as exc:  # includes pydantic's ValidationError
        raise RetrievalError(f"result has bad document metadata: {exc}") from exc
    if document.superseded:
        raise RetrievalError(
            f"superseded {document.document_id} v{document.version} passed the current-only filter"
        )
    # Managed KBs may omit the chunk-id metadata key; each of our files is exactly one chunk,
    # so the result's documentId identifies the chunk just as well.
    chunk_id = metadata.get(CHUNK_ID_KEY) or result.get("documentId")
    if not chunk_id:
        raise RetrievalError(f"result has no {CHUNK_ID_KEY} or documentId")
    score = result.get("score")
    if score is None:
        raise RetrievalError("result has no score")
    return RetrievedChunk(
        text=(result.get("content") or {}).get("text", ""),
        document=document,
        section=metadata.get("section"),
        chunk_id=str(chunk_id),
        score=float(score),
    )


def retrieve(
    client: RetrieveClient,
    knowledge_base_id: str,
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """Return up to `top_k` current chunks for `question`, highest score first."""
    if not question.strip():
        raise ValueError("question is blank")
    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")

    response = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": question},
        retrievalConfiguration={
            SEARCH_CONFIGURATION: {
                "numberOfResults": top_k,
                "filter": CURRENT_ONLY_FILTER,
            }
        },
    )
    chunks = sorted(
        (_parse(result) for result in response.get("retrievalResults", [])),
        key=lambda chunk: chunk.score,
        reverse=True,
    )
    log.info(
        "kb retrieve: %d results, top score %s",
        len(chunks),
        f"{chunks[0].score:.3f}" if chunks else "none",
    )
    return chunks
