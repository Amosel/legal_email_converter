from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WarningItem:
    code: str
    message: str


@dataclass
class ErrorItem:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    status: str
    final_package: str = ""
    email_count: int = 0
    attachment_file_count: int = 0
    attachment_doc_count: int = 0
    warnings: list[WarningItem] = field(default_factory=list)
    errors: list[ErrorItem] = field(default_factory=list)

