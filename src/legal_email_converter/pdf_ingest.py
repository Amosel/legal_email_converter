from __future__ import annotations

import csv
import json
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


STATUS_ORDER = {
    "failed": 0,
    "likely_bad_ocr": 1,
    "low_text": 2,
    "good": 3,
}


@dataclass
class PdfResult:
    file_path: str
    pages: int
    mode_used: str
    chars_extracted: int
    chars_per_page: float
    status: str
    warning: str
    retry_suggested: bool
    elapsed_seconds: float


def _require_command(name: str) -> tuple[bool, str]:
    if shutil.which(name):
        return True, ""
    if name == "pdftotext":
        return False, "Install: brew install poppler"
    if name == "ocrmypdf":
        return False, "Install: brew install ocrmypdf"
    return False, f"Missing command: {name}"


def run_preflight(profile: str) -> list[str]:
    problems: list[str] = []
    ok, msg = _require_command("pdftotext")
    if not ok:
        problems.append(msg)
    if profile in {"balanced", "thorough"}:
        ok, msg = _require_command("ocrmypdf")
        if not ok:
            problems.append(msg)
    return problems


def discover_pdfs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == ".pdf" else []
    return sorted(input_path.rglob("*.pdf"))


def _pdf_page_count(pdf_path: Path) -> int:
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return 0
        for line in result.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception:
        return 0
    return 0


