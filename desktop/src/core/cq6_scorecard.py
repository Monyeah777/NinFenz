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


from ._cq6_dims import _DIM_SCORERS


def _score_dimension(dim_id: str, root: str) -> Dict[str, Any]:
    """按证据规则给分（0–5）；返回 score/reason/evidence/gaps。"""
    scorer = _DIM_SCORERS.get(dim_id)
    if scorer is None:
        raise CQ6Error("未知维度：%s（修复指引：登记到 protocol/cq6.json）" % dim_id,
                       code="DIM-UNKNOWN")
    return scorer(root)


def _grade(score: float) -> str:
    for grade, floor in GRADE_BANDS:
        if score >= floor:
            return grade
    return "E"


def _dims(reg: Dict[str, Any], root: str) -> Tuple[List[Dict[str, Any]], int, float]:
    """逐维度算分并累计权重 → (dims, 权重合计, 加权总分)。"""
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
    return dims, total_weight, weighted


def _grade_capped(overall: float, min_score: int, red: Dict[str, Any],
                  p0: int) -> Tuple[str, bool]:
    """总分等级 + 红线封顶（维度最低分低于下限，或 P0>0 → 封 C）。"""
    grade = _grade(overall)
    capped = False
    if min_score < int(red.get("min_dimension") or 2):
        grade = "C"
        capped = True
    if p0:
        grade = "C"
        capped = True
    return grade, capped


def _remediation(dims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """逐维度 gap → 修复清单条目。"""
    remediation = []
    for dim in dims:
        for gap in dim["gaps"]:
            remediation.append({"dimension": dim["id"], "gap": gap, "owner": "maintainers",
                                "status": "open"})
    return remediation


def _ratchet(baseline: Dict[str, Any], dims: List[Dict[str, Any]], overall: float) -> Dict[str, Any]:
    """基线防回退：总分与逐维分不得低于基线。"""
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
    return ratchet


def build(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    dims, total_weight, weighted = _dims(reg, root)
    if total_weight != 100:
        raise CQ6Error("维度权重合计必须 100（当前 %d）" % total_weight, code="WEIGHT-SUM")
    overall = round(weighted / 100.0, 2)
    red = reg.get("red_lines") or {}
    min_score = min(d["score"] for d in dims)
    p0 = int((_json(Path(root) / "results" / "cq" / "scan.json").get("p0")) or 0)
    grade, capped = _grade_capped(overall, min_score, red, p0)
    remediation = _remediation(dims)
    baseline = _json(Path(root) / BASELINE_REL)
    ratchet = _ratchet(baseline, dims, overall)
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


def _dimension_issues(committed: Dict[str, Any]) -> List[str]:
    """维度权重合计与分数区间判据。"""
    out: List[str] = []
    dims = committed.get("dimensions") or []
    weights = sum(int(d.get("weight") or 0) for d in dims)
    if weights != 100:
        out.append("维度权重合计非 100（当前 %d）" % weights)
    for dim in dims:
        if not 0 <= int(dim.get("score") or 0) <= 5:
            out.append("%s 分数越界" % dim.get("id"))
    return out


def _grade_issues(committed: Dict[str, Any]) -> List[str]:
    """总评等级与红线（P0 / 最低维）判据。"""
    out: List[str] = []
    p0 = int((committed.get("red_lines") or {}).get("p0") or 0)
    grade = str(committed.get("grade"))
    if p0 and grade in ("A", "B"):
        out.append("存在 P0 时总评不得 A/B")
    min_dim = int((committed.get("red_lines") or {}).get("min_dimension") or 0)
    if min_dim < 2 and grade in ("A", "B"):
        out.append("维度 <2 时总评不得 A/B")
    return out


def _remediation_issues(committed: Dict[str, Any]) -> List[str]:
    """棘轮回退与整改项 owner 判据。"""
    out: List[str] = []
    if (committed.get("ratchet") or {}).get("regressions"):
        out.append("棘轮回退：%s" % (committed["ratchet"]["regressions"][:3]))
    for item in committed.get("remediation") or []:
        if not str(item.get("owner")):
            out.append("整改项缺 owner：%s" % item.get("gap"))
    return out


def _signoff_issues(committed: Dict[str, Any]) -> List[str]:
    """人工签核与宣称边界判据。"""
    out: List[str] = []
    signoff = committed.get("signoff") or {}
    if signoff.get("ai_may_sign") is not False:
        out.append("signoff.ai_may_sign 必须 false（AI 不得代签）")
    if str(signoff.get("status")) not in ("pending-human", "signed", "rejected"):
        out.append("signoff.status 非法")
    boundary = " ".join(str(x) for x in committed.get("claims_boundary") or [])
    if "不是质量认证" not in boundary:
        out.append("claims_boundary 必须写明不是质量认证")
    return out


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
    issues.extend(_dimension_issues(committed))
    issues.extend(_grade_issues(committed))
    issues.extend(_remediation_issues(committed))
    issues.extend(_signoff_issues(committed))
    return issues
