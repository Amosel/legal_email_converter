#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path


def _safe_name(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_", "."}:
            keep.append(ch)
        else:
            keep.append("_")
    out = "".join(keep).strip("._")
    return out or "file"


def fetch_one(*, source_id: str, url: str, out_dir: Path, max_bytes: int, timeout: int) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": "legal-email-converter-fixture-fetcher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            clen_header = resp.headers.get("Content-Length")
            if clen_header:
                try:
                    if int(clen_header) > max_bytes:
                        return {
                            "id": source_id,
                            "url": url,
                            "status": "skipped_too_large_header",
                            "size_bytes": int(clen_header),
                            "output": "",
                        }
                except ValueError:
                    pass

            data = resp.read(max_bytes + 1)
            if len(data) > max_bytes:
                return {
                    "id": source_id,
                    "url": url,
                    "status": "skipped_too_large_body",
                    "size_bytes": len(data),
                    "output": "",
                }

            if not data.startswith(b"%PDF"):
                # Accept some servers that still return PDF without perfect header but with PDF content type.
                if "pdf" not in ctype:
                    return {
                        "id": source_id,
                        "url": url,
                        "status": "skipped_not_pdf",
                        "size_bytes": len(data),
                        "output": "",
                    }

            out_file = out_dir / f"{_safe_name(source_id)}.pdf"
            out_file.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            return {
                "id": source_id,
                "url": url,
                "status": "downloaded",
                "size_bytes": len(data),
                "sha256": digest,
                "output": str(out_file),
            }

    except urllib.error.HTTPError as exc:
        return {"id": source_id, "url": url, "status": f"http_error_{exc.code}", "size_bytes": 0, "output": ""}
    except urllib.error.URLError as exc:
        return {"id": source_id, "url": url, "status": f"url_error_{exc.reason}", "size_bytes": 0, "output": ""}
    except Exception as exc:  # pragma: no cover
        return {"id": source_id, "url": url, "status": f"error_{type(exc).__name__}", "size_bytes": 0, "output": ""}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a lean hard-PDF fixture set from public sources.")
    parser.add_argument("--sources", default="tests/hard_pdf_sources.tsv", help="TSV source list")
    parser.add_argument("--out-dir", default="tests/fixtures_local/hard_pdfs", help="Output folder")
    parser.add_argument("--max-bytes", type=int, default=2_000_000, help="Max size per file")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    source_file = (root / args.sources).resolve()
    out_dir = (root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not source_file.exists():
        raise SystemExit(f"Source list not found: {source_file}")

    rows: list[tuple[str, str, str]] = []
    with source_file.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if len(row) < 2:
                continue
            source_id = row[0].strip()
            url = row[1].strip()
            tags = row[2].strip() if len(row) > 2 else ""
            if source_id and url:
                rows.append((source_id, url, tags))

    report: list[dict[str, object]] = []
    for source_id, url, tags in rows:
        rec = fetch_one(source_id=source_id, url=url, out_dir=out_dir, max_bytes=args.max_bytes, timeout=args.timeout)
        rec["tags"] = tags
        report.append(rec)
        print(f"{source_id}: {rec['status']}")

    manifest = {
        "sources": str(source_file),
        "out_dir": str(out_dir),
        "max_bytes": args.max_bytes,
        "results": report,
        "downloaded": sum(1 for r in report if r.get("status") == "downloaded"),
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\\nDownloaded: {manifest['downloaded']} / {len(report)}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
