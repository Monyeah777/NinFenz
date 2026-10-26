"""M80 质量门 profile 判据集（文档视图 + 5 条文本规则 + 结构/术语判据）。

从 `gate_profile.py` 拆出（2026-10-26）：核心代码指标对新文件有「≤800 行 /
单函数圈复杂度 ≤25」的冻结上限，拆分后两个模块各自在限内；`gate_profile` 保留
schema 校验 / 加载 / 逐条报告 / 质量门接线，并 re-export 本模块的公开面。

- `build_context()`：markdown → 判据视图（围栏感知；装载 profile 术语表）；
- `TEXT_RULES` / `_TEXT_IMPL`：5 条确定性文本规则（标题句式 / 标题末尾标点 /
  单空格 / 缩写首用 / 弱表达）；
- `PREDICATES` / `PREDICATE_KINDS`：结构判据（标题/引用/章节/表格/修订/术语等）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

#: 5 条确定性文本规则（clause predicate.kind == "text_rule" 的合法值）。
TEXT_RULES = ("heading_sentence", "heading_end_punct", "single_space",
              "acronym_first_use", "weak_expression")

#: 弱表达默认词表（profile 可用 predicate.options.weak_words 覆盖）。
DEFAULT_WEAK_WORDS = (
    "大概", "可能", "也许", "似乎", "尽量", "较为", "一定程度上", "差不多",
    "应该是", "或许", "大致", "稍微",
    "maybe", "probably", "possibly", "approximately", "might", "perhaps",
)

#: 标题末尾禁用的句末标点（MS Style: 标题不带句末标点）。
_HEADING_END_PUNCT = tuple("。.，,；;：:！!？?")

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_EXPLICIT_ANCHOR = re.compile(r"\{#([A-Za-z0-9._:-]+)\}")
_INLINE_LINK = re.compile(r"\]\(#([^)\s]+)\)")
_NUMBERED = re.compile(r"^\s*\d+[.)、]\s+\S")
_ACRONYM = re.compile(r"\b[A-Z]{2,}[A-Z0-9]{0,4}\b")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION = re.compile(r"^v?(\d+(?:\.\d+)*)$")


# ------------------------------------------------------------------ 文档视图
@dataclass
class DocContext:
    """一次判据执行的文档视图（只解析一次，逐 clause 复用）。"""
    text: str
    lines: List[str] = field(default_factory=list)
    in_code: List[bool] = field(default_factory=list)
    headings: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    glossary: List[Dict[str, Any]] = field(default_factory=list)

    def prose_lines(self) -> List[Tuple[int, str]]:
        return [(i + 1, ln) for i, ln in enumerate(self.lines) if not self.in_code[i]]

    def body_text(self) -> str:
        return "\n".join(ln for _i, ln in self.prose_lines())

    def heading_text(self) -> str:
        return "\n".join(h["raw"] for h in self.headings)


def _mark_code(lines: List[str]) -> List[bool]:
    """逐行标记是否在代码围栏内（围栏行自身也算「内」——围栏里的示例不判文风）。"""
    flags: List[bool] = []
    depth = 0
    for ln in lines:
        if _FENCE.match(ln):
            flags.append(True)      # 围栏行本身不参与正文判据
            depth = 0 if depth else 1
        else:
            flags.append(bool(depth))
    return flags


def _parse_headings(lines: List[str], in_code: List[bool]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, ln in enumerate(lines):
        if in_code[i]:
            continue
        m = _HEADING.match(ln)
        if not m:
            continue
        raw_text = m.group(2)
        anchors = _EXPLICIT_ANCHOR.findall(raw_text)
        text = _EXPLICIT_ANCHOR.sub("", raw_text).strip()
        out.append({"line": i + 1, "level": len(m.group(1)), "text": text,
                    "raw": ln, "anchors": anchors})
    return out


def _cells(row: str) -> List[str]:
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator(row: str) -> bool:
    cells = _cells(row)
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c) for c in cells if c != "") \
        and any(c for c in cells)


def _parse_tables(lines: List[str], in_code: List[bool]) -> List[Dict[str, Any]]:
    tables: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if in_code[i] or not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        start = i
        block: List[str] = []
        while i < len(lines) and not in_code[i] and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2:
            continue
        header = _cells(block[0])
        body_rows = [r for r in block[1:] if not _is_separator(r)]
        tables.append({"line": start + 1, "header": header,
                       "rows": [_cells(r) for r in body_rows], "raw": block})
    return tables


def _parse_glossary(path: Path) -> List[Dict[str, Any]]:
    """从术语表资产（markdown 表格：术语 | 定义 | 别名）解析术语条目。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    in_code = _mark_code(lines)
    out: List[Dict[str, Any]] = []
    for table in _parse_tables(lines, in_code):
        header = [c for c in table["header"]]
        idx_term = next((j for j, c in enumerate(header) if "术语" in c), None)
        idx_def = next((j for j, c in enumerate(header)
                        if "定义" in c or "说明" in c), None)
        if idx_term is None or idx_def is None:
            continue
        idx_alias = next((j for j, c in enumerate(header) if "别名" in c), None)
        for row in table["rows"]:
            if idx_term >= len(row):
                continue
            term = row[idx_term].strip().strip("`")
            if not term:
                continue
            definition = row[idx_def].strip() if idx_def < len(row) else ""
            aliases: List[str] = []
            if idx_alias is not None and idx_alias < len(row):
                aliases = [a.strip().strip("`") for a in
                           re.split(r"[、,，/;；\s]+", row[idx_alias])
                           if a.strip()]
            out.append({"term": term, "definition": definition, "aliases": aliases})
    return out


