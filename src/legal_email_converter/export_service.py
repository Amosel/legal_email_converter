from __future__ import annotations

from typing import Any

from .export_mbox_for_llm import export_mbox_review_package


def export_mbox_review_package_service(
    *,
    mbox: str,
    out_dir: str | None = None,
    name: str = "mailbox_review_package",
    keep_attachments: bool = False,
    keep_artifacts: bool = False,
    force: bool = False,
    skip_ocr: bool = False,
) -> dict[str, Any]:
    """Programmatic non-interactive entrypoint for exporter workflow."""
    return export_mbox_review_package(
        mbox=mbox,
        out_dir=out_dir,
        name=name,
        keep_attachments=keep_attachments,
        keep_artifacts=keep_artifacts,
        force=force,
        skip_ocr=skip_ocr,
    )


def export_mbox_review_package_api(
    *,
    mbox: str,
    out_dir: str | None = None,
    name: str = "mailbox_review_package",
    keep_attachments: bool = False,
    keep_artifacts: bool = False,
    force: bool = False,
    skip_ocr: bool = False,
) -> dict[str, Any]:
    """Backwards-compatible alias for service callers."""
    return export_mbox_review_package_service(
        mbox=mbox,
        out_dir=out_dir,
        name=name,
        keep_attachments=keep_attachments,
        keep_artifacts=keep_artifacts,
        force=force,
        skip_ocr=skip_ocr,
    )
