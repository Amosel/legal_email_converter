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

            def fake_pdftotext(path: Path, *, max_pages: int | None = None) -> str:
                return "x" * 500 if path.name == "a.pdf" else ""

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", side_effect=fake_pdftotext):
                with contextlib.redirect_stdout(io.StringIO()):
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
            self.assertIn("kpis", manifest)
            self.assertIn("north_star_tto_seconds", manifest["kpis"])
            self.assertIn("decision_ready_rate", manifest["kpis"])

    def test_balanced_routes_low_text_to_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a, b = self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            def fake_pdftotext(path: Path, *, max_pages: int | None = None) -> str:
                return "x" * 500 if path.name == "a.pdf" else ""

            def fake_ocr(
                path: Path,
                ocr_output_pdf: Path,
                *,
                ocr_jobs: int,
                ocr_timeout: int,
                max_pages: int | None = None,
            ):
                return ("y" * 600, "") if path.name == "b.pdf" else ("", "")

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", side_effect=fake_pdftotext), mock.patch.object(
                pdf_ingest, "_extract_ocr", side_effect=fake_ocr
            ):
                with contextlib.redirect_stdout(io.StringIO()):
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
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", return_value="x" * 500), mock.patch.object(
                pdf_ingest, "_extract_ocr", return_value=("y" * 500, "")
            ):
                with contextlib.redirect_stdout(io.StringIO()):
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
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", return_value="x" * 500):
                with contextlib.redirect_stdout(io.StringIO()):
                    first = pdf_ingest.run_pdf_ingest(
                        input_path=str(tmp_path / "input"),
                        profile="quick",
                        out_dir=str(out_dir),
                        resume_run_id=run_id,
                        quiet=True,
                    )
                    second = pdf_ingest.run_pdf_ingest(
                        input_path=str(tmp_path / "input"),
                        profile="quick",
                        out_dir=str(out_dir),
                        resume_run_id=run_id,
                        quiet=True,
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

            def fake_ocr(
                path: Path,
                ocr_output_pdf: Path,
                *,
                ocr_jobs: int,
                ocr_timeout: int,
                max_pages: int | None = None,
            ):
                ocr_calls["count"] += 1
                if path.name == "b.pdf":
                    return "", "OCR timed out after 1s"
                return "x" * 500, ""

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", return_value=""), mock.patch.object(
                pdf_ingest, "_extract_ocr", side_effect=fake_ocr
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    first = pdf_ingest.run_pdf_ingest(
                        input_path=str(tmp_path / "input"),
                        profile="balanced",
                        out_dir=str(out_dir),
                        resume_run_id=run_id,
                        ocr_timeout=1,
                        quiet=True,
                    )
                    second = pdf_ingest.run_pdf_ingest(
                        input_path=str(tmp_path / "input"),
                        profile="balanced",
                        out_dir=str(out_dir),
                        resume_run_id=run_id,
                        ocr_timeout=1,
                        quiet=True,
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

            def fake_pdftotext(path: Path, *, max_pages: int | None = None) -> str:
                return "x" * 500 if path.name == "a.pdf" else ""

            def fake_ocr(
                path: Path,
                ocr_output_pdf: Path,
                *,
                ocr_jobs: int,
                ocr_timeout: int,
                max_pages: int | None = None,
            ):
                if path.name == "b.pdf":
                    return "", "OCR timed out after 1s"
                return "x" * 500, ""

            buf = io.StringIO()
            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", side_effect=fake_pdftotext), mock.patch.object(
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

    def test_rich_progress_falls_back_to_plain_on_non_tty(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            buf = io.StringIO()
            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", return_value="x" * 500), contextlib.redirect_stdout(buf):
                pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="quick",
                    out_dir=str(out_dir),
                    progress_style="rich",
                )

            output = buf.getvalue()
            self.assertIn("Progress style: rich requested, falling back to plain", output)
            self.assertIn("Progress: 1/2", output)

    def test_invalid_progress_style_raises(self):
        with self.assertRaises(ValueError):
            pdf_ingest.run_pdf_ingest(input_path=".", profile="quick", progress_style="fancy")

    def test_quiet_mode_shows_summary_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            def fake_pdftotext(path: Path, *, max_pages: int | None = None) -> str:
                return "x" * 500 if path.name == "a.pdf" else ""

            buf = io.StringIO()
            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", side_effect=fake_pdftotext), contextlib.redirect_stdout(buf):
                pdf_ingest.run_pdf_ingest(
                    input_path=str(tmp_path / "input"),
                    profile="quick",
                    out_dir=str(out_dir),
                    quiet=True,
                )

            output = buf.getvalue()
            self.assertNotIn("Preflight: checking dependencies", output)
            self.assertNotIn("Progress:", output)
            self.assertIn("Completed: 2 files", output)
            self.assertIn("Run health: WARN", output)
            self.assertIn("Artifacts: quality_report=", output)

    def test_run_health_priority(self):
        self.assertEqual(pdf_ingest._compute_run_health({"failed": 1}), "FAIL")
        self.assertEqual(pdf_ingest._compute_run_health({"failed": 0, "likely_bad_ocr": 1}), "WARN")
        self.assertEqual(pdf_ingest._compute_run_health({"failed": 0, "likely_bad_ocr": 0, "low_text": 1}), "WARN")
        self.assertEqual(pdf_ingest._compute_run_health({"failed": 0, "likely_bad_ocr": 0, "low_text": 0}), "PASS")

    def test_kpi_runs_csv_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=10
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", return_value="x" * 500):
                with contextlib.redirect_stdout(io.StringIO()):
                    pdf_ingest.run_pdf_ingest(
                        input_path=str(tmp_path / "input"),
                        profile="quick",
                        out_dir=str(out_dir),
                        max_pages=25,
                    )

            kpi_csv = out_dir / "kpi_runs.csv"
            self.assertTrue(kpi_csv.exists())
            rows = kpi_csv.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(rows), 2)
            self.assertIn("north_star_tto_seconds", rows[0])

    def test_max_pages_is_forwarded_and_used_for_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._create_pdf_set(tmp_path)
            out_dir = tmp_path / "out"

            with mock.patch.object(pdf_ingest, "run_preflight", return_value=[]), mock.patch.object(
                pdf_ingest, "_pdf_page_count", return_value=200
            ), mock.patch.object(pdf_ingest, "_extract_pdftotext_range", return_value="x" * 500) as extract_text:
                with contextlib.redirect_stdout(io.StringIO()):
                    pdf_ingest.run_pdf_ingest(
                        input_path=str(tmp_path / "input"),
                        profile="quick",
                        out_dir=str(out_dir),
                        max_pages=50,
                    )

            call_kwargs = [call.kwargs for call in extract_text.call_args_list]
            self.assertTrue(all(kwargs.get("max_pages") == 50 for kwargs in call_kwargs))
            manifest = self._read_manifest(out_dir)
            self.assertTrue(all(r["pages"] == 50 for r in manifest["results"]))

    def test_pdftotext_range_adds_page_flags(self):
        cp = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch("legal_email_converter.pdf_ingest.subprocess.run", return_value=cp) as run_mock:
            out = pdf_ingest._extract_pdftotext_range(Path("/tmp/x.pdf"), max_pages=25)
        self.assertEqual(out, "ok")
        cmd = run_mock.call_args.args[0]
        self.assertEqual(cmd[:5], ["pdftotext", "-f", "1", "-l", "25"])

    def test_ocr_respects_max_pages(self):
        cp = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("legal_email_converter.pdf_ingest.subprocess.run", return_value=cp) as run_mock, mock.patch.object(
            pdf_ingest, "_extract_pdftotext_range", return_value="text"
        ):
            text, err = pdf_ingest._extract_ocr(
                Path("/tmp/x.pdf"),
                Path("/tmp/y.pdf"),
                ocr_jobs=2,
                ocr_timeout=30,
                max_pages=150,
            )
        self.assertEqual(text, "text")
        self.assertEqual(err, "")
        cmd = run_mock.call_args.args[0]
        self.assertIn("--pages", cmd)
        self.assertIn("1-150", cmd)


if __name__ == "__main__":
    unittest.main()
