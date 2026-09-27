import io
import json
import os
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

import attestwire
from attestwire._exceptions import ApiError, AttestwireError


class FakeResponse:
    """A minimal stand-in for what `urlopen()` returns, used as a context manager."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._body


VALID_RESULT = {
    "valid": True,
    "profile": "xrechnung-ubl",
    "errors": [],
    "warnings": [],
    "information": [],
}

INVALID_RESULT = {
    "valid": False,
    "profile": "xrechnung-ubl",
    "errors": [
        {
            "rule": "BR-DE-15",
            "field": "BT-10",
            "severity": "fatal",
            "message": "A German public-sector buyer requires a Leitweg-ID.",
            "fix": "Set buyerReference to the Leitweg-ID your client gave you.",
            "docsUrl": "https://attestwire.com/rules/BR-DE-15",
        }
    ],
    "warnings": [],
    "information": [],
}


class ApiSuccessTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

    def test_valid_json_document(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        result = attestwire.validate(b"<Invoice/>", api_key="aw_live_test", mode="api")
        self.assertTrue(result.valid)
        self.assertEqual(result.findings, [])
        self.assertEqual(result.profile, "xrechnung-ubl")
        self.assertEqual(result.mode, "api")
        urlopen.assert_called_once()

    def test_invalid_document_reports_findings_not_an_exception(self):
        mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(INVALID_RESULT).encode())).start()
        result = attestwire.validate(b"<Invoice/>", api_key="aw_live_test")
        self.assertFalse(result.valid)
        self.assertEqual(len(result.errors), 1)
        finding = result.errors[0]
        self.assertEqual(finding.rule, "BR-DE-15")
        self.assertEqual(finding.severity, "fatal")
        self.assertEqual(finding.fix, "Set buyerReference to the Leitweg-ID your client gave you.")
        self.assertEqual(finding.docs_url, "https://attestwire.com/rules/BR-DE-15")

    def test_sends_bearer_auth_and_user_agent(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        attestwire.validate(b"<Invoice/>", api_key="aw_live_abc123")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Authorization"), "Bearer aw_live_abc123")
        self.assertIn("attestwire-python/", request.get_header("User-agent"))

    def test_default_origin_and_path(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        attestwire.validate(b"<Invoice/>", api_key="k")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.attestwire.com/v1/validate")

    def test_custom_origin(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        attestwire.validate(b"<Invoice/>", api_key="k", origin="https://staging.example.com/")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://staging.example.com/v1/validate")

    def test_content_type_pdf_bytes(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        attestwire.validate(b"%PDF-1.7 ...", api_key="k")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Content-type"), "application/pdf")

    def test_content_type_xml_bytes_has_no_forced_charset(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        attestwire.validate(b"<Invoice/>", api_key="k")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Content-type"), "application/xml")

    def test_content_type_xml_str_declares_utf8_charset(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        attestwire.validate("<Invoice/>", api_key="k")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Content-type"), "application/xml; charset=utf-8")
        self.assertEqual(request.data, "<Invoice/>".encode("utf-8"))

    def test_api_key_falls_back_to_environment_variable(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        with mock.patch.dict(os.environ, {"ATTESTWIRE_API_KEY": "aw_live_from_env"}):
            attestwire.validate(b"<Invoice/>")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Authorization"), "Bearer aw_live_from_env")

    def test_explicit_api_key_wins_over_environment_variable(self):
        urlopen = mock.patch("attestwire._api.urlopen", return_value=FakeResponse(json.dumps(VALID_RESULT).encode())).start()
        with mock.patch.dict(os.environ, {"ATTESTWIRE_API_KEY": "aw_live_from_env"}):
            attestwire.validate(b"<Invoice/>", api_key="aw_live_explicit")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Authorization"), "Bearer aw_live_explicit")


class ApiFailureTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

    def test_missing_api_key_raises_locally_without_a_network_call(self):
        urlopen = mock.patch("attestwire._api.urlopen").start()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AttestwireError) as ctx:
                attestwire.validate(b"<Invoice/>")
        self.assertIn("api_key", str(ctx.exception))
        urlopen.assert_not_called()

    def test_http_error_with_json_body_becomes_api_error(self):
        body = json.dumps(
            {
                "error": "invalid_api_key",
                "message": "That API key is not recognised.",
                "docs": "https://api.attestwire.com/docs#auth",
            }
        ).encode()
        http_error = HTTPError("https://api.attestwire.com/v1/validate", 401, "Unauthorized", None, io.BytesIO(body))
        mock.patch("attestwire._api.urlopen", side_effect=http_error).start()

        with self.assertRaises(ApiError) as ctx:
            attestwire.validate(b"<Invoice/>", api_key="aw_live_bad")
        self.assertEqual(ctx.exception.status, 401)
        self.assertEqual(ctx.exception.code, "invalid_api_key")
        self.assertEqual(ctx.exception.message, "That API key is not recognised.")
        self.assertEqual(ctx.exception.docs, "https://api.attestwire.com/docs#auth")

    def test_http_error_with_upgrade_url(self):
        body = json.dumps(
            {"error": "plan_required", "message": "Needs a paid plan.", "upgrade_url": "https://attestwire.com/pricing"}
        ).encode()
        http_error = HTTPError("https://api.attestwire.com/v1/generate", 402, "Payment Required", None, io.BytesIO(body))
        mock.patch("attestwire._api.urlopen", side_effect=http_error).start()

        with self.assertRaises(ApiError) as ctx:
            attestwire.validate(b"<Invoice/>", api_key="k")
        self.assertEqual(ctx.exception.upgrade_url, "https://attestwire.com/pricing")

    def test_http_error_with_non_json_body_gets_a_fallback_message(self):
        http_error = HTTPError(
            "https://api.attestwire.com/v1/validate", 500, "Internal Server Error", None, io.BytesIO(b"<html>oops</html>")
        )
        mock.patch("attestwire._api.urlopen", side_effect=http_error).start()

        with self.assertRaises(ApiError) as ctx:
            attestwire.validate(b"<Invoice/>", api_key="k")
        self.assertEqual(ctx.exception.status, 500)
        self.assertIn("HTTP 500", ctx.exception.message)

    def test_connection_failure_raises_attestwire_error(self):
        mock.patch("attestwire._api.urlopen", side_effect=URLError("no route to host")).start()
        with self.assertRaises(AttestwireError):
            attestwire.validate(b"<Invoice/>", api_key="k")

    def test_wrong_data_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            attestwire.validate(12345, api_key="k")  # type: ignore[arg-type]

    def test_wrong_mode_raises_value_error(self):
        with self.assertRaises(ValueError):
            attestwire.validate(b"<Invoice/>", api_key="k", mode="carrier-pigeon")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
