"""DITA → 内容 IR 导入器（T9.2，零依赖：xml.etree）。

定位：把 `.dita`（topic/task/concept/reference）与 `.ditamap`（map）转成 **content IR**
（`core.content_ir`），使外部 DITA 资产可被 `nf ir check` / profile / 局部重写消费。
实现方式 = 归一为规范形 Markdown，再 `content_ir.parse`（**复用 IR 创建逻辑，不复制**）。

元素 → IR 映射（机读表 = `ELEMENT_MAP`；覆盖/未覆盖清单 = `coverage_report()`）：
- topic/task/concept/reference → document（title → H1 section）；
- shortdesc → paragraph(form=quote)，即 Markdown blockquote（DITA 短描述语义）；
- section → section（嵌套层级 +1）；
- p / lq / sl / li → paragraph(para)；
- ul → paragraph(list, bullet)；ol / steps → paragraph(list, ordered)；
- table（tgroup/trow/tentry）与 simpletable → paragraph(table)；
- note/warning/attention/tip/important/danger → paragraph(para)，前缀信号词；
- dl（dlentry/dt/dd）→ paragraph(para)，`**术语**：定义` 形式；
- xref/link/ph/codeph/cmdname/filepath/keyword/term 等内联元素 → 文本保留（链接形如
  `[文字](href)`）；
- 未覆盖元素（fig/image/figgroup/object/foreign 等）→ 文字可读则按段落保留，并记
  `warnings`（元素名 + 次数 + 修复指引），**不静默丢**；
- `.ditamap`：title → H1；topicref/navtitle → H2 section（href 作为引用文本保留；map 不
  展开被引 topic，`warnings` 明示「外部引用未展开」）。

fail-closed：文件不存在 / XML 不可解析 / 根元素不是 DITA 主题或 map / 超入站上限 →
抛 `DitaImportError`（带修复指引）；CLI 归 rc=2。

纪律：纯标准库；确定性；不改 `content_ir` 判定逻辑（只调用）。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from . import content_ir

SCHEMA = "nf-import-dita/1"
MAX_BYTES = 64 * 1024 * 1024

#: DITA 根元素 → 处理方式（未在册的根元素 fail-closed）。
ROOT_KINDS = ("topic", "task", "concept", "reference", "map", "bookmap")

#: DITA 块级元素 → IR 映射（机读覆盖表；单测/报告共用）。
ELEMENT_MAP: Dict[str, Dict[str, str]] = {
    "topic": {"ir": "document", "form": "document", "note": "根元素（topic/task/concept/reference 同构）"},
    "title": {"ir": "section.title", "form": "section", "note": "首个 title → H1；section 内 title → 下一级标题"},
    "shortdesc": {"ir": "paragraph", "form": "quote", "note": "Markdown blockquote（短描述）"},
    "section": {"ir": "section", "form": "section", "note": "嵌套层级 +1（最多 H6）"},
    "p": {"ir": "paragraph", "form": "para", "note": "普通段落"},
    "lq": {"ir": "paragraph", "form": "para", "note": "长引用按段落保留"},
    "ul": {"ir": "paragraph", "form": "list", "note": "无序列表（-）"},
    "ol": {"ir": "paragraph", "form": "list", "note": "有序列表（1.）"},
    "steps": {"ir": "paragraph", "form": "list", "note": "任务步骤 → 有序列表（step/stepxmp/stepresult 合并为一项）"},
    "step": {"ir": "paragraph", "form": "list", "note": "单步（steps 的子项）"},
    "table": {"ir": "paragraph", "form": "table", "note": "tgroup/trow/tentry → Markdown 表格（首行表头）"},
    "simpletable": {"ir": "paragraph", "form": "table", "note": "strow/stentry → Markdown 表格"},
    "dl": {"ir": "paragraph", "form": "para", "note": "dlentry → `**dt**：dd` 段落"},
    "note": {"ir": "paragraph", "form": "para", "note": "前缀「注意：」；warning/attention/tip/important/danger 同族"},
    "fig": {"ir": "paragraph", "form": "para", "note": "仅保留 fig 内可读文字（图本身无 IR 节点）"},
    "image": {"ir": "warning", "form": "uncovered", "note": "IR 无图片节点，仅记 warning"},
    "xref": {"ir": "inline", "form": "uncovered", "note": "内联链接：[文字](href)"},
    "link": {"ir": "inline", "form": "uncovered", "note": "内联链接：[文字](href)"},
    "keyword": {"ir": "inline", "form": "uncovered", "note": "内联文本"},
    "term": {"ir": "inline", "form": "uncovered", "note": "内联文本"},
    "codeph": {"ir": "inline", "form": "uncovered", "note": "内联代码文本（反引号）"},
    "filepath": {"ir": "inline", "form": "uncovered", "note": "内联路径文本"},
    "cmdname": {"ir": "inline", "form": "uncovered", "note": "内联命令文本"},
    "ph": {"ir": "inline", "form": "uncovered", "note": "通用内联文本"},
    "topicref": {"ir": "section", "form": "section", "note": "仅 .ditamap：navtitle → H2；href 不展开"},
}

#: 明确未覆盖（结构会丢；文字尽量保留）。
UNCOVERED_ELEMENTS: Tuple[str, ...] = (
    "fig", "image", "figgroup", "object", "foreign", "svg", "mathml",
    "audience", "platform", "props", "revised", "draft-comment",
)

_NOTE_PREFIX = {"note": "注意：", "warning": "警告：", "attention": "注意：",
                "tip": "提示：", "important": "重要：", "danger": "危险："}
_BLOCK = ("title", "shortdesc", "section", "p", "ul", "ol", "steps", "step",
          "table", "simpletable", "dl", "note", "warning", "attention", "tip",
          "important", "danger", "lq", "li", "body", "conbody", "taskbody",
          "topic", "concept", "reference", "task", "fig", "example")


class DitaImportError(ValueError):
    """DITA 导入失败（fail-closed；消息带修复指引）。"""


@dataclass
class Imported:
    ir: content_ir.Document
    markdown: str
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    schema: str = SCHEMA
    kind: str = "dita"

    def to_dict(self) -> Dict[str, Any]:
        import hashlib
        return {"schema": self.schema, "format": self.kind,
                "stats": dict(self.stats), "warnings": list(self.warnings),
                "canonical": self.ir.canonical, "title": self.ir.title,
                "markdown_sha256": hashlib.sha256(
                    self.markdown.encode("utf-8")).hexdigest(),
                "coverage": coverage_report()}


def coverage_report() -> Dict[str, Any]:
    """元素覆盖表（覆盖 / 明确未覆盖 / 未知元素按 warn 处理）。"""
    return {"covered": sorted(ELEMENT_MAP),
            "uncovered": sorted(UNCOVERED_ELEMENTS),
            "unknown_policy": "未在 ELEMENT_MAP 且未在 UNCOVERED 的元素：文字按段落保留 + warning"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _inline(el: ET.Element) -> str:
    """内联文本（含 xref/link 的 href 语义；后代块级元素不进内联）。"""
    pieces: List[str] = []

    def walk(node: ET.Element) -> None:
        name = _local(node.tag)
        if name in ("xref", "link"):
            label = _collapse("".join(node.itertext()))
            href = node.get("href") or node.get("scope") or ""
            pieces.append("[%s](%s)" % (label or href or "链接", href) if href else label)
            return
        if name == "image":
            alt = _collapse("".join(node.itertext()))
            pieces.append("[图%s]" % ("：" + alt if alt else ""))
            return
        if node.text:
            pieces.append(node.text)
        for child in node:
            if _local(child.tag) in _BLOCK:
                continue
            walk(child)
            if child.tail:
                pieces.append(child.tail)

    walk(el)
    return _collapse("".join(pieces))


def _child(el: ET.Element, name: str) -> Optional[ET.Element]:
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _esc(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _table_rows(el: ET.Element) -> List[List[str]]:
    rows: List[List[str]] = []
    for tr in el.iter():
        if _local(tr.tag) not in ("trow", "strow", "row"):
            continue
        cells = [tc for tc in tr
                 if _local(tc.tag) in ("tentry", "stentry", "entry")]
        if cells:
            rows.append([_inline(tc) for tc in cells])
    return rows


def _table_md(el: ET.Element) -> List[str]:
    rows = _table_rows(el)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(_esc(c) for c in rows[0]) + " |",
           "|" + "---|" * width]
    for row in rows[1:]:
        out.append("| " + " | ".join(_esc(c) for c in row) + " |")
    if len(rows) == 1:
        out.append("| " + " | ".join("" for _ in range(width)) + " |")
    return out


def _list_md(el: ET.Element, ordered: bool,
             warnings: List[str], seen_unknown: Dict[str, int]) -> List[str]:
    out: List[str] = []
    items = [c for c in el if _local(c.tag) in ("li", "step")]
    for idx, item in enumerate(items, 1):
        text = _inline(item)
        if not text:
            sub = [c for c in item if _local(c.tag) in _BLOCK]
            text = _collapse(" ".join("".join(c.itertext()) for c in sub))
        out.append(("%d. " % idx if ordered else "- ") + (text or "（空列表项）"))
        nested = [c for c in item if _local(c.tag) in ("ul", "ol", "steps")]
        for sub in nested:
            sub_lines = _list_md(sub, _local(sub.tag) != "ul", warnings, seen_unknown)
            out.extend("  " + ln for ln in sub_lines)
    return out


def _table_md_safe(el: ET.Element) -> List[str]:
    return _table_md(el)


def _md_list(child: ET.Element, name: str,
             warnings: List[str], seen_unknown: Dict[str, int]) -> List[str]:
    return _list_md(child, name != "ul", warnings, seen_unknown)


def _md_table(child: ET.Element) -> List[str]:
    return _table_md_safe(child)


def _md_dl(child: ET.Element) -> List[str]:
    """dl/dlentry/dt/dd → `**术语**：定义` 段落列表。"""
    out: List[str] = []
    for entry in _children(child, "dlentry"):
        dt_el = _child(entry, "dt")
        dt = _inline(dt_el) if dt_el is not None else ""
        dd = " ".join(_inline(d) for d in _children(entry, "dd"))
        text = ("**%s**：%s" % (dt, dd)) if dt else dd
        if text.strip():
            out.append(text.strip())
    return out


def _md_note(name: str, child: ET.Element) -> List[str]:
    text = _inline(child)
    return [_NOTE_PREFIX[name] + text] if text else []


def _walk_blocks(el: ET.Element, level: int, blocks: List[str],
                 warnings: List[str], seen_unknown: Dict[str, int],
                 first_title: bool = False) -> None:
    """DITA 容器 → Markdown 块（递归；各块类分派到 `_md_*` 小件以控圈复杂度）。"""
    for child in el:
        name = _local(child.tag)
        if name == "title":
            text = _inline(child) or "（无标题文字）"
            if first_title:
                blocks.append("# " + text)          # 根 title → H1
            else:
                blocks.append("%s %s" % ("#" * min(level + 1, 6), text))
            first_title = False
            continue
        if name == "shortdesc":
            text = _inline(child)
            if text:
                blocks.append("> " + text)
            continue
        if name in ("section", "example"):
            _walk_blocks(child, min(level + 1, 5), blocks, warnings, seen_unknown)
            continue
        if name == "p":
            text = _inline(child)
            if text:
                blocks.append(text)
            continue
        if name == "lq":
            text = _inline(child)
            if text:
                blocks.append("> " + text)
            continue
        if name in ("ul", "ol", "steps"):
            lines = _md_list(child, name, warnings, seen_unknown)
            if lines:
                blocks.append("\n".join(lines))
            continue
        if name == "li":
            lines = _md_list(child, "ul", warnings, seen_unknown)
            if lines:
                blocks.append("\n".join(lines))
            continue
        if name in ("table", "simpletable"):
            lines = _md_table(child)
            if lines:
                blocks.append("\n".join(lines))
            continue
        if name == "dl":
            blocks.extend(_md_dl(child))
            continue
        if name in _NOTE_PREFIX:
            blocks.extend(_md_note(name, child))
            continue
        if name in ("topicmeta", "body", "conbody", "taskbody", "refbody",
                    "topic", "concept", "reference", "task", "map"):
            _walk_blocks(child, level, blocks, warnings, seen_unknown)
            continue
        # 未知/未覆盖：文字可读则保留为段落，并逐元素累计 warning（不静默丢）。
        # 注意：fig/image 等「已知未覆盖」也走这里——image 的 alt 文字由 `_inline` 保留。
        seen_unknown[name] = seen_unknown.get(name, 0) + 1
        text = _inline(child) or _collapse("".join(child.itertext()))
        if text:
            blocks.append(text)


def _warn_uncovered(seen_unknown: Dict[str, int], warnings: List[str]) -> None:
    for name, n in sorted(seen_unknown.items()):
        note = "已知未覆盖元素" if name in UNCOVERED_ELEMENTS else "未知元素"
        warnings.append("%s <%s> ×%d：文字已按段落保留，结构/属性信息丢失"
                        "（修复指引：转换前改成 p/table/section 等受支持元素）"
                        % (note, name, n))


def _topic_markdown(root: ET.Element, warnings: List[str],
                    seen_unknown: Dict[str, int]) -> List[str]:
    blocks: List[str] = []
    _walk_blocks(root, 0, blocks, warnings, seen_unknown, first_title=True)
    return blocks


def _map_markdown(root: ET.Element, name: str, warnings: List[str],
                  seen_unknown: Dict[str, int]) -> Tuple[List[str], List[str]]:
    title_el = _child(root, "title")
    title = _inline(title_el) if title_el is not None else os.path.splitext(
        os.path.basename(name))[0]
    blocks: List[str] = ["# " + (title or "DITA map")]
    hrefs: List[str] = []
    for ref in root.iter():
        if _local(ref.tag) != "topicref":
            continue
        href = ref.get("href") or ""
        nav = ref.get("navtitle") or ""
        meta = _child(ref, "topicmeta")
        if not nav and meta is not None:
            nav_el = _child(meta, "navtitle")
            if nav_el is None:
                nav_el = _child(meta, "title")
            nav = _inline(nav_el) if nav_el is not None else ""
        label = nav or os.path.splitext(os.path.basename(href))[0] or "（未命名 topic）"
        blocks.append("## " + label)
        if href:
            blocks.append("- 引用：`%s`" % href)
            hrefs.append(href)
    if hrefs:
        warnings.append("ditamap 含 %d 个外部 topic 引用（%s…）：map 不展开被引 topic，"
                        "仅保留 navtitle/href；需内容请对每个 .dita 单独导入"
                        % (len(hrefs), "、".join(hrefs[:3])))
    seen_unknown.pop("topicref", None)
    return blocks, hrefs


def _to_markdown(blocks: List[str]) -> str:
    body = "\n\n".join(b.strip("\n") for b in blocks if b.strip())
    return body + "\n" if body else ""


def _ir_stats(ir: content_ir.Document) -> Dict[str, int]:
    forms = [n.form for n in ir.nodes.values() if n.kind == "paragraph"]
    return {"sections": len(ir.sections), "paragraphs": forms.count("para"),
            "tables": forms.count("table"), "lists": forms.count("list"),
            "quotes": forms.count("quote"), "claims": len(ir.claims)}


def import_bytes(data: bytes, *, name: str = "", base_dir: str = "") -> Imported:
    """DITA 字节 → Imported（损坏件/非法根元素 fail-closed）。"""
    if len(data) > MAX_BYTES:
        raise DitaImportError("DITA 文件过大：%d 字节 > 上限 %d 字节（修复指引：拆分后重导）"
                              % (len(data), MAX_BYTES))
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise DitaImportError(
            "DITA XML 不可解析：%s（修复指引：确认是合法 DITA XML；损坏件请从源系统重新"
            "导出）" % exc) from exc
    kind = _local(root.tag)
    if kind not in ROOT_KINDS:
        raise DitaImportError(
            "不是 DITA 主题或 map：根元素 <%s>（修复指引：本命令收 `topic`/`task`/"
            "`concept`/`reference`/`map`/`bookmap` 根；其它 XML 请先转成 DITA）" % kind)
    warnings: List[str] = []
    seen_unknown: Dict[str, int] = {}
    if kind in ("map", "bookmap"):
        blocks, _hrefs = _map_markdown(root, name, warnings, seen_unknown)
    else:
        blocks = _topic_markdown(root, warnings, seen_unknown)
        if not blocks or not any(b.startswith("#") for b in blocks):
            warnings.append("未发现根 <title>：section 数为 0（修复指引：DITA 主题必须有 "
                            "title 元素）")
    _warn_uncovered(seen_unknown, warnings)
    markdown = _to_markdown(blocks)
    ir = content_ir.parse(markdown, path=name, base_dir=base_dir)
    return Imported(ir=ir, markdown=markdown, schema=SCHEMA,
                    kind="ditamap" if kind in ("map", "bookmap") else "dita",
                    warnings=_dedupe(warnings), stats=_ir_stats(ir))


def _dedupe(items: List[str]) -> List[str]:
    seen: List[str] = []
    for it in items:
        if it not in seen:
            seen.append(it)
    return seen


def import_file(path: str, *, base_dir: Optional[str] = None) -> Imported:
    """`.dita` / `.ditamap` 文件 → Imported。"""
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        raise DitaImportError("文件不存在：%s（修复指引：给出在场的 .dita/.ditamap 路径）" % path)
    try:
        with open(p, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError as exc:
        raise DitaImportError("读取 DITA 失败：%s（修复指引：确认文件可读）" % exc) from exc
    base = base_dir if base_dir is not None else os.getcwd()
    return import_bytes(data, name=path, base_dir=base)
