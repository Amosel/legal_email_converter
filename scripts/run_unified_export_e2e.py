#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legal_email_converter.unified_export import discover_documents, run_unified_export


def _count_markers(text_path: Path) -> int:
    count = 0
    with text_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.rstrip("\n") == "=== DOCUMENT START ===":
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E checks for unified-export on real directories.")
    parser.add_argument("--input", required=True, help="Input folder or file")
    parser.add_argument("--out", help="Output text file path")
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR fallback for PDF extraction")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"FAIL: input path does not exist: {input_path}")
        return 2

    out_path = Path(args.out).expanduser().resolve() if args.out else (
        (input_path if input_path.is_dir() else input_path.parent) / "unified_case_export.txt"
    )

    print("CHECK 1/6: input path exists")
    print(f"  OK: {input_path}")

    print("CHECK 2/6: discover documents")
    docs = discover_documents(input_path)
    msg_count = sum(1 for p in docs if p.suffix.lower() == ".msg")
    pdf_count = sum(1 for p in docs if p.suffix.lower() == ".pdf")
    print(f"  Found total={len(docs)} msg={msg_count} pdf={pdf_count}")
    if not docs:
        print("  FAIL: no .msg/.pdf files discovered")
        return 1

    print("CHECK 3/6: run unified export")
    result = run_unified_export(input_path=str(input_path), out_path=str(out_path), skip_ocr=args.skip_ocr)
    print("  OK: export command returned status")

    output_file = Path(str(result.get("output", out_path))).expanduser().resolve()
    manifest_file = Path(str(result.get("manifest", out_path.with_suffix(".manifest.json")))).expanduser().resolve()

    print("CHECK 4/6: output and manifest files exist")
    if not output_file.exists() or not manifest_file.exists():
        print(f"  FAIL: missing output artifacts output={output_file.exists()} manifest={manifest_file.exists()}")
        return 1
    print(f"  OK: output={output_file}")
    print(f"  OK: manifest={manifest_file}")

    print("CHECK 5/6: manifest summary matches discovery")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    summary = manifest.get("summary", {})
    if int(summary.get("total", -1)) != len(docs):
        print(f"  FAIL: manifest total={summary.get('total')} discovered={len(docs)}")
        return 1
    if int(summary.get("msg", -1)) != msg_count:
        print(f"  FAIL: manifest msg={summary.get('msg')} discovered={msg_count}")
        return 1
    if int(summary.get("pdf", -1)) != pdf_count:
        print(f"  FAIL: manifest pdf={summary.get('pdf')} discovered={pdf_count}")
        return 1
    print("  OK: summary counts match")

    print("CHECK 6/6: output block count matches discovered docs")
    marker_count = _count_markers(output_file)
    if marker_count != len(docs):
        print(f"  FAIL: document markers={marker_count} discovered={len(docs)}")
        return 1
    print(f"  OK: document markers={marker_count}")

    failed_files = manifest.get("failed_files", [])
    print("\nRESULT: PASS")
    print(f"  discovered={len(docs)} msg={msg_count} pdf={pdf_count}")
    print(f"  failed_files={len(failed_files)}")
    print(f"  output={output_file}")
    print(f"  manifest={manifest_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
