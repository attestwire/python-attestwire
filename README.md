# attestwire

Create and check EN 16931 e-invoices — XRechnung, Factur-X/ZUGFeRD, Peppol
BIS 3 — from Python. Describe the invoice as a dict and get the XML or a
ready-to-send Factur-X / ZUGFeRD PDF; hand over an invoice you received and
get every problem in it, with the fix. Standard library only (`urllib`,
`json`, `subprocess`); nothing to install beyond this package itself.
Python 3.9+.

```bash
pip install attestwire
```

## Create an e-invoice

```python
import attestwire

invoice = {
    "profile": "facturx-en16931",   # or "xrechnung-ubl", "xrechnung-cii", "peppol-bis-3", "auto"
    "invoiceNumber": "2026-000142",
    "issueDate": "2026-08-09",
    "currency": "EUR",
    "seller": {
        "name": "Acme GmbH",
        "vatId": "DE123456789",
        "address": {"line1": "Chausseestr. 1", "city": "Berlin", "postalCode": "10115", "countryCode": "DE"},
        "contact": {"name": "Buchhaltung", "phone": "+49 30 1234567", "email": "rechnungen@acme.example"},
    },
    "buyer": {
        "name": "Client Exemple SARL",
        "vatId": "FR40303265045",
        "address": {"line1": "1 rue de la Paix", "city": "Paris", "postalCode": "75002", "countryCode": "FR"},
    },
    "vatScenario": "intra-eu-services",   # say what happened; the VAT codes are filled in
    "payment": {"iban": "DE02120300000000202051"},
    "lines": [
        {"id": "1", "description": "Consulting, August 2026", "quantity": 10, "unitCode": "HUR", "unitPrice": 150},
    ],
}

pdf = attestwire.generate(invoice, format="pdf", api_key="aw_live_...")
with open(pdf.filename, "wb") as f:      # 2026-000142.pdf
    f.write(pdf.content)

xml = attestwire.generate({**invoice, "profile": "xrechnung-ubl", "buyerReference": "PO-4711"}, api_key="aw_live_...")
print(xml.xml)
```

`format="pdf"` returns a Factur-X / ZUGFeRD PDF: a readable invoice page (in
German, French or English, from the seller's country unless you pass
`pdf_options={"language": "fr"}`), written as PDF/A-3B with the CII XML
embedded, so the customer's software reads the data and a person reads the
page. It carries the `facturx-en16931` profile. Without `format`, you get the
XML alone, for whichever profile the invoice names.

