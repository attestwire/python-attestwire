"""Opt-in tests that hit the real network. Skipped by default.

Run with:

    ATTESTWIRE_LIVE_TEST=1 ATTESTWIRE_API_KEY=aw_live_... python3 -m unittest tests.test_live -v

Neither environment variable is read anywhere else in this suite — every
other test mocks `urlopen` / `subprocess.run` and touches neither the network
nor Node. These exist to catch the hosted API's contract actually drifting
from what this package assumes, which a mock can never catch by construction.
"""

import os
import shutil
import unittest

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


@unittest.skipUnless(LIVE, "set ATTESTWIRE_LIVE_TEST=1 to run tests against the real API")
@unittest.skipUnless(shutil.which("node") or shutil.which("npx"), "Node.js/npx not installed")
class LiveCliTests(unittest.TestCase):
    def test_validate_via_cli_against_the_real_engine(self):
        result = attestwire.validate(INCOMPLETE_UBL, mode="cli")
        self.assertFalse(result.valid)
        self.assertGreater(len(result.errors), 0)


if __name__ == "__main__":
    unittest.main()