def _extract_pdftotext(pdf_path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode == 0:
            return (result.stdout or "").strip()
    except Exception:
        return ""
    return ""


def _extract_ocr(
    pdf_path: Path,
    ocr_output_pdf: Path,
    *,
    ocr_jobs: int,
    ocr_timeout: int,
) -> tuple[str, str]:
    try:
        result = subprocess.run(
            ["ocrmypdf", "--force-ocr", "--jobs", str(ocr_jobs), str(pdf_path), str(ocr_output_pdf)],
            capture_output=True,
            text=True,
            timeout=ocr_timeout,
        )
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            return "", err or f"ocrmypdf failed with exit code {result.returncode}"
        text = _extract_pdftotext(ocr_output_pdf)
        return text, ""
    except subprocess.TimeoutExpired:
        return "", f"OCR timed out after {ocr_timeout}s"
    except Exception as exc:
        return "", str(exc)


def _classify(chars: int, pages: int, mode_used: str) -> tuple[str, float, bool]:
    denom = pages if pages > 0 else 1
    cpp = chars / denom
    if mode_used == "ocr" and cpp < 15:
        return "likely_bad_ocr", cpp, True
    if cpp < 40:
        return "low_text", cpp, False
    return "good", cpp, False


def _print_progress(done: int, total: int, start: float, mode: str, current: str) -> None:
    elapsed = max(time.time() - start, 0.001)
    rate = done / elapsed
    remaining = total - done
    eta = int(remaining / rate) if rate > 0 else 0
    avg = elapsed / done if done > 0 else 0.0
    print(
        f"Progress: {done}/{total} | mode={mode} | current={current} | "
        f"ETA={eta}s | avg={avg:.1f}s/file"
    )


def _write_state_line(state_file: Path, run_id: str, result: PdfResult) -> None:
    payload = {
        "run_id": run_id,
        "file_path": result.file_path,
        "status": result.status,
        "mode_used": result.mode_used,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with state_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_completed_from_state(state_file: Path) -> set[str]:
    # Track last known status per file so resume decisions use freshest outcome.
    latest_status: dict[str, str] = {}
    if not state_file.exists():
        return set()
    for line in state_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            path = row.get("file_path")
            status = row.get("status")
            if path and status:
                latest_status[str(path)] = str(status)
        except Exception:
            continue
    # Resume should retry failures; only successful/usable outcomes are skipped.
    return {path for path, status in latest_status.items() if status != "failed"}


def _write_quality_outputs(out_dir: Path, results: list[PdfResult]) -> tuple[Path, Path]:
    quality_csv = out_dir / "quality_report.csv"
    failed_json = out_dir / "failed_files.json"

    sorted_rows = sorted(
        results,
        key=lambda r: (STATUS_ORDER.get(r.status, 99), r.chars_per_page, r.file_path),
    )
    with quality_csv.open("w", encoding="utf-8", newline="") as f:
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
        for r in sorted_rows:
            w.writerow(
                [
                    r.file_path,
                    r.pages,
                    r.mode_used,
                    r.chars_extracted,
                    f"{r.chars_per_page:.2f}",
                    r.status,
                    r.warning,
                    "1" if r.retry_suggested else "0",
                    f"{r.elapsed_seconds:.2f}",
                ]
            )

    failed_rows = [
        asdict(r)
        for r in results
        if r.status in {"failed", "likely_bad_ocr"} or r.retry_suggested
    ]
    failed_json.write_text(json.dumps(failed_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return quality_csv, failed_json


def _write_manifest(
    out_dir: Path,
    run_id: str,
    profile: str,
    input_path: str,
    results: list[PdfResult],
    quality_csv: Path,
    failed_json: Path,
) -> Path:
    summary = {"good": 0, "low_text": 0, "likely_bad_ocr": 0, "failed": 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    manifest = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "input_path": input_path,
        "file_count": len(results),
        "summary": summary,
        "quality_report_csv": str(quality_csv),
        "failed_files_json": str(failed_json),
        "results": [asdict(r) for r in results],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def run_pdf_ingest(
    *,
    input_path: str,
    profile: str = "balanced",
    out_dir: str | None = None,
    workers: int = 1,
    ocr_jobs: int = 2,
    ocr_timeout: int = 1200,
    progress_every: int = 5,
    resume_run_id: str | None = None,
    selected_files: list[str] | None = None,
) -> dict[str, object]:
    if profile not in {"quick", "balanced", "thorough"}:
        raise ValueError("profile must be one of: quick, balanced, thorough")
    print("Preflight: checking dependencies and filesystem access...")
    issues = run_preflight(profile=profile)
    if issues:
        raise RuntimeError("Preflight failed:\n" + "\n".join(f"- {x}" for x in issues))

    in_path = Path(input_path).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")
    resolved_out = Path(out_dir).expanduser().resolve() if out_dir else (Path.cwd() / "output" / "pdf_ingest")
    resolved_out.mkdir(parents=True, exist_ok=True)
    run_id = resume_run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    state_dir = resolved_out / ".run_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{run_id}.jsonl"
    completed = _load_completed_from_state(state_file) if resume_run_id else set()

    files = [Path(p).expanduser().resolve() for p in selected_files] if selected_files else discover_pdfs(in_path)
    files = [p for p in files if p.exists() and p.suffix.lower() == ".pdf"]
    files = [p for p in files if str(p) not in completed]
    total = len(files)
    if total == 0:
        return {
            "status": "ok",
            "run_id": run_id,
            "message": "No PDFs to process (possibly already completed).",
            "out_dir": str(resolved_out),
        }

    progress_every = max(1, progress_every)
    print(f"Found {total} PDF(s) to process | profile={profile} | workers={workers} | ocr_jobs={ocr_jobs}")
    print("What happened: starting extraction with automatic quality checks.")
    results: list[PdfResult] = []
    started = time.time()
    temp_dir = resolved_out / ".tmp_ocr"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        prev_mode: str | None = None
        for idx, pdf in enumerate(files, start=1):
            t0 = time.time()
            pages = _pdf_page_count(pdf)
            mode_used = "text-layer"
            warning = ""

            text = _extract_pdftotext(pdf)
            chars = len(text)
            status, cpp, retry_suggested = _classify(chars, pages, mode_used)

            should_ocr = False
            if profile == "thorough":
                should_ocr = True
            elif profile == "balanced" and status == "low_text":
                should_ocr = True

            if should_ocr:
                mode_used = "ocr"
                ocr_pdf = temp_dir / f"{pdf.stem}_{idx}.ocr.pdf"
                ocr_text, err = _extract_ocr(pdf, ocr_pdf, ocr_jobs=ocr_jobs, ocr_timeout=ocr_timeout)
                if err:
                    status = "failed"
                    warning = err
                    if "timed out" in err.lower():
                        warning = (
                            f"{pdf.name}: {err}. "
                            f"Try increasing --ocr-timeout (for example: --ocr-timeout {ocr_timeout * 2})."
                        )
                    chars = 0
                    cpp = 0.0
                    retry_suggested = True
                else:
                    chars = len(ocr_text)
                    status, cpp, retry_suggested = _classify(chars, pages, mode_used)

            elapsed = time.time() - t0
            result = PdfResult(
                file_path=str(pdf),
                pages=pages,
                mode_used=mode_used,
                chars_extracted=chars,
                chars_per_page=cpp,
                status=status,
                warning=warning,
                retry_suggested=retry_suggested,
                elapsed_seconds=elapsed,
            )
            results.append(result)
            _write_state_line(state_file, run_id, result)
            should_print = (
                idx == 1
                or idx == total
                or (idx % progress_every == 0)
                or mode_used != prev_mode
                or status in {"failed", "likely_bad_ocr"}
            )
            if should_print:
                _print_progress(idx, total, started, mode_used, pdf.name)
            prev_mode = mode_used

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    quality_csv, failed_json = _write_quality_outputs(resolved_out, results)
    manifest_path = _write_manifest(
        resolved_out, run_id, profile, str(in_path), results, quality_csv, failed_json
    )

    summary = {"good": 0, "low_text": 0, "likely_bad_ocr": 0, "failed": 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    print(
        f"Completed: {len(results)} files | "
        f"good={summary['good']} low_text={summary['low_text']} "
        f"likely_bad_ocr={summary['likely_bad_ocr']} failed={summary['failed']}"
    )
    print("What it means: review low_text and likely_bad_ocr rows before downstream use.")
    print(f"Artifacts: quality_report={quality_csv} | failures={failed_json} | manifest={manifest_path}")
    if summary["failed"] > 0 or summary["likely_bad_ocr"] > 0:
        print(
            "Next step: "
            f"legal-email-converter pdf-retry --from-csv '{quality_csv}' "
            "--status failed,likely_bad_ocr --profile thorough"
        )
    else:
        print(f"Next step: continue with downstream ingestion using {quality_csv}")

    return {
        "status": "ok",
        "run_id": run_id,
        "out_dir": str(resolved_out),
        "manifest": str(manifest_path),
        "quality_report_csv": str(quality_csv),
        "failed_files_json": str(failed_json),
        "summary": summary,
    }


def run_pdf_retry(
    *,
    from_csv: str,
    statuses: list[str],
    profile: str,
    out_dir: str | None = None,
    ocr_jobs: int = 2,
    ocr_timeout: int = 1200,
) -> dict[str, object]:
    source_csv = Path(from_csv).expanduser().resolve()
    if not source_csv.exists():
        raise FileNotFoundError(f"quality report not found: {source_csv}")
    selected: list[str] = []
    with source_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") in statuses and row.get("file_path"):
                selected.append(row["file_path"])
    if not selected:
        return {"status": "ok", "message": "No files matched requested statuses."}
    return run_pdf_ingest(
        input_path=str(source_csv.parent),
        profile=profile,
        out_dir=out_dir,
        workers=1,
        ocr_jobs=ocr_jobs,
        ocr_timeout=ocr_timeout,
        selected_files=selected,
    )
