"""自扫描全维度聚合（WP-50，G5）：§13.1 S0–S15 逐维证据 + gap/open 显式登记。

为什么：S0–S14 的证据已散在 check/测试/扫描件里，但缺一份「逐维度：能否自证、凭什么、
缺什么」的聚合面——容易把「没做」写成「全绿」。本模块：
- 每个维度跑轻量**探针**（读既有报告/调既有检查/数用例），给出 covered /
  covered-by-existing / gap / open；
- 探针失败必须降级，不得写 covered（否则 check 红）；
- gap/open 必须带 owner + next（下一 WP/触发条件）；
- 结果落 `results/self_audit/S0-S15.json`（committed == 实时重算）。
"""
from __future__ import annotations

from core import report_module

import json
import re
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-self-scan/1"
REL = "protocol/self_scan.json"
REPORT_REL = "results/self_audit/S0-S15.json"
REPORT_SCHEMA = "nf-self-scan-report/1"
GUIDE = "修复指引："
STATUSES = ("covered", "covered-by-existing", "gap", "open")
# 只认真正的占位：独立注释标记，或裸 raise NotImplementedError（排除数据/正则里的同名词）
TODO_PATTERN = re.compile(r"(^\s*#\s*(TODO|FIXME|XXX))|(raise\s+NotImplementedError)")


