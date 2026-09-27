import unittest

from attestwire._detect import sniff_media_type, suffix_for


class SniffMediaTypeTests(unittest.TestCase):
    def test_pdf_magic_number(self):
        self.assertEqual(sniff_media_type(b"%PDF-1.7\n..."), "application/pdf")

    def test_xml(self):
        self.assertEqual(sniff_media_type(b"<?xml version='1.0'?><Invoice/>"), "application/xml")

    def test_xml_with_leading_whitespace(self):
        self.assertEqual(sniff_media_type(b"\n\n  <Invoice/>"), "application/xml")

    def test_xml_with_utf8_bom(self):
        self.assertEqual(sniff_media_type(b"\xef\xbb\xbf<?xml version='1.0'?><Invoice/>"), "application/xml")

    def test_json_object(self):
        self.assertEqual(sniff_media_type(b'{"profile": "xrechnung-ubl"}'), "application/json")

    def test_json_array(self):
        self.assertEqual(sniff_media_type(b"[1, 2, 3]"), "application/json")

    def test_unrecognised_falls_back_to_octet_stream(self):
        self.assertEqual(sniff_media_type(b"\x00\x01garbage"), "application/octet-stream")

    def test_empty_bytes(self):
        self.assertEqual(sniff_media_type(b""), "application/octet-stream")


class SuffixForTests(unittest.TestCase):
    def test_pdf(self):
        self.assertEqual(suffix_for(b"%PDF-1.7"), ".pdf")

    def test_xml_and_everything_else(self):
        self.assertEqual(suffix_for(b"<Invoice/>"), ".xml")
        self.assertEqual(suffix_for(b'{"a": 1}'), ".xml")


if __name__ == "__main__":
    unittest.main()
