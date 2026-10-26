"""DOCX → 内容 IR 导入器（T9.2，零依赖：zipfile + xml.etree）。

定位：NF 此前只有「导出」面（content IR → markdown/适配器），本模块补**导入**面——
外部 `.docx` 经本模块转成 **content IR**（`core.content_ir` 的节点图），从而可被
`nf ir check` / profile 判据 / 局部重写消费。

映射（DOCX 结构 → IR；实现方式 = 先归一为规范形 Markdown，再 `content_ir.parse`，
**不复制 IR 创建逻辑**）：
- 标题样式（`Heading1..6` / `Title`，含中文 Word 的数字 styleId 1..6）→ `section`
  （标题层级即 section 层级；无标题样式的文档 section 数为 0，段落全部保留）；
- 普通段落 → `paragraph(form="para")`；
- 带 `w:numPr` 的段落 → `paragraph(form="list")`（连续项合并为一个列表块）；
- `w:tbl` → `paragraph(form="table")`（首行作表头，单元格内多段落以空格连接）；
- 超链接/域/书签内文字按内联文本合并（不丢文）；
- **未覆盖元素**（图片 `w:drawing`、脚注/尾注引用、批注引用、公式 `m:oMath`、
  嵌入对象、altChunk）→ 不静默丢：文字能取则按段落保留，同时写入 `warnings`
  （元素名 + 次数 + 修复指引）。

fail-closed：文件不存在 / 非 zip / 缺 `word/document.xml` / XML 不可解析 / 超出入站
上限 → 抛 `DocxImportError`（带可执行修复指引）；CLI 捕获后归 rc=2，不冒内部错误。

纪律：纯标准库；确定性（同输入同输出）；不改 `content_ir` 判定逻辑（只调用 parse/
render/canonical）。
"""
from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from . import content_ir

SCHEMA = "nf-import-docx/1"
MAX_BYTES = 64 * 1024 * 1024          # 入站上限（与 trust_boundary.MAX_IMPORT_BYTES 同量级）
DOCUMENT_MEMBER = "word/document.xml"

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

_HEADING_RE = re.compile(r"^(?:heading|标题)\s*([1-6])$", re.I)
_HEADING_NUM_RE = re.compile(r"^([1-6])$")
_TITLE_STYLES = {"title": 1, "subtitle": 2}
_LIST_ORDERED_RE = re.compile(r"(?:number|numbered|编号|有序)", re.I)

#: 未覆盖元素 → 说明（文字可取则保留；取不到只告警）。
UNCOVERED = {
    _W + "drawing": "内嵌图片/形状（IR 无图片节点）",
    _W + "pict": "旧式图片（IR 无图片节点）",
    _W + "footnoteReference": "脚注引用（脚注正文不随主文档导入）",
    _W + "endnoteReference": "尾注引用（尾注正文不随主文档导入）",
    _W + "commentReference": "批注引用（批注正文不随主文档导入）",
    _M + "oMath": "公式（IR 无公式节点；可读文字已保留）",
    _W + "object": "嵌入对象（OLE；IR 无对象节点）",
    _W + "altChunk": "外部 altChunk 片段（需先合并进主文档）",
}


class DocxImportError(ValueError):
    """DOCX 导入失败（fail-closed；消息带修复指引）。"""


@dataclass
class Imported:
    """导入结果（模块 API；CLI/单测共用）。"""
    ir: content_ir.Document
    markdown: str
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    schema: str = SCHEMA

    def to_dict(self) -> Dict[str, Any]:
        return {"schema": self.schema, "format": "docx",
                "stats": dict(self.stats), "warnings": list(self.warnings),
                "markdown_sha256": _sha(self.markdown),
                "canonical": self.ir.canonical,
                "title": self.ir.title}


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _w(el: Optional[ET.Element], name: str) -> Optional[ET.Element]:
    if el is None:
        return None
    return el.find(_W + name)


def _text_of(el: Optional[ET.Element]) -> str:
    """元素内全部文字（w:t / m:t 等 itertext；制表/换行归一为空格）。"""
    if el is None:
        return ""
    parts: List[str] = []
    for node in el.iter():
        if node.text and _local(node.tag) in ("t", "delText", "instrText"):
            parts.append(node.text)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _heading_level(p: ET.Element) -> int:
    style = _w(_w(p, "pPr"), "pStyle")
    if style is None:
        return 0
    val = str(style.get(_W + "val") or "").strip()
    if not val:
        return 0
    if val.lower() in _TITLE_STYLES:
        return _TITLE_STYLES[val.lower()]
    m = _HEADING_RE.match(val) or _HEADING_NUM_RE.match(val)
    return int(m.group(1)) if m else 0


