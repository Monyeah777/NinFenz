"""语言面判据（`nf-i18n/1`）：locale 覆盖 + 文档译件镜像 + 时区口径 + bidi/零宽控制字符闸门。

为什么（NF-Final WP-0E，P1 盲区 BL-09）：多语言最容易「只翻了一半」或「被 RTL 控制字符
伪装」——本模块把语言面策略做成数据 + 可执行扫描：
- 语言面真源仍是 `protocol/locales.json`（文件即真源 + source_sha256）；本模块只加策略与判据；
- 覆盖：locale 数、入口、docs/<lang>/ 与 zh 源件镜像、登记译件路径全部在场；
- 时区：安全时间戳一律 UTC ISO-8601（Z），显示转换不写进证据；用 `core.iso8601` 现验样例；
- RTL/Unicode：bidi 控制字符与零宽字符不得出现在语言面正文；新增 RTL locale 前必须先过扫描；
- 不声称完整 i18n/RTL 支持（当前无 RTL locale）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import iso8601

SCHEMA = "nf-i18n/1"
REL = "protocol/i18n.json"
GUIDE = "修复指引："
#: bidi 控制字符 + 零宽字符（同形/伪装面）。
BANNED_CODEPOINTS = (
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
    "\u200e", "\u200f", "\u200b", "\u200c", "\u200d", "\ufeff",
)


def load(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("缺 %s（%s 补语言面登记）" % (REL, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        raise ValueError(REL + " schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    return doc


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / str(rel)).is_file()


def _registry(root: str) -> Dict[str, Any]:
    rel = REL
    doc = load(root)
    reg_rel = str(doc.get("registry") or "")
    path = Path(root) / reg_rel
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _locale_views(reg: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """注册表 locales → (id 列表, entry 列表)。"""
    locales: List[str] = []
    entries: List[str] = []
    for x in reg.get("locales") or []:
        if isinstance(x, dict):
            locales.append(str(x.get("id")))
            entries.append(str(x.get("entry")))
    return locales, entries


def _doc_pairs(reg: Dict[str, Any]) -> int:
    """带非空 translations 的 docs 条目数。"""
    pairs = 0
    for item in reg.get("docs") or []:
        if not isinstance(item, dict):
            continue
        tr = item.get("translations") or {}
        if isinstance(tr, dict) and tr:
            pairs += 1
    return pairs


def _lang_files(root: str, lang: str) -> List[str]:
    """docs/<lang>/*.md 的文件名清单（目录不在场 → 空表）。"""
    base = Path(root) / "docs" / lang
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.glob("*.md"))


def locale_snapshot(root: str = ".") -> Dict[str, Any]:
    """语言面现状 → {locales, entries, doc_pairs, en/ja 文件集}（供判据与报告）。"""
    reg = _registry(root)
    locales, entries = _locale_views(reg)
    return {"locales": locales, "entries": entries, "doc_pairs": _doc_pairs(reg),
            "en": _lang_files(root, "en"), "ja": _lang_files(root, "ja")}


def bidi_controls(text: str) -> List[str]:
    """→ 命中控制字符的码点清单（去重、保持顺序）。"""
    hits: List[str] = []
    for ch in text:
        if ch in BANNED_CODEPOINTS and ("U+%04X" % ord(ch)) not in hits:
            hits.append("U+%04X" % ord(ch))
    return hits


def scan_surfaces(root: str = ".", rels: Any = None) -> Dict[str, Any]:
    """扫声明语言面目录 → {findings, scanned}；不可读件记 skipped（不当干净）。"""
    findings: List[Dict[str, str]] = []
    skipped: List[str] = []
    scanned = 0
    for rel in rels or []:
        base = Path(root) / str(rel)
        if not base.exists():
            skipped.append(str(rel) + "（不在场）")
            continue
        paths = sorted(base.rglob("*.md")) if base.is_dir() else [base]
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                skipped.append(str(path.relative_to(Path(root))).replace("\\", "/"))
                continue
            scanned += 1
            for code in bidi_controls(text):
                findings.append({"path": str(path.relative_to(Path(root))).replace("\\", "/"),
                                 "codepoint": code})
    return {"findings": findings, "skipped": skipped, "scanned": scanned}


def _locale_item_issues(item: Dict[str, Any], root: str) -> List[str]:
    """单个 locale 条目判据（entry 在场 / coverage 词表）。"""
    out: List[str] = []
    if not _exists(root, str(item.get("entry") or "")):
        out.append("locale %s 的 entry 不在场：%s" % (item.get("id"), item.get("entry")))
    if str(item.get("coverage")) not in ("entry", "entry+guides"):
        out.append("locale %s 的 coverage 非法：%s" % (item.get("id"), item.get("coverage")))
    return out


def _id_list(items: Any) -> List[str]:
    """对象数组 → id 字符串列表（非对象条目跳过）。"""
    return [str(x.get("id")) for x in items or [] if isinstance(x, dict)]


def _locales_issues(doc: Dict[str, Any], root: str, reg: Dict[str, Any]) -> List[str]:
    """locales 登记一致性 + 逐 locale 判据。"""
    actual = _id_list(reg.get("locales"))
    declared = _id_list(doc.get("locales"))
    out: List[str] = []
    if not declared:
        out.append("locales 为空（至少 zh/en/ja）")
    if list(actual) != list(declared):
        out.append("locales 登记 %s 与 locales.json 实际 %s 不一致" % (declared, actual))
    for item in doc.get("locales") or []:
        out.extend(_locale_item_issues(item, root))
    return out


def _below_floor(actual: int, minimum: Any) -> bool:
    """实际数是否低于下限（缺省下限=0）。"""
    return actual < int(minimum or 0)


def _coverage_issues(root: str, metrics: Dict[str, Any]) -> List[str]:
    """覆盖度下限 + en/ja 镜像判据。"""
    snap = locale_snapshot(root)
    out: List[str] = []
    if _below_floor(len(snap["locales"]), metrics.get("locales_min")):
        out.append("locale 数 %d < 下限 %s" % (len(snap["locales"]), metrics.get("locales_min")))
    if _below_floor(len(snap["entries"]), metrics.get("entries_min")):
        out.append("入口数 %d < 下限 %s" % (len(snap["entries"]), metrics.get("entries_min")))
    if _below_floor(snap["doc_pairs"], metrics.get("doc_pairs_min")):
        out.append("文档译件组 %d < 下限 %s（%s 补翻译或调下限=只降不升）"
                   % (snap["doc_pairs"], metrics.get("doc_pairs_min"), GUIDE))
    if snap["en"] != snap["ja"]:
        out.append("docs/en 与 docs/ja 文件集不镜像（en=%s / ja=%s）"
                   % (snap["en"], snap["ja"]))
    return out


def _doc_translation_issues(item: Dict[str, Any], root: str) -> List[str]:
    """单个文档源件的译件判据（源件/译件在场、source_sha256）。"""
    out: List[str] = []
    src = str(item.get("path") or "")
    if not _exists(root, src):
        out.append("文档源件不在场：%s" % src)
    for lang, tr in (item.get("translations") or {}).items():
        tr = tr or {}
        if not _exists(root, str(tr.get("path") or "")):
            out.append("译件不在场：%s/%s" % (src, lang))
        sha = str(tr.get("source_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            out.append("译件 %s/%s 的 source_sha256 非法（%s 跑 nf locales --write）"
                       % (src, lang, GUIDE))
    return out


def _doc_list_issues(reg: Dict[str, Any], root: str) -> List[str]:
    """locales.json docs 逐件判据。"""
    out: List[str] = []
    for item in reg.get("docs") or []:
        if not isinstance(item, dict):
            out.append("locales.json docs 含非对象")
            continue
        out.extend(_doc_translation_issues(item, root))
    return out


def _timezone_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """timezone 判据（四个必填键 + 证据在场）。"""
    tz = doc.get("timezone") or {}
    out: List[str] = []
    for key in ("safety_timestamps", "display", "tzdb", "evidence"):
        if not str(tz.get(key) or "").strip():
            out.append("timezone 缺 %s" % key)
    if not _exists(root, str(tz.get("evidence") or "")):
        out.append("timezone.evidence 不在场：%s" % tz.get("evidence"))
    return out


def _rtl_issues(doc: Dict[str, Any]) -> List[str]:
    """RTL 判据（policy / banned_codepoints / 当前是否声明 RTL）。"""
    rtl = doc.get("rtl") or {}
    out: List[str] = []
    if not str(rtl.get("policy") or "").strip():
        out.append("rtl 缺 policy（新增 RTL locale 前须过 bidi 扫描）")
    if not rtl.get("banned_codepoints"):
        out.append("rtl 缺 banned_codepoints")
    if rtl.get("current_rtl_locales"):
        out.append("当前声明了 RTL locale：%s（%s 必须先过渲染/扫描测试）"
                   % (rtl.get("current_rtl_locales"), GUIDE))
    return out


def _unicode_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """unicode 扫描面判据（禁用控制字符 / 不可判定件）。"""
    uni = doc.get("unicode") or {}
    surfaces = uni.get("scan_surfaces") or []
    out: List[str] = []
    if not surfaces:
        out.append("unicode 缺 scan_surfaces")
    scan = scan_surfaces(root, surfaces)
    for finding in scan["findings"]:
        out.append("语言面出现禁用控制字符：%s %s" % (finding["path"], finding["codepoint"]))
    if scan["skipped"]:
        out.append("语言面有不可判定件：%s" % scan["skipped"][:3])
    return out


def _review_issues(doc: Dict[str, Any]) -> List[str]:
    """review.claims_boundary 判据。"""
    claims = (doc.get("review") or {}).get("claims_boundary") or []
    if not any("不声称" in str(x) for x in claims):
        return ["review.claims_boundary 必须显式写「不声称完整 i18n/RTL 支持」"]
    return []


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    reg_rel = str(doc.get("registry") or "")
    if not _exists(root, reg_rel):
        return ["registry 不在场：%s（%s 指向 protocol/locales.json）" % (reg_rel, GUIDE)]
    reg = _registry(root)
    issues: List[str] = []
    issues.extend(_locales_issues(doc, root, reg))
    metrics = doc.get("coverage_metrics") or {}
    issues.extend(_coverage_issues(root, metrics))
    issues.extend(_doc_list_issues(reg, root))
    issues.extend(_timezone_issues(doc, root))
    if not iso8601.is_iso_instant("2026-11-14T00:00:00Z"):
        issues.append("core.iso8601 无法解析 UTC 秒级时间戳（时区口径失守）")
    issues.extend(_rtl_issues(doc))
    issues.extend(_unicode_issues(doc, root))
    issues.extend(_review_issues(doc))
    return issues
