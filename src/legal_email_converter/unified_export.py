from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .export_mbox_for_llm import extract_pdf_text, extract_pdf_text_with_ocr, normalize_text
from .ollama_client import OllamaClient, query_date_signal_with_ollama


SUPPORTED_SUFFIXES = {".msg", ".pdf"}
SORT_MODES = {"path", "date_signal_then_path", "date_query_then_path"}


@dataclass
class UnifiedDoc:
    kind: str
    path: Path
    metadata: dict[str, str]
    content: str
    error: str = ""


DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(
        r"\b("
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
        r")\s+\d{1,2},\s+\d{4}\b",
        re.IGNORECASE,
    ),
]


def _base_root(input_path: Path) -> Path:
    return input_path if input_path.is_dir() else input_path.parent


def _relative_path(path: Path, *, base_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(base_root.resolve())
        return str(rel) if str(rel) else path.name
    except Exception:
        return path.name


def _topic_from_relative(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        return "Root"
    return parts[0]


def _parse_date_candidate(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        pass

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def _extract_date_from_text(text: str) -> datetime | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(0)
        parsed = _parse_date_candidate(value)
        if parsed is not None:
            return parsed
    return None


def derive_date_signal(doc: UnifiedDoc) -> dict[str, object]:
    # Highest confidence: explicit metadata date.
    meta_date = str(doc.metadata.get("Date", "")).strip()
    parsed = _parse_date_candidate(meta_date)
    if parsed is not None:
        return {"value": parsed.date().isoformat(), "source": "metadata.date", "confidence": 0.95}

    # Medium confidence: date-like token in filename/path.
    parsed = _extract_date_from_text(str(doc.path.name))
    if parsed is not None:
        return {"value": parsed.date().isoformat(), "source": "path.name", "confidence": 0.7}

    # Lower confidence: date-like token in extracted content.
    parsed = _extract_date_from_text(doc.content[:12000] if doc.content else "")
    if parsed is not None:
        return {"value": parsed.date().isoformat(), "source": "content", "confidence": 0.5}

    return {"value": "", "source": "none", "confidence": 0.0}


def _sort_docs(docs: list[UnifiedDoc], *, mode: str, date_signals: dict[str, dict[str, object]]) -> list[UnifiedDoc]:
    if mode == "path":
        return sorted(docs, key=lambda d: str(d.path).lower())

    if mode in {"date_signal_then_path", "date_query_then_path"}:
        def key(doc: UnifiedDoc) -> tuple[int, str, str]:
            signal = date_signals[str(doc.path)]
            value = str(signal.get("value", "") or "")
            unresolved = 1 if not value else 0
            return (unresolved, value, str(doc.path).lower())

        return sorted(docs, key=key)

    raise ValueError(f"Unknown sort mode: {mode}")


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


def _write_txt(out_path: Path, source: Path, docs: list[UnifiedDoc], *, base_root: Path) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Unified Export\n")
        f.write(f"GeneratedUTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Source: {source}\n")
        f.write(f"DocumentCount: {len(docs)}\n\n")

        for idx, doc in enumerate(docs, start=1):
            rel_path = _relative_path(doc.path, base_root=base_root)
            f.write("=== DOCUMENT START ===\n")
            f.write(f"Index: {idx}\n")
            f.write(f"Type: {doc.kind}\n")
            f.write(f"Path: {rel_path}\n")
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
    sort_mode: str = "path",
    date_query_provider: str = "heuristic",
    ollama_base_url: str = "http://localhost:11434/api",
    ollama_model: str = "llama3.2:3b",
) -> dict[str, object]:
    if sort_mode not in SORT_MODES:
        raise ValueError(f"sort_mode must be one of: {', '.join(sorted(SORT_MODES))}")

    in_path = Path(input_path).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")
    base_root = _base_root(in_path)

    files = discover_documents(in_path)
    if not files:
        raise ValueError(f"No .msg or .pdf files found under: {in_path}")

    out_file = Path(out_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    docs = [_safe_extract(path, skip_ocr=skip_ocr) for path in files]
    if sort_mode == "date_query_then_path":
        if date_query_provider == "ollama":
            client = OllamaClient(base_url=ollama_base_url)

            def provider(doc: UnifiedDoc) -> dict[str, object]:
                return query_date_signal_with_ollama(
                    client=client,
                    model=ollama_model,
                    kind=doc.kind,
                    relative_path=_relative_path(doc.path, base_root=base_root),
                    metadata=doc.metadata,
                    content=doc.content,
                )

        else:
            # Keep query mode operational even without external provider.
            provider = derive_date_signal

        date_signals = {str(doc.path): provider(doc) for doc in docs}
    else:
        date_signals = {str(doc.path): derive_date_signal(doc) for doc in docs}
    docs = _sort_docs(docs, mode=sort_mode, date_signals=date_signals)
    _write_txt(out_file, in_path, docs, base_root=base_root)

    file_rows: list[dict[str, object]] = []
    topic_counts: dict[str, int] = {}
    date_source_counts: dict[str, int] = {}
    failed: list[str] = []
    for idx, doc in enumerate(docs, start=1):
        date_signal = date_signals[str(doc.path)]
        rel_path = _relative_path(doc.path, base_root=base_root)
        rel_parts = Path(rel_path).parts
        folder = str(Path(rel_path).parent) if len(rel_parts) > 1 else "Root"
        subfolders = list(rel_parts[:-1]) if len(rel_parts) > 1 else []
        topic = _topic_from_relative(rel_path)
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        source = str(date_signal.get("source", "none"))
        date_source_counts[source] = date_source_counts.get(source, 0) + 1
        if doc.error:
            failed.append(rel_path)
        file_rows.append(
            {
                "index": idx,
                "kind": doc.kind,
                "relative_path": rel_path,
                "folder": folder,
                "subfolders": subfolders,
                "topic": topic,
                "content_chars": len(doc.content or ""),
                "date_signal": date_signal,
                "has_error": bool(doc.error),
                "error": doc.error,
                "metadata": doc.metadata,
            }
        )

    summary = {
        "total": len(docs),
        "msg": sum(1 for d in docs if d.kind == "MSG"),
        "pdf": sum(1 for d in docs if d.kind == "PDF"),
        "failed": len(failed),
        "topics": topic_counts,
        "date_signals": {
            "resolved": sum(1 for d in docs if date_signals[str(d.path)].get("value")),
            "unresolved": sum(1 for d in docs if not date_signals[str(d.path)].get("value")),
            "by_source": date_source_counts,
        },
    }

    manifest_path = out_file.with_suffix(".manifest.json")
    manifest = {
        "status": "ok",
        "input_root": str(base_root.name or "Root"),
        "output_file": out_file.name,
        "summary": summary,
        "failed_files": failed,
        "files": file_rows,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        **manifest,
        "input": str(in_path),
        "output": str(out_file),
        "manifest": str(manifest_path),
    }
