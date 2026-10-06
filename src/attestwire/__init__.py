"""Create and validate EN 16931 e-invoices — XRechnung, Factur-X/ZUGFeRD,
Peppol BIS 3 — from Python, standard library only.

    import attestwire

    result = attestwire.validate(xml_bytes, api_key="aw_live_...")
    if not result.valid:
        for finding in result.errors:
            print(finding.rule, finding.message)
            print("  fix:", finding.fix)

    pdf = attestwire.generate(invoice, format="pdf", api_key="aw_live_...")
    open(pdf.filename, "wb").write(pdf.content)

`generate()` always goes through the hosted API. `validate()` has two
backends:

chosen with ``mode``:

``mode="api"`` (the default) posts the document to the hosted Attestwire API
(``POST https://api.attestwire.com/v1/validate``) with your API key. Needs a
key (``api_key=`` or the ``ATTESTWIRE_API_KEY`` environment variable) and
network access; nothing else.

``mode="cli"`` runs ``npx --yes @attestwire/en16931 --json <tmpfile>``
locally — the document never leaves your machine. Needs Node.js (``npx``) on
``PATH``; the first run downloads the package from npm unless it is already
cached, but the invoice itself is never uploaded anywhere.

Both return the same `ValidationResult`, so switching between them (say,
`api` in production, `cli` in a pre-commit hook with no API key configured)
is a one-argument change.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional, Union

from ._api import DEFAULT_ORIGIN, validate_via_api
from ._cli import DEFAULT_NODE_COMMAND, DEFAULT_PACKAGE_SPEC, validate_via_cli
from ._exceptions import ApiError, AttestwireError, CliError, InvalidInvoiceError
from ._generate import PDF_PROFILE, generate_via_api
from ._types import Finding, GeneratedInvoice, Location, Severity, ValidationResult
from ._version import __version__

__all__ = [
    "validate",
    "generate",
    "ValidationResult",
    "GeneratedInvoice",
    "Finding",
    "Location",
    "Severity",
    "AttestwireError",
    "ApiError",
    "CliError",
    "InvalidInvoiceError",
    "DEFAULT_ORIGIN",
    "PDF_PROFILE",
    "__version__",
]


def validate(
    data: Union[bytes, str],
    *,
    api_key: Optional[str] = None,
    mode: Literal["api", "cli"] = "api",
    origin: str = DEFAULT_ORIGIN,
    timeout: float = 30.0,
    node_command: str = DEFAULT_NODE_COMMAND,
    package_spec: str = DEFAULT_PACKAGE_SPEC,
) -> ValidationResult:
    """Validate one e-invoice document against EN 16931 and its CIUS rules.

    Args:
        data: The document, as it exists on disk or in memory — a UBL 2.1
            ``Invoice``/``CreditNote``, a UN/CEFACT CII ``CrossIndustryInvoice``,
            or a Factur-X/ZUGFeRD PDF. ``bytes`` for a PDF, or either ``bytes``
            or ``str`` for XML. Sniffed from its content (a leading ``%PDF``,
            ``<``, ``{``/``[``), not from a file name — there is no filename
            here to go by, and the hosted API itself does the same sniff.
        api_key: Your Attestwire API key (``aw_live_...`` / ``aw_test_...``).
            ``mode="api"`` only; falls back to the ``ATTESTWIRE_API_KEY``
            environment variable, then raises `AttestwireError` if neither is
            set. Ignored by ``mode="cli"``, which needs no account.
        mode: ``"api"`` (default) calls the hosted API over the network.
            ``"cli"`` runs the local, free ``@attestwire/en16931`` engine via
            ``npx``; needs Node.js, uploads nothing.
        origin: The API origin. ``mode="api"`` only.
        timeout: Seconds to wait: the HTTP request (``mode="api"``) or the
            subprocess (``mode="cli"``, where the first run can be slow while
            npx fetches the package).
        node_command: The command to run for ``mode="cli"``. Default ``"npx"``;
            override if it is not on `PATH` under that name.
        package_spec: The npm package `mode="cli"` runs. Override to pin a
            version, e.g. ``"@attestwire/en16931@0.12.1"``.

    Returns:
        A `ValidationResult`: ``valid``, ``findings`` (``rule``, ``severity``,
        ``message``, ``fix``, ``location``, ...), plus ``profile``/``syntax``
        when the document said what it was.

    Raises:
        AttestwireError: `mode="api"` with no API key available, or a network
            failure that never reached the API (DNS, connection refused, ...).
        ApiError: the API answered with an HTTP error status (401 unknown
            key, 413 too large, 429 rate limited, ...) — see `.status`,
            `.code`, `.message`, `.docs`, `.upgrade_url`. A *validation*
            failure — the invoice itself does not comply — is never this: it
            is a normal return with ``valid=False``.
        CliError: `mode="cli"` could not run at all (Node/npx missing, the
            subprocess timed out, or its output was not the JSON it promises).
        TypeError: `data` is neither `bytes` nor `str`.
        ValueError: `mode` is neither `"api"` nor `"cli"`.
    """

    was_text = isinstance(data, str)
    if was_text:
        raw = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        raise TypeError(f"attestwire.validate() expects bytes or str, got {type(data).__name__}.")

    if mode == "api":
        return validate_via_api(raw, was_text=was_text, api_key=api_key, origin=origin, timeout=timeout)
    if mode == "cli":
        return validate_via_cli(raw, node_command=node_command, package_spec=package_spec, timeout=timeout)
    raise ValueError(f'mode must be "api" or "cli", got {mode!r}.')


def generate(
    invoice: Union[Mapping[str, Any], str, bytes],
    *,
    format: Literal["xml", "pdf"] = "xml",
    pdf_options: Optional[Mapping[str, Any]] = None,
    api_key: Optional[str] = None,
    origin: str = DEFAULT_ORIGIN,
    timeout: float = 60.0,
) -> GeneratedInvoice:
    """Create an e-invoice from your own data: the XML, or a Factur-X / ZUGFeRD PDF.

    The invoice is checked against the rules first. If it fails any, nothing
    is generated and `InvalidInvoiceError` says which rules and how to fix
    them, exactly as `validate()` would.

    Args:
        invoice: The invoice as a dict (or its JSON text): seller, buyer,
            lines, VAT, in the shape the ``@attestwire/en16931`` package calls
            ``InvoiceInput`` (https://api.attestwire.com/docs#input). Its
            ``profile`` picks the format: ``"xrechnung-ubl"``,
            ``"xrechnung-cii"``, ``"peppol-bis-3"``, ``"facturx-en16931"``,
            ``"en16931"``, or ``"auto"`` to let the API choose from the buyer.
            Totals are calculated from the lines; you do not send them.
        format: ``"xml"`` (default) returns the XML document. ``"pdf"`` returns
            a Factur-X / ZUGFeRD PDF (PDF/A-3B, the CII XML embedded), and
            needs ``"profile": "facturx-en16931"``. On the free plan the PDF is
            a watermarked preview (``.watermarked``); paid plans get it clean.
        pdf_options: For ``format="pdf"``: options for the page, sent as the
            API names them — ``language`` (``"en"``, ``"de"``, ``"fr"``),
            ``logo``, ``paymentQr``, ``paymentLink``. See
            https://api.attestwire.com/docs#pdf-options.
        api_key: Your Attestwire API key; falls back to the
            ``ATTESTWIRE_API_KEY`` environment variable. ``"demo"`` works for
            trying it out, without signing up.
        origin: The API origin.
        timeout: Seconds to wait for the response.

    Returns:
        A `GeneratedInvoice`: ``content`` (bytes) and ``filename`` to save it
        under, plus ``xml`` or ``pdf``, ``profile``, and any warnings.

    Raises:
        InvalidInvoiceError: the invoice fails the rules; ``.result.errors``
            lists each one with its fix. Nothing is charged.
        ApiError: any other HTTP error (401 unknown key, 400 a profile the PDF
            cannot carry, 429 rate limited, ...).
        AttestwireError: no API key, or the API could not be reached.
        TypeError / ValueError: the arguments themselves are wrong.
    """

    return generate_via_api(
        invoice, format=format, pdf_options=pdf_options, api_key=api_key, origin=origin, timeout=timeout
    )
