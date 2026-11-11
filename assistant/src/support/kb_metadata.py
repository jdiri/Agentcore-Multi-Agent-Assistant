"""Read KB document headers into `KBDocument`s and mark superseded versions.

Every corpus file starts with an H1 title and a `Key: value` header block. The block ends at
the first blank line after it starts: policies continue with `## ` sections, FAQs go straight
into bold questions. A version is superseded when another document with the same Document ID says
`Supersedes:` that version. Any header problem stops the load: a document must never be
uploaded without correct metadata.
"""

from pathlib import Path

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


def parse_header(text: str, source: str) -> KBDocument:
    """Parse one file's header. `source` names the file in error messages."""
    title: str | None = None
    fields: dict[str, str] = {}
    in_block = False  # True once the first `Key: value` line is read

    for line in text.splitlines():
        line = line.strip()
        if not line:
            if in_block:
                break  # a blank line after the key block ends the header
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
        in_block = True
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


def sidecar(document: KBDocument) -> dict[str, dict[str, str | bool]]:
    """The `.metadata.json` body for one document.

    Bedrock metadata values must be strings, numbers, booleans or string lists, never null, so
    a missing `supersedes` is left out. `superseded` stays a real boolean: the retrieval filter
    matches `{"equals": {"key": "superseded", "value": false}}`.
    """
    return {"metadataAttributes": document.model_dump(mode="json", exclude_none=True)}
