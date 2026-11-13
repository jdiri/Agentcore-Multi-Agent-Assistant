"""Read KB documents, mark superseded versions and split them into upload-ready chunks.

Every corpus file starts with an H1 title and a `Key: value` header block. The block ends at
the first blank line after it starts: policies continue with `## ` sections, FAQs go straight
into bold questions. A version is superseded when another document with the same Document ID says
`Supersedes:` that version. Any header problem stops the load: a document must never be
uploaded without correct metadata.

Chunking is done here, not by Bedrock (the data source uses no or large fixed-size chunking):
one chunk per numbered `## ` section, one per FAQ question. Each chunk carries its own sidecar,
so `section` comes from the document, never from the model.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from common.contracts.support import KBDocument

# Header key -> KBDocument field. `Effective` is read but not kept; nothing uses it yet.
_FIELDS = {
    "Document ID": "document_id",
    "Version": "version",
    "Supersedes": "supersedes",
    "Owner": "owner",
}
_IGNORED = {"Effective"}


class KBHeaderError(ValueError):
    """A corpus file's header is missing, malformed or conflicts with another file."""


def _split_header(text: str) -> tuple[list[str], list[str]]:
    """(header lines, body lines). The header ends at the first blank line after the key block."""
    lines = text.splitlines()
    in_block = False  # True once a line other than the title is read
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if in_block:
                return lines[:index], lines[index + 1 :]
        elif not stripped.startswith("# "):
            in_block = True
    return lines, []


def parse_header(text: str, source: str) -> KBDocument:
    """Parse one file's header. `source` names the file in error messages."""
    title: str | None = None
    fields: dict[str, str] = {}

    for line in _split_header(text)[0]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("# "):
            if title is not None:
                raise KBHeaderError(f"{source}: more than one title")
            title = line[2:].strip()
            continue
        key, sep, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not sep or (key not in _FIELDS and key not in _IGNORED):
            raise KBHeaderError(f"{source}: unexpected header line {line!r}")
        if key in _IGNORED:
            continue
        if _FIELDS[key] in fields:
            raise KBHeaderError(f"{source}: {key} appears twice")
        fields[_FIELDS[key]] = value

    if title is None:
        raise KBHeaderError(f"{source}: no '# ' title")
    try:
        return KBDocument(title=title, **fields)
    except ValidationError as exc:
        raise KBHeaderError(f"{source}: {exc}") from exc


def mark_superseded(documents: dict[str, KBDocument]) -> dict[str, KBDocument]:
    """Return the same documents with `superseded=True` on every replaced version."""
    seen: dict[tuple[str, str], str] = {}
    for name, document in documents.items():
        key = (document.document_id, document.version)
        if key in seen:
            raise KBHeaderError(f"{seen[key]} and {name} are both {key[0]} v{key[1]}")
        seen[key] = name

    replaced = {
        (document.document_id, document.supersedes)
        for document in documents.values()
        if document.supersedes is not None
    }
    return {
        name: document.model_copy(
            update={"superseded": (document.document_id, document.version) in replaced}
        )
        for name, document in documents.items()
    }


def load_corpus(directory: Path) -> dict[str, KBDocument]:
    """Read every `.md` file in `directory`, keyed by file name, sorted, superseded marked."""
    paths = sorted(directory.glob("*.md"))
    if not paths:
        raise KBHeaderError(f"no .md files in {directory}")
    documents = {
        path.name: parse_header(path.read_text(encoding="utf-8"), path.name) for path in paths
    }
    return mark_superseded(documents)


def sidecar_name(file_name: str) -> str:
    """Bedrock looks for `<document file name>.metadata.json` in the same S3 folder."""
    return f"{file_name}.metadata.json"


# Bedrock KB metadata accepts only strings, numbers and string lists: a boolean `superseded`
# makes the whole sidecar invalid. So the flag is stored as `status`, and retrieval filters on
# {"equals": {"key": "status", "value": "current"}}.
STATUS_CURRENT = "current"
STATUS_SUPERSEDED = "superseded"
CURRENT_ONLY_FILTER = {"equals": {"key": "status", "value": STATUS_CURRENT}}


def sidecar(document: KBDocument) -> dict[str, dict[str, str]]:
    """The `.metadata.json` body for one document: strings only, no nulls."""
    attributes = document.model_dump(mode="json", exclude_none=True, exclude={"superseded"})
    attributes["status"] = STATUS_SUPERSEDED if document.superseded else STATUS_CURRENT
    return {"metadataAttributes": attributes}


