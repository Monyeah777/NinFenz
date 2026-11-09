"""NF 注册来源的有界只读证据摘录。"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from . import cognitive_cockpit as cc
from . import domain_sources, evidence_roles, json_asset
from .repo_context import repository_root

BASE = Path(__file__).parent
NF = repository_root()
REGISTRY = json_asset.load(BASE / "nf_source_registry.json")
BY_ID = {
    **{item["id"]: item for item in REGISTRY["sources"]},
    **domain_sources.BY_ID,
}
MAX_EXCERPTS = 4
MAX_CHARS = 320
MAX_DOMAIN_FILES = 32


@lru_cache(maxsize=128)
def _read_source(path_text: str, mtime_ns: int, size: int) -> tuple[str, tuple[str, ...]]:
    del mtime_ns, size
    data = Path(path_text).read_bytes()
    return (
        hashlib.sha256(data).hexdigest(),
        tuple(data.decode("utf-8", errors="replace").splitlines()),
    )


def _source_snapshot(path: Path) -> tuple[str, tuple[str, ...]]:
    stat = path.stat()
    return _read_source(str(path), stat.st_mtime_ns, stat.st_size)


def cache_info() -> dict:
    info = _read_source.cache_info()
    return {"hits": info.hits, "misses": info.misses, "size": info.currsize, "limit": info.maxsize}


def cache_clear() -> None:
    _read_source.cache_clear()


def _path_for(source_id: str) -> Path:
    item = BY_ID.get(source_id)
    if item is None or not item.get("path"):
        raise ValueError(f"unknown source: {source_id}")
    target = (NF / item["path"]).resolve()
    try:
        target.relative_to(NF.resolve())
    except ValueError as exc:
        raise ValueError(f"source path escape: {source_id}") from exc
    if not target.is_file():
        raise ValueError(f"source file missing: {source_id}")
    return target


def _paths_for(source_id: str) -> list[Path]:
    primary = _path_for(source_id)
    item = BY_ID[source_id]
    if not source_id.startswith("community:"):
        return [primary]
    root = (NF / item["path"]).resolve().parent
    candidates = [
        candidate
        for candidate in (root / "README.md", root / "protocol.yaml")
        if candidate.is_file()
    ]
    all_markdown = sorted(path.resolve() for path in root.rglob("*.md") if path.is_file())
    for folder in ("assets", "modules", "pipelines"):
        candidates += [path for path in all_markdown if folder in path.relative_to(root).parts]
    candidates += [path for path in all_markdown if path not in candidates]
    out = []
    seen = set()
    for path in candidates:
        try:
            path.relative_to(NF.resolve())
        except ValueError:
            continue
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
        if len(out) >= MAX_DOMAIN_FILES:
            break
    return out


def _role_for(source_id: str, path: Path) -> str:
    if not source_id.startswith("community:"):
        return "content"
    root = (NF / BY_ID[source_id]["path"]).resolve().parent
    if path.parent == root and path.name in {"README.md", "protocol.yaml"}:
        return "domain-scope"
    relative = path.relative_to(root).parts
    if relative and relative[0] == "outputs":
        return "domain-output"
    return "domain-content"


def _anchors(s: dict, references: list[dict] | None = None) -> list[str]:
    goal = s.get("goal", "")
    values = [str(item) for item in s.get("artifact", {}).get("parts", [])]
    for group in (cc.REQ_KEYS, cc.TECH_TERMS, cc.BUSINESS_TERMS, cc.GAME_TERMS):
        values += [term for term in group if term in goal]
    for reference in references or []:
        values += [str(term) for term in reference.get("keywords", [])]
    return sorted({item for item in values if item})


def _snippet(line: str, anchors: list[str]) -> tuple[str, bool, int, int]:
    text = line
    if len(text) <= MAX_CHARS:
        return text, False, 0, len(text)
    positions = [text.find(anchor) for anchor in anchors if text.find(anchor) >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - MAX_CHARS // 3)
    end = min(len(text), start + MAX_CHARS)
    start = max(0, end - MAX_CHARS)
    return text[start:end], True, start, end


def _cover_order(matches: list[dict], anchors: list[str], requested_roles: list[str]) -> list[dict]:
    remaining = set(anchors)
    remaining_roles = set(requested_roles)
    pending = list(matches)
    ordered = []
    while pending:
        best = max(
            pending,
            key=lambda item: (
                len(set(item["matched_terms"]) & remaining),
                len(set(item["matched_roles"]) & remaining_roles),
                len(item["matched_terms"]),
                -item["line"],
            ),
        )
        coverage = set(best["matched_terms"]) & remaining
        role_coverage = set(best["matched_roles"]) & remaining_roles
        if not coverage and not role_coverage:
            break
        ordered.append(best)
        pending.remove(best)
        remaining -= coverage
        remaining_roles -= role_coverage
    ordered.extend(
        sorted(
            pending,
            key=lambda item: (
                item["role"] == "domain-scope",
                -len(item["matched_roles"]),
                -len(item["matched_terms"]),
                item["line"],
            ),
        )
    )
    return ordered


def select(
    s: dict,
    references: list[dict],
    limit: int = MAX_EXCERPTS,
    requested_roles: list[str] | None = None,
) -> list[dict]:
    anchors = _anchors(s, references)
    if not anchors:
        return []
    roles = sorted(set(requested_roles or []))
    grouped: dict[str, list[dict]] = {}
    for reference in references:
        source_id = reference["source"]
        for path in _paths_for(source_id):
            file_digest, lines = _source_snapshot(path)
            role = _role_for(source_id, path)
            for line_no, line in enumerate(lines, 1):
                hits = [anchor for anchor in anchors if anchor in line]
                if not hits:
                    continue
                text, truncated, char_start, char_end = _snippet(line, anchors)
                if not text:
                    continue
                role_hits = [
                    role_name
                    for role_name in roles
                    if role_name in evidence_roles.ROLE_TERMS
                    and any(
                        term.casefold() in text.casefold()
                        for term in evidence_roles.ROLE_TERMS[role_name]
                    )
                ]
                grouped.setdefault(source_id, []).append(
                    {
                        "source": source_id,
                        "role": role,
                        "trust": ("derived" if role == "domain-output" else "local-trusted"),
                        "path": str(path.relative_to(NF)),
                        "line": line_no,
                        "text": text,
                        "truncated": truncated,
                        "char_start": char_start,
                        "char_end": char_end,
                        "normalization": "none",
                        "matched_terms": hits,
                        "matched_roles": role_hits,
                        "content_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "file_digest": file_digest,
                    }
                )
    for source_id, source_matches in grouped.items():
        grouped[source_id] = _cover_order(source_matches, anchors, roles)
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    scope_seen: set[str] = set()
    ordered_references = [
        reference for reference in references if not reference.get("context_only", False)
    ] + [reference for reference in references if reference.get("context_only", False)]
    source_order = [reference["source"] for reference in ordered_references]
    while len(out) < limit:
        progressed = False
        for source_id in source_order:
            values = grouped.get(source_id, [])
            while values:
                item = values.pop(0)
                key = (item["source"], item["text"])
                if key in seen:
                    continue
                if item["role"] == "domain-scope" and item["source"] in scope_seen:
                    continue
                seen.add(key)
                if item["role"] == "domain-scope":
                    scope_seen.add(item["source"])
                out.append(item)
                progressed = True
                break
            if len(out) >= limit:
                break
        if not progressed:
            break
    content_terms = {
        term
        for item in out
        if item["role"] in {"content", "domain-content"}
        for term in item["matched_terms"]
    }
    if len(content_terms) < 2 and not any(len(term) >= 4 for term in content_terms):
        out = [item for item in out if item["role"] == "domain-scope"]
    return out
