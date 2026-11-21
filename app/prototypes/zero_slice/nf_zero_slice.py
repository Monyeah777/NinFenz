#!/usr/bin/env python3
"""NF zero-slice import session reference implementation.

Purpose
-------
A small, dependency-free model of the APP's most important P0 layer:
  source -> structure -> spec mapping -> exceptions -> draft
with *reset* semantics that never auto-restore a cleared session.

This is a reference for the Rust/Kotlin implementation, not the Android app.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------

@dataclass
class Block:
    id: str
    kind: str  # heading|paragraph|list|table|code
    text: str
    level: int = 0
    order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Section:
    id: str
    title: str
    order: int
    blocks: list[Block] = field(default_factory=list)
    level: int = 0

    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks if b.text.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "order": self.order,
            "level": self.level, "blocks": [b.to_dict() for b in self.blocks],
        }


@dataclass
class Document:
    title: str
    blocks: list[Block]
    sections: list[Section]
    source_format: str = "markdown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title, "source_format": self.source_format,
            "blocks": [b.to_dict() for b in self.blocks],
            "sections": [s.to_dict() for s in self.sections],
        }


# ---------------------------------------------------------------------------
# Spec model
# ---------------------------------------------------------------------------

@dataclass
class SlotSpec:
    id: str
    name: str
    section: str
    required: bool = True
    type: str = "text"
    constraints: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SectionSpec:
    id: str
    title: str
    order: int
    required: bool = True
    slots: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MdSpec:
    id: str
    title: str
    sections: list[SectionSpec]
    slots: dict[str, SlotSpec]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "nf-md-spec/1", "id": self.id, "title": self.title,
            "sections": [s.to_dict() for s in self.sections],
            "slots": [s.to_dict() for s in self.slots.values()],
        }


def load_spec(data: dict[str, Any]) -> MdSpec:
    slots: dict[str, SlotSpec] = {}
    for raw in data.get("slots", []) or []:
        sid = str(raw.get("id") or raw.get("slot") or "")
        if not sid:
            continue
        slots[sid] = SlotSpec(
            id=sid,
            name=str(raw.get("name") or raw.get("title") or sid),
            section=str(raw.get("section") or ""),
            required=bool(raw.get("required", True)),
            type=str(raw.get("type") or raw.get("kind") or "text"),
            constraints=list(raw.get("constraints") or []),
        )
    sections: list[SectionSpec] = []
    for order, raw in enumerate(data.get("sections", []) or [], start=1):
        sid = str(raw.get("id") or f"SEC-{order:02d}")
        slot_ids = [str(x) for x in (raw.get("slots") or [])]
        sections.append(SectionSpec(
            id=sid,
            title=str(raw.get("title") or sid),
            order=int(raw.get("order") or order),
            required=bool(raw.get("required", True)),
            slots=slot_ids,
        ))
        for slot_id in slot_ids:
            if slot_id not in slots:
                slots[slot_id] = SlotSpec(id=slot_id, name=slot_id, section=sid)
    sections.sort(key=lambda s: s.order)
    return MdSpec(
        id=str(data.get("id") or "spec"),
        title=str(data.get("title") or data.get("id") or "spec"),
        sections=sections,
        slots=slots,
    )


def freeform_spec() -> MdSpec:
    slot = SlotSpec(id="SLOT-FREEFORM", name="正文", section="SEC-FREEFORM")
    sec = SectionSpec(id="SEC-FREEFORM", title="全文", order=1, slots=[slot.id])
    return MdSpec(id="freeform", title="自由稿", sections=[sec], slots={slot.id: slot})


# ---------------------------------------------------------------------------
# Markdown -> structure
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_FENCE = re.compile(r"^```")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _clean_heading(text: str) -> str:
    return re.sub(r"^[#\s]+", "", text).strip()


def parse_markdown(text: str, source_format: str = "markdown") -> Document:
    """Parse a small, predictable Markdown subset.

    Headings up to level 2 start sections; deeper headings stay as blocks.
    No headings => one freeform section with the first line as title.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ValueError("EMPTY_INPUT")

    lines = text.split("\n")
    blocks: list[Block] = []
    sections: list[Section] = []
    current: Section | None = None
    title = ""
    i = 0
    order = 0

    def ensure_section(level: int, heading: str | None) -> Section:
        nonlocal current
        heading = heading or "未命名"
        sec = Section(id=f"SEC-{len(sections) + 1:02d}", title=heading,
                      order=len(sections) + 1, level=level)
        sections.append(sec)
        current = sec
        return sec

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if _FENCE.match(line):
            buf = [line]
            i += 1
            while i < len(lines):
                buf.append(lines[i])
                if _FENCE.match(lines[i]) and len(buf) > 1:
                    i += 1
                    break
                i += 1
            order += 1
            b = Block(id=f"B{order:03d}", kind="code", text="\n".join(buf), order=order)
            blocks.append(b)
            if current is None:
                ensure_section(0, None)
            current.blocks.append(b)
            continue

        m = _HEADING.match(line)
        if m:
            level = len(m.group(1))
            heading = _clean_heading(m.group(2))
            # The first H1 is the document title, not a content section.
            if level == 1 and not title and not sections and current is None:
                title = heading
                order += 1
                blocks.append(Block(id=f"B{order:03d}", kind="heading",
                                    text=heading, level=level, order=order))
                i += 1
                continue
            order += 1
            b = Block(id=f"B{order:03d}", kind="heading", text=heading,
                      level=level, order=order)
            blocks.append(b)
            if level <= 2:
                ensure_section(level, heading)
                # keep heading as a block in its own section
                current.blocks.append(b)
            else:
                if current is None:
                    ensure_section(0, None)
                current.blocks.append(b)
            i += 1
            continue

        if line.lstrip().startswith("|"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                buf.append(lines[i].strip())
                i += 1
            order += 1
            b = Block(id=f"B{order:03d}", kind="table", text="\n".join(buf), order=order)
            blocks.append(b)
            if current is None:
                ensure_section(0, None)
            current.blocks.append(b)
            continue

        if _LIST.match(line):
            buf = []
            while i < len(lines) and lines[i].strip() and _LIST.match(lines[i]):
                buf.append(lines[i].strip())
                i += 1
            order += 1
            b = Block(id=f"B{order:03d}", kind="list", text="\n".join(buf), order=order)
            blocks.append(b)
            if current is None:
                ensure_section(0, None)
            current.blocks.append(b)
            continue

        buf = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _HEADING.match(lines[i]) \
                and not _LIST.match(lines[i]) and not lines[i].lstrip().startswith("|") \
                and not _FENCE.match(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        order += 1
        b = Block(id=f"B{order:03d}", kind="paragraph", text=" ".join(buf), order=order)
        blocks.append(b)
        if current is None:
            ensure_section(0, None)
        current.blocks.append(b)

    if not sections:
        ensure_section(0, None)
    if not title:
        first = next((b.text for b in blocks if b.text.strip()), "未命名")
        title = first.strip().splitlines()[0][:80]
    for sec in sections:
        sec.blocks.sort(key=lambda b: b.order)
    return Document(title=title, blocks=blocks, sections=sections,
                    source_format=source_format)


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

@dataclass
class Mapping:
    source_id: str
    source_title: str
    source_text: str
    target_slot: str | None
    target_name: str
    confidence: float
    reason: str
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MappingReport:
    mappings: list[Mapping]
    exceptions: list[Mapping]
    missing_required: list[str]
    coverage: float
    spec_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "coverage": round(self.coverage, 4),
            "mappings": [m.to_dict() for m in self.mappings],
            "exceptions": [m.to_dict() for m in self.exceptions],
            "missing_required": self.missing_required,
        }


def _title_score(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    ta = set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", a))
    tb = set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", b))
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / len(ta | tb)
    return min(0.8, 0.35 + 0.45 * j)


def infer_mappings(doc: Document, spec: MdSpec) -> MappingReport:
    if not doc.sections:
        raise ValueError("NO_SECTIONS")

    # Freeform / single-section single-slot specs always map the whole document.
    if spec.id == "freeform" or (len(spec.sections) == 1 and len(spec.sections[0].slots) == 1):
        sec_spec = spec.sections[0]
        target = sec_spec.slots[0]
        name = spec.slots.get(target, SlotSpec(target, target, sec_spec.id)).name
        text = "\n\n".join(b.text for s in doc.sections for b in s.blocks
                            if b.kind != "heading" and b.text.strip())
        m = Mapping("ALL", doc.title, text, target, name, 0.9,
                    "freeform/single-slot: whole document mapped")
        total = sum(len(s.text()) for s in doc.sections) or 1
        return MappingReport(mappings=[m], exceptions=[],
                             missing_required=[], coverage=min(1.0, len(text) / total),
                             spec_id=spec.id)

    mappings: list[Mapping] = []
    exceptions: list[Mapping] = []
    used_sections: set[str] = set()

    for sec_spec in spec.sections:
        best = max(doc.sections, key=lambda s: _title_score(s.title, sec_spec.title))
        score = _title_score(best.title, sec_spec.title)
        if score < 0.45:
            best = None
            score = 0.2
        else:
            used_sections.add(best.id)

        slot_ids = list(sec_spec.slots)
        if not slot_ids:
            # no slot declared: keep content as an extra, never drop it
            if best is not None:
                m = Mapping(best.id, best.title, best.text(), None,
                            sec_spec.title, min(score, 0.5),
                            "spec section has no slots; content kept as extra")
                exceptions.append(m)
            continue

        blocks = [b for b in (best.blocks if best else []) if b.kind != "heading"]
        text = "\n\n".join(b.text for b in blocks if b.text.strip())
        content_conf = 0.9 if text.strip() else 0.25
        target_conf = min(score, content_conf) if best else 0.2

        if len(slot_ids) == 1:
            target = slot_ids[0]
            name = spec.slots.get(target, SlotSpec(target, target, sec_spec.id)).name
            m = Mapping(best.id if best else "", best.title if best else "",
                        text, target, name, target_conf,
                        "single slot; whole section mapped")
            (exceptions if target_conf < 0.6 else mappings).append(m)
        else:
            # distribute blocks across slots; keep empty slots for exceptions
            chunks: list[str] = []
            if blocks:
                per = max(1, (len(blocks) + len(slot_ids) - 1) // len(slot_ids))
                for idx in range(len(slot_ids)):
                    part = blocks[idx * per:(idx + 1) * per]
                    chunks.append("\n\n".join(b.text for b in part if b.text.strip()))
            else:
                chunks = [""] * len(slot_ids)
            for idx, target in enumerate(slot_ids):
                name = spec.slots.get(target, SlotSpec(target, target, sec_spec.id)).name
                chunk = chunks[idx] if idx < len(chunks) else ""
                conf = target_conf * (0.75 if len(slot_ids) > 1 else 1.0)
                if not chunk.strip():
                    conf = min(conf, 0.3)
                m = Mapping(best.id if best else "", best.title if best else "",
                            chunk, target, name, conf,
                            "distributed across section slots")
                (exceptions if conf < 0.6 else mappings).append(m)

    # unmatched source sections: keep as extra; do not drop
    for sec in doc.sections:
        if sec.id in used_sections:
            continue
        extra_text = "\n\n".join(b.text for b in sec.blocks
                                  if b.kind != "heading" and b.text.strip())
        m = Mapping(sec.id, sec.title, extra_text, None, "附加内容", 0.3,
                    "source section not matched to spec; kept as extra")
        exceptions.append(m)

    mapped_slots = {m.target_slot for m in mappings + exceptions if m.target_slot}
    missing_required = [s.id for s in spec.slots.values()
                        if s.required and s.id not in mapped_slots]
    total_chars = sum(len(b.text) for s in doc.sections for b in s.blocks
                      if b.kind != "heading" and b.text.strip())
    mapped_chars = sum(len(m.source_text) for m in mappings + exceptions if m.source_text)
    coverage = min(1.0, (mapped_chars / total_chars)) if total_chars else 0.0
    return MappingReport(mappings=mappings, exceptions=exceptions,
                         missing_required=missing_required,
                         coverage=coverage, spec_id=spec.id)


# ---------------------------------------------------------------------------
# Draft store + session
# ---------------------------------------------------------------------------

class Stage(str, Enum):
    EMPTY = "empty"
    SOURCE = "source"
    PREVIEW = "preview"
    MAPPING = "mapping"
    DRAFT = "draft"


@dataclass
class Source:
    kind: str
    name: str
    text: str
    sha256: str

    @classmethod
    def from_text(cls, kind: str, name: str, text: str) -> "Source":
        return cls(kind=kind, name=name, text=text,
                   sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DraftStore:
    """File-backed drafts. Same source overwrites; different source creates new."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, draft_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", draft_id)[:80]
        return self.root / f"{safe}.json"

    def save(self, session: "ImportSession") -> str:
        if session.source is None or session.report is None:
            raise ValueError("NO_SESSION")
        draft_id = f"{Path(session.source.name).stem}-{session.source.sha256[:8]}"
        payload = {
            "schema": "nf-import-draft/1",
            "draft_id": draft_id,
            "source": session.source.to_dict(),
            "document": session.document.to_dict() if session.document else None,
            "spec": session.spec.to_dict() if session.spec else None,
            "report": session.report.to_dict(),
            "accepted": [m.to_dict() for m in session.report.mappings + session.report.exceptions
                         if m.accepted],
        }
        path = self._path(draft_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        session.draft_id = draft_id
        session.stage = Stage.DRAFT
        return draft_id

    def list(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))

    def delete(self, draft_id: str) -> bool:
        p = self._path(draft_id)
        if p.exists():
            p.unlink()
            return True
        return False

    def exists(self, draft_id: str) -> bool:
        return self._path(draft_id).exists()


@dataclass
class ImportSession:
    """Explicit state machine. reset() is real; no silent auto-restore."""

    store: DraftStore
    source: Source | None = None
    document: Document | None = None
    spec: MdSpec | None = None
    report: MappingReport | None = None
    draft_id: str | None = None
    stage: Stage = Stage.EMPTY
    _undo: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def _snapshot(self) -> None:
        self._undo.append({
            "source": self.source.to_dict() if self.source else None,
            "document": self.document.to_dict() if self.document else None,
            "spec": self.spec.to_dict() if self.spec else None,
            "report": self.report.to_dict() if self.report else None,
            "draft_id": self.draft_id,
            "stage": self.stage.value,
        })
        self._undo = self._undo[-10:]

    def start(self, source: Source, spec: MdSpec | None = None) -> None:
        if not source.text.strip():
            raise ValueError("EMPTY_INPUT")
        self._snapshot()
        self.source = source
        self.spec = spec
        self.stage = Stage.SOURCE
        self.document = None
        self.report = None
        self.draft_id = None

    def preview(self) -> Document:
        if self.source is None:
            raise ValueError("NO_SOURCE")
        self._snapshot()
        self.document = parse_markdown(self.source.text)
        self.stage = Stage.PREVIEW
        return self.document

    def infer(self) -> MappingReport:
        if self.document is None:
            self.preview()
        assert self.document is not None
        self._snapshot()
        spec = self.spec or freeform_spec()
        self.spec = spec
        self.report = infer_mappings(self.document, spec)
        self.stage = Stage.MAPPING
        return self.report

    def accept_all(self) -> None:
        if self.report is None:
            raise ValueError("NO_REPORT")
        for m in self.report.mappings + self.report.exceptions:
            m.accepted = True

    def toggle(self, index: int) -> bool:
        if self.report is None:
            raise ValueError("NO_REPORT")
        items = self.report.mappings + self.report.exceptions
        if not 0 <= index < len(items):
            raise IndexError(index)
        items[index].accepted = not items[index].accepted
        return items[index].accepted

    def save_draft(self) -> str:
        if self.report is None:
            raise ValueError("NO_REPORT")
        self._snapshot()
        return self.store.save(self)

    def reset(self, scope: str = "current") -> None:
        """Reset the live session. scope=current keeps saved drafts; all deletes it."""
        self._snapshot()
        if scope not in {"current", "all"}:
            raise ValueError("BAD_SCOPE")
        if scope == "all" and self.draft_id:
            self.store.delete(self.draft_id)
        self.source = None
        self.document = None
        self.spec = None
        self.report = None
        self.draft_id = None
        self.stage = Stage.EMPTY

    def undo(self) -> None:
        if not self._undo:
            raise ValueError("NOTHING_TO_UNDO")
        snap = self._undo.pop()
        self.source = Source(**snap["source"]) if snap["source"] else None
        self.document = _document_from_dict(snap["document"]) if snap["document"] else None
        self.spec = load_spec(snap["spec"]) if snap["spec"] else None
        self.report = _report_from_dict(snap["report"]) if snap["report"] else None
        self.draft_id = snap["draft_id"]
        self.stage = Stage(snap["stage"])

    def to_project(self) -> dict[str, Any]:
        """Reference conversion: project with document + accepted slots."""
        if self.report is None:
            raise ValueError("NO_REPORT")
        slots: dict[str, str] = {}
        for m in self.report.mappings + self.report.exceptions:
            if m.target_slot and m.accepted:
                slots[m.target_slot] = m.source_text
        return {
            "schema": "nf-project/1",
            "title": self.document.title if self.document else "未命名",
            "spec": self.spec.id if self.spec else "freeform",
            "document": self.document.to_dict() if self.document else None,
            "slots": slots,
            "draft_id": self.draft_id,
        }


def _document_from_dict(d: dict[str, Any]) -> Document:
    blocks = [Block(**b) for b in d.get("blocks", [])]
    sections = [Section(id=s["id"], title=s["title"], order=s["order"],
                        level=s.get("level", 0),
                        blocks=[Block(**b) for b in s.get("blocks", [])])
                for s in d.get("sections", [])]
    return Document(title=d["title"], blocks=blocks, sections=sections,
                    source_format=d.get("source_format", "markdown"))


def _report_from_dict(d: dict[str, Any]) -> MappingReport:
    def m(raw: dict[str, Any]) -> Mapping:
        return Mapping(**raw)
    return MappingReport(
        mappings=[m(x) for x in d.get("mappings", [])],
        exceptions=[m(x) for x in d.get("exceptions", [])],
        missing_required=list(d.get("missing_required", [])),
        coverage=float(d.get("coverage", 0.0)),
        spec_id=str(d.get("spec_id", "spec")),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_text(path: str) -> str:
    p = Path(path)
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return p.read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="NF zero-slice reference")
    ap.add_argument("--file", required=True)
    ap.add_argument("--spec", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    text = _read_text(args.file)
    spec = load_spec(json.loads(_read_text(args.spec))) if args.spec else freeform_spec()
    store = DraftStore(tempfile.mkdtemp(prefix="nf-drafts-"))
    session = ImportSession(store=store)
    session.start(Source.from_text("file", Path(args.file).name, text), spec)
    doc = session.preview()
    report = session.infer()

    out = {
        "title": doc.title,
        "sections": [{"id": s.id, "title": s.title, "chars": len(s.text())}
                     for s in doc.sections],
        "spec": spec.id,
        "coverage": round(report.coverage, 4),
        "mappings": [m.to_dict() for m in report.mappings],
        "exceptions": [m.to_dict() for m in report.exceptions],
        "missing_required": report.missing_required,
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"{doc.title} · {len(doc.sections)} sections · coverage {report.coverage:.0%}")
        for m in report.mappings + report.exceptions:
            flag = "!" if m in report.exceptions else " "
            print(f"{flag} {m.confidence:.2f} {m.source_title[:18]:18} -> {m.target_name}")
        if report.missing_required:
            print("missing:", ", ".join(report.missing_required))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

