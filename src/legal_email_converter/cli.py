from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .export_mbox_for_llm import export_mbox_review_package
from .pdf_ingest import run_pdf_ingest, run_pdf_retry
from .unified_export import run_unified_export


def _normalize_cli_path_arg(raw: str | None) -> str | None:
    if raw is None:
        return None
    # Users often quote a path and also escape spaces/parens inside the quotes.
    return re.sub(r"\\([ ,()\[\]])", r"\1", raw)


def _resolve_cli_path(raw: str | None) -> Path | None:
    normalized = _normalize_cli_path_arg(raw)
    if normalized is None:
        return None
    return Path(normalized).expanduser().resolve()


def _require_existing_path(path: Path, *, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def _prompt_for_path(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError("A path is required.")
    return value


def _print_friendly_error(exc: Exception, args: argparse.Namespace) -> None:
    print(f"Error: {exc}", file=sys.stderr)
    print("What it means: the command could not complete with the provided inputs.", file=sys.stderr)
    print("What to do next:", file=sys.stderr)
    if isinstance(exc, FileNotFoundError):
        print("- Verify the path exists and is readable.", file=sys.stderr)
        maybe_input = getattr(args, "input", None)
        maybe_csv = getattr(args, "from_csv", None)
        if (isinstance(maybe_input, str) and "\\ " in maybe_input) or (
            isinstance(maybe_csv, str) and "\\ " in maybe_csv
        ):
            print(
                "- If the path is quoted, do not escape spaces inside the quotes "
                '(use "/path/with spaces/file.pdf", not "/path/with\\ spaces/file.pdf").',
                file=sys.stderr,
            )
    elif isinstance(exc, ValueError):
        print("- Check flag values with: legal-email-converter <command> --help", file=sys.stderr)
    elif isinstance(exc, RuntimeError):
        print("- Resolve preflight/dependency issues shown above and retry.", file=sys.stderr)
    else:
        print("- Re-run with valid paths/flags. If this persists, report the command and error.", file=sys.stderr)


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
    ingest_cmd.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Reserved for future parallel processing (current implementation runs sequentially).",
    )
    ingest_cmd.add_argument("--ocr-jobs", type=int, default=2, help="ocrmypdf --jobs value")
    ingest_cmd.add_argument("--ocr-timeout", type=int, default=1200, help="OCR timeout seconds per file")
    ingest_cmd.add_argument(
        "--max-pages",
        type=int,
        help="Sample only the first N pages per PDF (for example: 25, 50, 150).",
    )
    ingest_cmd.add_argument(
        "--progress-every",
        type=int,
        default=5,
        help="Print progress every N files (default: 5)",
    )
    ingest_cmd.add_argument(
        "--progress-style",
        choices=["plain", "rich"],
        default="plain",
        help="Progress display mode: plain log lines or rich compact spinner+counters.",
    )
    ingest_cmd.add_argument(
        "--quiet",
        action="store_true",
        help="Summary-only output (suppresses preflight and progress logs).",
    )
    ingest_cmd.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in terminal output.",
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
    retry_cmd.add_argument(
        "--max-pages",
        type=int,
        help="Sample only the first N pages per PDF during retry runs.",
    )

    unified_cmd = sub.add_parser(
        "unified-export",
        help="Create one unified text file from .msg and .pdf files in a source folder.",
    )
    unified_cmd.add_argument("--input", help="Input folder or file (.msg/.pdf). If omitted, prompts interactively.")
    unified_cmd.add_argument("--out", help="Output text file path (default: <input-folder>/unified_case_export.txt)")
    unified_cmd.add_argument("--skip-ocr", action="store_true", help="Use text layer only for PDFs (faster).")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "export-mbox":
            mbox_path = _resolve_cli_path(args.mbox)
            if mbox_path is None:
                raise ValueError("--mbox is required")
            _require_existing_path(mbox_path, label="Mbox")
            result = export_mbox_review_package(
                mbox=str(mbox_path),
                out_dir=str(_resolve_cli_path(args.out_dir)) if args.out_dir else None,
                name=args.name,
                keep_attachments=args.keep_attachments,
                keep_artifacts=args.keep_artifacts,
                force=args.force,
                skip_ocr=args.skip_ocr,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "pdf-ingest":
            input_path = _resolve_cli_path(args.input)
            if input_path is None:
                raise ValueError("--input is required")
            _require_existing_path(input_path, label="Input")
            result = run_pdf_ingest(
                input_path=str(input_path),
                profile=args.profile,
                out_dir=str(_resolve_cli_path(args.out_dir)) if args.out_dir else None,
                workers=args.workers,
                ocr_jobs=args.ocr_jobs,
                ocr_timeout=args.ocr_timeout,
                max_pages=args.max_pages,
                progress_every=args.progress_every,
                progress_style=args.progress_style,
                quiet=args.quiet,
                no_color=args.no_color,
                resume_run_id=args.resume,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "pdf-retry":
            from_csv = _resolve_cli_path(args.from_csv)
            if from_csv is None:
                raise ValueError("--from-csv is required")
            _require_existing_path(from_csv, label="CSV")
            statuses = [s.strip() for s in args.status.split(",") if s.strip()]
            result = run_pdf_retry(
                from_csv=str(from_csv),
                statuses=statuses,
                profile=args.profile,
                out_dir=str(_resolve_cli_path(args.out_dir)) if args.out_dir else None,
                ocr_jobs=args.ocr_jobs,
                ocr_timeout=args.ocr_timeout,
                max_pages=args.max_pages,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "unified-export":
            input_raw = args.input or _prompt_for_path("Path to source folder or file (.msg/.pdf): ")
            input_path = _resolve_cli_path(input_raw)
            if input_path is None:
                raise ValueError("Input path is required.")
            _require_existing_path(input_path, label="Input")
            if args.out:
                out_path = _resolve_cli_path(args.out)
                if out_path is None:
                    raise ValueError("Output path is required.")
            else:
                base_dir = input_path if input_path.is_dir() else input_path.parent
                out_path = base_dir / "unified_case_export.txt"
                print(f"Output path not provided. Using default: {out_path}")

            result = run_unified_export(
                input_path=str(input_path),
                out_path=str(out_path),
                skip_ocr=args.skip_ocr,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        parser.error(f"Unknown command: {args.command}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        _print_friendly_error(exc, args)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