def _is_list_item(p: ET.Element, numbering: Dict[str, str]) -> Tuple[bool, bool]:
    """→ (是否列表项, 是否有序)。

    有序判定优先读 `word/numbering.xml` 的 numFmt（decimal/lowerLetter… = 有序；
    bullet/none = 无序）；缺 numbering 部件时退回样式名启发（编号/Number 字样 = 有序）。
    """
    ppr = _w(p, "pPr")
    numpr = _w(ppr, "numPr") if ppr is not None else None
    if numpr is None:
        return False, False
    num_id = _w(numpr, "numId")
    fmt = numbering.get(str(num_id.get(_W + "val") or ""), "") if num_id is not None else ""
    if fmt:
        return True, fmt not in ("bullet", "none")
    style = _w(ppr, "pStyle")
    val = str(style.get(_W + "val") or "") if style is not None else ""
    return True, bool(_LIST_ORDERED_RE.search(val))


def _numbering_formats(zf: zipfile.ZipFile) -> Dict[str, str]:
    """`word/numbering.xml` → {numId: numFmt}（缺部件/坏 XML 时返回空表，退回样式启发）。"""
    try:
        raw = zf.read("word/numbering.xml")
    except (KeyError, OSError, RuntimeError):
        return {}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return {}
    abstract: Dict[str, str] = {}
    for absnum in root.iter(_W + "abstractNum"):
        aid = str(absnum.get(_W + "abstractNumId") or "")
        lvl = _w(absnum, "lvl")
        fmt = _w(lvl, "numFmt") if lvl is not None else None
        if aid:
            abstract[aid] = str(fmt.get(_W + "val") or "") if fmt is not None else ""
    out: Dict[str, str] = {}
    for num in root.iter(_W + "num"):
        nid = str(num.get(_W + "numId") or "")
        ref = _w(num, "abstractNumId")
        aid = str(ref.get(_W + "val") or "") if ref is not None else ""
        if nid:
            out[nid] = abstract.get(aid, "")
    return out


def _cell_text(cell: ET.Element) -> str:
    texts = [_text_of(p) for p in cell.iter(_W + "p")]
    return " / ".join(t for t in texts if t)


def _table_markdown(tbl: ET.Element) -> List[str]:
    rows: List[List[str]] = []
    for tr in tbl.iter(_W + "tr"):
        cells = [_cell_text(tc) for tc in tr.iter(_W + "tc")]
        if cells:
            rows.append(cells)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(_esc(c) for c in rows[0]) + " |",
             "|" + "---|" * width]
    for r in rows[1:]:
        lines.append("| " + " | ".join(_esc(c) for c in r) + " |")
    if len(rows) == 1:                 # 只有表头行时补一行空数据，保证渲染成表
        lines.append("| " + " | ".join("" for _ in range(width)) + " |")
    return lines


