from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .export_mbox_for_llm import extract_pdf_text, extract_pdf_text_with_ocr, normalize_text
from .ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaModelNotFoundError,
    OllamaProtocolError,
    OllamaUnavailableError,
    query_date_signal_with_ollama,
)


SUPPORTED_SUFFIXES = {".msg", ".pdf"}
SORT_MODE_ALIASES = {
    "path": "path",
    "date-signal": "date_signal_then_path",
    "date-query": "date_query_then_path",
    "date_signal_then_path": "date_signal_then_path",
    "date_query_then_path": "date_query_then_path",
}
SORT_MODES = set(SORT_MODE_ALIASES)


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


def _sort_rows(rows: list[dict[str, object]], *, mode: str) -> list[dict[str, object]]:
    mode = SORT_MODE_ALIASES.get(mode, mode)
    if mode == "path":
        return sorted(rows, key=lambda r: str(r["relative_path"]).lower())

    if mode in {"date_signal_then_path", "date_query_then_path"}:
        def key(row: dict[str, object]) -> tuple[int, str, str]:
            signal = row.get("date_signal", {})
            value = str(signal.get("value", "") or "")
            unresolved = 1 if not value else 0
            return (unresolved, value, str(row["relative_path"]).lower())

        return sorted(rows, key=key)

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