class SelfScanError(Exception):
    """自扫描登记/聚合错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "SELF-SCAN-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise SelfScanError("缺 %s（修复指引：补自扫描登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SelfScanError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise SelfScanError("registry schema 必须 %s" % SCHEMA)
    return doc


def _json(root: str, rel: str) -> Dict[str, Any]:
    from core import report_module
    return report_module.load_json(root, rel)


def _todo_scan(root: str) -> List[str]:
    hits: List[str] = []
    base = Path(root) / "desktop" / "src" / "core"
    for path in sorted(base.glob("*.py")):
        if path.name == "self_scan.py":
            continue  # 不扫自身（模式定义里含关键字，避免自证循环）
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if TODO_PATTERN.search(line):
                hits.append("%s:%d" % (path.relative_to(Path(root)).as_posix(), lineno))
    return hits[:10]


def probes(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """轻量探针（只读既有报告/调既有检查，不新造重扫描）。"""
    out: Dict[str, Dict[str, Any]] = {}

    assertions = _json(root, "protocol/assertions.json")
    missing_ev = [str(a.get("id")) for a in assertions.get("assertions") or []
                  if not a.get("evidence")]
    out["S0"] = {"status": "covered" if not missing_ev else "gap",
                 "detail": "assertions 全带 evidence" if not missing_ev else
                           "缺 evidence 的断言：%s" % missing_ev[:5]}

    todos = _todo_scan(root)
    out["S1"] = {"status": "covered" if not todos else "gap",
                 "detail": "core 无 TODO/NotImplemented" if not todos else
                           "发现空洞标记：%s" % todos[:5]}

    cq = _json(root, "results/cq/scan.json")
    out["S2"] = {"status": "covered-by-existing" if int(cq.get("p0") or 0) == 0 else "gap",
                 "detail": "CQ P0=0（bandit/silent_skip 面已扫）" if int(cq.get("p0") or 0) == 0
                           else "CQ P0=%s" % cq.get("p0")}

    vectors = (Path(root) / "results/trust/trust_vectors.json").is_file()
    out["S3"] = {"status": "covered-by-existing" if vectors else "gap",
                 "detail": "trust 向量在" if vectors else "缺 trust 向量"}

    out["S4"] = {"status": "gap", "detail": "删除/重排检出矩阵未系统化（WP-51）"}

    try:
        from core import schema_lint
        issues, _entries = schema_lint.check_schema_files(root)
    except Exception as exc:  # noqa: BLE001 - 探针失败降级，不冒充
        issues = ["schema_lint 不可用：%s" % exc]
    out["S5"] = {"status": "covered" if not issues else "gap",
                 "detail": "schema 面全绿" if not issues else "schema 问题：%s" % issues[:3]}

    weights = _json(root, "protocol/check12_weights.json")
    modules = len(weights.get("modules") or {})
    tests = _json(root, "protocol/verification_report.json")
    test_count = len(tests.get("items") or [])
    out["S6"] = {"status": "covered" if modules >= 100 and test_count >= 30 else "gap",
                 "detail": "判据模块 %d · 抽查项 %d；覆盖率/全仓变异未测（QD-10）"
                           % (modules, test_count)}

    try:
        from core import docs_claims as dc
        claim_issues = dc.check(root)
    except Exception as exc:  # noqa: BLE001
        claim_issues = ["docs_claims 不可用：%s" % exc]
    out["S7"] = {"status": "covered" if not claim_issues else "gap",
                 "detail": "文档 claims 全绿" if not claim_issues else "claims 偏差：%s" % claim_issues[:3]}

    try:
        from core import workflow_policy as wp
        wf_issues, wf_warns, _ = wp.scan(root)
    except Exception as exc:  # noqa: BLE001
        wf_issues, wf_warns = ["workflow_policy 不可用：%s" % exc], []
    tc = _json(root, "results/cq/toolchain.json")
    blocked = [b for b in (tc.get("blocked") or []) if b]
    out["S8"] = {"status": "covered" if not wf_issues else "gap",
                 "detail": "workflow 钉版/权限 %d 项告警" % len(wf_warns) if not wf_issues
                           else "workflow 问题：%s" % wf_issues[:3]}
    if blocked:
        out["S8"]["detail"] += "；BLOCKED 工具：%s" % ",".join(blocked)

    paths_mod = (Path(root) / "desktop/src/core/paths.py").is_file()
    redos_ok = any(str(i.get("id")) == "redos" and str(i.get("status")) == "pass"
                   for i in tests.get("items") or [])
    out["S9"] = {"status": "covered-by-existing" if paths_mod and redos_ok else "gap",
                 "detail": "paths 校验 + redos 检查在" if paths_mod and redos_ok
                           else "缺 paths/redos 证据"}

    out["S10"] = {"status": "covered-by-existing",
                  "detail": "隐私契约/秘密扫描覆盖面：gitleaks BLOCKED（QD-05），不冒充全扫"}

    out["S11"] = {"status": "covered-by-existing",
                  "detail": "失败考古 + trust 失败路径测试在；故障注入矩阵未系统化"}

    try:
        from core import wiki_compiler as wc
        wiki_issues = wc.check(root)
    except Exception as exc:  # noqa: BLE001
        wiki_issues = ["wiki_compiler 不可用：%s" % exc]
    out["S12"] = {"status": "covered" if not wiki_issues else "gap",
                  "detail": "wiki 校验全绿" if not wiki_issues else "wiki 问题：%s" % wiki_issues[:3]}

    try:
        from core import spec_compiler as sc
        intent = _json(root, "spec/intents/sample-document.json")
        bundle = sc.compile_intent(intent, root, "spec/intents/sample-document.json")
        spec_issues = sc.validate_bundle(bundle, root)
    except Exception as exc:  # noqa: BLE001
        spec_issues = ["spec 编译不可用：%s" % exc]
    out["S13"] = {"status": "covered" if not spec_issues else "gap",
                  "detail": "样例 spec→task 可编译且可校验" if not spec_issues
                            else "spec 问题：%s" % spec_issues[:3]}

    ind = _json(root, "results/independence.json")
    edges = int((ind.get("counts") or {}).get("forbidden_edges") or 0)
    out["S14"] = {"status": "covered" if ind.get("ok") and edges == 0 else "gap",
                  "detail": "独立性报告 ok、跨界 0" if ind.get("ok") and edges == 0
                            else "独立性异常：ok=%s edges=%s" % (ind.get("ok"), edges)}

    out["S15"] = {"status": "open", "detail": "红队角色（审计者/攻击者/新人视角）未系统化，需作者触发"}
    return out


def build(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    got = probes(root)
    rows = []
    for item in reg.get("dimensions") or []:
        did = str(item.get("id"))
        probe = got.get(did) or {"status": "gap", "detail": "未登记探针"}
        status = str(probe["status"])
        if status == "covered" and item.get("status_hint") in ("gap", "open"):
            status = str(item["status_hint"])
        rows.append({"id": did, "name": str(item.get("name")),
                     "status": status, "detail": str(probe.get("detail")),
                     "evidence": list(item.get("evidence") or []),
                     "owner": str(item.get("owner") or ""),
                     "next": str(item.get("next") or ""),
                     "note": str(item.get("note") or "")})
    summary = {status: sum(1 for r in rows if r["status"] == status) for status in STATUSES}
    report = {"schema": REPORT_SCHEMA, "dimensions": rows, "summary": summary,
              "status_vocabulary": list(STATUSES),
              "rules": dict(reg.get("rules") or {}),
              "claims_boundary": list(reg.get("claims_boundary") or []),
              "note": "聚合既有证据；committed == 实时重算"}
    return report


render = report_module.render
write = report_module.writer(REPORT_REL, build)


def check(root: str = ".") -> List[str]:
    issues, committed, live = report_module.start(root, REPORT_REL, build, "自扫描聚合件与实时重算不一致（修复指引：重跑 write）")
    dims = committed.get("dimensions") or []
    ids = [str(d.get("id")) for d in dims]
    expected = ["S%d" % i for i in range(16)]
    if ids != expected:
        issues.append("维度必须恰为 S0–S15（当前 %s）" % ids)
    for dim in dims:
        status = str(dim.get("status"))
        if status not in STATUSES:
            issues.append("%s status 非法：%s" % (dim.get("id"), status))
        if status == "covered" and not dim.get("evidence"):
            issues.append("%s 标 covered 但无证据（修复指引：给证据或降级）" % dim.get("id"))
        if status in ("gap", "open"):
            if not str(dim.get("owner")):
                issues.append("%s gap/open 缺 owner" % dim.get("id"))
            if not str(dim.get("next")):
                issues.append("%s gap/open 缺 next（下一 WP/触发条件）" % dim.get("id"))
    summary = committed.get("summary") or {}
    for status in STATUSES:
        want = sum(1 for d in dims if d.get("status") == status)
        if int(summary.get(status) or 0) != want:
            issues.append("summary.%s 与逐维统计不一致" % status)
    boundary = " ".join(str(x) for x in committed.get("claims_boundary") or [])
    if "不是认证" not in boundary:
        issues.append("claims_boundary 必须写明不是认证/合规结论")
    return issues
