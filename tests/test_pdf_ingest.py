import csv
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from legal_email_converter import pdf_ingest


class PdfIngestTests(unittest.TestCase):
    def _create_pdf_set(self, tmp_path: Path) -> tuple[Path, Path]:
        root = tmp_path / "input"
        root.mkdir(parents=True, exist_ok=True)
        a = root / "a.pdf"
        b = root / "b.pdf"
        a.write_bytes(b"%PDF-1.4 a")
        b.write_bytes(b"%PDF-1.4 b")
        return a, b

    def _read_manifest(self, out_dir: Path) -> dict:
        return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

    def test_quick_profile_mixed_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a, b = self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            def fake_pdftotext(path: Path) -> str:
                return "x" * 500 if path.name == "a.pdf" else ""

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext", side_effect=fake_pdftotext):
                result = pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="quick",
                    out_dir=str(out_dir),
                )

            self.assertEqual(result["status"], "ok")
            manifest = self._read_manifest(out_dir)
            self.assertEqual(manifest["summary"]["good"], 1)
            self.assertEqual(manifest["summary"]["low_text"], 1)
            self.assertEqual(manifest["summary"]["failed"], 0)

    def test_balanced_routes_low_text_to_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a, b = self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            def fake_pdftotext(path: Path) -> str:
                return "x" * 500 if path.name == "a.pdf" else ""

            def fake_ocr(path: Path, ocr_output_pdf: Path, *, ocr_jobs: int, ocr_timeout: int):
                return ("y" * 600, "") if path.name == "b.pdf" else ("", "")

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext", side_effect=fake_pdftotext), mock.patch.object(
                pdf_ingest, "_extract_ocr", side_effect=fake_ocr
            ):
                pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="balanced",
                    out_dir=str(out_dir),
                )

            manifest = self._read_manifest(out_dir)
            by_file = {Path(r["file_path"]).name: r for r in manifest["results"]}
            self.assertEqual(by_file["a.pdf"]["mode_used"], "text-layer")
            self.assertEqual(by_file["b.pdf"]["mode_used"], "ocr")
            self.assertEqual(by_file["b.pdf"]["status"], "good")

    def test_thorough_ocrs_all_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext", return_value="x" * 500), mock.patch.object(
                pdf_ingest, "_extract_ocr", return_value=("y" * 500, "")
            ):
                pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="thorough",
                    out_dir=str(out_dir),
                )

            manifest = self._read_manifest(out_dir)
            self.assertTrue(all(r["mode_used"] == "ocr" for r in manifest["results"]))

    def test_retry_filters_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "quality_report.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "file_path",
                        "pages",
                        "mode_used",
                        "chars_extracted",
                        "chars_per_page",
                        "status",
                        "warning",
                        "retry_suggested",
                        "elapsed_seconds",
                    ]
                )
                w.writerow(["/x/a.pdf", 1, "ocr", 0, 0, "failed", "", 1, 0.1])
                w.writerow(["/x/b.pdf", 1, "text-layer", 100, 100, "good", "", 0, 0.1])

            with mock.patch.object(pdf_ingest, "run_pdf_ingest", return_value={"status": "ok"}) as m:
                out = pdf_ingest.run_pdf_retry(
                    from_csv=str(csv_path),
                    statuses=["failed"],
                    profile="thorough",
                    out_dir=str(tmp_path / "out"),
                )
            self.assertEqual(out["status"], "ok")
            kwargs = m.call_args.kwargs
            self.assertEqual(kwargs["selected_files"], ["/x/a.pdf"])

    def test_resume_skips_completed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"
            run_id = "resume_test"

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext", return_value="x" * 500):
                first = pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="quick",
                    out_dir=str(out_dir),
                    resume_run_id=run_id,
                )
                second = pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="quick",
                    out_dir=str(out_dir),
                    resume_run_id=run_id,
                )

            self.assertEqual(first["status"], "ok")
            self.assertEqual(second["status"], "ok")
            self.assertIn("No PDFs to process", second["message"])

    def test_resume_retries_failed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"
            run_id = "resume_failed"
            ocr_calls = {"count": 0}

            def fake_ocr(path: Path, ocr_output_pdf: Path, *, ocr_jobs: int, ocr_timeout: int):
                ocr_calls["count"] += 1
                if path.name == "b.pdf":
                    return "", "OCR timed out after 1s"
                return "x" * 500, ""

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext", return_value=""), mock.patch.object(
                pdf_ingest, "_extract_ocr", side_effect=fake_ocr
            ):
                first = pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="balanced",
                    out_dir=str(out_dir),
                    resume_run_id=run_id,
                    ocr_timeout=1,
                )
                second = pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="balanced",
                    out_dir=str(out_dir),
                    resume_run_id=run_id,
                    ocr_timeout=1,
                )

            self.assertEqual(first["status"], "ok")
            self.assertEqual(second["status"], "ok")
            self.assertNotIn("message", second)
            self.assertGreaterEqual(ocr_calls["count"], 3)

    def test_summary_copy_includes_artifacts_and_retry_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            def fake_pdftotext(path: Path) -> str:
                return "x" * 500 if path.name == "a.pdf" else ""

            def fake_ocr(path: Path, ocr_output_pdf: Path, *, ocr_jobs: int, ocr_timeout: int):
                if path.name == "b.pdf":
                    return "", "OCR timed out after 1s"
                return "x" * 500, ""

            buf = io.StringIO()
            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext", side_effect=fake_pdftotext), mock.patch.object(
                pdf_ingest, "_extract_ocr", side_effect=fake_ocr
            ), contextlib.redirect_stdout(buf):
                pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="balanced",
                    out_dir=str(out_dir),
                    ocr_timeout=1,
                )

            output = buf.getvalue()
            self.assertIn("What happened: starting extraction with automatic quality checks.", output)
            self.assertIn("What it means: review low_text and likely_bad_ocr rows", output)
            self.assertIn("Artifacts: quality_report=", output)
            self.assertIn("legal-email-converter pdf-retry --from-csv", output)


if __name__ == "__main__":
    unittest.main()
