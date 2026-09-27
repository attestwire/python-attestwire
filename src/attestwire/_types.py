"""Typed results shared by both `mode="api"` and `mode="cli"`.

Both backends produce the same shape: the hosted API's `ValidationResult`
JSON envelope (`errors` / `warnings` / `information`, each a `TeachingError`
with `rule`, `field`, `severity`, `message`, `fix`, `xpath`, `docsUrl`,
`example`, `location`) and the local CLI's `--json` output (the same
`TeachingError` shape, one file's worth, under `results[0].findings`) are
just two different envelopes around identical findings. This module is the
one place that shape is spelled out.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Literal, Optional, Sequence

Severity = Literal["fatal", "warning", "information"]


@dataclasses.dataclass(frozen=True)
class Location:
    """Where a finding's element is in the document you sent.

    Only present on a finding for an actual document (XML or PDF bytes) — a
    finding about the document as a whole (``rule`` starting ``AW-``) has no
    location, because it is not about one element.
    """

    line: Optional[int] = None
    column: Optional[int] = None
    path: Optional[str] = None
    exact: Optional[bool] = None
    #: Only set when the document was a Factur-X/ZUGFeRD PDF: the name of the
    #: attachment the XML came from (``factur-x.xml``, ...). ``line``/``column``
    #: are then positions in that attachment, not in the PDF.
    attachment: Optional[str] = None

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional["Location"]:
        if not data:
            return None
        return cls(
            line=data.get("line"),
            column=data.get("column"),
            path=data.get("path"),
            exact=data.get("exact"),
            attachment=data.get("attachment"),
        )


@dataclasses.dataclass(frozen=True)
class Finding:
    """One rule finding: the rule id, what's wrong, the fix, and where.

    ``rule``, ``severity``, ``message`` and ``fix`` are the four fields every
    caller wants first; ``field``, ``xpath``, ``docs_url``, ``example`` and
    ``location`` carry the rest of what the engine reports, when present.
    """

    rule: Optional[str]
    severity: Optional[Severity]
    message: Optional[str]
    fix: Optional[str] = None
    #: The business term(s) the rule constrains, e.g. "BT-10" or ["BT-31", "BT-32"].
    field: Optional[Any] = None
    xpath: Optional[str] = None
    docs_url: Optional[str] = None
    example: Optional[str] = None
    location: Optional[Location] = None

    @classmethod
    def from_json(cls, data: dict) -> "Finding":
        return cls(
            rule=data.get("rule"),
            severity=data.get("severity"),
            message=data.get("message"),
            fix=data.get("fix"),
            field=data.get("field"),
            xpath=data.get("xpath"),
            docs_url=data.get("docsUrl"),
            example=data.get("example"),
            location=Location.from_json(data.get("location")),
        )


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    """The result of validating one document, from either backend.

    ``findings`` is every finding — fatal, warning and information — in that
    order, each carrying its own ``severity``; filter it yourself, or use the
    ``errors`` / ``warnings`` / ``information`` properties below. ``valid`` is
    true exactly when there is no ``severity == "fatal"`` finding, matching
    the hosted API's own ``valid`` field and the CLI's per-file ``passed``.
    """

    valid: bool
    findings: Sequence[Finding]
    #: Which mode produced this: "api" or "cli".
    mode: Literal["api", "cli"] = "api"
    profile: Optional[str] = None
    #: "ubl" or "cii" — which syntax was read. None for a JSON InvoiceInput body.
    syntax: Optional[str] = None
    #: The PDF attachment the XML was read from (Factur-X/ZUGFeRD), or None.
    container: Optional[str] = None
    #: Plain-English statement of what was checked and what it does not prove.
    #: Only from mode="api"; the CLI does not return it.
    source: Optional[str] = None
    #: The full parsed JSON this was built from, in case you need a field this
    #: type does not model yet.
    raw: Optional[dict] = None

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.severity == "fatal"]

    @property
    def warnings(self) -> list:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def information(self) -> list:
        return [f for f in self.findings if f.severity == "information"]


def findings_from_validation_result_json(body: dict) -> list:
    """`errors` + `warnings` + `information`, in that order, as `Finding`s.

    This is the hosted API's `ValidationResult` shape: three arrays split by
    severity, each item a `TeachingError`. Concatenating them (fatal first)
    gives one flat, already-severity-tagged list, matching what the CLI's
    `--json` output gives per file.
    """

    findings = []
    for key in ("errors", "warnings", "information"):
        for item in body.get(key) or []:
            findings.append(Finding.from_json(item))
    return findings
