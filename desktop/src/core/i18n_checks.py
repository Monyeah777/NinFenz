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


def locale_snapshot(root: str = ".") -> Dict[str, Any]:
    """语言面现状 → {locales, entries, doc_pairs, en/ja 文件集}（供判据与报告）。"""
    reg = _registry(root)
    locales = [str(x.get("id")) for x in reg.get("locales") or [] if isinstance(x, dict)]
    entries = [str(x.get("entry")) for x in reg.get("locales") or [] if isinstance(x, dict)]
    docs = [d for d in reg.get("docs") or [] if isinstance(d, dict)]
    pairs = 0
    for item in docs:
        tr = item.get("translations") or {}
        if isinstance(tr, dict) and tr:
            pairs += 1
    en = sorted(p.name for p in (Path(root) / "docs" / "en").glob("*.md")) \
        if (Path(root) / "docs" / "en").is_dir() else []
    ja = sorted(p.name for p in (Path(root) / "docs" / "ja").glob("*.md")) \
        if (Path(root) / "docs" / "ja").is_dir() else []
    return {"locales": locales, "entries": entries, "doc_pairs": pairs,
            "en": en, "ja": ja}


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


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    reg_rel = str(doc.get("registry") or "")
    if not _exists(root, reg_rel):
        return ["registry 不在场：%s（%s 指向 protocol/locales.json）" % (reg_rel, GUIDE)]
    reg = _registry(root)
    actual = [str(x.get("id")) for x in reg.get("locales") or [] if isinstance(x, dict)]
    declared = [str(x.get("id")) for x in doc.get("locales") or [] if isinstance(x, dict)]
    if not declared:
        issues.append("locales 为空（至少 zh/en/ja）")
    if list(actual) != list(declared):
        issues.append("locales 登记 %s 与 locales.json 实际 %s 不一致" % (declared, actual))
    for item in doc.get("locales") or []:
        if not _exists(root, str(item.get("entry") or "")):
            issues.append("locale %s 的 entry 不在场：%s"
                          % (item.get("id"), item.get("entry")))
        if str(item.get("coverage")) not in ("entry", "entry+guides"):
            issues.append("locale %s 的 coverage 非法：%s"
                          % (item.get("id"), item.get("coverage")))
    metrics = doc.get("coverage_metrics") or {}
    snap = locale_snapshot(root)
    if len(snap["locales"]) < int(metrics.get("locales_min") or 0):
        issues.append("locale 数 %d < 下限 %s" % (len(snap["locales"]), metrics.get("locales_min")))
    if len(snap["entries"]) < int(metrics.get("entries_min") or 0):
        issues.append("入口数 %d < 下限 %s" % (len(snap["entries"]), metrics.get("entries_min")))
    if snap["doc_pairs"] < int(metrics.get("doc_pairs_min") or 0):
        issues.append("文档译件组 %d < 下限 %s（%s 补翻译或调下限=只降不升）"
                      % (snap["doc_pairs"], metrics.get("doc_pairs_min"), GUIDE))
    if snap["en"] != snap["ja"]:
        issues.append("docs/en 与 docs/ja 文件集不镜像（en=%s / ja=%s）"
                      % (snap["en"], snap["ja"]))
    for item in reg.get("docs") or []:
        if not isinstance(item, dict):
            issues.append("locales.json docs 含非对象")
            continue
        src = str(item.get("path") or "")
        if not _exists(root, src):
            issues.append("文档源件不在场：%s" % src)
        for lang, tr in (item.get("translations") or {}).items():
            if not _exists(root, str((tr or {}).get("path") or "")):
                issues.append("译件不在场：%s/%s" % (src, lang))
            sha = str((tr or {}).get("source_sha256") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", sha):
                issues.append("译件 %s/%s 的 source_sha256 非法（%s 跑 nf locales --write）"
                              % (src, lang, GUIDE))
    tz = doc.get("timezone") or {}
    for key in ("safety_timestamps", "display", "tzdb", "evidence"):
        if not str(tz.get(key) or "").strip():
            issues.append("timezone 缺 %s" % key)
    if not _exists(root, str(tz.get("evidence") or "")):
        issues.append("timezone.evidence 不在场：%s" % tz.get("evidence"))
    if not iso8601.is_iso_instant("2026-11-14T00:00:00Z"):
        issues.append("core.iso8601 无法解析 UTC 秒级时间戳（时区口径失守）")
    rtl = doc.get("rtl") or {}
    if not str(rtl.get("policy") or "").strip():
        issues.append("rtl 缺 policy（新增 RTL locale 前须过 bidi 扫描）")
    if not rtl.get("banned_codepoints"):
        issues.append("rtl 缺 banned_codepoints")
    if rtl.get("current_rtl_locales"):
        issues.append("当前声明了 RTL locale：%s（%s 必须先过渲染/扫描测试）"
                      % (rtl.get("current_rtl_locales"), GUIDE))
    uni = doc.get("unicode") or {}
    surfaces = uni.get("scan_surfaces") or []
    if not surfaces:
        issues.append("unicode 缺 scan_surfaces")
    scan = scan_surfaces(root, surfaces)
    for finding in scan["findings"]:
        issues.append("语言面出现禁用控制字符：%s %s" % (finding["path"], finding["codepoint"]))
    if scan["skipped"]:
        issues.append("语言面有不可判定件：%s" % scan["skipped"][:3])
    claims = (doc.get("review") or {}).get("claims_boundary") or []
    if not any("不声称" in str(x) for x in claims):
        issues.append("review.claims_boundary 必须显式写「不声称完整 i18n/RTL 支持」")
    return issues
