"""``mode="api"``: ``POST {origin}/v1/validate`` with stdlib ``urllib`` only.

The request/response contract here is the hosted API's published one
(https://api.attestwire.com/openapi.json and https://api.attestwire.com/docs): auth is ``Authorization: Bearer <key>``, the body
is the raw document (XML or PDF bytes, or a JSON ``InvoiceInput``) sent with
the matching ``Content-Type``, and the response — on every status, success or
error — is JSON. A ``200`` is a ``ValidationResult``: ``valid`` plus three
findings arrays, ``errors``/``warnings``/``information``, whether or not the
invoice passed (``valid: false`` is still a normal, billable ``200``). An
error status carries ``{error, message, docs, ...}``.
"""

from __future__ import annotations

import json
import os
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._detect import sniff_media_type
from ._exceptions import ApiError, AttestwireError
from ._types import ValidationResult, findings_from_validation_result_json
from ._version import __version__

DEFAULT_ORIGIN = "https://api.attestwire.com"
#: Read when `api_key` is not passed explicitly.
API_KEY_ENV_VAR = "ATTESTWIRE_API_KEY"


def _content_type(data: bytes, was_text: bool) -> str:
    media = sniff_media_type(data)
    # A `str` you gave us was encoded to UTF-8 by this module, below — telling
    # the API that outranks whatever encoding the XML declaration itself
    # names (RFC 7303), which matters if you built the string from a document
    # that declared e.g. ISO-8859-1 and did not re-declare it after re-encoding.
    if media == "application/xml" and was_text:
        return "application/xml; charset=utf-8"
    return media


def validate_via_api(
    data: bytes,
    *,
    was_text: bool,
    api_key: Optional[str],
    origin: str = DEFAULT_ORIGIN,
    timeout: float = 30.0,
) -> ValidationResult:
    key = api_key or os.environ.get(API_KEY_ENV_VAR)
    if not key:
        raise AttestwireError(
            "validate(mode=\"api\") needs an API key: pass api_key=..., or set the "
            f"{API_KEY_ENV_VAR} environment variable. Get one free, no card required, "
            f"with POST {origin}/v1/keys — see {origin}/docs#auth."
        )

    url = f"{origin.rstrip('/')}/v1/validate"
    request = Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": _content_type(data, was_text),
            "User-Agent": f"attestwire-python/{__version__}",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read()
        try:
            error_body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            error_body = {}
        raise ApiError(
            exc.code,
            error_body.get("error", "unknown_error"),
            error_body.get("message") or f"POST {url} failed with HTTP {exc.code}.",
            docs=error_body.get("docs"),
            upgrade_url=error_body.get("upgrade_url"),
        ) from exc
    except URLError as exc:
        raise AttestwireError(f"Could not reach {url}: {exc.reason}") from exc

    return ValidationResult(
        valid=bool(body.get("valid")),
        findings=findings_from_validation_result_json(body),
        mode="api",
        profile=body.get("profile"),
        syntax=body.get("syntax"),
        container=body.get("container"),
        source=body.get("source"),
        raw=body,
    )
