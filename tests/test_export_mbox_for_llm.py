import base64
import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "5_export_mbox_for_llm.py"
)
SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def load_export_module():
    spec = importlib.util.spec_from_file_location("export_mbox_for_llm", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def wrap_mbox_message(raw_message: str, envelope_from: str = "sender@example.com") -> str:
    return (
        f"From {envelope_from} Mon Jan 01 00:00:00 2024\n"
        f"{raw_message.rstrip()}\n\n"
    )


class ExportMboxForLlmTests(unittest.TestCase):
    def _run_export(self, module, mbox_content: str, keep_attachments: bool = False):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mbox_path = tmp_path / "sample.mbox"
            out_dir = tmp_path / "out"
            package_name = "mailbox_review_package"
            mbox_path.write_text(mbox_content, encoding="utf-8")

            argv = [
                "prog",
                "--mbox",
                str(mbox_path),
                "--out-dir",
                str(out_dir),
                "--name",
                package_name,
                "--force",
            ]
            if keep_attachments:
                argv.append("--keep-attachments")

            with mock.patch.object(sys, "argv", argv):
                module.main()

            zip_path = out_dir / f"{package_name}.zip"
            self.assertTrue(zip_path.exists())

            with zipfile.ZipFile(zip_path, "r") as zf:
                names = set(zf.namelist())
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                review = zf.read("review.md").decode("utf-8")
                corpus_lines = [
                    json.loads(line)
                    for line in zf.read("llm_corpus.jsonl").decode("utf-8").splitlines()
                    if line.strip()
                ]
            return names, manifest, review, corpus_lines

    def test_smoke_single_package_with_expected_files(self):
        module = load_export_module()

        attachment_text = "This is attached text."
        attachment_b64 = base64.b64encode(attachment_text.encode("utf-8")).decode("ascii")

        msg1 = """Date: Mon, 01 Jan 2024 10:00:00 +0000
From: Alice <alice@example.com>
To: Bob <bob@example.com>
Subject: First
Message-ID: <m1@example.com>
Content-Type: text/plain; charset="utf-8"

Hello from message one.
"""
        msg2 = f"""Date: Mon, 01 Jan 2024 11:00:00 +0000
From: Carol <carol@example.com>
To: Dave <dave@example.com>
Subject: Second
Message-ID: <m2@example.com>
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="B"

--B
Content-Type: text/plain; charset="utf-8"

Body with attachment.
--B
Content-Type: text/plain; charset="utf-8"; name="notes.txt"
Content-Disposition: attachment; filename="notes.txt"
Content-Transfer-Encoding: base64

{attachment_b64}
--B--
"""
        names, manifest, review, corpus = self._run_export(
            module, wrap_mbox_message(msg1) + wrap_mbox_message(msg2)
        )

        self.assertIn("manifest.json", names)
        self.assertIn("review.md", names)
        self.assertIn("llm_corpus.jsonl", names)
        self.assertEqual(manifest["email_count"], 2)
        self.assertFalse(manifest["includes_raw_attachments"])
        self.assertIn("Hello from message one.", review)

        email_docs = [d for d in corpus if d.get("doc_type") == "email"]
        self.assertEqual(len(email_docs), 2)

    def test_decodes_subject_and_extracts_html_body(self):
        module = load_export_module()

        msg = """Date: Tue, 02 Jan 2024 09:00:00 +0000
From: Encoded <enc@example.com>
To: Reader <reader@example.com>
Subject: =?UTF-8?Q?Policy_=E2=9C=93?=
Message-ID: <m3@example.com>
MIME-Version: 1.0
Content-Type: text/html; charset="utf-8"

<html><body><h1>Coverage</h1><p>Deductible details.</p></body></html>
"""
        _, manifest, review, corpus = self._run_export(module, wrap_mbox_message(msg))

        self.assertEqual(manifest["email_count"], 1)
        self.assertIn("Policy ✓", review)
        self.assertIn("Coverage", review)
        self.assertIn("Deductible details.", review)
        self.assertEqual(corpus[0]["doc_type"], "email")

    def test_pdf_attachment_generates_attachment_doc_and_optional_raw_files(self):
        module = load_export_module()
        package_module = importlib.import_module("legal_email_converter.export_mbox_for_llm")

        pdf_bytes = b"%PDF-1.4\\n% minimal test payload\\n"
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

        msg = f"""Date: Wed, 03 Jan 2024 12:00:00 +0000
From: Adjuster <adj@example.com>
To: Client <client@example.com>
Subject: PDF Included
Message-ID: <m4@example.com>
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="P"

--P
Content-Type: text/plain; charset="utf-8"

Please see attached PDF.
--P
Content-Type: application/pdf; name="claim.pdf"
Content-Disposition: attachment; filename="claim.pdf"
Content-Transfer-Encoding: base64

{pdf_b64}
--P--
"""
        with mock.patch.object(
            package_module, "extract_pdf_text_with_ocr", return_value="Extracted PDF text"
        ):
            names, manifest, _, corpus = self._run_export(
                module, wrap_mbox_message(msg), keep_attachments=True
            )

        attachment_docs = [d for d in corpus if d.get("doc_type") == "attachment"]
        self.assertEqual(len(attachment_docs), 1)
        self.assertIn("Extracted PDF text", attachment_docs[0]["text"])
        self.assertTrue(manifest["includes_raw_attachments"])
        self.assertTrue(any(n.startswith("attachments/email_") for n in names))

    def test_defaults_output_next_to_input_when_out_dir_not_provided(self):
        module = load_export_module()
        msg = """Date: Thu, 04 Jan 2024 08:00:00 +0000
From: A <a@example.com>
To: B <b@example.com>
Subject: Default Out
Message-ID: <m5@example.com>
Content-Type: text/plain; charset="utf-8"

Hello.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mbox_path = tmp_path / "sample.mbox"
            mbox_path.write_text(wrap_mbox_message(msg), encoding="utf-8")
            zip_path = tmp_path / "mailbox_review_package.zip"

            with mock.patch.object(
                sys,
                "argv",
                [
                    "prog",
                    "--mbox",
                    str(mbox_path),
                    "--name",
                    "mailbox_review_package",
                    "--force",
                    "--skip-ocr",
                ],
            ):
                module.main()

            self.assertTrue(zip_path.exists())

    def test_programmatic_export_function_non_interactive(self):
        module = load_export_module()
        msg = """Date: Fri, 05 Jan 2024 08:00:00 +0000
From: Programmatic <p@example.com>
To: Caller <c@example.com>
Subject: API Call
Message-ID: <m6@example.com>
Content-Type: text/plain; charset="utf-8"

Hello via function call.
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mbox_path = tmp_path / "sample.mbox"
            out_dir = tmp_path / "out"
            mbox_path.write_text(wrap_mbox_message(msg), encoding="utf-8")

            result = module.export_mbox_review_package(
                mbox=str(mbox_path),
                out_dir=str(out_dir),
                name="programmatic_package",
                force=True,
                skip_ocr=True,
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["email_count"], 1)
            self.assertTrue((out_dir / "programmatic_package.zip").exists())


if __name__ == "__main__":
    unittest.main()
