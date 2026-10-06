# Changelog

## [Unreleased]

## [0.2.0] — 2026-10-06

- **`generate(invoice, *, format="xml" | "pdf")` creates e-invoices.** Pass the
  invoice as a dict (the `InvoiceInput` shape) and get the XML for its profile,
  or with `format="pdf"` a Factur-X / ZUGFeRD PDF (PDF/A-3B, CII embedded, page
  in German, French or English; `pdf_options` for the language, logo, payment
  QR code and payment link). Calls `POST /v1/generate` on the hosted API.
  Returns a `GeneratedInvoice` (`content`, `filename`, `xml` or `pdf`,
  `profile`, `warnings`, `watermarked`).
- **`InvalidInvoiceError`**: an invoice that breaks a rule is not generated;
  the error's `.result` is the `ValidationResult` with each fix. A subclass of
  `ApiError` (status 422, code `invoice_invalid`).

## [0.1.0] — 2026-09-26

- Initial release: `validate(data, *, api_key=None, mode="api")`, with `mode="api"`
  (`POST /v1/validate` on the hosted Attestwire API) and `mode="cli"` (local
  `npx @attestwire/en16931 --json`) backends, a typed `ValidationResult` /
  `Finding` / `Location`, and documented recipes for akretion's `factur-x` and
  pretix's `python-drafthorse`.