def build_context(text: str, profile: Optional[Dict[str, Any]] = None,
                  base_dir: Optional[Path] = None) -> DocContext:
    """文档 → 判据视图（围栏感知；profile.assets.glossary 存在时一并装载）。"""
    lines = text.splitlines()
    in_code = _mark_code(lines)
    ctx = DocContext(text=text, lines=lines, in_code=in_code,
                     headings=_parse_headings(lines, in_code),
                     tables=_parse_tables(lines, in_code))
    assets = (profile or {}).get("assets") or {}
    rel = assets.get("glossary")
    if rel and base_dir is not None:
        ctx.glossary = _parse_glossary(Path(base_dir) / rel)
    return ctx


# ------------------------------------------------------------------ 取证件
def _finding(f: str, line: int = 0, text: str = "") -> Dict[str, Any]:
    return {"line": int(line), "text": text.strip(), "message": f}


def _snippet(s: str, n: int = 80) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "…"


# ---------------------------------------------------------- 5 条确定性文本规则
def _text_heading_sentence(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    """标题句式（MS Style：句式大小写、陈述式名词短语）。"""
    out: List[Dict[str, Any]] = []
    for h in ctx.headings:
        text = h["text"]
        if not text:
            out.append(_finding("空标题（标题须有实义文本）", h["line"], h["raw"]))
            continue
        latin = [c for c in text if c.isascii() and c.isalpha()]
        if latin and all(c.isupper() for c in latin):
            out.append(_finding("标题全大写（MS Style：标题用句式大小写，不整句大写）",
                                h["line"], h["raw"]))
        first = text.lstrip()[0]
        if first.isascii() and first.isalpha() and first.islower():
            out.append(_finding("标题首词小写（标题首字母/首词应大写）", h["line"], h["raw"]))
        if text.rstrip().endswith(("?", "？", "！", "!")):
            out.append(_finding("标题为疑问/感叹句（主题式标题应用陈述式名词短语）",
                                h["line"], h["raw"]))
    return out


def _text_heading_end_punct(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    """标题末尾标点（标题不带句末标点）。"""
    out: List[Dict[str, Any]] = []
    for h in ctx.headings:
        if h["raw"].rstrip().endswith("```"):
            continue
        if h["text"].rstrip().endswith(_HEADING_END_PUNCT):
            out.append(_finding("标题末尾带句末标点（标题不加句号/冒号等）",
                                h["line"], h["raw"]))
    return out


def _text_single_space(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    """单空格（正文：词间单空格；标点前不空格）。"""
    out: List[Dict[str, Any]] = []
    for lineno, ln in ctx.prose_lines():
        stripped = ln.strip()
        if not stripped or stripped.startswith("|"):
            continue        # 表格对齐空格属排版，不属「词间空格」
        if re.search(r"\S {2,}\S", ln):
            out.append(_finding("正文出现连续多个空格（词间应为单空格）", lineno, ln))
        if re.search(r"[ \t][，。；：！？,.;:!?]", ln):
            out.append(_finding("标点前出现空格（标点应紧贴前文）", lineno, ln))
    return out


def _acronym_defined(token: str, line: str) -> bool:
    """首用是否带定义：`API（应用程序接口）` 或 `应用程序接口（API）`。"""
    if re.search(re.escape(token) + r"\s*[（(][^）)]{1,40}[）)]", line):
        return True
    return bool(re.search(r"[^。；\n]{1,40}[（(]\s*" + re.escape(token) + r"\s*[）)]", line))


def _text_acronym_first_use(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    """缩写首用定义（MS Style：首次出现先写全称，缩写放括号内；词表内视为已定义）。"""
    options = pred.get("options") or {}
    allowed = {str(x).upper() for x in (options.get("allowed_acronyms") or [])}
    seen: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    for lineno, ln in ctx.prose_lines():
        if ln.strip().startswith("|"):
            continue
        for m in _ACRONYM.finditer(ln):
            token = m.group(0)
            if token in allowed or token in seen:
                continue
            seen[token] = lineno
            if not _acronym_defined(token, ln):
                out.append(_finding(
                    "缩写「%s」首次出现未定义（须全称 + 括号缩写，或列入 profile 词表）"
                    % token, lineno, ln))
    return out


def _text_weak_expression(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    """弱表达（程序性/规格文本禁用含糊措辞；词表可由 predicate.options 覆盖）。"""
    options = pred.get("options") or {}
    words = options.get("weak_words") or DEFAULT_WEAK_WORDS
    out: List[Dict[str, Any]] = []
    for lineno, ln in ctx.prose_lines():
        for w in words:
            if w in ln:
                out.append(_finding("弱表达「%s」（规范文本应给确定说法/判定条件）" % w,
                                    lineno, ln))
                break
    return out


_TEXT_IMPL: Dict[str, Callable[[Dict[str, Any], DocContext], List[Dict[str, Any]]]] = {
    "heading_sentence": _text_heading_sentence,
    "heading_end_punct": _text_heading_end_punct,
    "single_space": _text_single_space,
    "acronym_first_use": _text_acronym_first_use,
    "weak_expression": _text_weak_expression,
}


# ------------------------------------------------------------------ 结构判据
def _p_regex(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    scope = str(pred.get("scope") or "prose")
    if scope == "heading":
        lines = [(h["line"], h["raw"]) for h in ctx.headings]
    elif scope == "all":
        lines = [(i + 1, ln) for i, ln in enumerate(ctx.lines)]
    else:
        lines = ctx.prose_lines()
    expect = str(pred.get("expect") or "absent")
    flags = re.M
    try:
        pat = re.compile(str(pred.get("pattern") or ""), flags)
    except re.error as exc:
        return [_finding("判据正则非法：%s" % exc)]
    out: List[Dict[str, Any]] = []
    matched = 0
    for lineno, ln in lines:
        if not pat.search(ln):
            continue
        matched += 1
        if expect == "absent":
            out.append(_finding(str(pred.get("message") or "命中禁用模式：%s"
                                    % pred.get("pattern")), lineno, ln))
    if expect == "present" and matched == 0:
        out.append(_finding(str(pred.get("message") or
                                "缺少要求模式：%s" % pred.get("pattern"))))
    return out


def _p_heading_unique(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    level = pred.get("level")
    seen: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    for h in ctx.headings:
        if level is not None and h["level"] != int(level):
            continue
        key = " ".join(h["text"].split()).lower()
        if not key:
            continue
        if key in seen:
            out.append(_finding("标题重复（同一层级标题应唯一可寻址）：%s" % h["text"],
                                h["line"], h["raw"]))
        else:
            seen[key] = h["line"]
    return out


def _p_heading_no_skip(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    prev = 0
    for h in ctx.headings:
        if prev and h["level"] > prev + 1:
            out.append(_finding("标题层级跳级（H%d → H%d）" % (prev, h["level"]),
                                h["line"], h["raw"]))
        prev = h["level"]
    return out


def _p_heading_max_depth(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    limit = int(pred.get("value") or 4)
    return [_finding("标题层级过深（H%d > 上限 H%d）" % (h["level"], limit),
                     h["line"], h["raw"])
            for h in ctx.headings if h["level"] > limit]


def _p_heading_count(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    level = int(pred.get("level") or 1)
    want = int(pred.get("expect") if pred.get("expect") is not None else 1)
    got = sum(1 for h in ctx.headings if h["level"] == level)
    if got == want:
        return []
    return [_finding("H%d 标题数=%d（要求 %d）" % (level, got, want),
                     text="、".join(h["raw"] for h in ctx.headings
                                   if h["level"] == level)[:80])]


def _p_anchor_link(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    anchors = set()
    slugs = set()
    for h in ctx.headings:
        anchors.update(h["anchors"])
        slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", h["text"].strip().lower()).strip("-")
        slugs.add(slug)
    out: List[Dict[str, Any]] = []
    for lineno, ln in ctx.prose_lines():
        for target in _INLINE_LINK.findall(ln):
            if target in anchors or target in slugs:
                continue
            out.append(_finding("文档内链接目标不可寻址：#%s" % target, lineno, ln))
    return out


def _doc_type_value(ctx: DocContext) -> str:
    for lineno, ln in ctx.prose_lines():
        m = re.match(r"^\s*>\s*文档类型\s*[：:]\s*(\S+)", ln) \
            or re.match(r"^\s*文档类型\s*[：:]\s*(\S+)", ln) \
            or re.match(r"^\s*doc_type\s*[：:]\s*(\S+)", ln)
        if m:
            return m.group(1).strip().strip("`")
    return ""


def _p_doc_type(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    allowed = [str(x) for x in (pred.get("allowed") or [])]
    got = _doc_type_value(ctx)
    if not got:
        return [_finding("缺文档类型声明（`> 文档类型：<type>`；DITA 以 topic type 定内容模型；"
                         "白名单=%s）" % "、".join(allowed))]
    if allowed and got not in allowed:
        return [_finding("文档类型「%s」不在白名单：%s" % (got, "、".join(allowed)))]
    return []


def _section_range(ctx: DocContext, needle: str) -> Optional[Tuple[int, int]]:
    """返回标题含 needle 的节点范围（行下标区间 [start,end)）；找不到 = None。"""
    for idx, h in enumerate(ctx.headings):
        if needle in h["text"]:
            start = h["line"] - 1
            end = len(ctx.lines)
            for h2 in ctx.headings[idx + 1:]:
                if h2["level"] <= h["level"]:
                    end = h2["line"] - 1
                    break
            return start, end
    return None


def _p_section(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    needle = str(pred.get("heading") or "")
    require = str(pred.get("require") or "present")
    span = _section_range(ctx, needle)
    if span is None:
        return [_finding("缺章节：%s" % needle)]
    start, end = span
    body = [(i + 1, ctx.lines[i]) for i in range(start, end)
            if not ctx.in_code[i] and ctx.lines[i].strip()]
    if require in ("non_empty", "has_table", "has_numbered_list"):
        content = [(i, ln) for i, ln in body if not _HEADING.match(ln)]
        if not content:
            return [_finding("章节「%s」无正文内容（空章节）" % needle, start + 1)]
        if require == "has_table" and not any(start < t["line"] <= end
                                              for t in ctx.tables):
            return [_finding("章节「%s」缺表格（要求表格化呈现）" % needle, start + 1)]
        if require == "has_numbered_list" and not any(_NUMBERED.match(ln)
                                                      for _i, ln in content):
            return [_finding("章节「%s」缺有序步骤列表（程序性内容须编号）" % needle,
                             start + 1)]
    return []


def _p_required_sections(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for needle in [str(x) for x in (pred.get("headings") or [])]:
        if _section_range(ctx, needle) is None:
            out.append(_finding("缺必备章节：%s" % needle))
    return out


def _table_matches(table: Dict[str, Any], columns_all: List[str]) -> bool:
    header = table["header"]
    return all(any(col in h for h in header) for col in columns_all)


def _p_table(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    candidates = pred.get("columns_any") or []
    if candidates and isinstance(candidates[0], str):
        candidates = [candidates]
    min_rows = int(pred.get("min_rows") or 1)
    for table in ctx.tables:
        for cols in candidates:
            if _table_matches(table, [str(c) for c in cols]):
                if len(table["rows"]) >= min_rows:
                    return []
                return [_finding("表格「%s」数据行 %d < 下限 %d"
                                 % ("、".join(cols), len(table["rows"]), min_rows),
                                 table["line"])]
    return [_finding("缺表格：需含列 %s" %
                     " / ".join("、".join(str(c) for c in cols) for cols in candidates))]


def _p_table_columns(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for table in ctx.tables:
        want = len(table["header"])
        for n, row in enumerate(table["rows"]):
            if len(row) != want:
                out.append(_finding("表格列数不一致：表头 %d 列，数据行 %d 列"
                                    % (want, len(row)), table["line"]))
                break
    return out


def _p_fence_balance(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    marks = [(i + 1, ln) for i, ln in enumerate(ctx.lines) if _FENCE.match(ln)]
    if len(marks) % 2 == 0:
        return []
    return [_finding("代码围栏未配平（标记 %d 个，须为偶数）" % len(marks),
                     marks[-1][0] if marks else 0,
                     marks[-1][1] if marks else "")]


def _p_revision_trace(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    """修订记录可追溯：表在 + 版本递增 + 日期 ISO 8601。"""
    cand = None
    for table in ctx.tables:
        if _table_matches(table, ["版本", "日期"]):
            cand = table
            break
    if cand is None:
        return [_finding("缺修订记录表（须含「版本」「日期」列——GB/T 19678.1 修订追溯）")]
    header = cand["header"]
    idx_ver = next((j for j, c in enumerate(header) if "版本" in c), None)
    idx_date = next((j for j, c in enumerate(header) if "日期" in c), None)
    out: List[Dict[str, Any]] = []
    last: Optional[Tuple[int, ...]] = None
    for n, row in enumerate(cand["rows"]):
        ver = row[idx_ver].strip().strip("`") if idx_ver is not None and idx_ver < len(row) else ""
        date = row[idx_date].strip().strip("`") if idx_date is not None and idx_date < len(row) else ""
        m = _VERSION.match(ver)
        if not m:
            out.append(_finding("修订版本号非法：%r（须 v?MAJOR[.MINOR[.PATCH]]）"
                                % ver, cand["line"] + n + 2))
            continue
        cur = tuple(int(x) for x in m.group(1).split("."))
        if last is not None and cur <= last:
            out.append(_finding("修订版本号未递增：%s → %s" % (last, ver),
                                cand["line"] + n + 2))
        last = cur
        if not _ISO_DATE.match(date):
            out.append(_finding("修订日期非 ISO 8601（YYYY-MM-DD）：%r" % date,
                                cand["line"] + n + 2))
    return out


def _p_term_first_use(pred: Dict[str, Any], ctx: DocContext) -> List[Dict[str, Any]]:
    """术语首用即定义（GB/T 19678.1）：首现须在术语表内或带括注定义。"""
    if not ctx.glossary:
        return [_finding("术语表数据不可用（profile assets.glossary 未装载或为空）")]
    span = _section_range(ctx, "术语表")
    out: List[Dict[str, Any]] = []
    for entry in ctx.glossary:
        term = entry["term"]
        first: Optional[Tuple[int, str]] = None
        for lineno, ln in ctx.prose_lines():
            if term in ln:
                first = (lineno, ln)
                break
        if first is None:
            continue
        lineno, ln = first
        if span is not None and linenumber_in_span(lineno, span):
            continue
        if _acronym_defined(term, ln):
            continue
        out.append(_finding("术语「%s」首用未定义（首次使用前须在术语表定义或就地括注）"
                            % term, lineno, ln))
    return out


def linenumber_in_span(lineno: int, span: Tuple[int, int]) -> bool:
    return span[0] + 1 <= lineno <= span[1]


def _p_term_alias_consistency(pred: Dict[str, Any],
                              ctx: DocContext) -> List[Dict[str, Any]]:
    """术语一致（同概念不混用别名）：**术语表之外**的正文不得与别名并存。

    术语表本身正是别名登记处（别名列与定义列天然会同时出现），故判据面排除术语表
    章节——只看读者正文里是否既用规范术语又用别名（GB/T 19678.1 术语一致性）。
    """
    if not ctx.glossary:
        return [_finding("术语表数据不可用（profile assets.glossary 未装载或为空）")]
    span = _section_range(ctx, "术语表")
    body_lines = [ln for no, ln in ctx.prose_lines()
                  if not (span is not None and linenumber_in_span(no, span))]
    body = "\n".join(body_lines)
    out: List[Dict[str, Any]] = []
    for entry in ctx.glossary:
        term = entry["term"]
        if term not in body:
            continue
        for alias in entry["aliases"]:
            if alias and alias != term and alias in body:
                out.append(_finding("术语混用：规范术语「%s」与别名「%s」同篇并存"
                                    % (term, alias)))
    return out


_PREDICATES: Dict[str, Callable[[Dict[str, Any], DocContext], List[Dict[str, Any]]]] = {
    "text_rule": lambda pred, ctx: _TEXT_IMPL[str(pred.get("rule") or "")](pred, ctx),
    "regex": _p_regex,
    "heading_unique": _p_heading_unique,
    "heading_no_skip": _p_heading_no_skip,
    "heading_max_depth": _p_heading_max_depth,
    "heading_count": _p_heading_count,
    "anchor_link": _p_anchor_link,
    "doc_type": _p_doc_type,
    "section": _p_section,
    "required_sections": _p_required_sections,
    "table": _p_table,
    "table_columns": _p_table_columns,
    "fence_balance": _p_fence_balance,
    "revision_trace": _p_revision_trace,
    "term_first_use": _p_term_first_use,
    "term_alias_consistency": _p_term_alias_consistency,
}
PREDICATE_KINDS = tuple(sorted(_PREDICATES))


