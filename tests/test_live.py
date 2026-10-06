"""Opt-in tests that hit the real network. Skipped by default.

Run with:

    ATTESTWIRE_LIVE_TEST=1 ATTESTWIRE_API_KEY=aw_live_... python3 -m unittest tests.test_live -v

Neither environment variable is read anywhere else in this suite — every
other test mocks `urlopen` / `subprocess.run` and touches neither the network
nor Node. These exist to catch the hosted API's contract actually drifting
from what this package assumes, which a mock can never catch by construction.
"""

import contextlib
import io
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import attestwire

LIVE = os.environ.get("ATTESTWIRE_LIVE_TEST") == "1"
API_KEY = os.environ.get("ATTESTWIRE_API_KEY")

# A syntactically well-formed but incomplete UBL invoice: enough to be read as
# an XML document, not enough to pass a single business rule. The point of
# this test is "does the real API still speak the contract this package
# assumes", not "is this a compliant invoice".
INCOMPLETE_UBL = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>TEST-0001</cbc:ID>
</Invoice>
"""


@unittest.skipUnless(LIVE, "set ATTESTWIRE_LIVE_TEST=1 to run tests against the real API")
class LiveApiTests(unittest.TestCase):
    def test_validate_via_api_against_the_real_endpoint(self):
        if not API_KEY:
            self.skipTest("set ATTESTWIRE_API_KEY to a real key to run this test")
        result = attestwire.validate(INCOMPLETE_UBL, api_key=API_KEY, mode="api")
        # An incomplete invoice is still a normal 200: valid=False, with findings
        # that name the missing business terms.
        self.assertFalse(result.valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(all(f.rule for f in result.errors))

    def test_invalid_api_key_raises_api_error(self):
        with self.assertRaises(attestwire.ApiError) as ctx:
            attestwire.validate(INCOMPLETE_UBL, api_key="aw_live_definitely_not_a_real_key", mode="api")
        self.assertEqual(ctx.exception.status, 401)
        self.assertEqual(ctx.exception.code, "invalid_api_key")


# The smallest XRechnung that passes every rule: what generate() needs to
# produce a document at all.
VALID_INVOICE = {
    "profile": "xrechnung-ubl",
    "invoiceNumber": "LIVE-0001",
    "issueDate": "2026-08-09",
    "currency": "EUR",
    "buyerReference": "04011000-1234512345-06",
    "deliveryDate": "2026-08-31",
    "seller": {
        "name": "Acme GmbH",
        "vatId": "DE123456789",
        "address": {"line1": "Chausseestr. 1", "city": "Berlin", "postalCode": "10115", "countryCode": "DE"},
        "electronicAddress": {"schemeId": "0204", "value": "04011000-1234512345-06"},
        "contact": {"name": "Buchhaltung", "phone": "+49 30 1234567", "email": "rechnungen@acme.example"},
    },
    "buyer": {
        "name": "Stadt Bonn",
        "address": {"line1": "Berliner Platz 2", "city": "Bonn", "postalCode": "53111", "countryCode": "DE"},
        "electronicAddress": {"schemeId": "0204", "value": "04011000-1234512345-06"},
    },
    "payment": {"meansCode": "58", "iban": "DE02120300000000202051"},
    "lines": [
        {"id": "1", "description": "Consulting", "quantity": 10, "unitCode": "HUR", "unitPrice": 150, "vatCategory": "S", "vatRate": 19}
    ],
}


@unittest.skipUnless(LIVE, "set ATTESTWIRE_LIVE_TEST=1 to run tests against the real API")
class LiveGenerateTests(unittest.TestCase):
    # The public demo key works on /v1/generate, so these need no account.
    KEY = API_KEY or "demo"

    def test_generate_xml(self):
        out = attestwire.generate(VALID_INVOICE, api_key=self.KEY)
        self.assertEqual(out.syntax, "ubl")
        self.assertTrue(out.xml.startswith("<?xml"))

    def test_generate_pdf(self):
        out = attestwire.generate({**VALID_INVOICE, "profile": attestwire.PDF_PROFILE}, format="pdf", api_key=self.KEY)
        self.assertTrue(out.pdf.startswith(b"%PDF"))
        self.assertEqual(out.filename, "LIVE-0001.pdf")

    def test_the_readme_example_runs(self):
        readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
        block = re.search(r"## Create an e-invoice\n\n```python\n(.*?)```", readme, re.S)
        self.assertIsNotNone(block, "README.md has no Create an e-invoice example")
        code = block.group(1).replace('"aw_live_..."', repr(self.KEY))
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with contextlib.redirect_stdout(io.StringIO()) as printed:
                    exec(code, {})
                self.assertTrue(Path(tmp, "2026-000142.pdf").read_bytes().startswith(b"%PDF"))
            finally:
                os.chdir(cwd)
        self.assertIn("<cbc:BuyerReference>PO-4711</cbc:BuyerReference>", printed.getvalue())

    def test_generate_refuses_an_invalid_invoice_with_its_findings(self):
        invalid = {k: v for k, v in VALID_INVOICE.items() if k != "buyerReference"}
        with self.assertRaises(attestwire.InvalidInvoiceError) as ctx:
            attestwire.generate(invalid, api_key=self.KEY)
        self.assertEqual([f.rule for f in ctx.exception.result.errors], ["BR-DE-15"])


@unittest.skipUnless(LIVE, "set ATTESTWIRE_LIVE_TEST=1 to run tests against the real API")
@unittest.skipUnless(shutil.which("node") or shutil.which("npx"), "Node.js/npx not installed")
class LiveCliTests(unittest.TestCase):
    def test_validate_via_cli_against_the_real_engine(self):
        result = attestwire.validate(INCOMPLETE_UBL, mode="cli")
        self.assertFalse(result.valid)
        self.assertGreater(len(result.errors), 0)


if __name__ == "__main__":
    unittest.main()
