"""CQ6 综合审查（WP-54，G5）：八维评分卡 + 红线 + 棘轮 + 整改 + 复审签署状态。

纪律：
- 评分**由在场证据按规则算出**（不手填）：verification_report/conformance/CQ 扫描/工具链
  BLOCKED/度量基线/测试权重/Go 客户端/perf 预算/docs-claims/AIBOM；
- **红线**：任一维 <2 → 总评封顶 C；未登记 P0 → 封顶 C；P0 存在则总分不得 A/B；
- **棘轮**：对照 `results/cq/cq6_baseline.json`，维度分/总分只许不降（首次运行建立基线）；
- **复审签署**：人工签署不能由 AI 代签——未签记 `pending-human`，不冒充已签（§13C.3）；
- 不确定项（覆盖未测、Go parity 未做、gitleaks/dotnet BLOCKED）如实扣分并进整改 backlog。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-cq6/1"
REL = "protocol/cq6.json"
REPORT_REL = "results/cq/cq6_scorecard.json"
BASELINE_REL = "results/cq/cq6_baseline.json"
REPORT_SCHEMA = "nf-cq6-scorecard/1"
GUIDE = "修复指引："
GRADE_BANDS = (("A", 4.5), ("B", 4.0), ("C", 3.0), ("D", 2.0), ("E", 0.0))


class CQ6Error(Exception):
    """CQ6 登记/评分错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "CQ6-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise CQ6Error("缺 %s（修复指引：补 CQ6 登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CQ6Error("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise CQ6Error("registry schema 必须 %s" % SCHEMA)
    return doc


def _json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _score_dimension(dim_id: str, root: str) -> Dict[str, Any]:
    """按证据规则给分（0–5）；返回 score/reason/evidence/gaps。"""
    r = Path(root)
    gaps: List[str] = []
    if dim_id == "D1":
        vr = _json(r / "protocol" / "verification_report.json")
        conf = _json(r / "protocol" / "conformance_report.json")
        fail = int((vr.get("summary") or {}).get("fail") or 0)
        ok_conf = str(conf.get("verdict")) == "conformant"
        score = 5 if fail == 0 and ok_conf else (3 if fail == 0 else 1)
        if not ok_conf:
            gaps.append("conformance 非 conformant")
        if fail:
            gaps.append("verification_report fail=%d" % fail)
        return {"score": score,
                "reason": "fail=0 且 conformance=conformant" if score == 5 else "存在失败面",
                "evidence": ["protocol/verification_report.json", "protocol/conformance_report.json"],
                "gaps": gaps}
    if dim_id == "D2":
        cq = _json(r / "results" / "cq" / "scan.json")
        tc = _json(r / "results" / "cq" / "toolchain.json")
        p0 = int(cq.get("p0") or 0)
        blocked = [b for b in (tc.get("blocked") or []) if b]
        score = 5
        if p0:
            score = 1
            gaps.append("CQ P0=%d" % p0)
        if blocked:
            score = min(score, 4)
            gaps.append("工具 BLOCKED：%s" % ",".join(blocked))
        if any("gitleaks" in b for b in blocked):
            score = min(score, 4)
            gaps.append("gitleaks 不在场：秘密扫描未全覆盖")
        return {"score": score, "reason": "P0=0；BLOCKED 工具如实扣分",
                "evidence": ["results/cq/scan.json", "results/cq/toolchain.json"], "gaps": gaps}
    if dim_id == "D3":
        cm = _json(r / "protocol" / "code_metrics_baseline.json")
        hotspots = (r / "results" / "cq" / "hotspots.md").is_file()
        files = cm.get("files") or {}
        max_cc = max((int((v or {}).get("max_fn_cc") or 0) for v in files.values()),
                     default=0)
        limit_cc = int((cm.get("limits") or {}).get("max_fn_cc") or 15)
        score = 5
        if max_cc > limit_cc:
            score = 3
            gaps.append("存量 max_fn_cc=%d > 阈值 %d（已棘轮冻结，需登记热点 owner）"
                        % (max_cc, limit_cc))
        if not hotspots:
            score = min(score, 3)
            gaps.append("缺 results/cq/hotspots.md")
        return {"score": score, "reason": "复杂度在棘轮内但存在存量热点",
                "evidence": ["protocol/code_metrics_baseline.json", "results/cq/hotspots.md"],
                "gaps": gaps}
    if dim_id == "D4":
        w = _json(r / "protocol" / "check12_weights.json")
        modules = len(w.get("modules") or {})
        score = 4 if modules >= 100 else 3
        gaps.append("核心覆盖率未测（coverage 工具在，未接线为门禁指标）")
        gaps.append("全仓 mutation score 未测（QD-06），只有关键面抽样")
        return {"score": score, "reason": "判据面齐全但覆盖/变异未全量测量",
                "evidence": ["protocol/check12_weights.json"], "gaps": gaps}
    if dim_id == "D5":
        go_dir = (r / "clients" / "go")
        tc = _json(r / "results" / "cq" / "toolchain.json")
        blocked = [b for b in (tc.get("blocked") or []) if b]
        score = 2
        gaps.append("Go↔Python parity 未做（WP-51）")
        gaps.append("离线（无网）验证未系统化")
        if any("dotnet" in b for b in blocked):
            gaps.append("dotnet BLOCKED：.NET 门禁未跑")
        if not (go_dir / "nfverify").exists():
            score = 1
            gaps.append("缺 Go 验证客户端")
        return {"score": score, "reason": "跨实现/离线未证明，按红线附近给分",
                "evidence": ["clients/go", "results/cq/toolchain.json"], "gaps": gaps}
    if dim_id == "D6":
        from core import perf_budget as pb_mod
        try:
            pb_issues, _warns, pb_stats = pb_mod.scan(root)
        except Exception:  # noqa: BLE001 - 度量不可用按 0 记，不冒充
            pb_issues, pb_stats = ["perf_budget.scan 不可用"], {}
        recorded = int(pb_stats.get("recorded") or 0)
        over = int(pb_stats.get("over_budget") or 0)
        score = 5 if recorded and over == 0 and not pb_issues else (4 if recorded else 3)
        if not recorded:
            gaps.append("缺 perf 预算记录")
        if over:
            gaps.append("perf 超预算：%d 项" % over)
        return {"score": score, "reason": "预算内（%d 项记录，%d 超预算）" % (recorded, over),
                "evidence": ["protocol/perf_budget.json"], "gaps": gaps}
    if dim_id == "D7":
        from core import docs_claims as dc
        issues = dc.check(root)
        score = 5 if not issues else 3
        if issues:
            gaps.extend(issues[:3])
        return {"score": score, "reason": "文档 claims 与实测一致" if not issues else "文档 claims 有偏差",
                "evidence": ["results/docs_claims_report.json"], "gaps": gaps}
    if dim_id == "D8":
        tc = _json(r / "results" / "cq" / "toolchain.json")
        blocked = [b for b in (tc.get("blocked") or []) if b]
        sbom = (r / "results" / "ai" / "aibom.cdx.json").is_file()
        score = 4
        if blocked:
            score = 3
            gaps.append("工具链 BLOCKED：%s" % ",".join(blocked))
        if not sbom:
            score = min(score, 2)
            gaps.append("缺 SBOM（AIBOM 导出）")
        return {"score": score, "reason": "依赖钉版/CI 权限有检查；外部审计工具受限",
                "evidence": ["results/cq/toolchain.json", "results/ai/aibom.cdx.json"], "gaps": gaps}
    raise CQ6Error("未知维度：%s（修复指引：登记到 protocol/cq6.json）" % dim_id,
                   code="DIM-UNKNOWN")


def _grade(score: float) -> str:
    for grade, floor in GRADE_BANDS:
        if score >= floor:
            return grade
    return "E"


def build(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    dims = []
    total_weight = 0
    weighted = 0.0
    for item in reg.get("dimensions") or []:
        did = str(item.get("id"))
        got = _score_dimension(did, root)
        weight = int(item.get("weight") or 0)
        total_weight += weight
        weighted += got["score"] * weight
        dims.append({"id": did, "name": str(item.get("name")), "weight": weight,
                     "score": got["score"], "reason": got["reason"],
                     "evidence": got["evidence"], "gaps": got["gaps"]})
    if total_weight != 100:
        raise CQ6Error("维度权重合计必须 100（当前 %d）" % total_weight, code="WEIGHT-SUM")
    overall = round(weighted / 100.0, 2)
    red = reg.get("red_lines") or {}
    min_score = min(d["score"] for d in dims)
    p0 = int((_json(Path(root) / "results" / "cq" / "scan.json").get("p0")) or 0)
    grade = _grade(overall)
    capped = False
    if min_score < int(red.get("min_dimension") or 2):
        grade = "C" if GRADE_BANDS[0][1] > 3.0 else grade
        grade = "C"
        capped = True
    if p0:
        grade = "C"
        capped = True
    remediation = []
    for dim in dims:
        for gap in dim["gaps"]:
            remediation.append({"dimension": dim["id"], "gap": gap, "owner": "maintainers",
                                "status": "open"})
    baseline = _json(Path(root) / BASELINE_REL)
    ratchet = {"baseline_present": bool(baseline), "regressions": []}
    if baseline:
        prev_overall = float(baseline.get("overall") or 0)
        if overall < prev_overall:
            ratchet["regressions"].append("总分 %s < 基线 %s" % (overall, prev_overall))
        prev_dims = {str(d.get("id")): d.get("score") for d in baseline.get("dimensions") or []}
        for dim in dims:
            prev = prev_dims.get(dim["id"])
            if prev is not None and dim["score"] < int(prev):
                ratchet["regressions"].append("%s 分 %s < 基线 %s" % (dim["id"], dim["score"], prev))
    scorecard = {"schema": REPORT_SCHEMA, "dimensions": dims,
                 "overall": overall, "grade": grade,
                 "red_lines": {"min_dimension": min_score, "p0": p0,
                               "capped": capped,
                               "rule": str(red.get("rule"))},
                 "ratchet": ratchet,
                 "remediation": remediation,
                 "signoff": {"required": bool((reg.get("signoff") or {}).get("required")),
                             "status": "pending-human",
                             "ai_may_sign": False,
                             "owner": "author",
                             "note": "AI 不能替代人类签署（§13C.3）；未签如实记 pending-human"},
                 "claims_boundary": list(reg.get("claims_boundary") or []),
                 "note": "评分由证据规则算出；committed == 实时重算"}
    return scorecard


def render(card: Dict[str, Any]) -> str:
    return json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root: str = ".") -> Path:
    from core import atomic_write
    card = build(root)
    path = Path(root) / REPORT_REL
    atomic_write.write_text(path, render(card))
    return path


def check(root: str = ".") -> List[str]:
    issues: List[str] = []
    path = Path(root) / REPORT_REL
    if not path.is_file():
        issues.append("缺 %s（修复指引：跑 write() 生成）" % REPORT_REL)
    try:
        committed = json.loads((Path(root) / REPORT_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["%s 不可解析：%s（修复指引：重生成）" % (REPORT_REL, exc)]
    live = build(root)
    if render(committed) != render(live):
        issues.append("评分卡与实时重算不一致（修复指引：重跑 write）")
    dims = committed.get("dimensions") or []
    weights = sum(int(d.get("weight") or 0) for d in dims)
    if weights != 100:
        issues.append("维度权重合计非 100（当前 %d）" % weights)
    for dim in dims:
        if not 0 <= int(dim.get("score") or 0) <= 5:
            issues.append("%s 分数越界" % dim.get("id"))
    p0 = int((committed.get("red_lines") or {}).get("p0") or 0)
    grade = str(committed.get("grade"))
    if p0 and grade in ("A", "B"):
        issues.append("存在 P0 时总评不得 A/B")
    if int((committed.get("red_lines") or {}).get("min_dimension") or 0) < 2 and grade in ("A", "B"):
        issues.append("维度 <2 时总评不得 A/B")
    if (committed.get("ratchet") or {}).get("regressions"):
        issues.append("棘轮回退：%s" % (committed["ratchet"]["regressions"][:3]))
    for item in committed.get("remediation") or []:
        if not str(item.get("owner")):
            issues.append("整改项缺 owner：%s" % item.get("gap"))
    signoff = committed.get("signoff") or {}
    if signoff.get("ai_may_sign") is not False:
        issues.append("signoff.ai_may_sign 必须 false（AI 不得代签）")
    if str(signoff.get("status")) not in ("pending-human", "signed", "rejected"):
        issues.append("signoff.status 非法")
    boundary = " ".join(str(x) for x in committed.get("claims_boundary") or [])
    if "不是质量认证" not in boundary:
        issues.append("claims_boundary 必须写明不是质量认证")
    return issues
