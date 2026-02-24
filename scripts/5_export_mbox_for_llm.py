#!/usr/bin/env python3
"""Compatibility wrapper for the installable export module."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure local src package is importable when run from repo checkout.
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from legal_email_converter.export_mbox_for_llm import export_mbox_review_package, main

__all__ = ["export_mbox_review_package", "main"]


if __name__ == "__main__":
    main()
