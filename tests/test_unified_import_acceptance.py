import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from legal_email_converter import unified_export


class UnifiedImportAcceptanceTests(unittest.TestCase):
    def _fake_msg_doc(self, path: Path):
        return unified_export.UnifiedDoc(
            kind="MSG",
            path=path,
            metadata={"Subject": "stub-msg"},
            content="stub msg content",
        )

    def _fake_pdf_doc(self, path: Path, *, skip_ocr: bool):
        mode = "text-layer-only" if skip_ocr else "text-layer-then-ocr"
        return unified_export.UnifiedDoc(
            kind="PDF",
            path=path,
            metadata={"ExtractionMode": mode},
            content="stub pdf content",
        )

    def _run_case(self, *, layout: list[str], input_selector: str, skip_ocr: bool):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixture"
            root.mkdir(parents=True, exist_ok=True)
            for rel in layout:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("x", encoding="utf-8")

            if input_selector == "root":
                input_path = root
            else:
                input_path = root / input_selector

            out_path = root / "result.txt"

            with mock.patch.object(unified_export, "_extract_msg_doc", side_effect=self._fake_msg_doc), mock.patch.object(
                unified_export, "_extract_pdf_doc", side_effect=self._fake_pdf_doc
            ):
                result = unified_export.run_unified_export(
                    input_path=str(input_path),
                    out_path=str(out_path),
                    skip_ocr=skip_ocr,
                )

            self.assertEqual(result["status"], "ok")
            manifest_path = Path(result["manifest"])
            self.assertTrue(out_path.exists())
            self.assertTrue(manifest_path.exists())

            discovered = unified_export.discover_documents(input_path)
            msg_count = sum(1 for p in discovered if p.suffix.lower() == ".msg")
            pdf_count = sum(1 for p in discovered if p.suffix.lower() == ".pdf")

            self.assertEqual(result["summary"]["total"], len(discovered))
            self.assertEqual(result["summary"]["msg"], msg_count)
            self.assertEqual(result["summary"]["pdf"], pdf_count)
            self.assertEqual(result["summary"]["failed"], 0)

            text = out_path.read_text(encoding="utf-8")
            self.assertEqual(text.count("=== DOCUMENT START ==="), len(discovered))

    def test_acceptance_matrix(self):
        cases = [
            {"id": "pdf_root_only", "layout": ["one.pdf"], "input_selector": "root", "modes": [True, False]},
            {"id": "msg_root_only", "layout": ["one.msg"], "input_selector": "root", "modes": [True]},
            {
                "id": "mixed_root",
                "layout": ["one.msg", "one.pdf"],
                "input_selector": "root",
                "modes": [True, False],
            },
            {
                "id": "mixed_nested",
                "layout": ["level1/one.pdf", "level1/level2/one.msg"],
                "input_selector": "root",
                "modes": [True, False],
            },
            {
                "id": "single_pdf_input_file",
                "layout": ["single.pdf"],
                "input_selector": "single.pdf",
                "modes": [True, False],
            },
            {
                "id": "single_msg_input_file",
                "layout": ["single.msg"],
                "input_selector": "single.msg",
                "modes": [True],
            },
        ]

        for case in cases:
            for skip_ocr in case["modes"]:
                with self.subTest(case=case["id"], skip_ocr=skip_ocr):
                    self._run_case(
                        layout=case["layout"],
                        input_selector=case["input_selector"],
                        skip_ocr=skip_ocr,
                    )


if __name__ == "__main__":
    unittest.main()
