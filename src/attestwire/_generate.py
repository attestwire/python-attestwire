"""``generate()``: ``POST {origin}/v1/generate``, with stdlib ``urllib`` only.

The contract is the hosted API's (https://api.attestwire.com/docs#endpoints
and #facturx-pdf). The body is the invoice as JSON — the same ``InvoiceInput``
the ``@attestwire/en16931`` package takes — or, with page options for the PDF,
``{"invoice": ..., "pdf": {...}}``. Without ``?format=pdf`` the answer is a JSON
envelope (``xml``, ``profile``, ``syntax``, ``warnings``, ``information``);
with it, the PDF's bytes, with what the caller needs to know about them in
headers. An invoice with a fatal finding is refused with 422 and the same
``ValidationResult`` ``/v1/validate`` returns, and nothing is charged.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Mapping, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._api import DEFAULT_ORIGIN, api_error_from, read_error_body, resolve_api_key
from ._exceptions import AttestwireError, InvalidInvoiceError
from ._types import GeneratedInvoice, ValidationResult, findings_from_validation_result_json
from ._version import __version__

#: The one profile a Factur-X / ZUGFeRD PDF carries.
PDF_PROFILE = "facturx-en16931"


def _invoice_json(invoice: Union[Mapping[str, Any], str, bytes]) -> Any:
    if isinstance(invoice, Mapping):
        return dict(invoice)
    if isinstance(invoice, (bytes, bytearray)):
        invoice = bytes(invoice).decode("utf-8")
    if isinstance(invoice, str):
        try:
            return json.loads(invoice)
        except json.JSONDecodeError as exc:
            raise ValueError(f"generate() was given a string that is not JSON: {exc}") from exc
    raise TypeError(
        f"generate() expects the invoice as a dict (or its JSON text), got {type(invoice).__name__}."
    )


def _filename(disposition: Optional[str]) -> Optional[str]:
    match = re.search(r'filename="([^"]+)"', disposition or "")
    return match.group(1) if match else None


def _xml_filename(invoice: Any) -> str:
    number = invoice.get("invoiceNumber") if isinstance(invoice, dict) else None
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(number or "invoice"))[:80] or "invoice"
    return f"{stem}.xml"


def generate_via_api(
    invoice: Union[Mapping[str, Any], str, bytes],
    *,
    format: Literal["xml", "pdf"] = "xml",
    pdf_options: Optional[Mapping[str, Any]] = None,
    api_key: Optional[str] = None,
    origin: str = DEFAULT_ORIGIN,
    timeout: float = 60.0,
) -> GeneratedInvoice:
    if format not in ("xml", "pdf"):
        raise ValueError(f'format must be "xml" or "pdf", got {format!r}.')
    if pdf_options is not None and format != "pdf":
        raise ValueError('pdf_options only apply to format="pdf".')

    parsed = _invoice_json(invoice)
    key = resolve_api_key(api_key, origin, "generate()")

    body: Any = {"invoice": parsed, "pdf": dict(pdf_options)} if pdf_options else parsed
    url = f"{origin.rstrip('/')}/v1/generate" + ("?format=pdf" if format == "pdf" else "")
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": f"attestwire-python/{__version__}",
            "Accept": "application/pdf, application/json" if format == "pdf" else "application/json",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            headers = response.headers
    except HTTPError as exc:
        error_body = read_error_body(exc)
        if exc.code == 422 and "valid" in error_body:
            result = ValidationResult(
                valid=False,
                findings=findings_from_validation_result_json(error_body),
                mode="api",
                profile=error_body.get("profile"),
                raw=error_body,
            )
            raise InvalidInvoiceError(result) from exc
        raise api_error_from(exc, url, error_body) from exc
    except URLError as exc:
        raise AttestwireError(f"Could not reach {url}: {exc.reason}") from exc

    if format == "pdf":
        if not payload.startswith(b"%PDF"):
            raise AttestwireError(f"POST {url} answered 200 with something that is not a PDF.")
        return GeneratedInvoice(
            format="pdf",
            pdf=payload,
            filename=_filename(headers.get("Content-Disposition")),
            profile=PDF_PROFILE,
            watermarked=headers.get("Attestwire-Preview") == "watermarked",
            language=headers.get("Content-Language"),
            unrendered_characters=int(headers.get("X-Unrendered-Characters") or 0),
        )

    try:
        envelope = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AttestwireError(f"POST {url} answered 200 with a body that is not JSON.") from exc
    return GeneratedInvoice(
        format="xml",
        xml=envelope.get("xml"),
        filename=_xml_filename(parsed),
        profile=envelope.get("profile"),
        syntax=envelope.get("syntax"),
        findings=findings_from_validation_result_json(envelope),
        note=envelope.get("note"),
        raw=envelope,
    )
