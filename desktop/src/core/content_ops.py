"""内容 SRE：只从**真实产物**采集 SLI，没有数据就 UNKNOWN（不编造、不判绿）。

背景（T11.1）：NF 的质量结论此前散在 verify/conformance/audit/bench 等产物里，没有一层
「面向运行」的观测口径：哪些数字是实测的？哪些压根没测（真实模型 0 行、M2 记录 0 条）？
本模块把既有产物聚合成一份 **`nf-ops-report/1`** 报告，每条 SLI 带
`value / unit / source / freshness / status ∈ OK|WARN|UNKNOWN`：

- **OK**：来源在场、可解析、且满足阈值；
- **WARN**：来源在场但越阈值（或新鲜度超期）——如实报警，不掩盖；
- **UNKNOWN**：来源缺失/不可解析，或**已知无数据**（真实模型 0 行、M2 记录 0 条、
  live 扫描被显式关闭）。已知无数据不判绿，也不冒充 WARN。

纪律：**只读**——不写任何既有产物；live 面（安全扫描 / 模型检查 / 知识图 check）只调用
既有只读扫描器，不落盘。`check()` 对「缺源/不可解析/值非法」fail-closed（返回 issue），
对「已知无数据」的 UNKNOWN 不算失败（那是现实，不是缺陷）。
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import time
from contextlib import redirect_stdout
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "nf-ops-report/1"
OK, WARN, UNKNOWN = "OK", "WARN", "UNKNOWN"

#: 各产物的新鲜度预算（天）：过预算 → WARN（不改变值，只标 freshness.stale）
MAX_AGE_DAYS = {
    "results/bench/gate_defect_report.json": 30,
    "results/bench/LEADERBOARD.md": 90,
    "protocol/conformance_report.json": 30,
    "protocol/RECEIPTS.json": 30,
    "protocol/verification_report.json": 30,
    "results/audit": 90,
    "protocol/registry_index.json": 30,
    "protocol/concept_graph_index.json": 30,
    "protocol/exec_records": 90,
}
_HEX = re.compile(r"^[0-9a-f]{64}$")
_KNOWN_EMPTY = ("no_real_model_rows", "no_m2_records", "live_disabled")


# ---------------------------------------------------------------- 通用小件

def _fresh(source: str, path: Optional[str], now: float) -> Dict[str, Any]:
    days = MAX_AGE_DAYS.get(source, 30)
    if not path:
        return {"mtime": None, "age_days": None, "max_age_days": days, "stale": False}
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {"mtime": None, "age_days": None, "max_age_days": days, "stale": False}
    age = max(0.0, (now - mtime) / 86400.0)
    return {"mtime": int(mtime), "age_days": round(age, 1), "max_age_days": days,
            "stale": age > days}


def _sli(sid: str, title: str, value: Any, unit: str, source: str,
         fresh: Dict[str, Any], status: str, reason: str = "",
         threshold: Any = None, detail: str = "") -> Dict[str, Any]:
    return {"id": sid, "title": title, "value": value, "unit": unit, "source": source,
            "freshness": fresh, "status": status, "reason": reason,
            "threshold": threshold, "detail": detail}


def _read_json(root: str, rel: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """→ (data, 绝对路径, 错误)。缺件/坏 JSON 都返回错误（调用方转 UNKNOWN）。"""
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return None, None, "missing_source"
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        if not isinstance(doc, dict):
            return None, path, "malformed_source: 顶层不是对象"
        return doc, path, None
    except (OSError, ValueError) as exc:
        return None, path, "malformed_source: %s" % exc


def _unknown(sid: str, title: str, unit: str, source: str, fresh: Dict[str, Any],
             reason: str, detail: str = "") -> Dict[str, Any]:
    return _sli(sid, title, None, unit, source, fresh, UNKNOWN, reason=reason,
                detail=detail)


# ---------------------------------------------------------------- 各面采集

def _gate_slis(root: str, now: float) -> List[Dict[str, Any]]:
    rel = "results/bench/gate_defect_report.json"
    rep, path, err = _read_json(root, rel)
    fresh = _fresh(rel, path, now)
    if err or not isinstance(rep, dict):
        return [_unknown("gate_defect_detection_rate", "门禁缺陷检出率", "ratio", rel, fresh,
                         err or "malformed_source"),
                _unknown("gate_defect_fp_rate", "门禁误报率", "ratio", rel, fresh,
                         err or "malformed_source")]
    overall = rep.get("overall") or {}
    th = rep.get("thresholds") or {}
    min_det = float(th.get("min_detection_rate", 0.9))
    max_fp = float(th.get("max_fp_rate", 0.1))
    det = float(overall.get("detection_rate") or 0.0)
    fp = float(overall.get("fp_rate") or 0.0)
    ok_verdict = bool((rep.get("verdict") or {}).get("ok"))
    out = [
        _sli("gate_defect_detection_rate", "门禁缺陷检出率", round(det, 4), "ratio", rel,
             fresh, OK if det >= min_det and ok_verdict else WARN,
             reason="" if det >= min_det and ok_verdict else "below_min_detection_rate",
             threshold={"min": min_det},
             detail="detected=%s/%s · clean=%s" % (overall.get("detected"),
                                                   overall.get("negatives"),
                                                   overall.get("clean_cases"))),
        _sli("gate_defect_fp_rate", "门禁误报率", round(fp, 4), "ratio", rel, fresh,
             OK if fp <= max_fp else WARN,
             reason="" if fp <= max_fp else "above_max_fp_rate",
             threshold={"max": max_fp},
             detail="fail_flagged_clean=%s" % overall.get("fail_flagged_clean")),
    ]
    return _apply_fresh(out)


def _contract_slis(root: str, now: float) -> List[Dict[str, Any]]:
    rel = "protocol/conformance_report.json"
    rep, path, err = _read_json(root, rel)
    fresh = _fresh(rel, path, now)
    if err or not isinstance(rep, dict):
        return [_unknown("conformance_passed", "契约符合面", "ratio", rel, fresh,
                         err or "malformed_source")]
    total = int(rep.get("total") or 0)
    passed = int(rep.get("passed") or 0)
    ok = total > 0 and passed == total and str(rep.get("verdict")) == "conformant"
    ratio = round(passed / total, 4) if total else 0.0
    return _apply_fresh([_sli(
        "conformance_passed", "契约符合面", ratio, "ratio", rel, fresh,
        OK if ok else WARN, reason="" if ok else "contracts_not_all_pass",
        threshold={"min": 1.0},
        detail="passed=%d/%d · verdict=%s · root=%s"
               % (passed, total, rep.get("verdict"), str(rep.get("root"))[:12]))])


def _receipts_sli(root: str, now: float) -> Dict[str, Any]:
    rel = "protocol/RECEIPTS.json"
    rec, path, err = _read_json(root, rel)
    fresh = _fresh(rel, path, now)
    if err or not isinstance(rec, dict):
        return _unknown("receipts_root", "协议层回执根", "件", rel, fresh,
                        err or "malformed_source")
    entries = len(rec.get("entries") or [])
    root_ok = bool(_HEX.match(str(rec.get("root") or "")))
    return _sli("receipts_root", "协议层回执根", entries, "件", rel, fresh,
                OK if entries > 0 and root_ok else WARN,
                reason="" if entries > 0 and root_ok else "receipts_root_invalid",
                detail="root=%s · scope=%s"
                       % (str(rec.get("root"))[:16], rec.get("scope")))


def _audit_sli(root: str, now: float) -> Dict[str, Any]:
    files = sorted(glob.glob(os.path.join(root, "results", "audit", "*.md")))
    newest = max((os.path.getmtime(f) for f in files), default=None)
    budget = MAX_AGE_DAYS["results/audit"]
    fresh = {"mtime": int(newest) if newest else None,
             "age_days": (round(max(0.0, (now - newest) / 86400.0), 1)
                          if newest else None),
             "max_age_days": budget,
             "stale": bool(newest and (now - newest) / 86400.0 > budget)}
    return _sli("audit_count", "审计件数", len(files), "件", "results/audit", fresh,
                OK if files else WARN, reason="" if files else "no_audits")


def _verify_slis(root: str, now: float) -> List[Dict[str, Any]]:
    rel = "protocol/verification_report.json"
    vr, path, err = _read_json(root, rel)
    fresh = _fresh(rel, path, now)
    if err or not isinstance(vr, dict):
        return [_unknown("verify_report_fail", "verify 判据面失败数", "条", rel, fresh,
                         err or "malformed_source"),
                _unknown("verify_report_warn", "verify 判据面告警数", "条", rel, fresh,
                         err or "malformed_source")]
    s = vr.get("summary") or {}
    fail = int(s.get("fail") or 0) + int(s.get("error") or 0)
    warns = int(s.get("warn") or 0)
    return [
        _sli("verify_report_fail", "verify 判据面失败数", fail, "条", rel, fresh,
             OK if fail == 0 else WARN,
             reason="" if fail == 0 else "verify_failures_present",
             detail="pass=%s · fail=%s · error=%s"
                    % (s.get("pass"), s.get("fail"), s.get("error"))),
        _sli("verify_report_warn", "verify 判据面告警数", warns, "条", rel, fresh,
             OK if warns == 0 else WARN,
             reason="" if warns == 0 else "verify_warnings_present",
             detail="report_items=%s"
                    % (vr.get("declared") or {}).get("report_items")),
    ]


def _evidence_slis(root: str, now: float) -> List[Dict[str, Any]]:
    out = [_receipts_sli(root, now), _audit_sli(root, now)]
    out.extend(_verify_slis(root, now))
    return _apply_fresh(out)


def _leaderboard_rows(text: str) -> Tuple[int, int]:
    """→ (真实模型行数, baseline 行数)。列序固定（scripts/bench_leaderboard.py 生成）。"""
    model = baseline = 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if all(set(c) <= set("-: ") for c in cells) or cells[0].lower() == "profile":
            continue
        if cells[1].lower().startswith("baseline"):
            baseline += 1
        else:
            model += 1
    return model, baseline


def _coverage_slis(root: str, now: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    rel = "results/bench/LEADERBOARD.md"
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        out.append(_unknown("benchmark_real_model_rows", "真实模型结果行数", "行", rel,
                            _fresh(rel, None, now), "missing_source"))
    else:
        with open(path, encoding="utf-8") as fh:
            model_rows, baseline_rows = _leaderboard_rows(fh.read())
        fresh = _fresh(rel, path, now)
        out.append(_sli("benchmark_real_model_rows", "真实模型结果行数", model_rows, "行",
                        rel, fresh, UNKNOWN if model_rows == 0 else OK,
                        reason="no_real_model_rows" if model_rows == 0 else "",
                        detail="baseline_rows=%d" % baseline_rows))
    # M2 执行记录（protocol/exec_records/*.json；排除模板与 template:true）
    rec_dir = os.path.join(root, "protocol", "exec_records")
    real = 0
    for f in sorted(glob.glob(os.path.join(rec_dir, "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and not doc.get("template"):
            real += 1
    newest = max((os.path.getmtime(f) for f in glob.glob(os.path.join(rec_dir, "*.json"))),
                 default=None)
    fresh = {"mtime": int(newest) if newest else None,
             "age_days": (round(max(0.0, (now - newest) / 86400.0), 1)
                          if newest else None),
             "max_age_days": MAX_AGE_DAYS["protocol/exec_records"],
             "stale": bool(newest and (now - newest) / 86400.0
                           > MAX_AGE_DAYS["protocol/exec_records"])}
    out.append(_sli("exec_records_m2", "M2 真实执行记录", real, "条",
                    "protocol/exec_records", fresh,
                    UNKNOWN if real == 0 else OK,
                    reason="no_m2_records" if real == 0 else "",
                    detail="模板件不计入 M2（template:true = 未执行）"))
    return _apply_fresh(out)


def _index_slis(root: str, now: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    specs = (("registry_index", "protocol/registry_index.json", "entries", "件"),
             ("concept_index", "protocol/concept_graph_index.json", "nodes", "条"))
    for sid, rel, count_key, unit in specs:
        doc, path, err = _read_json(root, rel)
        fresh = _fresh(rel, path, now)
        if err or not isinstance(doc, dict):
            out.append(_unknown(sid, "%s root" % sid, unit, rel, fresh,
                                err or "malformed_source"))
            continue
        count = len(doc.get(count_key) or [])
        root_ok = bool(_HEX.match(str(doc.get("root") or "")))
        out.append(_sli(sid, "%s root" % sid, count, unit, rel, fresh,
                        OK if count > 0 and root_ok else WARN,
                        reason="" if count > 0 and root_ok else "index_invalid",
                        detail="root=%s · schema=%s"
                               % (str(doc.get("root"))[:16], doc.get("schema"))))
    return _apply_fresh(out)


def _live_slis(root: str, now: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    # 安全面：内容供应链扫描（只读；critical 数）
    try:
        from core import content_security as cs
        rep = cs.scan(None, root=root)
        summary = rep.get("summary") or {}
        critical = int(summary.get("critical") or 0)
        undecidable = int(summary.get("undecidable") or 0)
        out.append(_sli("security_critical", "内容安全 critical 数", critical, "条",
                        "core.content_security.scan", _fresh("live", None, now),
                        OK if critical == 0 and undecidable == 0 else WARN,
                        reason="" if critical == 0 and undecidable == 0
                        else "security_findings_present",
                        detail="findings=%s · warn=%s · undecidable=%s"
                               % (summary.get("findings"), summary.get("warn"), undecidable)))
    except Exception as exc:                                # noqa: BLE001 - 扫描不可用按 UNKNOWN
        out.append(_unknown("security_critical", "内容安全 critical 数", "条",
                            "core.content_security.scan", _fresh("live", None, now),
                            "scanner_unavailable: %s" % exc))
    # 形式化面：modelcheck verdict
    try:
        from core import model_check as mc
        buf = io.StringIO()
        with redirect_stdout(buf):
            mc.run(root, as_json=True)
        doc = json.loads(buf.getvalue())
        if not isinstance(doc, dict):
            raise ValueError("modelcheck 输出顶层不是对象"
                             "（修复指引：检查 core.model_check.run 的返回结构，勿改本采集器）")
        verdict = str(doc.get("verdict") or "")
        out.append(_sli("modelcheck_verdict", "模型检查 verdict", verdict, "verdict",
                        "core.model_check.run", _fresh("live", None, now),
                        OK if verdict == "pass" else WARN,
                        reason="" if verdict == "pass" else "modelcheck_not_pass",
                        detail="issues=%d · states=%s"
                               % (len(doc.get("issues") or []),
                                  (doc.get("stats") or {}).get("states"))))
    except Exception as exc:                                # noqa: BLE001
        out.append(_unknown("modelcheck_verdict", "模型检查 verdict", "verdict",
                            "core.model_check.run", _fresh("live", None, now),
                            "modelcheck_unavailable: %s" % exc))
    # 知识图 check 状态（只读重算）
    try:
        from core import concept_index as ci
        issues, _doc = ci.check(root)
        out.append(_sli("knowledge_graph_check", "知识图索引一致性", len(issues), "条",
                        "core.concept_index.check", _fresh("live", None, now),
                        OK if not issues else WARN,
                        reason="" if not issues else "knowledge_graph_drift",
                        detail="; ".join(issues[:2])))
    except Exception as exc:                                # noqa: BLE001
        out.append(_unknown("knowledge_graph_check", "知识图索引一致性", "条",
                            "core.concept_index.check", _fresh("live", None, now),
                            "check_unavailable: %s" % exc))
    return _apply_fresh(out)


def _apply_fresh(slis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for s in slis:
        if s["status"] == OK and (s.get("freshness") or {}).get("stale"):
            s["status"] = WARN
            s["reason"] = "stale_source"
    return slis


# ---------------------------------------------------------------- 汇总 / 校验

def collect(root: str = ".", now: Optional[float] = None, live: bool = True) -> Dict[str, Any]:
    """只读采集全部 SLI → `nf-ops-report/1` 文档。`now` 可注入（确定性测试用）。"""
    now = time.time() if now is None else float(now)
    slis = (_gate_slis(root, now) + _contract_slis(root, now) + _evidence_slis(root, now)
            + _coverage_slis(root, now) + _index_slis(root, now))
    if live:
        slis += _live_slis(root, now)
    else:
        slis += [_unknown(sid, title, unit, "（live 面未执行：--no-live）",
                          _fresh("live", None, now), "live_disabled")
                 for sid, title, unit in (
                     ("security_critical", "内容安全 critical 数", "条"),
                     ("modelcheck_verdict", "模型检查 verdict", "verdict"),
                     ("knowledge_graph_check", "知识图索引一致性", "条"))]
    counts = {OK: 0, WARN: 0, UNKNOWN: 0}
    for s in slis:
        counts[s["status"]] += 1
    overall = UNKNOWN if counts[UNKNOWN] else (WARN if counts[WARN] else OK)
    report = {
        "schema": SCHEMA,
        "as_of": int(now),
        "window": "on-demand",
        "overall": overall,
        "status_counts": counts,
        "slis": slis,
        "uncovered": [
            "无生产流量/真实用户请求（本仓是离线工具链）",
            "无真实模型执行：benchmark 真实模型行数=%s、M2 记录=%s"
            % (next((s["value"] for s in slis if s["id"] == "benchmark_real_model_rows"), None),
               next((s["value"] for s in slis if s["id"] == "exec_records_m2"), None)),
            "无长期窗口/告警分页（on-demand 采样，非连续监控）",
            "安全面仅内容供应链扫描，不含主机/依赖漏洞面",
            "modelcheck 结论含不可判定项（verdict=warn 不等于通过）",
            "无成本/延迟 SLI（本地离线执行）",
        ],
        "targets": {"detection_rate": ">= thresholds.min_detection_rate（当前 0.90）",
                    "fp_rate": "<= thresholds.max_fp_rate（当前 0.10）",
                    "conformance": "passed == total 且 verdict=conformant",
                    "evidence": "回执根 64hex、audit>0、verify fail+error==0",
                    "coverage": "真实模型行数>0 且 M2 记录>0 才判 OK（当前 UNKNOWN）",
                    "index": "root 64hex、条数>0 且新鲜度 ≤30 天",
                    "safety": "critical==0 且 undecidable==0；modelcheck verdict=pass"},
    }
    return report


def _source_issue(s: Dict[str, Any]) -> Optional[str]:
    if s["status"] != UNKNOWN:
        return None
    reason = str(s.get("reason") or "")
    if reason in _KNOWN_EMPTY:
        return None
    if reason.startswith("live_disabled"):
        return None
    return "%s：%s（source=%s）" % (s["id"], reason, s["source"])


def _value_issue(s: Dict[str, Any]) -> Optional[str]:
    name = s["id"]
    if s["status"] == UNKNOWN:
        return None
    if "rate" in name or name == "conformance_passed":
        try:
            v = float(s["value"])
        except (TypeError, ValueError):
            return "%s：value 不是数值（%r）" % (name, s["value"])
        if not 0.0 <= v <= 1.0:
            return "%s：ratio 越界 %r" % (name, v)
    if name in ("verify_report_fail", "verify_report_warn", "security_critical",
                "audit_count", "receipts_root", "exec_records_m2",
                "benchmark_real_model_rows", "registry_index", "concept_index") \
            and not isinstance(s["value"], int):
        return "%s：value 应为整数（%r）" % (name, s["value"])
    return None


def check(root: str = ".", now: Optional[float] = None,
          live: bool = True) -> Tuple[List[str], Dict[str, Any]]:
    """校验：缺源/不可解析/值非法 → issue（fail-closed）；已知无数据 UNKNOWN 不算失败。"""
    report = collect(root, now=now, live=live)
    issues: List[str] = []
    for s in report["slis"]:
        for issue in (_source_issue(s), _value_issue(s)):
            if issue:
                issues.append(issue)
    if not report["slis"]:
        issues.append("没有任何 SLI（采集面为空）")
    return issues, report


def run(root: str = ".", now: Optional[float] = None, live: bool = True) -> Dict[str, Any]:
    """门禁入口（与 repo_stats.scan 同形）：返回报告；缺源问题在 `check()`。"""
    return collect(root, now=now, live=live)
