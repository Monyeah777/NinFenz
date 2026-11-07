"""Structural field extraction for YAML-like contract blocks."""

from __future__ import annotations

import hashlib
import os
import re

DOC_RANGE = re.compile(r"^((?:0[1-9]|[12][0-9]|3[0-6]))_")
_VERSION = re.compile(r"v\d+(?:\.\d+){1,2}")
_REF_P = re.compile(r"(?<![A-Za-z0-9])P\d{2,4}")
_REF_M = re.compile(r"(?<![A-Za-z0-9])M\d{2,4}")
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")
_YAML_FENCE = re.compile(r"^```[ \t]*[Yy][Aa][Mm][Ll]?[ \t]*$", re.M)
_BLOCK_KEY = re.compile(r"^([A-Za-z_][\w]*):\s*$", re.M)


def parse_doc_id(path: str) -> str:
    """Return the two-digit root protocol number, or an empty string."""
    match = DOC_RANGE.match(os.path.basename(path))
    return match.group(1) if match else ""


def kind_of(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "/03_管线库/" in normalized or "/pipelines/" in normalized:
        return "pipeline"
    if "/04_模块库/" in normalized or "/modules/" in normalized:
        return "module"
    return "doc"


def extract_fences(text: str) -> list[str]:
    """Extract YAML-like fenced blocks without using a YAML parser."""
    out = []
    in_fence = False
    buf: list[str] = []
    for line in text.splitlines():
        if not in_fence:
            if _YAML_FENCE.match(line):
                in_fence = True
                buf = []
        elif line.strip().startswith("```"):
            in_fence = False
            out.append("\n".join(buf))
        else:
            buf.append(line)
    return out


def _field_from_fence(text: str, field: str) -> str:
    for fence in extract_fences(text):
        match = re.search(rf"(?m)^\s*{re.escape(field)}:\s*(.+?)\s*$", fence)
        if match:
            return match.group(1).strip().strip("'\"")
    return ""


def field_paths(fences: list[str]) -> list[str]:
    """Extract nested field paths from YAML-like fenced blocks."""
    out: list[str] = []
    for fence in fences:
        stack: list[tuple[int, str]] = []
        for line in fence.splitlines():
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(stripped)
            item = stripped[2:].strip() if stripped.startswith("- ") else stripped
            match = re.match(r"^([A-Za-z_][\w.-]*):(?:\s+(.*))?$", item)
            if not match:
                continue
            while stack and indent <= stack[-1][0]:
                stack.pop()
            prefix = stack[-1][1] + "." if stack else ""
            path = prefix + match.group(1)
            if stripped.startswith("- "):
                path = prefix.rstrip(".") + "[]." + match.group(1)
            out.append(path)
            stack.append((indent, path))
    return sorted(set(out))


def build_signature_text(path: str, raw: str) -> dict:
    """Build a deterministic document signature from already-loaded text."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()
    headings = []
    for line in lines:
        match = _HEADING.match(line)
        if match and not match.group(1).startswith("#"):
            headings.append(match.group(1).strip())
    fences = extract_fences(text)
    schema_names = []
    for fence in fences:
        for match in _BLOCK_KEY.finditer(fence):
            name = match.group(1)
            if name not in ("yaml", "yml", "text"):
                schema_names.append(name)
    title = headings[0] if headings else os.path.basename(path)
    version = _VERSION.search(title + "\n" + "\n".join(lines[:8]))
    refs = sorted(set(_REF_M.findall(text) + _REF_P.findall(text)))
    return {
        "kind": kind_of(path),
        "path": path.replace("\\", "/"),
        "doc_id": parse_doc_id(path),
        "title": title,
        "version": version.group(0) if version else "",
        "self_id": _field_from_fence(text, "id"),
        "layer": _field_from_fence(text, "layer"),
        "category": _field_from_fence(text, "category"),
        "heading_count": len(headings),
        "headings": headings,
        "schema_names": sorted(set(schema_names)),
        "field_paths": field_paths(fences),
        "refs": refs,
        "meta_line_count": len([line for line in lines if line.strip().startswith(">")]),
        "line_count": len(lines),
        "body_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
