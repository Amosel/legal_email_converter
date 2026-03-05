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
            self.assertIn("Path: email.msg", text)
            self.assertIn("Path: doc.pdf", text)

            manifest = (root / "out.manifest.json").read_text(encoding="utf-8")
            self.assertIn('"relative_path": "email.msg"', manifest)
            self.assertIn('"relative_path": "doc.pdf"', manifest)
            self.assertIn('"topic": "Root"', manifest)
            self.assertIn('"date_signal"', manifest)
            self.assertIn('"date_signals"', manifest)

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

    def test_sort_mode_date_signal_then_path_orders_by_inferred_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Keep filenames intentionally out of date order to prove sort is date-driven.
            (root / "zeta.pdf").write_text("%PDF-1.4", encoding="utf-8")
            (root / "alpha.msg").write_text("x", encoding="utf-8")
            out = root / "out.txt"

            fake_docs = [
                unified_export.UnifiedDoc(
                    kind="PDF",
                    path=root / "zeta.pdf",
                    metadata={},
                    content="Filed on 2025-05-01",
                ),
                unified_export.UnifiedDoc(
                    kind="MSG",
                    path=root / "alpha.msg",
                    metadata={"Date": "2024-01-01 09:30:00-05:00"},
                    content="",
                ),
            ]

            with mock.patch.object(unified_export, "_safe_extract", side_effect=fake_docs):
                unified_export.run_unified_export(
                    input_path=str(root),
                    out_path=str(out),
                    skip_ocr=True,
                    sort_mode="date_signal_then_path",
                )

            text = out.read_text(encoding="utf-8")
            self.assertLess(text.find("Path: alpha.msg"), text.find("Path: zeta.pdf"))

    def test_sort_mode_date_query_then_path_uses_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.pdf").write_text("%PDF-1.4", encoding="utf-8")
            (root / "a.msg").write_text("x", encoding="utf-8")
            out = root / "out.txt"

            fake_docs = [
                unified_export.UnifiedDoc(kind="PDF", path=root / "b.pdf", metadata={}, content=""),
                unified_export.UnifiedDoc(kind="MSG", path=root / "a.msg", metadata={}, content=""),
            ]

            def fake_query(*args, **kwargs):
                rel = kwargs.get("relative_path", "")
                if rel == "b.pdf":
                    return {"value": "2020-01-01", "source": "query.path", "confidence": 0.9}
                return {"value": "2021-01-01", "source": "query.path", "confidence": 0.9}

            with mock.patch.object(unified_export, "_safe_extract", side_effect=fake_docs), mock.patch.object(
                unified_export, "query_date_signal_with_ollama", side_effect=fake_query
            ):
                unified_export.run_unified_export(
                    input_path=str(root),
                    out_path=str(out),
                    skip_ocr=True,
                    sort_mode="date_query_then_path",
                    date_query_provider="ollama",
                )

            text = out.read_text(encoding="utf-8")
            self.assertLess(text.find("Path: b.pdf"), text.find("Path: a.msg"))


if __name__ == "__main__":
    unittest.main()
