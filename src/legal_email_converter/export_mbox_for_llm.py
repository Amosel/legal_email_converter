#!/usr/bin/env python3
"""
Export a raw mbox file into a single review package for humans and LLMs.

Final product:
  - mailbox_review_package.zip
    - review.md
    - llm_corpus.jsonl
    - manifest.json
    - attachments/ (optional, only with --keep-attachments)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Generator

_CMD_CACHE: dict[str, bool] = {}


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


@dataclass
class AttachmentInfo:
    filename: str
    mime_type: str
    size_bytes: int
    relative_path: str
    extracted_text: str


@dataclass
class EmailRecord:
    email_id: str
    date: str
    sender: str
    to: str
    cc: str
    bcc: str
    subject: str
    message_id: str
    envelope_from: str
    body_text: str
    attachments: list[AttachmentInfo]


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def html_to_text(value: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(value)
    return normalize_text(stripper.get_text())


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return cleaned or fallback


def command_exists(name: str) -> bool:
    if name in _CMD_CACHE:
        return _CMD_CACHE[name]
    exists = subprocess.run(["which", name], capture_output=True).returncode == 0
    _CMD_CACHE[name] = exists
    return exists


def parse_mbox_messages(path: Path) -> Generator[tuple[str, bytes], None, None]:
    envelope = ""
    current_lines: list[bytes] = []

    with path.open("rb") as f:
        for line in f:
            if line.startswith(b"From "):
                if current_lines:
                    yield envelope, b"".join(current_lines)
                    current_lines = []
                envelope = line.decode("utf-8", errors="replace").rstrip("\n")
                continue
            current_lines.append(line)

    if current_lines:
        yield envelope, b"".join(current_lines)


def decode_part_text(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return normalize_text(raw if isinstance(raw, str) else "")

    charset = part.get_content_charset() or "utf-8"
    for enc in [charset, "utf-8", "latin-1"]:
        try:
            return normalize_text(payload.decode(enc, errors="replace"))
        except Exception:
            continue
    return ""


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return normalize_text("\n".join(pages))
    except Exception:
        pass

    if not command_exists("pdftotext"):
        return ""

    try:
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return normalize_text(result.stdout)
    except Exception:
        return ""
    return ""


def extract_pdf_text_with_ocr(path: Path) -> str:
    text = extract_pdf_text(path)
    if text:
        return text

    if command_exists("ocrmypdf") and command_exists("pdftotext"):
        try:
            with tempfile.TemporaryDirectory(prefix="mbox_pdf_ocr_") as tmp_dir:
                tmp_out = Path(tmp_dir) / f"ocr_{path.name}"
                result = subprocess.run(
                    ["ocrmypdf", "--force-ocr", str(path), str(tmp_out)],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if result.returncode == 0 and tmp_out.exists():
                    text_result = subprocess.run(
                        ["pdftotext", str(tmp_out), "-"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if text_result.returncode == 0:
                        return normalize_text(text_result.stdout)
        except Exception:
            return ""

    if not (command_exists("pdftoppm") and command_exists("tesseract")):
        return ""

    try:
        with tempfile.TemporaryDirectory(prefix="mbox_pdf_img_ocr_") as tmp_dir:
            img_prefix = Path(tmp_dir) / "page"
            render = subprocess.run(
                ["pdftoppm", "-r", "300", "-png", str(path), str(img_prefix)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if render.returncode != 0:
                return ""

            image_files = sorted(Path(tmp_dir).glob("page-*.png"))
            if not image_files:
                return ""

            chunks: list[str] = []
            for img in image_files:
                ocr = subprocess.run(
                    ["tesseract", str(img), "stdout"],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if ocr.returncode == 0 and ocr.stdout.strip():
                    chunks.append(ocr.stdout)

            return normalize_text("\n\n".join(chunks))
    except Exception:
        return ""


def extract_email_body(msg) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            disposition = (part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            ctype = (part.get_content_type() or "").lower()
            if ctype == "text/plain":
                plain_parts.append(decode_part_text(part))
            elif ctype == "text/html":
                html_parts.append(html_to_text(decode_part_text(part)))
    else:
        ctype = (msg.get_content_type() or "").lower()
        if ctype == "text/plain":
            plain_parts.append(decode_part_text(msg))
        elif ctype == "text/html":
            html_parts.append(html_to_text(decode_part_text(msg)))

    body = "\n\n".join([p for p in plain_parts if p]).strip()
    if body:
        return body
    return "\n\n".join([p for p in html_parts if p]).strip()


def extract_attachments(
    msg,
    attachments_root: Path,
    email_idx: int,
    keep_raw_attachments: bool,
    skip_ocr: bool,
) -> list[AttachmentInfo]:
    attachments: list[AttachmentInfo] = []
    email_attachment_dir = attachments_root / f"email_{email_idx:05d}"
    email_attachment_dir.mkdir(parents=True, exist_ok=True)

    att_idx = 0
    for part in msg.walk():
        disposition = (part.get_content_disposition() or "").lower()
        filename = decode_header_value(part.get_filename())
        is_attachment = disposition == "attachment" or bool(filename)
        if not is_attachment:
            continue

        payload = part.get_payload(decode=True) or b""
        att_idx += 1
        base_name = safe_name(filename, f"attachment_{att_idx:03d}.bin")
        file_path = email_attachment_dir / base_name
        file_path.write_bytes(payload)

        mime_type = (part.get_content_type() or "application/octet-stream").lower()
        extracted_text = ""

        if mime_type.startswith("text/"):
            for enc in [(part.get_content_charset() or "utf-8"), "utf-8", "latin-1"]:
                try:
                    extracted_text = normalize_text(payload.decode(enc, errors="replace"))
                    if extracted_text:
                        break
                except Exception:
                    continue
        elif mime_type == "application/pdf" or file_path.suffix.lower() == ".pdf":
            extracted_text = (
                extract_pdf_text(file_path)
                if skip_ocr
                else extract_pdf_text_with_ocr(file_path)
            )

        rel_path = str(Path("attachments") / f"email_{email_idx:05d}" / base_name)
        attachments.append(
            AttachmentInfo(
                filename=base_name,
                mime_type=mime_type,
                size_bytes=len(payload),
                relative_path=rel_path,
                extracted_text=extracted_text,
            )
        )

    if not keep_raw_attachments:
        shutil.rmtree(email_attachment_dir, ignore_errors=True)

    return attachments


def build_review_markdown(records: list[EmailRecord]) -> str:
    lines: list[str] = [
        "# Mailbox Review Package",
        "",
        f"Total emails: {len(records)}",
        "",
        "---",
        "",
    ]

    for r in records:
        lines.extend(
            [
                f"## {r.email_id} | {r.subject or '(No Subject)'}",
                f"- Date: {r.date}",
                f"- From: {r.sender}",
                f"- To: {r.to}",
                f"- Cc: {r.cc}",
                f"- Message-ID: {r.message_id}",
                "",
                "### Body",
                "",
                r.body_text or "(No body text)",
                "",
            ]
        )

        if r.attachments:
            lines.extend(["### Attachments", ""])
            for att in r.attachments:
                lines.append(f"- {att.filename} ({att.mime_type}, {att.size_bytes} bytes)")
                if att.extracted_text:
                    excerpt = att.extracted_text[:3000]
                    lines.extend(
                        [
                            "",
                            f"[attachment: {att.filename}]",
                            "",
                            excerpt,
                            "",
                        ]
                    )
            lines.append("")

        lines.extend(["---", ""])

    return "\n".join(lines).strip() + "\n"


def write_review_record(out, record: EmailRecord) -> None:
    out.write(f"## {record.email_id} | {record.subject or '(No Subject)'}\n")
    out.write(f"- Date: {record.date}\n")
    out.write(f"- From: {record.sender}\n")
    out.write(f"- To: {record.to}\n")
    out.write(f"- Cc: {record.cc}\n")
    out.write(f"- Message-ID: {record.message_id}\n\n")
    out.write("### Body\n\n")
    out.write((record.body_text or "(No body text)") + "\n\n")

    if record.attachments:
        out.write("### Attachments\n\n")
        for att in record.attachments:
            out.write(f"- {att.filename} ({att.mime_type}, {att.size_bytes} bytes)\n")
            if att.extracted_text:
                out.write(f"\n[attachment: {att.filename}]\n\n")
                out.write(att.extracted_text[:3000] + "\n\n")

    out.write("---\n\n")


def prompt_if_missing(current: str | None, prompt_text: str) -> str:
    if current:
        return current
    return input(prompt_text).strip()


def pick_output_zip(out_dir: Path, package_name: str, force: bool) -> Path:
    out_zip = out_dir / f"{package_name}.zip"
    if force or not out_zip.exists():
        return out_zip
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return out_dir / f"{package_name}_{stamp}.zip"


def export_mbox_review_package(
    *,
    mbox: str,
    out_dir: str | None = None,
    name: str = "mailbox_review_package",
    keep_attachments: bool = False,
    keep_artifacts: bool = False,
    force: bool = False,
    skip_ocr: bool = False,
) -> dict[str, str | int]:
    mbox_path = Path(mbox).expanduser().resolve()

    if not mbox_path.exists() or not mbox_path.is_file():
        raise SystemExit(f"Invalid mbox file: {mbox_path}")

    resolved_out_dir = (
        Path(out_dir).expanduser().resolve()
        if out_dir
        else mbox_path.parent
    )
    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    package_name = safe_name(name, "mailbox_review_package")
    out_zip = pick_output_zip(resolved_out_dir, package_name, force)
    artifact_dir = resolved_out_dir / package_name

    email_docs = 0
    attachment_docs = 0
    attachment_files = 0

    with tempfile.TemporaryDirectory(prefix="mbox_review_pkg_") as tmp:
        tmp_root = Path(tmp)
        pkg_dir = tmp_root / package_name
        attachments_root = pkg_dir / "attachments"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        attachments_root.mkdir(parents=True, exist_ok=True)

        review_path = pkg_dir / "review.md"
        corpus_path = pkg_dir / "llm_corpus.jsonl"
        with review_path.open("w", encoding="utf-8") as review_out, corpus_path.open(
            "w", encoding="utf-8"
        ) as out:
            review_out.write("# Mailbox Review Package\n\n")
            review_out.write("Total emails: generated in manifest.json\n\n")
            review_out.write("---\n\n")

            for idx, (envelope_from, raw_message) in enumerate(
                parse_mbox_messages(mbox_path), start=1
            ):
                msg = BytesParser(policy=policy.default).parsebytes(raw_message)
                body = extract_email_body(msg)
                attachments = extract_attachments(
                    msg=msg,
                    attachments_root=attachments_root,
                    email_idx=idx,
                    keep_raw_attachments=keep_attachments,
                    skip_ocr=skip_ocr,
                )

                r = EmailRecord(
                    email_id=f"email_{idx:05d}",
                    date=decode_header_value(msg.get("Date")),
                    sender=decode_header_value(msg.get("From")),
                    to=decode_header_value(msg.get("To")),
                    cc=decode_header_value(msg.get("Cc")),
                    bcc=decode_header_value(msg.get("Bcc")),
                    subject=decode_header_value(msg.get("Subject")),
                    message_id=decode_header_value(msg.get("Message-ID")),
                    envelope_from=envelope_from,
                    body_text=body,
                    attachments=attachments,
                )
                write_review_record(review_out, r)

                email_docs += 1
                out.write(
                    json.dumps(
                        {
                            "doc_id": r.email_id,
                            "doc_type": "email",
                            "date": r.date,
                            "from": r.sender,
                            "to": r.to,
                            "cc": r.cc,
                            "subject": r.subject,
                            "message_id": r.message_id,
                            "text": normalize_text(
                                "\n".join(
                                    [
                                        f"Date: {r.date}",
                                        f"From: {r.sender}",
                                        f"To: {r.to}",
                                        f"Cc: {r.cc}",
                                        f"Subject: {r.subject}",
                                        "",
                                        r.body_text,
                                    ]
                                )
                            )[:60000],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

                for att_i, att in enumerate(r.attachments, start=1):
                    attachment_files += 1
                    if not att.extracted_text:
                        continue
                    attachment_docs += 1
                    out.write(
                        json.dumps(
                            {
                                "doc_id": f"{r.email_id}_att_{att_i:02d}",
                                "doc_type": "attachment",
                                "parent_email_id": r.email_id,
                                "filename": att.filename,
                                "mime_type": att.mime_type,
                                "relative_path": att.relative_path,
                                "text": att.extracted_text[:60000],
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_mbox": str(mbox_path),
            "email_count": email_docs,
            "attachment_file_count": attachment_files,
            "email_doc_count": email_docs,
            "attachment_doc_count": attachment_docs,
            "includes_raw_attachments": keep_attachments,
            "files": [
                "review.md",
                "llm_corpus.jsonl",
                "manifest.json",
            ]
            + (["attachments/"] if keep_attachments else []),
        }
        (pkg_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if out_zip.exists() and force:
            out_zip.unlink()

        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(pkg_dir.rglob("*")):
                if path.is_dir():
                    continue
                rel = path.relative_to(pkg_dir)
                if not keep_attachments and rel.parts and rel.parts[0] == "attachments":
                    continue
                zf.write(path, arcname=str(rel))

        if keep_artifacts:
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir, ignore_errors=True)
            shutil.copytree(pkg_dir, artifact_dir)

    return {
        "status": "ok",
        "final_package": str(out_zip),
        "email_count": email_docs,
        "attachment_file_count": attachment_files,
        "attachment_doc_count": attachment_docs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a single review package zip from a raw mbox."
    )
    parser.add_argument("--mbox", help="Path to raw mbox file")
    parser.add_argument("--out-dir", help="Directory for final zip output")
    parser.add_argument(
        "--name",
        default="mailbox_review_package",
        help="Final package base name (without extension)",
    )
    parser.add_argument(
        "--keep-attachments",
        action="store_true",
        help="Include raw attachment files inside the final zip.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep expanded artifact folder alongside the zip.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing zip with same name.",
    )
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Skip OCR fallback for PDFs (faster, lower text coverage on scanned PDFs).",
    )
    args = parser.parse_args()

    result = export_mbox_review_package(
        mbox=prompt_if_missing(args.mbox, "Path to mbox file: "),
        out_dir=args.out_dir,
        name=args.name,
        keep_attachments=args.keep_attachments,
        keep_artifacts=args.keep_artifacts,
        force=args.force,
        skip_ocr=args.skip_ocr,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
