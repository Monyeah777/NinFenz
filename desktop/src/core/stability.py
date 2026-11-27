"""稳定性/长稳证据（WP-51，G5）：进程内重复 + 并发确定性对照。

纪律：
- 对纯管线（assembly/output/delivery/metrics/docs_claims/AIBOM/AI 证据链）跑 **N 次重复**
  与 **C 路并发**，要求每次摘要逐字节一致、0 mismatch；
- 结果落 `results/stability/report.json`（committed == 实时重算）；
- **只证明进程内重复/并发确定性**：不是长稳 soak、不代表真实模型/外部环境稳定，
  不声称 SLA/可用性（外部长期观测属 OPEN）。
"""
from __future__ import annotations

from core import report_module

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List

SCHEMA = "nf-stability/1"
REL = "protocol/stability.json"
REPORT_REL = "results/stability/report.json"
REPORT_SCHEMA = "nf-stability-report/1"
INTENT = "spec/intents/sample-document.json"
GUIDE = "修复指引："


class StabilityError(Exception):
    """稳定性登记/复算错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "STABILITY-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise StabilityError("缺 %s（修复指引：补稳定性登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StabilityError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise StabilityError("registry schema 必须 %s" % SCHEMA)
    return doc


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest_check(check_id: str, root: str) -> str:
    from core import ai_evidence as ae
    from core import assembly_runtime as ar
    from core import aibom_export as ax
    from core import delivery as dv
    from core import docs_claims as dc
    from core import output_validation as ov
    from core import production_metrics as pm
    from core import spec_compiler as sc
    from core import context_packer as cp
    from core import agent_adapter as aa
    if check_id == "S-01":
        return _sha(ar.render(ar.run(INTENT, "mock", root)))
    if check_id == "S-02":
        intent = json.loads((Path(root) / INTENT).read_text(encoding="utf-8"))
        task = sc.compile_intent(intent, root, INTENT)["tasks"][0]
        pack = cp.pack_task(task, root, budget_chars=2000, role="author")
        out = aa.run("mock", task, pack, root)
        return _sha(ov.render(ov.validate(out, task, pack, root)))
    if check_id == "S-03":
        intent = json.loads((Path(root) / INTENT).read_text(encoding="utf-8"))
        task = sc.compile_intent(intent, root, INTENT)["tasks"][0]
        pack = cp.pack_task(task, root, budget_chars=2000, role="author")
        out = aa.run("mock", task, pack, root)
        report = ov.validate(out, task, pack, root)
        pkg = dv.build(ar.run(INTENT, "mock", root), out, report, sidecar=True)
        return _sha(json.dumps(pkg["manifest"], ensure_ascii=False, sort_keys=True))
    if check_id == "S-04":
        return _sha(pm.render(pm.build(root)))
    if check_id == "S-05":
        return _sha(dc.render(dc.build(root)))
    if check_id == "S-06":
        doc = ax.build(root)
        return _sha(ax.render(doc["cdx"]) + ax.render(doc["spdx"]))
    if check_id == "S-07":
        sample = ae.load_sample(root)
        payload = json.dumps([sample["card"], sample["lineage"], sample["review"]],
                             ensure_ascii=False, sort_keys=True)
        return _sha(payload + json.dumps(ae.check(root), sort_keys=True))
    raise StabilityError("未知稳定性 check：%s（修复指引：登记到 protocol/stability.json）"
                         % check_id, code="CHECK-UNKNOWN")


def _collect(root: str, registry: Dict[str, Any]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for item in registry.get("checks") or []:
        out[str(item.get("id"))] = [_digest_check(str(item.get("id")), root)]
    return out


def _stability_row(item: dict, root: str, runs: int, workers: int) -> tuple:
    """单项重复/并发跑 → (id, 结果行)。"""
    cid = str(item.get("id"))
    seq = [_digest_check(cid, root) for _ in range(max(1, runs))]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        par = list(pool.map(lambda _: _digest_check(cid, root), range(max(1, runs))))
    digests = seq + par
    mismatches = sum(1 for d in digests if d != digests[0])
    return cid, {"id": cid, "name": str(item.get("name")),
                 "digest": digests[0], "runs": len(digests),
                 "identical": mismatches == 0, "mismatches": mismatches}


def build(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    runs = int(reg.get("runs") or 5)
    workers = int(reg.get("concurrency") or 4)
    results: Dict[str, Dict[str, Any]] = {}
    for item in reg.get("checks") or []:
        cid, row = _stability_row(item, root, runs, workers)
        results[cid] = row
    report = {"schema": REPORT_SCHEMA, "runs": runs, "concurrency": workers,
              "checks": [results[k] for k in sorted(results)],
              "summary": {"checks": len(results),
                          "unique_digests": len({r["digest"] for r in results.values()}),
                          "mismatches": sum(r["mismatches"] for r in results.values())},
              "scope": {"in_process_repeat": True, "concurrent": True, "soak_hours": False,
                        "note": "只证明进程内重复/并发确定性；长稳 soak 与外部环境稳定属 OPEN"},
              "claims_boundary": list(reg.get("claims_boundary") or []),
              "note": "committed == 实时重算"}
    return report


render = report_module.render
write = report_module.writer(REPORT_REL, build)


def _item_issues(committed: dict[str, Any]) -> List[str]:
    """逐项：重复/并发摘要必须一致。"""
    issues: List[str] = []
    for item in committed.get("checks") or []:
        if not item.get("identical") or int(item.get("mismatches") or 0) != 0:
            issues.append("%s 重复/并发摘要不一致（%s mismatches）"
                          "（修复指引：查非确定性来源）" % (item.get("id"), item.get("mismatches")))
    return issues


def _declaration_issues(committed: dict[str, Any]) -> List[str]:
    """summary / scope / claims_boundary 声明面（不得冒充长稳 soak）。"""
    issues: List[str] = []
    if int((committed.get("summary") or {}).get("mismatches") or 0) != 0:
        issues.append("summary.mismatches 非 0")
    scope = committed.get("scope") or {}
    if scope.get("soak_hours") is not False:
        issues.append("scope.soak_hours 必须 false（本件不是长稳 soak，不得冒充）")
    boundary = " ".join(str(x) for x in committed.get("claims_boundary") or [])
    if "不是长稳 soak" not in boundary:
        issues.append("claims_boundary 必须写明不是长稳 soak")
    return issues


def check(root: str = ".") -> List[str]:
    issues, committed, live = report_module.start(root, REPORT_REL, build, "稳定性报告与实时重算不一致（修复指引：重跑 write）")
    issues += _item_issues(committed)
    issues += _declaration_issues(committed)
    return issues
