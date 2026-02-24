from __future__ import annotations

import argparse
import json

from .export_mbox_for_llm import export_mbox_review_package
from .pdf_ingest import run_pdf_ingest, run_pdf_retry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legal-email-converter",
        description="Legal Email Converter CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export_cmd = sub.add_parser(
        "export-mbox",
        help="Create a review package zip from a raw mbox file.",
    )
    export_cmd.add_argument("--mbox", required=True, help="Path to raw mbox file")
    export_cmd.add_argument("--out-dir", help="Directory for final zip output")
    export_cmd.add_argument(
        "--name",
        default="mailbox_review_package",
        help="Final package base name (without extension)",
    )
    export_cmd.add_argument(
        "--keep-attachments",
        action="store_true",
        help="Include raw attachment files in final zip.",
    )
    export_cmd.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep expanded package folder alongside zip.",
    )
    export_cmd.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing zip with same name.",
    )
    export_cmd.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Skip OCR fallback for PDFs.",
    )

    ingest_cmd = sub.add_parser(
        "pdf-ingest",
        help="Ingest PDFs with profile-based text extraction and OCR fallback.",
    )
    ingest_cmd.add_argument("--input", required=True, help="Input PDF file or directory")
    ingest_cmd.add_argument(
        "--profile",
        choices=["quick", "balanced", "thorough"],
        default="balanced",
        help=(
            "Extraction profile: quick=fast text-layer only, "
            "balanced=text-layer then OCR for low-text files, "
            "thorough=OCR all files (slowest, highest coverage)."
        ),
    )
    ingest_cmd.add_argument("--out-dir", help="Output directory for reports/artifacts")
    ingest_cmd.add_argument("--workers", type=int, default=1, help="Parallel worker count")
    ingest_cmd.add_argument("--ocr-jobs", type=int, default=2, help="ocrmypdf --jobs value")
    ingest_cmd.add_argument("--ocr-timeout", type=int, default=1200, help="OCR timeout seconds per file")
    ingest_cmd.add_argument(
        "--progress-every",
        type=int,
        default=5,
        help="Print progress every N files (default: 5)",
    )
    ingest_cmd.add_argument("--resume", help="Resume run_id from existing state")

    retry_cmd = sub.add_parser(
        "pdf-retry",
        help="Retry only selected statuses from a quality report.",
    )
    retry_cmd.add_argument("--from-csv", required=True, help="Path to quality_report.csv")
    retry_cmd.add_argument(
        "--status",
        default="failed,likely_bad_ocr",
        help="Comma-separated statuses to retry",
    )
    retry_cmd.add_argument(
        "--profile",
        choices=["quick", "balanced", "thorough"],
        default="thorough",
        help="Retry profile (default: thorough)",
    )
    retry_cmd.add_argument("--out-dir", help="Output directory for retry results")
    retry_cmd.add_argument("--ocr-jobs", type=int, default=2, help="ocrmypdf --jobs value")
    retry_cmd.add_argument("--ocr-timeout", type=int, default=1200, help="OCR timeout seconds per file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "export-mbox":
        result = export_mbox_review_package(
            mbox=args.mbox,
            out_dir=args.out_dir,
            name=args.name,
            keep_attachments=args.keep_attachments,
            keep_artifacts=args.keep_artifacts,
            force=args.force,
            skip_ocr=args.skip_ocr,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "pdf-ingest":
        result = run_pdf_ingest(
            input_path=args.input,
            profile=args.profile,
            out_dir=args.out_dir,
            workers=args.workers,
            ocr_jobs=args.ocr_jobs,
            ocr_timeout=args.ocr_timeout,
            progress_every=args.progress_every,
            resume_run_id=args.resume,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "pdf-retry":
        statuses = [s.strip() for s in args.status.split(",") if s.strip()]
        result = run_pdf_retry(
            from_csv=args.from_csv,
            statuses=statuses,
            profile=args.profile,
            out_dir=args.out_dir,
            ocr_jobs=args.ocr_jobs,
            ocr_timeout=args.ocr_timeout,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