def _write_txt(out_path: Path, source: Path, rows: list[dict[str, object]]) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Unified Export\n")
        f.write(f"GeneratedUTC: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Source: {source}\n")
        f.write(f"DocumentCount: {len(rows)}\n\n")

        for idx, row in enumerate(rows, start=1):
            metadata = row.get("metadata", {})
            content_file = Path(str(row["content_file"]))
            f.write("=== DOCUMENT START ===\n")
            f.write(f"Index: {idx}\n")
            f.write(f"Type: {row['kind']}\n")
            f.write(f"Path: {row['relative_path']}\n")
            for key, value in metadata.items():
                f.write(f"{key}: {value}\n")
            if row.get("error"):
                f.write(f"Error: {row['error']}\n")
            f.write("--- CONTENT ---\n")
            content = content_file.read_text(encoding="utf-8") if content_file.exists() else ""
            f.write(content + "\n")
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
    date_query_strict: bool = False,
    date_query_retries: int = 1,
    date_query_preflight: bool = True,
) -> dict[str, object]:
    if sort_mode not in SORT_MODES:
        raise ValueError(f"sort_mode must be one of: {', '.join(sorted(SORT_MODES))}")
    canonical_sort_mode = SORT_MODE_ALIASES[sort_mode]

    in_path = Path(input_path).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")
    base_root = _base_root(in_path)

    files = discover_documents(in_path)
    if not files:
        raise ValueError(f"No .msg or .pdf files found under: {in_path}")

    out_file = Path(out_path).expanduser().resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    file_rows: list[dict[str, object]] = []
    topic_counts: dict[str, int] = {}
    date_source_counts: dict[str, int] = {}
    failed: list[str] = []
    query_diagnostics: dict[str, object] = {
        "enabled": bool(canonical_sort_mode == "date_query_then_path"),
        "provider": date_query_provider,
        "strict": bool(date_query_strict),
        "preflight_enabled": bool(date_query_preflight),
        "retries": max(0, int(date_query_retries)),
        "preflight_ok": None,
        "preflight_error": "",
        "fallbacks": 0,
        "invalid_json_fallbacks": 0,
        "transport_errors": 0,
        "protocol_errors": 0,
        "model_not_found_errors": 0,
        "other_errors": 0,
    }
    with tempfile.TemporaryDirectory(prefix="unified_export_") as tmp_dir:
        artifact_root = Path(tmp_dir)
        provider = derive_date_signal
        if canonical_sort_mode == "date_query_then_path" and date_query_provider == "ollama":
            client = OllamaClient(base_url=ollama_base_url)
            preflight_ok = True

            if date_query_preflight:
                try:
                    client.ping()
                    models = client.list_models()
                    if models and ollama_model not in models:
                        raise OllamaModelNotFoundError(
                            f"Model '{ollama_model}' not found in Ollama tags: {', '.join(models[:10])}"
                        )
                except OllamaError as exc:
                    preflight_ok = False
                    query_diagnostics["preflight_error"] = str(exc)
                    if isinstance(exc, OllamaUnavailableError):
                        query_diagnostics["transport_errors"] = int(query_diagnostics["transport_errors"]) + 1
                    elif isinstance(exc, OllamaProtocolError):
                        query_diagnostics["protocol_errors"] = int(query_diagnostics["protocol_errors"]) + 1
                    elif isinstance(exc, OllamaModelNotFoundError):
                        query_diagnostics["model_not_found_errors"] = int(
                            query_diagnostics["model_not_found_errors"]
                        ) + 1
                    else:
                        query_diagnostics["other_errors"] = int(query_diagnostics["other_errors"]) + 1

                    if date_query_strict:
                        raise RuntimeError(f"Ollama preflight failed: {exc}") from exc
            query_diagnostics["preflight_ok"] = preflight_ok

            if not preflight_ok and not date_query_strict:
                provider = derive_date_signal
            else:

                def provider(doc: UnifiedDoc) -> dict[str, object]:
                    rel = _relative_path(doc.path, base_root=base_root)
                    retries = max(0, int(date_query_retries))
                    for attempt in range(retries + 1):
                        try:
                            result = query_date_signal_with_ollama(
                                client=client,
                                model=ollama_model,
                                kind=doc.kind,
                                relative_path=rel,
                                metadata=doc.metadata,
                                content=doc.content,
                            )
                            if (
                                str(result.get("source", "")) == "query.invalid_json"
                                and not date_query_strict
                            ):
                                query_diagnostics["invalid_json_fallbacks"] = int(
                                    query_diagnostics["invalid_json_fallbacks"]
                                ) + 1
                                query_diagnostics["fallbacks"] = int(query_diagnostics["fallbacks"]) + 1
                                fallback = derive_date_signal(doc)
                                fallback_source = str(fallback.get("source", "none"))
                                return {
                                    **fallback,
                                    "source": f"fallback.invalid_json.{fallback_source}",
                                }
                            return result
                        except OllamaError as exc:
                            if isinstance(exc, OllamaUnavailableError):
                                query_diagnostics["transport_errors"] = int(query_diagnostics["transport_errors"]) + 1
                            elif isinstance(exc, OllamaProtocolError):
                                query_diagnostics["protocol_errors"] = int(query_diagnostics["protocol_errors"]) + 1
                            elif isinstance(exc, OllamaModelNotFoundError):
                                query_diagnostics["model_not_found_errors"] = int(
                                    query_diagnostics["model_not_found_errors"]
                                ) + 1
                            else:
                                query_diagnostics["other_errors"] = int(query_diagnostics["other_errors"]) + 1

                            if attempt < retries:
                                continue
                            if date_query_strict:
                                raise RuntimeError(f"Ollama date query failed for '{rel}': {exc}") from exc

                            query_diagnostics["fallbacks"] = int(query_diagnostics["fallbacks"]) + 1
                            fallback = derive_date_signal(doc)
                            fallback_source = str(fallback.get("source", "none"))
                            return {
                                **fallback,
                                "source": f"fallback.ollama_error.{fallback_source}",
                            }

        # Pass 1: extract one file at a time, write content artifact, keep compact index rows in memory.
        for idx, path in enumerate(files, start=1):
            doc = _safe_extract(path, skip_ocr=skip_ocr)
            rel_path = _relative_path(doc.path, base_root=base_root)
            rel_parts = Path(rel_path).parts
            folder = str(Path(rel_path).parent) if len(rel_parts) > 1 else "Root"
            subfolders = list(rel_parts[:-1]) if len(rel_parts) > 1 else []
            topic = _topic_from_relative(rel_path)
            date_signal = provider(doc)
            source = str(date_signal.get("source", "none"))

            content_file = artifact_root / f"{idx:06d}.txt"
            content_file.write_text(doc.content or "", encoding="utf-8")

            topic_counts[topic] = topic_counts.get(topic, 0) + 1
            date_source_counts[source] = date_source_counts.get(source, 0) + 1
            if doc.error:
                failed.append(rel_path)

            file_rows.append(
                {
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
                    "content_file": str(content_file),
                }
            )

        # Pass 2: order compact rows and stream content from artifacts to final output.
        sorted_rows = _sort_rows(file_rows, mode=canonical_sort_mode)
        for index, row in enumerate(sorted_rows, start=1):
            row["index"] = index
        _write_txt(out_file, in_path, sorted_rows)

    summary = {
        "total": len(file_rows),
        "msg": sum(1 for r in file_rows if r.get("kind") == "MSG"),
        "pdf": sum(1 for r in file_rows if r.get("kind") == "PDF"),
        "failed": len(failed),
        "topics": topic_counts,
        "date_signals": {
            "resolved": sum(1 for r in file_rows if str(r.get("date_signal", {}).get("value", "")).strip()),
            "unresolved": sum(1 for r in file_rows if not str(r.get("date_signal", {}).get("value", "")).strip()),
            "by_source": date_source_counts,
        },
    }

    manifest_path = out_file.with_suffix(".manifest.json")
    manifest = {
        "status": "ok",
        "input_root": str(base_root.name or "Root"),
        "output_file": out_file.name,
        "sort_mode": canonical_sort_mode,
        "date_query_provider": date_query_provider,
        "date_query": query_diagnostics,
        "summary": summary,
        "failed_files": failed,
        "files": [{k: v for k, v in row.items() if k != "content_file"} for row in sorted_rows],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        **manifest,
        "input": str(in_path),
        "output": str(out_file),
        "manifest": str(manifest_path),
    }
