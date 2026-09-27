"""Exceptions `validate()` can raise. Everything else is a `ValidationResult`.

A finding — even a fatal one, "this invoice is not compliant" — is never an
exception: `validate()` returns normally with `valid=False` and the findings
that explain why. These are for when validation could not run at all.
"""

from __future__ import annotations

from typing import Optional


class AttestwireError(Exception):
    """Base class for everything this package raises."""


class ApiError(AttestwireError):
    """`mode="api"` got an HTTP error response.

    Mirrors the hosted API's error envelope: `{error, message, docs, ...}`
    (documented at https://api.attestwire.com/docs).
    """

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        docs: Optional[str] = None,
        upgrade_url: Optional[str] = None,
    ) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.docs = docs
        self.upgrade_url = upgrade_url


class CliError(AttestwireError):
    """`mode="cli"` could not run, or could not make sense of what ran.

    Covers: Node/npx not found, the subprocess timed out, or its stdout was
    not the JSON `--json` promises (usually an npm/npx error printed instead,
    included in the message).
    """
