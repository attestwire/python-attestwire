"""Exceptions `validate()` and `generate()` can raise.

For `validate()`, a finding — even a fatal one, "this invoice is not
compliant" — is never an exception: it returns normally with `valid=False`
and the findings that explain why. `generate()` is different, because there
is nothing to return: the API refuses to write a document that fails the
rules, and that refusal is `InvalidInvoiceError`, carrying the same findings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._types import ValidationResult


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


class InvalidInvoiceError(ApiError):
    """`generate()` was refused because the invoice fails the rules (HTTP 422).

    The API never writes XML or a PDF it knows a receiver would reject.
    `result` is the same `ValidationResult` `validate()` would return for this
    invoice: `result.errors` names each rule, what is wrong and the fix.
    Nothing is charged against your quota for a refusal.
    """

    def __init__(self, result: "ValidationResult", *, docs: Optional[str] = None) -> None:
        rules = ", ".join(f.rule or "?" for f in result.errors) or "no rule named"
        count = len(result.errors)
        message = (
            f"The invoice does not pass {count} rule{'s' if count != 1 else ''} ({rules}), "
            "so nothing was generated. See .result.errors for each fix."
        )
        super().__init__(422, "invoice_invalid", message, docs=docs)
        self.result = result


class CliError(AttestwireError):
    """`mode="cli"` could not run, or could not make sense of what ran.

    Covers: Node/npx not found, the subprocess timed out, or its stdout was
    not the JSON `--json` promises (usually an npm/npx error printed instead,
    included in the message).
    """
