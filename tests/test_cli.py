import json
import os
import subprocess
import unittest
from unittest import mock

import attestwire
from attestwire._exceptions import CliError

CLI_JSON_OUTPUT = {
    "engine": "@attestwire/en16931@0.12.1",
    "failOn": "error",
    "summary": {"files": 1, "failed": 0, "errors": 0, "warnings": 0, "information": 0},
    "results": [
        {
            "file": "/tmp/whatever.xml",
            "syntax": "ubl",
            "profile": "xrechnung-ubl",
            "container": None,
            "unmapped": [],
            "findings": [],
            "passed": True,
        }
    ],
}

CLI_JSON_OUTPUT_FAILING = {
    "engine": "@attestwire/en16931@0.12.1",
    "failOn": "error",
    "summary": {"files": 1, "failed": 1, "errors": 1, "warnings": 0, "information": 0},
    "results": [
        {
            "file": "/tmp/whatever.xml",
            "syntax": "ubl",
            "profile": "xrechnung-ubl",
            "container": None,
            "unmapped": [],
            "findings": [
                {
                    "rule": "BR-DE-15",
                    "field": "BT-10",
                    "severity": "fatal",
                    "message": "A German public-sector buyer requires a Leitweg-ID.",
                    "fix": "Set buyerReference to the Leitweg-ID your client gave you.",
                    "location": {"line": 9, "column": 2, "path": "/ubl:Invoice", "exact": True},
                }
            ],
            "passed": False,
        }
    ],
}


def _completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["npx"], returncode=returncode, stdout=stdout, stderr=stderr)


class CliSuccessTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

    def test_valid_document(self):
        mock.patch("attestwire._cli.subprocess.run", return_value=_completed(json.dumps(CLI_JSON_OUTPUT))).start()
        result = attestwire.validate(b"<Invoice/>", mode="cli")
        self.assertTrue(result.valid)
        self.assertEqual(result.findings, [])
        self.assertEqual(result.profile, "xrechnung-ubl")
        self.assertEqual(result.syntax, "ubl")
        self.assertEqual(result.mode, "cli")

    def test_invalid_document_maps_findings(self):
        mock.patch("attestwire._cli.subprocess.run", return_value=_completed(json.dumps(CLI_JSON_OUTPUT_FAILING), returncode=1)).start()
        result = attestwire.validate(b"<Invoice/>", mode="cli")
        self.assertFalse(result.valid)
        self.assertEqual(len(result.errors), 1)
        finding = result.errors[0]
        self.assertEqual(finding.rule, "BR-DE-15")
        self.assertEqual(finding.location.line, 9)
        self.assertEqual(finding.location.path, "/ubl:Invoice")

    def test_no_api_key_needed(self):
        # mode="cli" must not require api_key at all, and must not touch the environment.
        mock.patch("attestwire._cli.subprocess.run", return_value=_completed(json.dumps(CLI_JSON_OUTPUT))).start()
        with mock.patch.dict(os.environ, {}, clear=True):
            result = attestwire.validate(b"<Invoice/>", mode="cli")
        self.assertTrue(result.valid)

    def test_command_line_built_correctly_with_defaults(self):
        run = mock.patch("attestwire._cli.subprocess.run", return_value=_completed(json.dumps(CLI_JSON_OUTPUT))).start()
        attestwire.validate(b"<Invoice/>", mode="cli")
        args, kwargs = run.call_args
        command = args[0]
        self.assertEqual(command[:3], ["npx", "--yes", "@attestwire/en16931"])
        self.assertEqual(command[3], "--json")
        self.assertTrue(command[4].endswith(".xml"))
        self.assertTrue(kwargs.get("capture_output"))
        self.assertTrue(kwargs.get("text"))

    def test_pdf_bytes_get_a_pdf_suffix_temp_file(self):
        run = mock.patch("attestwire._cli.subprocess.run", return_value=_completed(json.dumps(CLI_JSON_OUTPUT))).start()
        attestwire.validate(b"%PDF-1.7 ...", mode="cli")
        command = run.call_args[0][0]
        self.assertTrue(command[4].endswith(".pdf"))

    def test_custom_node_command_and_package_spec(self):
        run = mock.patch("attestwire._cli.subprocess.run", return_value=_completed(json.dumps(CLI_JSON_OUTPUT))).start()
        attestwire.validate(b"<Invoice/>", mode="cli", node_command="/usr/local/bin/npx", package_spec="@attestwire/en16931@0.12.1")
        command = run.call_args[0][0]
        self.assertEqual(command[0], "/usr/local/bin/npx")
        self.assertEqual(command[2], "@attestwire/en16931@0.12.1")

    def test_temp_file_is_written_and_cleaned_up(self):
        seen_path = {}

        def fake_run(command, **kwargs):
            tmp_path = command[4]
            seen_path["path"] = tmp_path
            with open(tmp_path, "rb") as fh:
                seen_path["contents"] = fh.read()
            return _completed(json.dumps(CLI_JSON_OUTPUT))

        mock.patch("attestwire._cli.subprocess.run", side_effect=fake_run).start()
        attestwire.validate(b"<Invoice>hello</Invoice>", mode="cli")
        self.assertEqual(seen_path["contents"], b"<Invoice>hello</Invoice>")
        self.assertFalse(os.path.exists(seen_path["path"]))


class CliFailureTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

    def test_node_not_found(self):
        mock.patch("attestwire._cli.subprocess.run", side_effect=FileNotFoundError()).start()
        with self.assertRaises(CliError) as ctx:
            attestwire.validate(b"<Invoice/>", mode="cli")
        self.assertIn("Node.js", str(ctx.exception))

    def test_timeout(self):
        mock.patch(
            "attestwire._cli.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=1),
        ).start()
        with self.assertRaises(CliError):
            attestwire.validate(b"<Invoice/>", mode="cli", timeout=1)

    def test_non_json_stdout_includes_stderr_in_the_error(self):
        mock.patch(
            "attestwire._cli.subprocess.run",
            return_value=_completed("", returncode=1, stderr="npm error network timeout"),
        ).start()
        with self.assertRaises(CliError) as ctx:
            attestwire.validate(b"<Invoice/>", mode="cli")
        self.assertIn("npm error network timeout", str(ctx.exception))

    def test_empty_results_array(self):
        mock.patch(
            "attestwire._cli.subprocess.run",
            return_value=_completed(json.dumps({"results": []})),
        ).start()
        with self.assertRaises(CliError):
            attestwire.validate(b"<Invoice/>", mode="cli")

    def test_temp_file_cleaned_up_even_on_failure(self):
        seen_path = {}

        def fake_run(command, **kwargs):
            seen_path["path"] = command[4]
            raise subprocess.TimeoutExpired(cmd=command, timeout=1)

        mock.patch("attestwire._cli.subprocess.run", side_effect=fake_run).start()
        with self.assertRaises(CliError):
            attestwire.validate(b"<Invoice/>", mode="cli", timeout=1)
        self.assertFalse(os.path.exists(seen_path["path"]))


if __name__ == "__main__":
    unittest.main()
