import unittest

from attestwire._types import (
    Finding,
    Location,
    ValidationResult,
    findings_from_validation_result_json,
)


class LocationFromJsonTests(unittest.TestCase):
    def test_none_when_absent(self):
        self.assertIsNone(Location.from_json(None))
        self.assertIsNone(Location.from_json({}))

    def test_maps_every_field(self):
        loc = Location.from_json(
            {"line": 14, "column": 3, "path": "/ubl:Invoice/cbc:ID", "exact": True, "attachment": "factur-x.xml"}
        )
        self.assertEqual(loc, Location(line=14, column=3, path="/ubl:Invoice/cbc:ID", exact=True, attachment="factur-x.xml"))


class FindingFromJsonTests(unittest.TestCase):
    def test_maps_a_full_teaching_error(self):
        finding = Finding.from_json(
            {
                "rule": "BR-DE-15",
                "field": "BT-10",
                "severity": "fatal",
                "message": "A German public-sector buyer requires a Leitweg-ID.",
                "fix": "Set buyerReference to the Leitweg-ID your client gave you.",
                "xpath": "/ubl:Invoice/cac:OrderReference/cbc:ID",
                "docsUrl": "https://attestwire.com/rules/BR-DE-15",
                "example": "04011000-1234512345-06",
                "location": {"line": 12, "column": 5, "path": "/ns:Invoice", "exact": True},
            }
        )
        self.assertEqual(finding.rule, "BR-DE-15")
        self.assertEqual(finding.severity, "fatal")
        self.assertEqual(finding.fix, "Set buyerReference to the Leitweg-ID your client gave you.")
        self.assertEqual(finding.docs_url, "https://attestwire.com/rules/BR-DE-15")
        self.assertEqual(finding.location, Location(line=12, column=5, path="/ns:Invoice", exact=True))

    def test_an_aw_finding_has_no_location_or_docs_url(self):
        finding = Finding.from_json(
            {
                "rule": "AW-PROFILE-SUBSET",
                "field": "document",
                "severity": "fatal",
                "message": "This profile carries too little to be an EN 16931 invoice.",
                "fix": "Export MINIMUM or BASIC WL as a plain PDF invoice instead.",
            }
        )
        self.assertIsNone(finding.location)
        self.assertIsNone(finding.docs_url)
        self.assertIsNone(finding.xpath)


class FindingsFromValidationResultJsonTests(unittest.TestCase):
    def test_concatenates_errors_warnings_information_in_order(self):
        body = {
            "valid": False,
            "errors": [{"rule": "BR-11", "severity": "fatal", "message": "e", "fix": "f"}],
            "warnings": [{"rule": "BR-DE-TMP-32", "severity": "warning", "message": "w", "fix": "f"}],
            "information": [{"rule": "ATW-CREDIT-NOTE-NO-PRECEDING-INVOICE", "severity": "information", "message": "i", "fix": "f"}],
        }
        findings = findings_from_validation_result_json(body)
        self.assertEqual([f.rule for f in findings], ["BR-11", "BR-DE-TMP-32", "ATW-CREDIT-NOTE-NO-PRECEDING-INVOICE"])
        self.assertEqual([f.severity for f in findings], ["fatal", "warning", "information"])

    def test_missing_arrays_are_treated_as_empty(self):
        self.assertEqual(findings_from_validation_result_json({"valid": True}), [])


class ValidationResultPropertiesTests(unittest.TestCase):
    def test_errors_warnings_information_filter_by_severity(self):
        findings = [
            Finding(rule="A", severity="fatal", message="a"),
            Finding(rule="B", severity="warning", message="b"),
            Finding(rule="C", severity="information", message="c"),
            Finding(rule="D", severity="fatal", message="d"),
        ]
        result = ValidationResult(valid=False, findings=findings)
        self.assertEqual([f.rule for f in result.errors], ["A", "D"])
        self.assertEqual([f.rule for f in result.warnings], ["B"])
        self.assertEqual([f.rule for f in result.information], ["C"])

    def test_valid_result_with_no_findings(self):
        result = ValidationResult(valid=True, findings=[])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.information, [])


if __name__ == "__main__":
    unittest.main()
