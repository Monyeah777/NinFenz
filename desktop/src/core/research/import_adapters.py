"""Minimal import sniffer/normalizer for App input.

Supports text/markdown/json; detects zip/docx/pdf and reports them as
unsupported instead of pretending to parse. No network, no OCR.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "nf-import/1"
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class ImportDoc:
    name: str
    detected: str
    confidence: float
    text: str = ""
    structure: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    schema: str = field(default=SCHEMA, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "source": {"name": self.name},
                "detected": self.detected, "confidence": self.confidence,
                "text": self.text, "structure": self.structure,
                "warnings": self.warnings}


def _text(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def sniff(name: str, data: bytes) -> dict[str, Any]:
    ext = Path(name).suffix.lower()
    if data[:4] == b"%PDF":
        return {"format": "pdf", "confidence": 0.99, "supported": False}
    if data[:2] == b"PK":
        if ext in {".docx", ".zip"}:
            return {"format": ext.lstrip("."), "confidence": 0.95,
                    "supported": False}
        return {"format": "zip", "confidence": 0.9, "supported": False}
    text = _text(data)
    if text is None:
        return {"format": "binary", "confidence": 0.8, "supported": False}
    if ext in {".md", ".markdown"}:
        return {"format": "markdown", "confidence": 0.99, "supported": True}
    if ext == ".json" or text.lstrip().startswith(("{", "[")):
        try:
            json.loads(text)
            return {"format": "json", "confidence": 0.98, "supported": True}
        except json.JSONDecodeError:
            if ext == ".json":
                return {"format": "json", "confidence": 0.7,
                        "supported": True, "warning": "json_parse_failed"}
    if ext in {".txt", ".text", ""}:
        return {"format": "text", "confidence": 0.9, "supported": True}
    return {"format": "text", "confidence": 0.6, "supported": True,
            "warning": "unknown_extension"}


def normalize(name: str, data: bytes) -> ImportDoc:
    info = sniff(name, data)
    doc = ImportDoc(name, info["format"], info["confidence"])
    if not info["supported"]:
        doc.warnings.append("unsupported_format:" + info["format"])
        return doc
    text = _text(data) or ""
    doc.text = text
    if info.get("warning"):
        doc.warnings.append(info["warning"])
    try:
        if info["format"] == "json":
            parsed = json.loads(text)
            doc.structure = [{"kind": "json", "type": type(parsed).__name__}]
        elif info["format"] == "markdown":
            doc.structure = [{"kind": "heading", "level": len(m.group(1)),
                              "title": m.group(2).strip()}
                             for m in _HEADING.finditer(text)]
    except json.JSONDecodeError:
        doc.warnings.append("json_parse_failed")
    return doc
