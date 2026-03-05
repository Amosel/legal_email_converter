import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from legal_email_converter import unified_export


class UnifiedExportTests(unittest.TestCase):
    def test_discover_documents_filters_and_sorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.msg").write_text("x", encoding="utf-8")
            (root / "a.pdf").write_text("x", encoding="utf-8")
            (root / "c.txt").write_text("x", encoding="utf-8")

            docs = unified_export.discover_documents(root)
            self.assertEqual([p.name for p in docs], ["a.pdf", "b.msg"])

    def test_run_unified_export_writes_txt_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "email.msg").write_text("not-a-real-msg", encoding="utf-8")
            (root / "doc.pdf").write_text("%PDF-1.4", encoding="utf-8")
            out = root / "out.txt"

            fake_docs = [
                unified_export.UnifiedDoc(
                    kind="MSG",
                    path=root / "email.msg",
                    metadata={"Subject": "Hello"},
                    content="Body A",
                ),
                unified_export.UnifiedDoc(
                    kind="PDF",
                    path=root / "doc.pdf",
                    metadata={"FileSizeBytes": "7"},
                    content="Body B",
                    error="",
                ),
            ]

            with mock.patch.object(unified_export, "_safe_extract", side_effect=fake_docs):
                result = unified_export.run_unified_export(input_path=str(root), out_path=str(out), skip_ocr=True)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["summary"]["total"], 2)
            self.assertTrue(out.exists())
            self.assertTrue((root / "out.manifest.json").exists())
            text = out.read_text(encoding="utf-8")
            self.assertIn("=== DOCUMENT START ===", text)
            self.assertIn("Type: MSG", text)
            self.assertIn("Type: PDF", text)

    def test_run_unified_export_requires_supported_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                unified_export.run_unified_export(
                    input_path=str(root),
                    out_path=str(root / "out.txt"),
                    skip_ocr=False,
                )


if __name__ == "__main__":
    unittest.main()
