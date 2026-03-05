from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .export_mbox_for_llm import extract_pdf_text, extract_pdf_text_with_ocr, normalize_text


SUPPORTED_SUFFIXES = {".msg", ".pdf"}


@dataclass
class UnifiedDoc:
    kind: str
    path: Path
    metadata: dict[str, str]
    content: str
    error: str = ""


def discover_documents(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_SUFFIXES else []

    files = [p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    return sorted(files, key=lambda p: str(p).lower())


def _extract_msg_doc(path: Path) -> UnifiedDoc:
    try:
        import extract_msg  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("extract-msg is required to parse .msg files. Install with: pip install extract-msg") from exc

    msg = extract_msg.Message(str(path))
    try:
        body = normalize_text(str(msg.body) if msg.body else "")
        metadata = {
            "Date": str(msg.date) if msg.date else "",
            "From": str(msg.sender) if msg.sender else "",
            "To": str(msg.to) if msg.to else "",
            "Cc": str(msg.cc) if msg.cc else "",
            "Subject": str(msg.subject) if msg.subject else "",
        }
        return UnifiedDoc(kind="MSG", path=path, metadata=metadata, content=body)
    finally:
        close_fn = getattr(msg, "close", None)
        if callable(close_fn):
            close_fn()


def _extract_pdf_doc(path: Path, *, skip_ocr: bool) -> UnifiedDoc:
    text = extract_pdf_text(path) if skip_ocr else extract_pdf_text_with_ocr(path)
    metadata = {
        "FileSizeBytes": str(path.stat().st_size),
        "ExtractionMode": "text-layer-only" if skip_ocr else "text-layer-then-ocr",
    }
    return UnifiedDoc(kind="PDF", path=path, metadata=metadata, content=normalize_text(text))


def _safe_extract(path: Path, *, skip_ocr: bool) -> UnifiedDoc:
    try:
        if path.suffix.lower() == ".msg":
            return _extract_msg_doc(path)
        if path.suffix.lower() == ".pdf":
            return _extract_pdf_doc(path, skip_ocr=skip_ocr)
        return UnifiedDoc(kind="UNKNOWN", path=path, metadata={}, content="", error="Unsupported file type")
    except Exception as exc:
        return UnifiedDoc(kind=path.suffix.lower().lstrip(".").upper(), path=path, metadata={}, content="", error=str(exc))


def _write_txt(out_path: Path, source: Path, docs: list[UnifiedDoc]) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Unified Export\n")
        f.write(f"GeneratedUTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Source: {source}\n")
        f.write(f"DocumentCount: {len(docs)}\n\n")

        for idx, doc in enumerate(docs, start=1):
            f.write("=== DOCUMENT START ===\n")
            f.write(f"Index: {idx}\n")
            f.write(f"Type: {doc.kind}\n")
            f.write(f"Path: {doc.path}\n")
            for key, value in doc.metadata.items():
                f.write(f"{key}: {value}\n")
            if doc.error:
                f.write(f"Error: {doc.error}\n")
            f.write("--- CONTENT ---\n")
            f.write((doc.content or "") + "\n")
            f.write("=== DOCUMENT END ===\n\n")


def run_unified_export(
    *,
    input_path: str,
    out_path: str,
    skip_ocr: bool = False,
) -> dict[str, object]:
    in_path = Path(input_path).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")

    files = discover_documents(in_path)
    if not files:
        raise ValueError(f"No .msg or .pdf files found under: {in_path}")

    out_file = Path(out_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    docs = [_safe_extract(path, skip_ocr=skip_ocr) for path in files]
    _write_txt(out_file, in_path, docs)

    failed = [str(d.path) for d in docs if d.error]
    summary = {
        "total": len(docs),
        "msg": sum(1 for d in docs if d.kind == "MSG"),
        "pdf": sum(1 for d in docs if d.kind == "PDF"),
        "failed": len(failed),
    }

    manifest_path = out_file.with_suffix(".manifest.json")
    manifest = {
        "status": "ok",
        "input": str(in_path),
        "output": str(out_file),
        "summary": summary,
        "failed_files": failed,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest["manifest"] = str(manifest_path)
    return manifest
