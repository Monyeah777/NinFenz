"""Sanitization and structured security-event logging."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

_SECRET = re.compile(
    r"(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9_-]{16,}|bearer\s+[A-Za-z0-9._~+/=-]{16,})"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u2028\u2029\u0085]")


def sanitize(value: Any, limit: int = 2048) -> str:
    """Flatten one diagnostic value and redact common credential forms."""
    text = str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    text = _CONTROL.sub(lambda match: f"\\u{ord(match.group(0)):04x}", text)
    text = _SECRET.sub("[REDACTED]", text)
    return text[:max(0, int(limit))]


def security_event(logger: logging.Logger, event: str, **fields: Any) -> dict[str, Any]:
    """Write one JSON security event after escaping and redaction."""
    payload = {"event": sanitize(event, 128)}
    payload.update({sanitize(key, 64): sanitize(value) for key, value in fields.items()})
    logger.warning(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    )
    return payload
