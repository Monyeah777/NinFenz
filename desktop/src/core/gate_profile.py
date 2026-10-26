"""M80 质量门 profile 引擎（软门 · 可插拔 · 协议层不内嵌条目）。

定位（M80 §2.2「质量门」）：结构门是硬门（`quality_gate.default_rules`），质量门
由**用户/域包 profile** 定义——本模块只提供**加载 / 校验 / 逐条报告**的引擎，不内嵌
任何固定风格条目。技术文档域包的 `gate_profiles/techdoc-strict.json` 是第一个
L2 参考 profile（DITA 1.3 / GB/T 19678.1-2018 / Microsoft Style Guide 条款映射）。

profile 形状（`nf-gate-profile/1`）::

    {
      "schema": "nf-gate-profile/1",
      "profile_id": "techdoc-strict",
      "description": "…",
      "assets": {"glossary": "../assets/TECH_GLOSSARY.md"},
      "clauses": [
        {"clause_id": "MS-STYLE-HEADING-SENTENCE",
         "level": "fail",                    # fail | warn | info
         "predicate": {"kind": "text_rule", "rule": "heading_sentence"},
         "evidence": "标题用句式大小写，不用全大写/疑问句",
         "source": {"standard": "Microsoft Style Guide", "ref": "Headings"},
         "data_source": "document.headings"}
      ]
    }

判据 predicate 的 `kind` 覆盖：
- `text_rule`：5 条**确定性文本规则**（标题句式 / 标题末尾标点 / 单空格 / 缩写首用 /
  弱表达），规则实现见 `_TEXT_IMPL`；
- `regex`：文面正/负例（`expect=present|absent`，`scope=prose|heading|all`）；
- 结构判据：`heading_unique` / `heading_no_skip` / `heading_max_depth` /
  `heading_count` / `anchor_link` / `doc_type` / `section` / `required_sections` /
  `table` / `table_columns` / `revision_trace` / `fence_balance`；
- 术语判据：`term_first_use` / `term_alias_consistency`（读 profile `assets.glossary`）。

消费面：
1. `report(text, profile)` → 逐条 clause 报告（clause_id / level / ok / evidence /
   data_source / findings；`findings` 带行号与命中片段——可对产物逐条对账）；
2. `ir_rules(profile)` → 一批 `quality_gate.Rule`，交给
   `run_gate(ir, default_rules() + ir_rules(profile))`；**不进 default_rules**，
   未装 profile 的叙事流行为不变；
3. `python desktop/src/core/gate_profile.py --profile … --text …` → 人读/JSON 报告
   （验收命令「profile 对 fixture 出 clause 报告」的入口）。

纪律：纯标准库、确定性（同输入同报告）；判据只认可机检形状，不替作者做文风裁决。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = "nf-gate-profile/1"
REPORT_SCHEMA = "nf-gate-profile-report/1"
LEVELS = ("fail", "warn", "info")
REQUIRED_CLAUSE_KEYS = ("clause_id", "level", "predicate", "evidence", "source",
                        "data_source")
CLAUSE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,80}$")

try:                       # 包内导入（CLI 经 `core.gate_profile` 使用本模块）
    from .gate_profile_rules import (  # noqa: F401 - 判据集 re-export
        DEFAULT_WEAK_WORDS, PREDICATE_KINDS, TEXT_RULES, DocContext, _finding,
        _PREDICATES, _section_range, _TEXT_IMPL, build_context, linenumber_in_span)
except ImportError:        # pragma: no cover - 仅脚本直跑触发（python …/gate_profile.py）
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
    from core.gate_profile_rules import (  # type: ignore[no-redef]  # noqa: F401
        DEFAULT_WEAK_WORDS, PREDICATE_KINDS, TEXT_RULES, DocContext, _finding,
        _PREDICATES, _section_range, _TEXT_IMPL, build_context, linenumber_in_span)

# ------------------------------------------------------------------ 加载/校验
def load(path: str) -> Dict[str, Any]:
    """读 profile JSON；返回的 dict 带 `_base_dir`（资产相对解析基点）。"""
    p = Path(path)
    with open(p, encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise ValueError("gate profile 顶层须为对象：%s" % path)
    doc["_base_dir"] = str(p.resolve().parent)
    doc["_path"] = str(p)
    return doc


def _base_dir(profile: Dict[str, Any], base_dir: Optional[Any]) -> Optional[Path]:
    if base_dir is not None:
        return Path(base_dir)
    rel = profile.get("_base_dir")
    return Path(rel) if rel else None


def _validate_clause(clause: Any, i: int, seen: Dict[str, int],
                     issues: List[str]) -> None:
    """逐条 clause 形状校验（拆自 validate，控制单函数圈复杂度）。"""
    at = "clauses[%d]" % i
    if not isinstance(clause, dict):
        issues.append("%s 须为对象" % at)
        return
    for key in REQUIRED_CLAUSE_KEYS:
        if key not in clause:
            issues.append("%s 缺必填字段 %s" % (at, key))
    cid = str(clause.get("clause_id") or "").strip()
    if not cid:
        return
    at = "clause %s" % cid
    if not CLAUSE_ID_RE.match(cid):
        issues.append("%s 的 clause_id 形态非法（[A-Za-z0-9._-]，2-80 字符）" % at)
    if cid in seen:
        issues.append("%s 重复（首次出现于 clauses[%d]）" % (at, seen[cid]))
    seen[cid] = i
    if str(clause.get("level") or "") not in LEVELS:
        issues.append("%s 的 level 非法：%r（允许 %s）"
                      % (at, clause.get("level"), "/".join(LEVELS)))
    pred = clause.get("predicate")
    if not isinstance(pred, dict) or not pred.get("kind"):
        issues.append("%s 的 predicate 须为带 kind 的对象" % at)
    else:
        kind = str(pred.get("kind"))
        if kind not in _PREDICATES:
            issues.append("%s 的 predicate.kind 未注册：%r（已支持 %s）"
                          % (at, kind, "、".join(PREDICATE_KINDS)))
        elif kind == "text_rule" and str(pred.get("rule")) not in _TEXT_IMPL:
            issues.append("%s 的 text_rule 未注册：%r（已支持 %s）"
                          % (at, pred.get("rule"), "、".join(TEXT_RULES)))
    if not str(clause.get("evidence") or "").strip():
        issues.append("%s 的 evidence 不得为空（判据依据须可读）" % at)
    src = clause.get("source")
    if not ((isinstance(src, dict) and src.get("standard")) or
            (isinstance(src, str) and src.strip())):
        issues.append("%s 的 source 须给标准出处（对象含 standard 或字符串）" % at)
    if not str(clause.get("data_source") or "").strip():
        issues.append("%s 的 data_source 不得为空（数据来源须可追）" % at)


def _validate_assets(profile: Dict[str, Any], base: Optional[Path],
                     issues: List[str]) -> None:
    for key, rel in (profile.get("assets") or {}).items():
        if base is None:
            continue
        if not (base / str(rel)).is_file():
            issues.append("assets.%s 指向的资产不存在：%s（相对 %s）"
                          % (key, rel, base))


def validate(profile: Dict[str, Any], base_dir: Optional[Any] = None) -> List[str]:
    """校验 profile 形状与判据可执行性 → 问题清单（空 = 合法）。"""
    issues: List[str] = []
    if str(profile.get("schema") or "") != SCHEMA:
        issues.append("schema 非 %s：%r" % (SCHEMA, profile.get("schema")))
    if not str(profile.get("profile_id") or "").strip():
        issues.append("缺 profile_id")
    clauses = profile.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        return issues + ["clauses 须为非空列表"]
    seen: Dict[str, int] = {}
    for i, clause in enumerate(clauses):
        _validate_clause(clause, i, seen, issues)
    _validate_assets(profile, _base_dir(profile, base_dir), issues)
    return issues


# ------------------------------------------------------------------ 逐条报告
def report(text: str, profile: Dict[str, Any],
           base_dir: Optional[Any] = None) -> Dict[str, Any]:
    """逐条 clause 报告（同输入同输出；ok = 无 fail 级违例）。"""
    base = _base_dir(profile, base_dir)
    ctx = build_context(text, profile, base)
    rows: List[Dict[str, Any]] = []
    n_fail = n_warn = 0
    for clause in profile.get("clauses") or []:
        cid = str(clause.get("clause_id") or "")
        level = str(clause.get("level") or "fail")
        try:
            findings = list(_PREDICATES[str(clause["predicate"]["kind"])](
                clause["predicate"], ctx))
        except Exception as exc:      # noqa: BLE001 - 判据执行失败按违例报，不静默通过
            findings = [_finding("判据执行失败：%s" % exc)]
        ok = not findings
        if not ok:
            if level == "fail":
                n_fail += 1
            elif level == "warn":
                n_warn += 1
        rows.append({"clause_id": cid, "level": level, "ok": ok,
                     "predicate": clause.get("predicate"),
                     "evidence": clause.get("evidence"),
                     "source": clause.get("source"),
                     "data_source": clause.get("data_source"),
                     "findings": findings})
    return {"schema": REPORT_SCHEMA,
            "profile_id": str(profile.get("profile_id") or ""),
            "summary": {"clauses": len(rows), "pass": len(rows) - n_fail - n_warn,
                        "warn": n_warn, "fail": n_fail},
            "ok": n_fail == 0,
            "clauses": rows}


def report_text(doc: Dict[str, Any]) -> str:
    """人读报告（逐条 [PASS]/[WARN]/[FAIL] + 命中证据行）。"""
    s = doc.get("summary") or {}
    lines = ["== gate profile 报告：%s ==" % doc.get("profile_id"),
             "  clause %d · PASS %d · WARN %d · FAIL %d（%s）"
             % (s.get("clauses", 0), s.get("pass", 0), s.get("warn", 0),
                s.get("fail", 0), "通过" if doc.get("ok") else "存在 FAIL")]
    for row in doc.get("clauses") or []:
        tag = "PASS" if row["ok"] else ("FAIL" if row["level"] == "fail" else
                                        "WARN" if row["level"] == "warn" else "INFO")
        lines.append("[%s] %-28s %s" % (tag, row["clause_id"],
                                        str(row.get("evidence") or "")[:60]))
        for f in row.get("findings") or []:
            where = "L%d " % f["line"] if f.get("line") else ""
            lines.append("        · %s%s" % (where, f.get("message", "")))
    return "\n".join(lines)


# ------------------------------------------------------------------ 质量门接线
def ir_rules(profile: Dict[str, Any], base_dir: Optional[Any] = None) -> List[Any]:
    """profile → `quality_gate.Rule` 列表（按 clause 逐条成规则）。

    `run_gate(ir, default_rules() + ir_rules(profile))`：未装 profile 时叙事默认行为
    不变（M80 §2.2 profile 未配置 = 仅过结构门）。规则消息带 clause_id，便于与
    `report()` 的逐条报告对账。
    """
    from .quality_gate import Issue   # 仅在接线时导入，避免循环依赖

    base = _base_dir(profile, base_dir)
    clauses = [c for c in (profile.get("clauses") or []) if isinstance(c, dict)]

    def _make(clause: Dict[str, Any]) -> Any:
        cid = str(clause.get("clause_id") or "")
        level = str(clause.get("level") or "fail")
        evidence = str(clause.get("evidence") or "")

        def rule(ir: Any) -> List[Any]:
            text = _ir_text(ir)
            ctx = build_context(text, profile, base)
            try:
                findings = list(_PREDICATES[str(clause["predicate"]["kind"])](
                    clause["predicate"], ctx))
            except Exception as exc:  # noqa: BLE001
                findings = [_finding("判据执行失败：%s" % exc)]
            if not findings:
                return []
            msg = "[%s] %s" % (cid, findings[0]["message"])
            issue_level = "fail" if level == "fail" else "warn"
            return [Issue(issue_level, msg, suggestion=evidence)]
        rule.__name__ = "profile_%s" % re.sub(r"\W", "_", cid)
        return rule

    return [_make(c) for c in clauses]


def _ir_text(ir: Any) -> str:
    """IR → 判据文本：标题补为 H1（IR 的 title 与模块正文分离）。"""
    parts: List[str] = []
    title = str(getattr(ir, "title", "") or "").strip()
    if title:
        parts.append("# " + title)
    for layer in getattr(ir, "layers", []) or []:
        for m in getattr(layer, "modules", []) or []:
            parts.append(getattr(m, "content", "") or "")
    for m in getattr(ir, "extra_modules", []) or []:
        parts.append(getattr(m, "content", "") or "")
    return "\n\n".join(parts)


# ------------------------------------------------------------------ CLI
def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="gate_profile",
        description="M80 质量门 profile：对产物逐条输出 clause 报告（默认人读；--json 机读）")
    ap.add_argument("--profile", required=True, help="gate profile JSON 路径")
    ap.add_argument("--text", required=True, help="待检产物 markdown 路径")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON 报告")
    args = ap.parse_args(argv)
    try:
        profile = load(args.profile)
    except (OSError, ValueError) as exc:
        print("  ✗ profile 不可读：%s" % exc, file=sys.stderr)
        return 2
    issues = validate(profile)
    if issues:
        print("  ✗ profile 非法：", file=sys.stderr)
        for i in issues:
            print("    - %s" % i, file=sys.stderr)
        return 2
    try:
        text = Path(args.text).read_text(encoding="utf-8")
    except OSError as exc:
        print("  ✗ 产物不可读：%s" % exc, file=sys.stderr)
        return 2
    doc = report(text, profile)
    if args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report_text(doc))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
