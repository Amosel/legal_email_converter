import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from legal_email_converter import cli


class CliTests(unittest.TestCase):
    def test_normalize_cli_path_arg_unescapes_quoted_space_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "with space.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            escaped = str(pdf).replace(" ", "\\ ")
            normalized = cli._normalize_cli_path_arg(escaped)
            self.assertEqual(normalized, str(pdf))

    def test_main_handles_missing_input_with_friendly_error(self):
        argv = [
            "legal-email-converter",
            "pdf-ingest",
            "--input",
            "/tmp/does\\ not\\ exist.pdf",
            "--profile",
            "quick",
        ]
        err = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                cli.main()
        self.assertEqual(cm.exception.code, 2)
        output = err.getvalue()
        self.assertIn("Error: Input not found:", output)
        self.assertIn("What it means:", output)
        self.assertIn("do not escape spaces", output)

    def test_main_normalizes_input_before_calling_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "sample file.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            escaped = str(pdf).replace(" ", "\\ ")
            argv = [
                "legal-email-converter",
                "pdf-ingest",
                "--input",
                escaped,
                "--profile",
                "quick",
            ]
            out = io.StringIO()
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                cli,
                "run_pdf_ingest",
                return_value={"status": "ok"},
            ) as ingest_mock, contextlib.redirect_stdout(out):
                cli.main()
            self.assertEqual(ingest_mock.call_args.kwargs["input_path"], str(pdf))


if __name__ == "__main__":
    unittest.main()