def document_from_sidecar(metadata: Mapping[str, Any]) -> KBDocument:
    """Rebuild a `KBDocument` from sidecar attributes, e.g. a Bedrock retrieval result's metadata.

    Bedrock adds its own `x-amz-bedrock-kb-*` keys, and chunks carry `section` and
    `source_file`; those are ignored here. A missing or unknown `status` is an error, never a
    guess: treating an unmarked document as current could let v3.1 through.
    """
    status = metadata.get("status")
    if status not in (STATUS_CURRENT, STATUS_SUPERSEDED):
        raise ValueError(f"metadata has no valid status (got {status!r})")
    fields = {key: metadata[key] for key in KBDocument.model_fields if key in metadata}
    return KBDocument(**fields, superseded=status == STATUS_SUPERSEDED)


# Well under Titan Text Embeddings V2's ~8k-token input; the largest real chunk is far smaller.
MAX_CHUNK_CHARS = 6000

_SECTION_HEADING = re.compile(r"^## (\d+)\. (.+)$")
_QUESTION = re.compile(r"^\*\*(.+)\*\*$")
# Unnumbered sections left out of the KB. The transfer policy's revision history lists the old
# v3.1 figures and has no section number, so it could never be cited anyway.
_SKIPPED_HEADINGS = {"## Revision history"}


@dataclass(frozen=True)
class KBChunk:
    """One upload-ready piece of a document: a numbered section or one FAQ question."""

    name: str  # file name in S3, e.g. account-transfer-policy-v3.2__s4.md
    source_file: str
    document: KBDocument
    section: str | None  # None for FAQ questions
    text: str


def _label(document: KBDocument) -> str:
    """`Title v3.2` for numbered versions, `Title, 2026-01` for dated ones (as in citations)."""
    if "." in document.version:
        return f"{document.title} v{document.version}"
    return f"{document.title}, {document.version}"


def _groups(lines: list[str], source: str, faq: bool) -> list[tuple[str, str | None, list[str]]]:
    """Split body lines into (heading, section, content lines) at each section or question."""
    groups: list[tuple[str, str | None, list[str]]] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if faq:
                raise KBHeaderError(f"{source}: unexpected section heading {stripped!r} in an FAQ")
            skipping = stripped in _SKIPPED_HEADINGS
            if skipping:
                continue
            match = _SECTION_HEADING.match(stripped)
            if match is None:
                raise KBHeaderError(f"{source}: unnumbered section heading {stripped!r}")
            groups.append((stripped[3:], match.group(1), []))
        elif faq and (match := _QUESTION.match(stripped)):
            groups.append((match.group(1), None, []))
        elif skipping:
            continue
        elif not groups:
            if stripped:
                raise KBHeaderError(f"{source}: text before the first section: {stripped[:40]!r}")
        else:
            groups[-1][2].append(line)
    return groups


def split_document(source_file: str, text: str, document: KBDocument) -> list[KBChunk]:
    """Split one document into chunks. Any structural surprise stops with the file name."""
    faq = document.document_type == "faq"
    groups = _groups(_split_header(text)[1], source_file, faq)
    if not groups:
        raise KBHeaderError(f"{source_file}: no sections or questions found")

    stem = source_file.removesuffix(".md")
    chunks: list[KBChunk] = []
    seen: set[str] = set()
    for number, (heading, section, content) in enumerate(groups, start=1):
        body = "\n".join(content).strip()
        if not body:
            raise KBHeaderError(f"{source_file}: {heading!r} has no text")
        if section is not None:
            if section in seen:
                raise KBHeaderError(f"{source_file}: section {section} appears twice")
            seen.add(section)
        chunk_text = f"{_label(document)} — {heading}\n\n{body}\n"
        if len(chunk_text) > MAX_CHUNK_CHARS:
            raise KBHeaderError(
                f"{source_file}: {heading!r} is {len(chunk_text)} characters,"
                f" over the {MAX_CHUNK_CHARS} limit"
            )
        suffix = f"s{section}" if section is not None else f"q{number:02d}"
        chunks.append(
            KBChunk(
                name=f"{stem}__{suffix}.md",
                source_file=source_file,
                document=document,
                section=section,
                text=chunk_text,
            )
        )
    return chunks


def split_corpus(directory: Path) -> list[KBChunk]:
    """Load, mark superseded and split every document in `directory`."""
    chunks: list[KBChunk] = []
    for name, document in load_corpus(directory).items():
        text = (directory / name).read_text(encoding="utf-8")
        chunks.extend(split_document(name, text, document))
    return chunks


def chunk_sidecar(chunk: KBChunk) -> dict[str, dict[str, str]]:
    """The document's sidecar plus `source_file`, and `section` when the chunk has one."""
    attributes = {**sidecar(chunk.document)["metadataAttributes"], "source_file": chunk.source_file}
    if chunk.section is not None:
        attributes["section"] = chunk.section
    return {"metadataAttributes": attributes}
