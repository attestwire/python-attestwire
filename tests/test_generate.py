import io
import json
import os
import unittest
from email.message import Message
from unittest import mock
from urllib.error import HTTPError, URLError

import attestwire
from attestwire._exceptions import ApiError, AttestwireError, InvalidInvoiceError


class FakeResponse:
    """What `urlopen()` returns: a context manager with `read()` and `headers`."""

    def __init__(self, body: bytes, headers=None):
        self._body = body
        self.headers = Message()
        for name, value in (headers or {}).items():
            self.headers[name] = value

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._body


INVOICE = {
    "profile": "xrechnung-ubl",
    "invoiceNumber": "2026/000142",
    "issueDate": "2026-08-09",
    "currency": "EUR",
    "lines": [],
}

XML_ENVELOPE = {
    "xml": '<?xml version="1.0" encoding="UTF-8"?>\n<ubl:Invoice/>',
    "profile": "xrechnung-ubl",
    "syntax": "ubl",
    "warnings": [{"rule": "BR-DE-17", "severity": "warning", "message": "Unusual type code."}],
    "information": [],
    "provenance": {},
}

REFUSAL = {
    "valid": False,
    "profile": "xrechnung-ubl",
    "errors": [
        {
            "rule": "BR-DE-15",
            "field": "BT-10",
            "severity": "fatal",
            "message": "XRechnung requires a buyer reference (BT-10).",
            "fix": "Ask your client for their Leitweg-ID.",
        }
    ],
    "warnings": [],
    "information": [],
}


def http_error(status, body):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    return HTTPError("https://api.attestwire.com/v1/generate", status, "error", None, io.BytesIO(raw))


class GenerateXmlTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        self.urlopen = mock.patch(
            "attestwire._generate.urlopen", return_value=FakeResponse(json.dumps(XML_ENVELOPE).encode())
        ).start()

    def test_returns_the_xml_and_its_advisory_findings(self):
        out = attestwire.generate(INVOICE, api_key="k")
        self.assertEqual(out.format, "xml")
        self.assertEqual(out.xml, XML_ENVELOPE["xml"])
        self.assertIsNone(out.pdf)
        self.assertEqual(out.content, XML_ENVELOPE["xml"].encode("utf-8"))
        self.assertEqual(out.profile, "xrechnung-ubl")
        self.assertEqual(out.syntax, "ubl")
        self.assertEqual([f.rule for f in out.warnings], ["BR-DE-17"])

    def test_filename_comes_from_the_invoice_number_made_safe(self):
        self.assertEqual(attestwire.generate(INVOICE, api_key="k").filename, "2026_000142.xml")

    def test_posts_the_invoice_as_json_to_v1_generate(self):
        attestwire.generate(INVOICE, api_key="aw_live_abc")
        request = self.urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.attestwire.com/v1/generate")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Authorization"), "Bearer aw_live_abc")
        self.assertIn("attestwire-python/", request.get_header("User-agent"))
        self.assertEqual(json.loads(request.data), INVOICE)

    def test_accepts_the_invoice_as_json_text_or_bytes(self):
        attestwire.generate(json.dumps(INVOICE), api_key="k")
        attestwire.generate(json.dumps(INVOICE).encode(), api_key="k")
        for call in self.urlopen.call_args_list:
            self.assertEqual(json.loads(call[0][0].data), INVOICE)

    def test_api_key_falls_back_to_environment_variable(self):
        with mock.patch.dict(os.environ, {"ATTESTWIRE_API_KEY": "aw_live_env"}):
            attestwire.generate(INVOICE)
        self.assertEqual(self.urlopen.call_args[0][0].get_header("Authorization"), "Bearer aw_live_env")


class GeneratePdfTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

    def pdf_response(self, **headers):
        base = {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="2026-000142.pdf"',
            "Content-Language": "de",
        }
        base.update(headers)
        return FakeResponse(b"%PDF-1.7\n...", base)

    def test_returns_the_pdf_bytes_and_what_the_headers_say(self):
        mock.patch(
            "attestwire._generate.urlopen",
            return_value=self.pdf_response(**{"Attestwire-Preview": "watermarked", "X-Unrendered-Characters": "2"}),
        ).start()
        out = attestwire.generate({**INVOICE, "profile": "facturx-en16931"}, format="pdf", api_key="k")
        self.assertEqual(out.format, "pdf")
        self.assertEqual(out.pdf, b"%PDF-1.7\n...")
        self.assertEqual(out.content, out.pdf)
        self.assertIsNone(out.xml)
        self.assertEqual(out.filename, "2026-000142.pdf")
        self.assertEqual(out.profile, "facturx-en16931")
        self.assertTrue(out.watermarked)
        self.assertEqual(out.language, "de")
        self.assertEqual(out.unrendered_characters, 2)

    def test_a_paid_plan_pdf_is_not_watermarked(self):
        mock.patch("attestwire._generate.urlopen", return_value=self.pdf_response()).start()
        out = attestwire.generate(INVOICE, format="pdf", api_key="k")
        self.assertFalse(out.watermarked)
        self.assertEqual(out.unrendered_characters, 0)

    def test_asks_for_format_pdf(self):
        urlopen = mock.patch("attestwire._generate.urlopen", return_value=self.pdf_response()).start()
        attestwire.generate(INVOICE, format="pdf", api_key="k")
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.attestwire.com/v1/generate?format=pdf")
        self.assertEqual(json.loads(request.data), INVOICE)

    def test_page_options_wrap_the_invoice(self):
        urlopen = mock.patch("attestwire._generate.urlopen", return_value=self.pdf_response()).start()
        attestwire.generate(INVOICE, format="pdf", pdf_options={"language": "fr"}, api_key="k")
        self.assertEqual(json.loads(urlopen.call_args[0][0].data), {"invoice": INVOICE, "pdf": {"language": "fr"}})

    def test_a_200_that_is_not_a_pdf_is_an_error_not_a_file(self):
        mock.patch("attestwire._generate.urlopen", return_value=FakeResponse(b"<html>proxy</html>")).start()
        with self.assertRaises(AttestwireError):
            attestwire.generate(INVOICE, format="pdf", api_key="k")


class GenerateFailureTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

    def test_a_refused_invoice_raises_with_the_findings(self):
        mock.patch("attestwire._generate.urlopen", side_effect=http_error(422, REFUSAL)).start()
        with self.assertRaises(InvalidInvoiceError) as ctx:
            attestwire.generate(INVOICE, api_key="k")
        err = ctx.exception
        self.assertIsInstance(err, ApiError)
        self.assertEqual(err.status, 422)
        self.assertEqual(err.code, "invoice_invalid")
        self.assertIn("BR-DE-15", str(err))
        self.assertFalse(err.result.valid)
        self.assertEqual([f.fix for f in err.result.errors], ["Ask your client for their Leitweg-ID."])

    def test_other_errors_keep_the_api_error_envelope(self):
        body = {"error": "unsupported_profile", "message": "?format=pdf carries facturx-en16931 only.", "docs": "d"}
        mock.patch("attestwire._generate.urlopen", side_effect=http_error(400, body)).start()
        with self.assertRaises(ApiError) as ctx:
            attestwire.generate(INVOICE, format="pdf", api_key="k")
        self.assertNotIsInstance(ctx.exception, InvalidInvoiceError)
        self.assertEqual(ctx.exception.code, "unsupported_profile")
        self.assertEqual(ctx.exception.docs, "d")

    def test_a_422_without_findings_is_a_plain_api_error(self):
        mock.patch("attestwire._generate.urlopen", side_effect=http_error(422, b"not json")).start()
        with self.assertRaises(ApiError) as ctx:
            attestwire.generate(INVOICE, api_key="k")
        self.assertNotIsInstance(ctx.exception, InvalidInvoiceError)
        self.assertIn("HTTP 422", ctx.exception.message)

    def test_missing_api_key_raises_without_a_network_call(self):
        urlopen = mock.patch("attestwire._generate.urlopen").start()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(AttestwireError) as ctx:
                attestwire.generate(INVOICE)
        self.assertIn("generate()", str(ctx.exception))
        urlopen.assert_not_called()

    def test_connection_failure_raises_attestwire_error(self):
        mock.patch("attestwire._generate.urlopen", side_effect=URLError("no route to host")).start()
        with self.assertRaises(AttestwireError):
            attestwire.generate(INVOICE, api_key="k")

    def test_bad_arguments_fail_before_any_request(self):
        urlopen = mock.patch("attestwire._generate.urlopen").start()
        with self.assertRaises(ValueError):
            attestwire.generate(INVOICE, format="docx", api_key="k")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            attestwire.generate(INVOICE, pdf_options={"language": "de"}, api_key="k")
        with self.assertRaises(ValueError):
            attestwire.generate("not json", api_key="k")
        with self.assertRaises(TypeError):
            attestwire.generate(12345, api_key="k")  # type: ignore[arg-type]
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
