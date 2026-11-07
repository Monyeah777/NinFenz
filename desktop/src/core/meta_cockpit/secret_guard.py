"""Detect and redact high-confidence credentials without echoing values."""

from __future__ import annotations

import re
from typing import Any

PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I)),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I)),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "named-secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)"
            r"\s*[:=]\s*[\"']?([A-Za-z0-9._~+/=-]{8,})"
        ),
    ),
)
REDACTION = "[REDACTED]"


def _is_secret_value(value: str) -> bool:
    lowered = value.casefold()
    return (
        value != REDACTION
        and not value.startswith("<")
        and "example" not in lowered
        and "placeholder" not in lowered
    )


def scan_text(text: str) -> list[str]:
    kinds = []
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(text):
            captured = match.group(1) if match.lastindex else match.group(0)
            if _is_secret_value(captured):
                kinds.append(kind)
                break
    return kinds


def find(value: Any, path: str = "$") -> list[dict]:
    found: list[dict] = []
    if isinstance(value, str):
        found.extend(
            {
                "path": path,
                "kind": kind,
            }
            for kind in scan_text(value)
        )
    elif isinstance(value, dict):
        for key, child in value.items():
            found.extend(find(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(find(child, f"{path}[{index}]"))
    return found


def redact(text: str) -> str:
    result = text
    for _, pattern in PATTERNS:
        result = pattern.sub(REDACTION, result)
    return result