The invoice is a dict in the shape the
[`@attestwire/en16931`](https://www.npmjs.com/package/@attestwire/en16931)
package calls `InvoiceInput`, documented field by field at
[api.attestwire.com/docs#input](https://api.attestwire.com/docs#input).
Totals are calculated from the lines; you do not send them.

**An invoice that breaks a rule is not generated.** `generate()` raises
`attestwire.InvalidInvoiceError`, and `.result` is what `validate()` would
have returned: each rule, what is wrong and how to fix it.

```python
try:
    attestwire.generate(invoice, format="pdf")
except attestwire.InvalidInvoiceError as err:
    for finding in err.result.errors:
        print(finding.rule, finding.fix)
```

Generation goes through the hosted API, so it needs a key (`api_key=` or
`ATTESTWIRE_API_KEY`); [get one free](https://api.attestwire.com/docs#auth),
or pass `api_key="demo"` to try it without signing up. On the free plan the
PDF is a watermarked preview (`pdf.watermarked` is `True`); paid plans get it
clean. A refused invoice costs nothing.

## Check an e-invoice

```python
with open("invoice.xml", "rb") as f:
    result = attestwire.validate(f.read(), api_key="aw_live_...")

if not result.valid:
    for finding in result.errors:
        print(finding.rule, finding.message)
        print("  fix:", finding.fix)
```

`data` is the document itself — XML bytes/text, or a Factur-X/ZUGFeRD PDF's
bytes — sniffed from its content (`%PDF`, `<`, ...), not a file name. There is
no separate "read this file" step: pass the bytes you already have, from disk,
from a request body, from whatever generated them.

## Two ways to validate

```python
attestwire.validate(data, api_key=API_KEY)             # mode="api" (default)
attestwire.validate(data, mode="cli")                   # mode="cli"
```

**`mode="api"`** (default) posts the document to the hosted Attestwire API —
`POST https://api.attestwire.com/v1/validate` — with your API key as
`Authorization: Bearer`. Needs network access and a key: pass `api_key=`, or
set the `ATTESTWIRE_API_KEY` environment variable. Get one free (no card
required) at `POST /v1/keys` — see
[api.attestwire.com/docs#auth](https://api.attestwire.com/docs#auth).

**`mode="cli"`** runs `npx --yes @attestwire/en16931 --json <tmpfile>`
locally: the document is written to a temporary file, handed to the engine's
own command-line validator, and the temp file is deleted afterwards.
**Nothing is uploaded anywhere.** Needs Node.js (`npx`) on `PATH` — the first
run downloads `@attestwire/en16931` from npm if it isn't already cached, but
that's the *validator* being fetched, never your invoice. No API key needed.

Both return the same `ValidationResult`, so switching between them — `api` in
a production webhook, `cli` in a pre-commit hook or CI job with no key
configured — is a one-keyword change.

## The result

```python
@dataclass
class ValidationResult:
    valid: bool
    findings: list[Finding]
    mode: str              # "api" or "cli"
    profile: str | None
    syntax: str | None     # "ubl" or "cii", when the document said which
    container: str | None  # the PDF attachment name, for a Factur-X/ZUGFeRD PDF
    source: str | None     # mode="api" only: what was checked and what it doesn't prove
    raw: dict | None       # the full parsed JSON, for anything not modelled above

    errors: list[Finding]        # severity == "fatal" — these set valid=False
    warnings: list[Finding]      # severity == "warning"
    information: list[Finding]   # severity == "information" (advisory)

@dataclass
class Finding:
    rule: str | None            # "BR-DE-15", "ATW-CREDIT-NOTE-...", or an "AW-*" whole-document finding
    severity: str | None        # "fatal" | "warning" | "information"
    message: str | None
    fix: str | None
    field: ...                  # the business term(s), e.g. "BT-10" or ["BT-31", "BT-32"]
    xpath: str | None
    docs_url: str | None        # https://attestwire.com/rules/<rule>, when the finding is a rule
    example: str | None
    location: Location | None   # line/column/path in the document you sent, when applicable

@dataclass
class Location:
    line: int | None
    column: int | None
    path: str | None
    exact: bool | None
    attachment: str | None      # set only when the document was a PDF: which embedded XML this is in
```

`findings` is `errors + warnings + information`, in that order — already
tagged with its own `severity`, so filter it however you like; the three
properties above are there for when you just want one bucket.

## Errors you handle vs. exceptions you don't expect

A **non-compliant invoice is never an exception from `validate()`.** It returns
normally with `result.valid is False` and the findings that explain why —
that's the whole point of the package. `generate()` has nothing to return for
one, so it raises `InvalidInvoiceError` with the same findings. What *can*
raise:

| Exception | When |
| --- | --- |
| `attestwire.InvalidInvoiceError` | `generate()` only: the invoice breaks a rule, so nothing was generated (HTTP 422). `.result` is the `ValidationResult`, with each finding's fix. A subclass of `ApiError`. |
| `attestwire.ApiError` | `mode="api"` or `generate()` got an HTTP error status: `.status`, `.code`, `.message`, `.docs`, `.upgrade_url` (e.g. `401 invalid_api_key`, `413 too_large`, `429 rate_limited`). |
| `attestwire.CliError` | `mode="cli"` couldn't run at all: Node/npx missing, the subprocess timed out, or its output wasn't the JSON it promises (message includes stderr). |
| `attestwire.AttestwireError` | `mode="api"` or `generate()` with no key available anywhere, or a network failure that never reached the API. Base class of the two above, if you want to catch either. |
| `TypeError` | `data` is neither `bytes` nor `str`; `generate()`'s invoice is not a dict or JSON text. |
| `ValueError` | `mode` is neither `"api"` nor `"cli"`; `generate()`'s `format` is neither `"xml"` nor `"pdf"`, or its invoice text is not JSON. |

## Recipes: the validation step for existing Python e-invoicing libraries

Both packages below *build* Factur-X/CII documents; neither is a full EN
16931/XRechnung/Peppol business-rule checker (see why for each). Attestwire
plugs into the validation step either already needs to run elsewhere, or
never had at all.

### akretion's `factur-x`

[`factur-x`](https://github.com/akretion/factur-x) builds and reads Factur-X
PDFs (CII or UBL XML embedded in a PDF/A-3) and can check the XML it produces
two ways: `xml_check_xsd()` (schema-only, local, no Java) and
`xml_check_schematron()` (the EN 16931/CIUS *business rules* — BR-\*, BR-DE-\*,
and friends). **As of factur-x 6.0, that second check no longer runs
in-process:** it removed the bundled `saxonche` engine and instead does an
HTTP POST to a Saxon Server you run yourself — every schematron-capable
function (`xml_check_schematron`, `generate_from_file`/`generate_from_binary`
with `check_schematron=True`, the `get_*_xml_from_pdf` extractors,
`generate_cii_xml`/`generate_ubl_xml`) takes `saxon_server_url`, defaulting to
`http://localhost:5000/transform` — i.e. it expects a Saxon HTTP server
already listening on your machine or network, which factur-x does not itself
install, start or document how to stand up.

Attestwire replaces that call with one that needs no Java, no Saxon server,
and no server to keep running:

```python
from facturx import generate_from_file
import attestwire

# 1. Build the PDF/A-3, XSD-checked only (fast, local, no Saxon involved) —
#    this half of factur-x's validation is unaffected by any of this.
pdf_bytes = generate_from_binary(
    pdf_content, xml_content, check_xsd=True, check_schematron=False,
)

# 2. Where you would otherwise call
#      xml_check_schematron(xml_content, saxon_server_url="http://localhost:5000/transform")
#    validate the business rules with Attestwire instead — no Saxon server to run:
result = attestwire.validate(xml_content, api_key=API_KEY)   # or mode="cli": no key, no network
if not result.valid:
    for finding in result.errors:
        print(finding.rule, finding.message, "-- fix:", finding.fix)
    raise SystemExit(1)
```

You can skip factur-x's `get_facturx_xml_from_pdf()` extraction step
entirely, too: `attestwire.validate()` reads a Factur-X/ZUGFeRD PDF directly
(same as the hosted API's `POST /v1/validate` and the local CLI both do) and
validates the CII XML it finds inside, reporting which attachment it came
from as `result.container`.

```python
with open("invoice-facturx.pdf", "rb") as f:
    result = attestwire.validate(f.read(), api_key=API_KEY)
print(result.container)   # "factur-x.xml"
```

### pretix's `python-drafthorse`

[`python-drafthorse`](https://github.com/pretix/python-drafthorse) is a
direct, 1:1 data binding for the CII XML format — you build a `Document`,
populate its trade/line-item tree, and call `.serialize()`. Its own
validation is XSD-only (`Document.serialize(schema="FACTUR-X_EXTENDED")` runs
the embedded XSD via lxml; pass `schema=None` to skip even that) — there is no
schematron or business-rule engine in it at all, so this isn't replacing a
Java step, it's adding the EN 16931/XRechnung layer `python-drafthorse` never
had. Schema-valid CII XML can still fail BR-DE-15 (no Leitweg-ID), use the
wrong VAT category, or omit a mandatory party field — none of which an XSD
catches.

```python
from drafthorse.models.document import Document
from drafthorse.pdf import attach_xml
import attestwire

doc = Document()
# ... populate doc.header, doc.trade.agreement.seller / .buyer, line items ...

xml_bytes = doc.serialize(schema="FACTUR-X_EXTENDED")  # XSD-only; no business rules

result = attestwire.validate(xml_bytes, api_key=API_KEY)  # or mode="cli"
if not result.valid:
    for finding in result.errors:
        print(finding.rule, finding.message, "-- fix:", finding.fix)
    raise SystemExit(1)

pdf_bytes = attach_xml(base_pdf_bytes, xml_bytes)  # only once validation passed
```

## `mode="cli"` in CI, with no API key

Because `mode="cli"` needs no account, it's the natural choice for a
pre-commit hook or a CI job that only has Node available:

```python
result = attestwire.validate(generated_xml, mode="cli")
assert result.valid, "\n".join(f"{f.rule}: {f.message}" for f in result.errors)
```

Pin the engine version explicitly in CI for reproducibility:

```python
attestwire.validate(xml, mode="cli", package_spec="@attestwire/en16931@0.12.1")
```

## Development

```bash
python3 -m unittest discover -v
```

Every test mocks `urllib.request.urlopen` or `subprocess.run` — nothing here
touches the network or Node. `tests/test_live.py` is the one exception: it is
skipped unless you set `ATTESTWIRE_LIVE_TEST=1` (and, for the API half,
`ATTESTWIRE_API_KEY`), and it exists specifically to catch the hosted
contract drifting from what the mocks assume — something mocks cannot catch
by construction.

```bash
ATTESTWIRE_LIVE_TEST=1 ATTESTWIRE_API_KEY=aw_live_... python3 -m unittest tests.test_live -v
```

## Related

- [`@attestwire/en16931`](https://github.com/attestwire/en16931) — the rule
  engine `mode="cli"` runs locally.
- [Attestwire API docs](https://api.attestwire.com/docs) — the full
  request/response contract `mode="api"` implements.
- [Rule reference](https://attestwire.com/rules/) — one page per rule, with
  the reason and the fix.

## License

MIT.

## Trademark

"Attestwire"™ and the Attestwire logo are trademarks of this project's owner.
The MIT license covers the code and grants no trademark rights. You may say
your integration uses this package, or is built on it; you may not name or
brand a product or service "Attestwire", or imply that we endorse yours.