def _esc(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _warn_unsupported(node: ET.Element, warnings: List[str]) -> None:
    for child in node.iter():
        tag = child.tag
        if tag in UNCOVERED:
            warnings.append("未覆盖元素 <%s>：%s——文字可读内容已保留，结构/格式信息丢失"
                            "（修复指引：转换前在 Word 中改为纯文本表格/段落）"
                            % (_local(tag), UNCOVERED[tag]))


def _collect_body_blocks(body: ET.Element, warnings: List[str],
                         numbering: Optional[Dict[str, str]] = None) -> List[str]:
    """docx body → 规范形 Markdown 块列表。"""
    numbering = numbering or {}
    blocks: List[str] = []
    para_buf: List[str] = []
    list_buf: List[str] = []
    list_ordered = False

    def flush_para() -> None:
        if para_buf:
            blocks.append("\n".join(para_buf))
            para_buf.clear()

    def flush_list() -> None:
        nonlocal list_ordered
        if list_buf:
            blocks.append("\n".join(list_buf))
            list_buf.clear()
        list_ordered = False

    for child in body:
        tag = child.tag
        if tag == _W + "p":
            _warn_unsupported(child, warnings)
            text = _text_of(child)
            level = _heading_level(child)
            is_list, ordered = _is_list_item(child, numbering)
            if level:
                flush_para()
                flush_list()
                blocks.append("%s %s" % ("#" * min(level, 6), text or "（无标题文字）"))
            elif is_list:
                flush_para()
                if list_buf and ordered != list_ordered:
                    flush_list()
                list_ordered = ordered
                marker = ("%d. " % (len(list_buf) + 1)) if ordered else "- "
                list_buf.append(marker + (text or "（空列表项）"))
            elif text:
                flush_list()
                para_buf.append(text)
        elif tag == _W + "tbl":
            _warn_unsupported(child, warnings)
            flush_para()
            flush_list()
            table = _table_markdown(child)
            if table:
                blocks.append("\n".join(table))
        elif tag == _W + "sectPr":
            continue
        else:
            _warn_unsupported(child, warnings)
    flush_para()
    flush_list()
    return blocks


def _to_markdown(blocks: List[str]) -> str:
    body = "\n\n".join(b.strip("\n") for b in blocks if b.strip())
    return body + "\n" if body else ""


def _ir_stats(ir: content_ir.Document) -> Dict[str, int]:
    forms = [n.form for n in ir.nodes.values() if n.kind == "paragraph"]
    return {"sections": len(ir.sections), "paragraphs": forms.count("para"),
            "tables": forms.count("table"), "lists": forms.count("list"),
            "headings": sum(1 for s in ir.sections if s.level > 1),
            "claims": len(ir.claims)}


def import_bytes(data: bytes, *, name: str = "", base_dir: str = "") -> Imported:
    """docx 字节 → Imported（CLI/测试共用；损坏件 fail-closed）。"""
    if len(data) > MAX_BYTES:
        raise DocxImportError("docx 过大：%d 字节 > 上限 %d 字节（修复指引：拆分文档后重导）"
                              % (len(data), MAX_BYTES))
    import io
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DocxImportError(
            "不是合法的 .docx（zip 结构损坏：%s）（修复指引：用 Word/WPS 另存为 .docx；"
            "旧式 .doc 须先另存为新格式）" % exc) from exc
    with zf:
        try:
            raw = zf.read(DOCUMENT_MEMBER)
        except KeyError as exc:
            raise DocxImportError(
                "docx 缺主文档部件 %s（修复指引：确认是 Word 生成的 .docx，而不是改了后缀的 "
                "zip/二进制）" % DOCUMENT_MEMBER) from exc
        except (OSError, RuntimeError) as exc:
            raise DocxImportError("docx 部件读取失败：%s（修复指引：重新导出文档）" % exc) from exc
        numbering = _numbering_formats(zf)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise DocxImportError(
            "docx 主文档 XML 不可解析：%s（修复指引：文件可能损坏，用 Word 重新保存）" % exc) from exc
    body = root.find(_W + "body")
    if body is None:
        raise DocxImportError("docx 主文档缺 w:body（修复指引：文件可能损坏，用 Word 重新保存）")
    warnings: List[str] = []
    blocks = _collect_body_blocks(body, warnings, numbering)
    if not any(b.startswith("#") for b in blocks):
        warnings.append("未发现标题样式（Heading/Title）：导入产物 section 数为 0——所有文字"
                        "按段落保留（修复指引：在 Word 中用「标题 1/2…」样式标记章节）")
    markdown = _to_markdown(blocks)
    ir = content_ir.parse(markdown, path=name, base_dir=base_dir)
    return Imported(ir=ir, markdown=markdown, warnings=_dedupe(warnings),
                    stats=_ir_stats(ir))


def _dedupe(items: List[str]) -> List[str]:
    seen: List[str] = []
    for it in items:
        if it not in seen:
            seen.append(it)
    return seen


def import_file(path: str, *, base_dir: Optional[str] = None) -> Imported:
    """`.docx` 文件 → Imported。"""
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        raise DocxImportError("文件不存在：%s（修复指引：给出在场的 .docx 路径）" % path)
    try:
        with open(p, "rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError as exc:
        raise DocxImportError("读取 docx 失败：%s（修复指引：确认文件可读）" % exc) from exc
    base = base_dir if base_dir is not None else os.getcwd()
    return import_bytes(data, name=path, base_dir=base)
