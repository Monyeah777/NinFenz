"""内容 IR（T7.2）：把 Markdown 产物升成**带类型的节点图**（content IR）。

定位：`core/ir.py` 的 IRDocument 是「装配结果 → 渲染」的薄中间层；本模块是**内容层**
IR——面向门禁与局部重写：产物不再只是一段散文，而是一棵带稳定 id 的节点树，节点可
被逐条判定（section / claim / 引用 / 实体 / slot 引用）、可被 diff/局部替换。

节点类型（`kind`）：
- `document`：根（title + 子节点）；
- `section`：标题节点（level/title/role；role = 八段结构角色，见 `SECTION_ROLES`）；
- `paragraph`：**通用内容块**（`form` 细分：para / list / table / quote / code /
  frontmatter / rule / html）——正文与表格/列表/代码围栏都保形保留，供逐字节还原；
- `claim`：句子级断言（从段落/列表项切分；`normative` 标记规范性措辞）；
- `citation`：引用（§N / 第N节 / 全限定编号 / 链接 / 路径 / URL）；
- `entity`：实体引用（模块 Mxx、管线 Pxx、术语）；
- `slot_ref`：数据槽/资产键引用（`asset_get("KEY")` 与反引号大写键）。

稳定 id：`id = "<kind>-" + sha256(kind \\0 path \\0 规范内容)[:16]`。同输入同 id；
内容或结构路径变则 id 变（路径含兄弟序号与层级）。

规范形（`canonical`）与逐字节确定性：
- 编码 UTF-8、换行 LF、文件尾单个换行；
- 行尾空白全部去除；块间恰好一个空行；块内空行保留（代码围栏内原样）；
- 标题规范为 `#…###### + 单空格 + 标题文本`；
- `render(parse(text)) == canonical(text)`（对任意输入成立；规范形输入则与原文逐字节一致）。

`check_file(path)` 做节点级检查：section / paragraph / claim / citation 计数、无归属
引用、悬空引用、悬空实体，并把 techdoc-strict profile 的 3 条文本规则（标题句式 /
标题末尾标点 / 单空格）**以 IR 节点为执行面**重跑（复用 `gate_profile_rules` 的判据
实现，不改 profile 引擎）。

纪律：纯标准库；确定性（同输入同输出）；不猜测缺失字段（无声明即如实报悬空）。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA = "nf-content-ir/1"
REPORT_SCHEMA = "nf-content-ir-check/1"

#: 八段结构角色（标题文本关键词匹配；顺序即优先级）。
SECTION_ROLES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("assembly_record", ("装配记录",)),
    ("overview", ("速览", "概览")),
    ("pipeline", ("管线",)),
    ("registry", ("注册表", "投影")),
    ("modules", ("模块库", "模块")),
    ("assets", ("资产",)),
    ("guide", ("装载指引", "指引")),
    ("checklist", ("自检清单", "校验", "验收")),
    ("appendix", ("附录",)),
)

#: 3 条以 IR 节点为执行面的 techdoc-strict 文本规则（clause_id → rule id）。
IR_TEXT_RULES: Tuple[Tuple[str, str], ...] = (
    ("MS-STYLE-HEADING-SENTENCE", "heading_sentence"),
    ("MS-STYLE-HEADING-PUNCT", "heading_end_punct"),
    ("MS-STYLE-SPACE-01", "single_space"),
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
_TABLE_RE = re.compile(r"^\s*\|")
_QUOTE_RE = re.compile(r"^\s*>")
_LIST_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+\S")
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_TEXT_RULE_LEAD = "（规则说明见 profile evidence）"

_CITE_SECTION = re.compile(r"§\s*(\d+(?:[.-]\d+)*)")
_CITE_CHAPTER = re.compile(r"第\s*(\d+)\s*(?:节|章|步)")
_CITE_QUALIFIED = re.compile(r"\b([0-9A-Za-z_\u4e00-\u9fa5]+:[MTP]\d{2,3})\b")
_CITE_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CITE_PATH = re.compile(r"`([^`\n]*(?:/|\.md|\.json)[^`\n]*)`")
_CITE_URL = re.compile(r"(https?://[^\s)>\]]+)")
_ENTITY_MODULE = re.compile(r"\b((?:[0-9A-Za-z_\u4e00-\u9fa5]+:)?[MP]\d{2,3})\b")
_SLOT_KEY = re.compile(r"`([A-Z][A-Z0-9_]{2,})`")
_ASSET_CALL = re.compile(r"asset_(?:get|query|match|roll)\(\s*[\"']([A-Z][A-Z0-9_]{2,})")
_TERM_ROW = re.compile(r"^\s*\|\s*([^|]{1,40}?)\s*\|")
_SENTENCE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
_NORMATIVE = re.compile(r"(必须|应当|应|禁止|不得|须|要求|输出|结论|见|依据|禁止|不应)")

MAX_NODES = 200_000


# ------------------------------------------------------------------ 节点
@dataclass
class Node:
    """内容 IR 节点（类型化：document / section / paragraph / claim / citation /
    entity / slot_ref）。序列化面 = `to_dict()`（键序固定，JSON 确定性）。"""
    kind: str
    path: str
    id: str = ""
    form: str = ""
    text: str = ""
    title: str = ""
    level: int = 0
    role: str = ""
    anchor: str = ""
    target: str = ""
    owner: str = ""
    resolved: bool = True
    normative: bool = False
    raw: List[str] = field(default_factory=list)
    children: List["Node"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """确定性字典（键序固定；raw 仅在内容块上出现）。"""
        out: Dict[str, Any] = {"kind": self.kind, "id": self.id, "path": self.path}
        for key in ("form", "text", "title", "role", "anchor", "target", "owner"):
            val = getattr(self, key)
            if val:
                out[key] = val
        if self.kind == "section":
            out["level"] = self.level
        if self.kind == "claim":
            out["normative"] = self.normative
        if self.kind == "citation":
            out["resolved"] = self.resolved
        if self.raw:
            out["raw"] = list(self.raw)
        if self.children:
            out["children"] = [c.to_dict() for c in self.children]
        return out

    def walk(self) -> Iterable["Node"]:
        yield self
        for c in self.children:
            yield from c.walk()


@dataclass
class Document:
    """内容 IR 根：`title` + 树 + 派生索引（声明/引用/实体）。"""
    schema: str = SCHEMA
    path: str = ""
    base_dir: str = ""
    title: str = ""
    canonical: bool = True
    noncanonical_reason: str = ""
    root: Node = field(default_factory=lambda: Node(kind="document", path="doc"))
    nodes: Dict[str, Node] = field(default_factory=dict)
    citations: List[Node] = field(default_factory=list)
    entities: List[Node] = field(default_factory=list)
    slot_refs: List[Node] = field(default_factory=list)
    sections: List[Node] = field(default_factory=list)
    claims: List[Node] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"schema": self.schema, "path": self.path, "title": self.title,
                "canonical": self.canonical,
                "noncanonical_reason": self.noncanonical_reason,
                "counts": {"sections": len(self.sections),
                           "claims": len(self.claims),
                           "citations": len(self.citations),
                           "entities": len(self.entities),
                           "slot_refs": len(self.slot_refs),
                           "nodes": len(self.nodes)},
                "root": self.root.to_dict()}


def _nid(kind: str, path: str, content: str) -> str:
    """稳定 id = kind + 结构路径 + 规范内容（内容/位置变则变）。"""
    h = hashlib.sha256(("%s\0%s\0%s" % (kind, path, content)).encode("utf-8")).hexdigest()
    return "%s-%s" % (kind, h[:16])


def _section_role(title: str) -> str:
    for role, words in SECTION_ROLES:
        if any(w in title for w in words):
            return role
    return "unknown"


def _heading_line(level: int, title: str) -> str:
    return "%s %s" % ("#" * level, _collapse_ws(title))


def _collapse_ws(text: str) -> str:
    """标题文本内空白归一到单空格（空白不敏感的规范形判据）。"""
    return re.sub(r"\s+", " ", str(text or "")).strip()


# ------------------------------------------------------------------ 规范形
def _normalize_lines(text: str) -> str:
    """行级归一（LF / 行尾空白 / 连续空行 / 标题单空格 / 文件尾单换行）。"""
    t = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    out: List[str] = []
    for raw in t.split("\n"):
        ln = raw.rstrip()
        m = _HEADING_RE.match(ln)
        if m:
            ln = _heading_line(len(m.group(1)), m.group(2))
        if not ln:
            if out and out[-1] != "":
                out.append("")
            continue
        out.append(ln)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n" if out else ""


def canonical(text: str) -> str:
    """规范形 Markdown = `render(parse(text))`。

    规范形在行级归一之外还规定**块间边界**（块与块之间恰好一个空行；标题后、
    列表/表格/围栏/引用前后都按块边界处理）。因此任意输入都可归一到规范形；
    已经是规范形的产物（`nf assemble` 八段产物）满足 `canonical(t) == t`。
    """
    return render(parse(text))


def render(ir: Document) -> str:
    """IR → 规范形 Markdown（逐字节确定性；同 IR 同输出）。"""
    lines: List[str] = []

    def push(block_lines: List[str]) -> None:
        if not block_lines:
            return
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(block_lines)

    def emit(node: Node) -> None:
        if node.kind == "document":
            for c in node.children:
                emit(c)
            return
        if node.kind == "section":
            push([_heading_line(node.level, node.title)])
            for c in node.children:
                emit(c)
            return
        if node.raw:
            push(list(node.raw))
            for c in node.children:
                emit(c)

    emit(ir.root)
    body = "\n".join(lines).rstrip("\n")
    return body + "\n" if body else ""


# ------------------------------------------------------------------ 解析
def _take_fence(lines: List[str], i: int) -> Tuple[List[str], int]:
    m = _FENCE_RE.match(lines[i])
    assert m is not None
    ch, size = m.group(2)[0], len(m.group(2))
    block = [lines[i]]
    j = i + 1
    while j < len(lines):
        block.append(lines[j])
        mm = _FENCE_RE.match(lines[j])
        if mm and mm.group(2)[0] == ch and len(mm.group(2)) >= size \
                and not mm.group(3).strip():
            return block, j + 1
        j += 1
    return block, j


def _take_while(lines: List[str], i: int, pred) -> Tuple[List[str], int]:
    block: List[str] = []
    j = i
    while j < len(lines) and pred(lines[j], block):
        block.append(lines[j])
        j += 1
    return block, j


def _is_block_start(ln: str) -> bool:
    return bool(_HEADING_RE.match(ln) or _FENCE_RE.match(ln) or _TABLE_RE.match(ln)
                or _QUOTE_RE.match(ln) or _LIST_RE.match(ln) or _HR_RE.match(ln)
                or ln.lstrip().startswith("<!--"))


def _list_cont(ln: str, block: List[str]) -> bool:
    return bool(_LIST_RE.match(ln) or (block and ln.startswith((" ", "\t"))
                                       and not _is_block_start(ln)))


def _split_blocks(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """规范行文本 → 顶层块列表（[{"form","lines"}]）与原文行。"""
    lines = _normalize_lines(text).splitlines()
    blocks: List[Dict[str, Any]] = []
    i = 0
    # frontmatter（首个非空块是 --- … ---）
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        close = next((j for j in range(i + 1, len(lines)) if lines[j].strip() == "---"), -1)
        if close > 0:
            blocks.append({"form": "frontmatter", "lines": lines[i:close + 1]})
            i = close + 1
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        m = _HEADING_RE.match(ln)
        if m:
            blocks.append({"form": "heading", "level": len(m.group(1)),
                           "title": _collapse_ws(m.group(2)),
                           "lines": [_heading_line(len(m.group(1)), m.group(2))]})
            i += 1
            continue
        if _FENCE_RE.match(ln):
            raw, i = _take_fence(lines, i)
            blocks.append({"form": "code", "lines": raw})
            continue
        if _TABLE_RE.match(ln):
            raw, i = _take_while(lines, i, lambda x, _b: bool(_TABLE_RE.match(x)))
            blocks.append({"form": "table", "lines": raw})
            continue
        if _QUOTE_RE.match(ln):
            raw, i = _take_while(lines, i, lambda x, _b: bool(_QUOTE_RE.match(x)))
            blocks.append({"form": "quote", "lines": raw})
            continue
        if _LIST_RE.match(ln):
            raw, i = _take_while(lines, i, _list_cont)
            blocks.append({"form": "list", "lines": raw})
            continue
        if _HR_RE.match(ln):
            blocks.append({"form": "rule", "lines": [ln]})
            i += 1
            continue
        if ln.lstrip().startswith("<!--"):
            raw, i = _take_while(lines, i, lambda x, b: not b or "-->" not in b[-1])
            blocks.append({"form": "html", "lines": raw})
            continue
        raw, i = _take_while(
            lines, i,
            lambda x, b: bool(x.strip()) and (not b or not _is_block_start(x)))
        blocks.append({"form": "para", "lines": raw})
    return blocks, lines


class _Builder:
    """块列表 → 节点树（section 栈；节点 id 按路径+内容派生）。"""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.sections: List[Node] = []
        self.counters: Dict[str, int] = {}
        self.root = Node(kind="document", path="doc",
                         id=_nid("document", "doc", ""))

    def _child_path(self, parent: Node, kind: str) -> str:
        key = parent.path
        self.counters[key] = self.counters.get(key, 0) + 1
        return "%s/%s%d" % (parent.path, kind[0], self.counters[key])

    def add_block(self, parent: Node, form: str, raw: List[str],
                  title: str = "", level: int = 0) -> Node:
        if form == "heading":
            node = Node(kind="section", path=self._child_path(parent, "section"),
                        form="", title=title, level=level,
                        role=_section_role(title))
            node.id = _nid("section", node.path,
                           "%d\n%s" % (level, title.strip()))
            node.raw = [_heading_line(level, title)]
            parent.children.append(node)
            self.nodes[node.id] = node
            self.sections.append(node)
            return node
        node = Node(kind="paragraph", path=self._child_path(parent, "block"),
                    form=form, raw=list(raw))
        node.text = "\n".join(raw)
        node.id = _nid("paragraph", node.path, node.text)
        parent.children.append(node)
        self.nodes[node.id] = node
        return node


def _attach_section_tree(root: Node, blocks: List[Dict[str, Any]]) -> List[Node]:
    builder = _Builder()
    builder.root = root
    stack: List[Node] = [root]
    for blk in blocks:
        form = blk["form"]
        if form == "heading":
            while len(stack) > 1 and stack[-1].kind == "section" \
                    and stack[-1].level >= blk["level"]:
                stack.pop()
            node = builder.add_block(stack[-1], "heading", blk["lines"],
                                     title=blk["title"], level=blk["level"])
            stack.append(node)
        else:
            builder.add_block(stack[-1], form, blk["lines"])
    return builder.sections


def _rebuild_indexes(ir: Document) -> None:
    """重建节点索引与派生面（两遍：先登记 section 树 → 再抽 claim/引用/实体）。"""
    ir.nodes = {}
    ir.sections, ir.claims, ir.citations = [], [], []
    ir.entities, ir.slot_refs = [], []
    ir.nodes[ir.root.id] = ir.root

    def visit(node: Node, section: Optional[Node]) -> None:
        node.owner = "" if section is None else section.id
        ir.nodes[node.id] = node
        if node.kind == "section":
            ir.sections.append(node)
            for child in node.children:
                visit(child, node)
            return
        for child in node.children:
            if child.kind == "paragraph":
                visit(child, section)

    for child in ir.root.children:
        visit(child, None)

    def derive(node: Node, section: Optional[Node]) -> None:
        if node.kind == "section":
            for child in node.children:
                derive(child, node)
            return
        if node.kind != "paragraph":
            return
        if node.form in ("para", "list", "quote"):
            _derive_claims(ir, node, section)
        else:
            _extract(ir, node, None, section)

    for child in ir.root.children:
        derive(child, None)


def _derive_claims(ir: Document, block: Node, section: Optional[Node]) -> None:
    """段落/列表/引用 → claim 节点；引用与实体挂到 claim（无 claim 才挂块）。"""
    pairs = _claims_of(block)
    for idx, (text, _off) in enumerate(pairs):
        claim = Node(kind="claim", path="%s/claim%d" % (block.path, idx),
                     text=text, normative=bool(_NORMATIVE.search(text)),
                     owner=block.id)
        claim.id = _nid("claim", claim.path, text)
        ir.claims.append(claim)
        ir.nodes[claim.id] = claim
        block.children.append(claim)
        _extract(ir, claim, claim, section)
    if not pairs:                      # 空段（如仅分隔符）也保留块级引用面
        _extract(ir, block, None, section)


def _extract(ir: Document, base: Node, claim: Optional[Node],
             section: Optional[Node]) -> None:
    """从块/claim 文本抽取引用、实体、slot 引用。"""
    owner = base.id
    owner_section = section.id if section is not None else ""
    for cid, (kind, target, match_text) in enumerate(_citations_in(base.text)):
        cite = Node(kind="citation", path="%s/cite%d" % (base.path, cid),
                    form=kind, text=match_text, target=target, owner=owner,
                    anchor=owner_section)
        if kind in ("section", "anchor", "path"):
            cite.resolved = _resolved(ir, kind, target)
        cite.id = _nid("citation", cite.path,
                       "%s\n%s\n%s" % (kind, target, match_text))
        ir.citations.append(cite)
        ir.nodes[cite.id] = cite
        if claim is not None:
            claim.children.append(cite)
    for pos, (kind, value) in enumerate(_entities_in(base.text)):
        ent = Node(kind="entity", path="%s/ent%d" % (base.path, pos),
                   form=kind, text=value, owner=owner, anchor=owner_section)
        ent.id = _nid("entity", ent.path, "%s\n%s" % (kind, value))
        ir.entities.append(ent)
        ir.nodes[ent.id] = ent
        if claim is not None:
            claim.children.append(ent)
    for pos, key in enumerate(_slot_keys_in(base.text)):
        slot = Node(kind="slot_ref", path="%s/slot%d" % (base.path, pos),
                    form="asset_key", text=key, owner=owner)
        slot.id = _nid("slot_ref", slot.path, key)
        ir.slot_refs.append(slot)
        ir.nodes[slot.id] = slot
        if claim is not None:
            claim.children.append(slot)


def _claims_of(block: Node) -> List[Tuple[str, int]]:
    """块 → [(句子文本, 行偏移)]（列表项逐项、段落整体切句）。"""
    out: List[Tuple[str, int]] = []
    for off, ln in enumerate(block.raw):
        if block.form == "list":
            m = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", ln)
            text = (m.group(1) if m else ln.strip())
        elif block.form in ("para", "quote"):
            text = ln.strip().lstrip(">").strip()
        else:
            continue
        for s in _SENTENCE.findall(text):
            s = s.strip()
            if s:
                out.append((s, off))
    return out


def _citations_in(text: str) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    for m in _CITE_CHAPTER.finditer(text):
        out.append(("section", m.group(1), m.group(0)))
    for m in _CITE_SECTION.finditer(text):
        out.append(("section", m.group(1), m.group(0)))
    for m in _CITE_QUALIFIED.finditer(text):
        out.append(("qualified", m.group(1), m.group(0)))
    for m in _CITE_LINK.finditer(text):
        target = m.group(1)
        kind = "anchor" if target.startswith("#") else ("url" if "://" in target else "path")
        out.append((kind, target.lstrip("#") if kind == "anchor" else target, m.group(0)))
    for m in _CITE_URL.finditer(text):
        out.append(("url", m.group(1), m.group(0)))
    seen: Dict[Tuple[str, str], int] = {}
    uniq: List[Tuple[str, str, str]] = []
    for kind, target, raw in out:
        key = (kind, target)
        if key in seen:
            continue
        seen[key] = 1
        uniq.append((kind, target, raw))
    return uniq


def _entities_in(text: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for m in _ENTITY_MODULE.finditer(text):
        val = m.group(1)
        out.append(("pipeline" if val.startswith("P") else "module", val))
    return out


def _slot_keys_in(text: str) -> List[str]:
    keys = [m.group(1) for m in _SLOT_KEY.finditer(text)]
    keys += [m.group(1) for m in _ASSET_CALL.finditer(text)]
    return sorted(set(keys))


def _resolved(ir: Document, kind: str, target: str) -> bool:
    if kind == "path":
        return _path_exists(ir, target)
    if kind == "anchor":
        return _anchor_exists(ir, target)
    if kind == "section":
        return _section_number_exists(ir, target)
    return True


def _anchor_exists(ir: Document, target: str) -> bool:
    for sec in ir.sections:
        if _anchor_of(sec) == target or _slug(sec.title) == target:
            return True
    return False


def _slug(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text.strip().lower()).strip("-")


def _anchor_of(sec: Node) -> str:
    m = re.search(r"\{#([A-Za-z0-9._:-]+)\}", sec.raw[0] if sec.raw else "")
    return m.group(1) if m else ""


def _section_number_exists(ir: Document, target: str) -> bool:
    want = str(target).strip().split(".")[0]
    for sec in ir.sections:
        m = re.match(r"^(\d+)\s*[.、]", sec.title.strip())
        if m and m.group(1) == want:
            return True
    return False


def _path_exists(ir: Document, target: str) -> bool:
    """路径引用可寻址：文件同目录 → IR base_dir（仓库根）→ 当前工作目录。"""
    cand = Path(target)
    if cand.is_absolute():
        return cand.exists()
    bases = [Path(ir.base_dir)] if ir.base_dir else []
    if ir.path:
        bases.append(Path(ir.path).resolve().parent)
    bases.append(Path.cwd())
    return any((b / cand).exists() for b in bases)


def _frontmatter_title(blocks: List[Dict[str, Any]]) -> str:
    """frontmatter 的 `title:` 兜底（无 H1 的馆藏样本靠它取标题）。"""
    for blk in blocks:
        if blk["form"] != "frontmatter":
            continue
        for ln in blk["lines"][1:]:
            m = re.match(r"^title:\s*(.+?)\s*$", ln)
            if m:
                return m.group(1).strip().strip("\"'`")
    return ""


def parse(text: str, path: str = "", base_dir: str = "") -> Document:
    """Markdown → 内容 IR（确定性：同输入同节点/id）。"""
    ir = Document(path=path, base_dir=base_dir)
    blocks, _lines = _split_blocks(text)
    title = next((b["title"] for b in blocks if b["form"] == "heading"
                  and b["level"] == 1), "")
    ir.title = title or _frontmatter_title(blocks)
    _attach_section_tree(ir.root, blocks)
    _rebuild_indexes(ir)
    canon = render(ir)
    ir.canonical = (canon == _normalize_source(text))
    if not ir.canonical:
        ir.noncanonical_reason = ("原文非规范形（行尾空白/空行数/标题间距/文件尾换行/"
                                  "块间空行）——以 `nf ir render` 的 canonical 输出为准")
    return ir


def _normalize_source(text: str) -> str:
    """原文按「仅换行归一」的对照面（用于判断是否已是规范形）。"""
    t = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return t + "\n" if t and not t.endswith("\n") else t


# ------------------------------------------------------------------ 节点级检查
def _declared_sets(ir: Document) -> Tuple[set, set]:
    """文档内**已声明**的实体与 slot 键（按八段角色定位声明区）。"""
    decl_roles = {"registry", "modules", "pipeline", "assets", "glossary"}
    entities, slots = set(), set()
    for sec in ir.sections:
        if sec.role in decl_roles or "术语表" in sec.title:
            for node in sec.walk():
                if node.kind != "paragraph":
                    continue
                for _kind, val in _entities_in(node.text):
                    entities.add(val)
                slots.update(_slot_keys_in(node.text))
    return entities, slots


def _check_citations(ir: Document) -> Tuple[List[Node], List[Node]]:
    """→ (无归属引用, 悬空引用)。"""
    unattributed = [c for c in ir.citations if not c.anchor]
    dangling = [c for c in ir.citations if not c.resolved]
    return unattributed, dangling


def _check_entities(ir: Document) -> List[Node]:
    declared, declared_slots = _declared_sets(ir)
    out: List[Node] = []
    for ent in ir.entities:
        if ent.text not in declared:
            out.append(ent)
    for slot in ir.slot_refs:
        if slot.text not in declared_slots:
            out.append(slot)
    return out


def ir_text_rule_findings(ir: Document) -> List[Dict[str, Any]]:
    """3 条 techdoc-strict 文本规则 → 对 IR 节点执行（复用引擎判据实现，不改引擎）。"""
    from core import gate_profile_rules as gpr   # 惰性：只借判据实现，不碰 profile 引擎

    findings: List[Dict[str, Any]] = []
    for clause_id, rule in IR_TEXT_RULES:
        pred = {"kind": "text_rule", "rule": rule}
        if rule in ("heading_sentence", "heading_end_punct"):
            targets = [(sec.id, "section", "## %s" % sec.title) for sec in ir.sections]
        else:
            targets = [(p.id, p.form, "\n".join(p.raw))
                       for p in ir.nodes.values() if p.kind == "paragraph"]
        for node_id, node_kind, content in sorted(targets):
            for f in gpr._TEXT_IMPL[rule](pred, gpr.build_context(content)):
                findings.append({"clause_id": clause_id, "rule": rule,
                                 "node_id": node_id, "node_kind": node_kind,
                                 "message": f.get("message", ""),
                                 "line": f.get("line", 0),
                                 "text": f.get("text", "")})
    return findings


def check_file(path: str, root: Optional[str] = None) -> Dict[str, Any]:
    """节点级检查：读文件 → parse → 统计/悬空/无归属/3 条文本规则。"""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    ir = parse(text, path=str(p), base_dir=str(root or ""))
    unattributed, dangling = _check_citations(ir)
    dangling_entities = _check_entities(ir)
    rule_findings = ir_text_rule_findings(ir)
    report = {
        "schema": REPORT_SCHEMA,
        "path": str(path),
        "title": ir.title,
        "canonical": ir.canonical,
        "noncanonical_reason": ir.noncanonical_reason,
        "counts": {"sections": len(ir.sections), "claims": len(ir.claims),
                   "citations": len(ir.citations), "entities": len(ir.entities),
                   "slot_refs": len(ir.slot_refs),
                   "paragraphs": sum(1 for n in ir.nodes.values()
                                     if n.kind == "paragraph"),
                   "nodes": len(ir.nodes)},
        "unattributed_citations": [_cite_row(c) for c in unattributed],
        "dangling_citations": [_cite_row(c) for c in dangling],
        "dangling_entities": [_entity_row(e) for e in dangling_entities],
        "text_rules": rule_findings,
        "roundtrip_ok": render(parse(canonical(text))) == canonical(text),
    }
    report["ok"] = (not dangling and not dangling_entities
                    and report["roundtrip_ok"])
    return report


def _cite_row(c: Node) -> Dict[str, Any]:
    return {"kind": c.form, "target": c.target, "owner": c.owner,
            "section": c.anchor, "raw": c.text}


def _entity_row(e: Node) -> Dict[str, Any]:
    return {"kind": e.form, "value": e.text, "owner": e.owner}


def format_report(report: Dict[str, Any]) -> str:
    """人读报告（`nf ir check` 默认输出）。"""
    c = report.get("counts") or {}
    lines = ["== nf ir check：%s ==" % report.get("path"),
             "  规范形：%s%s" % ("是" if report.get("canonical") else "否",
                                "（%s）" % report["noncanonical_reason"]
                                if report.get("noncanonical_reason") else ""),
             "  节点：section %d · paragraph %d · claim %d · citation %d · entity %d · slot_ref %d"
             % (c.get("sections", 0), c.get("paragraphs", 0), c.get("claims", 0),
                c.get("citations", 0), c.get("entities", 0), c.get("slot_refs", 0)),
             "  往返：%s（parse→render == canonical）"
             % ("逐字节一致" if report.get("roundtrip_ok") else "不一致")]
    for label, key in (("无归属引用", "unattributed_citations"),
                       ("悬空引用", "dangling_citations"),
                       ("悬空实体", "dangling_entities")):
        rows = report.get(key) or []
        lines.append("  %s：%d%s" % (label, len(rows),
                                     "（%s）" % "、".join(str(r) for r in rows[:3])
                                     if rows else ""))
    rules = report.get("text_rules") or []
    lines.append("  IR 文本规则（3 条）：%d 处命中" % len(rules))
    for row in rules[:8]:
        lines.append("    · [%s] %s <- %s" % (row["clause_id"], row["message"],
                                              row["node_id"]))
    return "\n".join(lines)


def to_json(ir: Document, indent: int = 2) -> str:
    """确定性 JSON（键序固定；UTF-8 直出）。"""
    return json.dumps(ir.to_dict(), ensure_ascii=False, indent=indent, sort_keys=False)
