"""cq6_scorecard 私有子模块：D1–D8 证据规则给分（按证据规则打 0–5，返回 score/reason/evidence/gaps）。

门面 core.cq6_scorecard 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core import cq6_scorecard as _dm


def _blocked_tools(r: Path) -> List[str]:
    """工具链 BLOCKED 列表（如实扣分，不冒充全扫）。"""
    tc = _dm._json(r / "results" / "cq" / "toolchain.json")
    return [b for b in (tc.get("blocked") or []) if b]


def _d6_score(recorded: int, over: int, pb_issues: list) -> int:
    """D6 分数：有记录且零超预算且无问题 → 5；有记录 → 4；无记录 → 3。"""
    if recorded and over == 0 and not pb_issues:
        return 5
    return 4 if recorded else 3


def _dim_d1(root: str) -> Dict[str, Any]:
    """D1：验证/一致性门禁面。"""
    r = Path(root)
    gaps: List[str] = []
    vr = _dm._json(r / "protocol" / "verification_report.json")
    conf = _dm._json(r / "protocol" / "conformance_report.json")
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


def _dim_d2(root: str) -> Dict[str, Any]:
    """D2：CQ P0 / 工具链 BLOCKED / 秘密扫描覆盖。"""
    r = Path(root)
    gaps: List[str] = []
    cq = _dm._json(r / "results" / "cq" / "scan.json")
    p0 = int(cq.get("p0") or 0)
    blocked = _blocked_tools(r)
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


def _dim_d3(root: str) -> Dict[str, Any]:
    """D3：复杂度棘轮与存量热点。"""
    r = Path(root)
    gaps: List[str] = []
    cm = _dm._json(r / "protocol" / "code_metrics_baseline.json")
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


def _dim_d4(root: str) -> Dict[str, Any]:
    """D4：判据面齐全度（覆盖/变异未全量）。"""
    r = Path(root)
    gaps: List[str] = []
    w = _dm._json(r / "protocol" / "check12_weights.json")
    modules = len(w.get("modules") or {})
    score = 4 if modules >= 100 else 3
    gaps.append("核心覆盖率未测（coverage 工具在，未接线为门禁指标）")
    gaps.append("全仓 mutation score 未测（QD-06），只有关键面抽样")
    return {"score": score, "reason": "判据面齐全但覆盖/变异未全量测量",
            "evidence": ["protocol/check12_weights.json"], "gaps": gaps}


def _dim_d5(root: str) -> Dict[str, Any]:
    """D5：跨实现 / 离线验证。"""
    r = Path(root)
    gaps: List[str] = []
    go_dir = (r / "clients" / "go")
    blocked = _blocked_tools(r)
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


def _dim_d6(root: str) -> Dict[str, Any]:
    """D6：perf 预算记录与超预算面。"""
    from core import perf_budget as pb_mod
    gaps: List[str] = []
    try:
        pb_issues, _warns, pb_stats = pb_mod.scan(root)
    except Exception:  # noqa: BLE001 - 度量不可用按 0 记，不冒充
        pb_issues, pb_stats = ["perf_budget.scan 不可用"], {}
    recorded = int(pb_stats.get("recorded") or 0)
    over = int(pb_stats.get("over_budget") or 0)
    score = _d6_score(recorded, over, pb_issues)
    if not recorded:
        gaps.append("缺 perf 预算记录")
    if over:
        gaps.append("perf 超预算：%d 项" % over)
    return {"score": score, "reason": "预算内（%d 项记录，%d 超预算）" % (recorded, over),
            "evidence": ["protocol/perf_budget.json"], "gaps": gaps}


def _dim_d7(root: str) -> Dict[str, Any]:
    """D7：文档 claims 与实测一致。"""
    from core import docs_claims as dc
    gaps: List[str] = []
    issues = dc.check(root)
    score = 5 if not issues else 3
    if issues:
        gaps.extend(issues[:3])
    return {"score": score, "reason": "文档 claims 与实测一致" if not issues else "文档 claims 有偏差",
            "evidence": ["results/docs_claims_report.json"], "gaps": gaps}


def _dim_d8(root: str) -> Dict[str, Any]:
    """D8：依赖钉版 / CI 权限 / SBOM。"""
    r = Path(root)
    gaps: List[str] = []
    blocked = _blocked_tools(r)
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


_DIM_SCORERS: Dict[str, Any] = {
    "D1": _dim_d1,
    "D2": _dim_d2,
    "D3": _dim_d3,
    "D4": _dim_d4,
    "D5": _dim_d5,
    "D6": _dim_d6,
    "D7": _dim_d7,
    "D8": _dim_d8,
}
