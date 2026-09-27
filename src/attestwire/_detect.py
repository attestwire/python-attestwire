"""Sniff a document's bytes to choose the HTTP Content-Type / file suffix.

The hosted API reads a document by its declared Content-Type, not its file
name (https://api.attestwire.com/docs): `application/pdf` for a Factur-X/ZUGFeRD PDF,
`application/xml` or `text/xml` for an XML file, `application/json` for the
JSON `InvoiceInput` model. Callers of this package hand `validate()` raw
bytes or text with no such header attached, so it has to be sniffed the same
way the engine's own CLI sniffs a file by its content rather than trusting an
extension (`src/cli.ts` in github.com/attestwire/en16931's `%PDF` magic-number check).
"""

from __future__ import annotations

_WHITESPACE = b" \t\r\n"
_BOMS = (
    b"\xef\xbb\xbf",  # UTF-8
    b"\xff\xfe",  # UTF-16 LE
    b"\xfe\xff",  # UTF-16 BE
)


def _strip_leading(data: bytes) -> bytes:
    for bom in _BOMS:
        if data.startswith(bom):
            data = data[len(bom) :]
            break
    return data.lstrip(_WHITESPACE)


def sniff_media_type(data: bytes) -> str:
    """`"application/pdf"`, `"application/xml"`, `"application/json"`, or
    `"application/octet-stream"` when none of those is recognisable — the API
    accepts that too, and sniffs the bytes itself from there."""

    stripped = _strip_leading(data)
    if stripped[:4] == b"%PDF":
        return "application/pdf"
    if stripped[:1] == b"<":
        return "application/xml"
    if stripped[:1] in (b"{", b"["):
        return "application/json"
    return "application/octet-stream"


def suffix_for(data: bytes) -> str:
    """The file suffix the local CLI needs to read `data` as the right kind
    of file: it walks a name ending `.xml` or `.pdf` and nothing else
    (`src/cli.ts` in github.com/attestwire/en16931's `expand()`)."""

    return ".pdf" if sniff_media_type(data) == "application/pdf" else ".xml"
