"""英文术语层（glossary）：每条英文术语可追溯到中文协议里的**真实锚点**。

定位（T12.2）：这是**术语层，不是全文翻译**。`protocol/glossary.json` 的 `entries` 给出
核心术语的双语定义；每条 `source` 指向中文协议/代码里的真实件与锚点（章节标题或关键词），
`nf glossary check` 逐条核验锚点真能定位——**禁止写假行号/假章节**。

数据形状（schema 兼容 `nf-glossary/1`；既有 `terms` 行话表保持原样，互不影响）::

    {
      "schema": "nf-glossary/1",
      "terms": [ ... 既有行话表（cognition 消费）... ],
      "categories": ["协议层", "装配层", ...],
      "entries": [
        {"id": "GL-001", "zh": "模块", "en": "module",
         "definition_zh": "…", "definition_en": "…", "category": "协议层",
         "source": {"file": "01_核心协议.md", "section": "1. 模块协议",
                    "keyword": "模块"}}
      ]
    }

`source` 规则：
- `file`：仓库相对路径（必须真实在场；拒绝绝对路径/`..` 逃逸）；
- `section`（可选）：文件里必须存在**逐字包含**该文本的标题行；
- `keyword`（可选）：文件里必须**逐字出现**该关键词；
- `line`（可选，不推荐）：一旦声明，行号必须真实存在且该行含 `keyword`/`zh`——
  历史假行号就是靠这条判死；
- `section` / `keyword` / `line` 至少给一个，否则视为无法定位。

判据（`check(root)`）：
1. schema / entries 非空 / 每条必填字段（id/zh/en/definition_zh/definition_en/category/source）；
2. `zh` 与 `en` 各自全表唯一（en 大小写不敏感）；id 唯一；
3. `category` ∈ `categories`；
4. source 锚点逐条真实可定位；
5. 必含术语清单（`REQUIRED_TERMS`）齐全——缺一条即失败（非零退出）。

人读渲染：`render_markdown()` 按 category 分组（顺序取自 `categories`），同组按 `zh` 排序，
**同输入同字节**（`docs/protocol/glossary.en.md` 由本模块生成，禁止手改）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "nf-glossary/1"
CHECK_SCHEMA = "nf-glossary-check/1"
GLOSSARY_REL = "protocol/glossary.json"

#: 默认分类顺序（数据里 `categories` 缺省时使用）。
DEFAULT_CATEGORIES: Tuple[str, ...] = ("协议层", "装配层", "质量层", "证据层",
                                       "运行层", "领域层", "成熟度")

#: 必含术语清单（T12.2）：缺一条 `nf glossary check` 即失败。
REQUIRED_TERMS: Tuple[str, ...] = (
    "交付物契约", "槽", "事件", "层", "模块", "门", "契约", "规范形", "回执", "一致性",
    "域包", "管线", "资产", "成熟度 M0", "成熟度 M1", "成熟度 M2", "成熟度 M3",
    "门禁", "审计", "证据", "证据链", "工作流", "状态", "角色", "装配", "产物",
    "条款", "用例", "基准", "缺陷注入", "可复现", "确定性", "参考运行时",
)

_ENTRY_KEYS = ("id", "zh", "en", "definition_zh", "definition_en",
               "category", "source")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def load(root: str = ".") -> Dict[str, Any]:
    """读 glossary 数据件；缺件/坏 JSON 抛 ValueError（带修复指引）。"""
    p = Path(root) / GLOSSARY_REL
    if not p.is_file():
        raise ValueError("缺术语数据件 %s（修复指引：恢复 protocol/glossary.json）"
                         % GLOSSARY_REL)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("术语数据件不可读/非法 JSON：%s（修复指引：修正 %s 后重试）"
                         % (exc, GLOSSARY_REL)) from exc
    if not isinstance(doc, dict):
        raise ValueError("术语数据件顶层须为对象：%s" % GLOSSARY_REL)
    return doc


def _categories(doc: Dict[str, Any]) -> List[str]:
    cats = doc.get("categories")
    if isinstance(cats, list) and cats and all(isinstance(c, str) for c in cats):
        return [str(c) for c in cats]
    return list(DEFAULT_CATEGORIES)


def _entry_issues(entry: Any, idx: int) -> List[str]:
    at = "entries[%d]" % idx
    if not isinstance(entry, dict):
        return ["%s 须为对象" % at]
    issues: List[str] = []
    for key in _ENTRY_KEYS:
        if key not in entry:
            issues.append("%s 缺必填字段 %s" % (at, key))
    for key in ("id", "zh", "en", "definition_zh", "definition_en", "category"):
        if key in entry and not str(entry.get(key) or "").strip():
            issues.append("%s 的 %s 不得为空" % (at, key))
    src = entry.get("source")
    if not isinstance(src, dict):
        issues.append("%s 的 source 须为对象（file + section/keyword/line）" % at)
        return issues
    if not str(src.get("file") or "").strip():
        issues.append("%s 的 source.file 不得为空" % at)
    locators = [k for k in ("section", "keyword", "line") if src.get(k) not in (None, "")]
    if not locators:
        issues.append("%s 的 source 缺定位锚点（section / keyword / line 至少一个）" % at)
    if "line" in locators:
        line = src.get("line")
        if not isinstance(line, int) or line < 1:
            issues.append("%s 的 source.line 须为正整数行号（禁止假行号）" % at)
    return issues


def _resolve_source(root: str, src: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    """校验 source 锚点 → (文件正文, issues)。"""
    issues: List[str] = []
    rel = str(src.get("file") or "").strip()
    try:
        from core import paths as _paths
        path = _paths.validate_path(str(root), rel)
    except Exception as exc:  # noqa: BLE001 - 统一框成可读问题（含越界/缺件）
        return None, ["source.file 不可定位：%r（%s）（修复指引：写仓库相对路径）"
                      % (rel, exc)]
    p = Path(path)
    if not p.is_file():
        return None, ["source.file 不存在：%s（修复指引：锚点必须指向在场真实件）" % rel]
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, ["source.file 不可读：%s（%s）" % (rel, exc)]
    lines = text.splitlines()
    section = str(src.get("section") or "").strip()
    keyword = str(src.get("keyword") or "").strip()
    zh = str(src.get("_zh") or "")
    if section:
        headings = [m.group(2).strip() for m in
                    (_HEADING.match(ln) for ln in lines) if m is not None]
        if not any(h == section or section in h for h in headings):
            issues.append("source.section 在 %s 中不存在：%r（修复指引：逐字写真实标题）"
                          % (rel, section))
    if keyword and keyword not in text:
        issues.append("source.keyword 未在 %s 中出现：%r（修复指引：写文件中逐字出现的"
                      "关键词）" % (rel, keyword))
    if src.get("line") not in (None, ""):
        line = src["line"]
        if isinstance(line, int) and 1 <= line <= len(lines):
            probe = zh or keyword
            if probe and probe not in lines[line - 1]:
                issues.append("source.line 与锚点不符：%s 第 %d 行不含 %r（禁止假行号）"
                              % (rel, line, probe))
        else:
            issues.append("source.line 越界：%s 共 %d 行，声明 %r（禁止假行号）"
                          % (rel, len(lines), line))
    return text, issues


def check(root: str = ".", doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """全量校验 → 结构化报告（`ok=False` 即非零退出）。

    `doc` 可由调用方直接传入（单测注入变异件用；缺省从 `root/protocol/glossary.json` 读）。
    """
    stats: Dict[str, Any] = {"entries": 0, "categories": 0,
                             "required": len(REQUIRED_TERMS)}
    if doc is None:
        try:
            doc = load(root)
        except ValueError as exc:
            return {"schema": CHECK_SCHEMA, "ok": False, "issues": [str(exc)],
                    "stats": stats}
    if not isinstance(doc, dict):
        return {"schema": CHECK_SCHEMA, "ok": False,
                "issues": ["术语数据件须为 JSON 对象"], "stats": stats}
    return _check_doc(doc, root, stats)


def _check_doc(doc: Dict[str, Any], root: str,
               stats: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    if str(doc.get("schema") or "") != SCHEMA:
        issues.append("schema 非 %s：%r" % (SCHEMA, doc.get("schema")))
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        issues.append("entries 须为非空列表（英文术语层；legacy terms 不替代它）")
        entries = []
    cats = _categories(doc)
    stats["categories"] = len(cats)
    stats["entries"] = len(entries)
    seen_zh: Dict[str, int] = {}
    seen_en: Dict[str, int] = {}
    seen_id: Dict[str, int] = {}
    per_cat: Dict[str, int] = {}
    for idx, entry in enumerate(entries):
        issues.extend(_entry_issues(entry, idx))
        if not isinstance(entry, dict):
            continue
        zh = str(entry.get("zh") or "").strip()
        en = str(entry.get("en") or "").strip()
        eid = str(entry.get("id") or "").strip()
        if eid:
            if eid in seen_id:
                issues.append("条目 id 重复：%s（首次出现于 entries[%d]）"
                              % (eid, seen_id[eid]))
            seen_id[eid] = idx
        if zh:
            if zh in seen_zh:
                issues.append("中文术语重复：%r（entries[%d] 与 entries[%d]）"
                              % (zh, seen_zh[zh], idx))
            seen_zh[zh] = idx
        if en:
            key = en.casefold()
            if key in seen_en:
                issues.append("英文术语重复：%r（entries[%d] 与 entries[%d]）"
                              % (en, seen_en[key], idx))
            seen_en[key] = idx
        cat = str(entry.get("category") or "")
        if cat:
            if cat not in cats:
                issues.append("category 不在 categories 在册：%r（entries[%d]）"
                              % (cat, idx))
            per_cat[cat] = per_cat.get(cat, 0) + 1
        src = entry.get("source")
        if isinstance(src, dict) and src.get("file"):
            probe = dict(src)
            probe["_zh"] = zh
            _text, src_issues = _resolve_source(root, probe)
            issues.extend("entries[%d]（%s）：%s" % (idx, zh or "?", i)
                          for i in src_issues)
    missing = [t for t in REQUIRED_TERMS if t not in seen_zh]
    if missing:
        issues.append("必含术语缺项 %d 条：%s（修复指引：补齐术语层 entries）"
                      % (len(missing), "、".join(missing)))
    stats["per_category"] = dict(sorted(per_cat.items()))
    return {"schema": CHECK_SCHEMA, "ok": not issues, "issues": issues,
            "stats": stats, "categories": cats}


def _source_label(src: Dict[str, Any]) -> str:
    parts = ["`%s`" % src.get("file", "?")]
    if src.get("section"):
        parts.append("§%s" % src["section"])
    if src.get("keyword"):
        parts.append("关键词「%s」" % src["keyword"])
    if src.get("line"):
        parts.append("第 %s 行" % src["line"])
    return " · ".join(parts)


def render_markdown(doc: Dict[str, Any], root: str = ".") -> str:
    """数据 → 人读英文术语表（按 category 分组；确定性）。"""
    cats = _categories(doc)
    entries = [e for e in (doc.get("entries") or []) if isinstance(e, dict)]
    entries.sort(key=lambda e: (cats.index(str(e.get("category")))
                                if str(e.get("category")) in cats else len(cats),
                                str(e.get("zh") or ""), str(e.get("en") or "")))
    lines = [
        "# NF Glossary · English Terminology Layer",
        "",
        "> Terminology layer, not a full translation: each English term maps to a real "
        "Chinese-protocol anchor (file + section/keyword). "
        "Source of truth: `protocol/glossary.json`; generated by "
        "`nf glossary render` — do not edit by hand.",
        "> 术语层（非全文翻译）：英文术语逐条可追溯到中文协议里的真实锚点；"
        "真源 `protocol/glossary.json`，本文件由 `nf glossary render` 生成。",
        "",
        "| Field | Value |",
        "|---|---|",
        "| entries | %d |" % len(entries),
        "| required terms | %d |" % len(REQUIRED_TERMS),
        "| categories | %s |" % "、".join(cats),
        "",
    ]
    for cat in cats:
        group = [e for e in entries if str(e.get("category")) == cat]
        if not group:
            continue
        lines += ["## %s" % cat, ""]
        for e in group:
            lines += [
                "### %s · %s" % (e.get("en", ""), e.get("zh", "")),
                "",
                "- **EN**：%s" % e.get("definition_en", ""),
                "- **中文**：%s" % e.get("definition_zh", ""),
                "- **Source**：%s" % _source_label(e.get("source") or {}),
                "",
            ]
    return "\n".join(lines).rstrip("\n") + "\n"


def write_markdown(doc: Dict[str, Any], out: str, root: str = ".") -> str:
    """把渲染结果原子写入（相对路径按仓库根，绝对路径按原样）。"""
    from core import atomic_write
    text = render_markdown(doc, root)
    atomic_write.write_text(str(out), text)
    return text


def run(as_json: bool = False, root: str = ".") -> int:
    """`nf glossary check` 执行体 → 退出码（0 = 全部通过）。"""
    report = check(root)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1
    s = report["stats"]
    print("== nf glossary check ==")
    print("  entries %d · categories %d · required %d"
          % (s.get("entries", 0), s.get("categories", 0), s.get("required", 0)))
    for issue in report.get("issues") or []:
        print("  [FAIL] %s" % issue)
    if report["ok"]:
        print("  ✓ 术语层通过：schema/唯一性/锚点真实/必含清单齐（非全文翻译）")
        return 0
    print("  ✗ 术语层未通过（%d 项，见上）" % len(report.get("issues") or []))
    return 1
