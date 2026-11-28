"""§19.1 交付物补件：Wiki/Spec 报告 + 分层 QA 映射（G5 收口用）。

方案 §19.1 要求 `results/wiki-report.json`、`results/spec-report.json`、`results/qa/` 与
`docs/qa/`。本模块**聚合既有件**生成确定性报告（不引新扫描器）：
- wiki-report：wiki 投影（pages/INDEX/GRAPH/llms/mcp）的摘要与 digest + 校验 issues；
- spec-report：样例 intent→spec→task 的 bundle digest/任务数 + 校验 issues；
- qa/layers：§13A.2 L0–L20 逐层映射到既有证据，status 用 covered/partial/gap/open，
  partial/gap/open 必须带 owner+next（不得把没有 QA 报告写成 covered）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-layer-reports/1"
WIKI_REPORT_REL = "results/wiki-report.json"
SPEC_REPORT_REL = "results/spec-report.json"
QA_REL = "results/qa/layers.json"
INTENT = "spec/intents/sample-document.json"
GUIDE = "修复指引："
STATUSES = ("covered", "partial", "gap", "open")

LAYERS = [
    ("L0", "真源/契约"), ("L1", "LLMWiki"), ("L2", "Spec Compiler"),
    ("L3", "Context Packer"), ("L4", "Agent Adapter"), ("L5", "Assembly Runtime"),
    ("L6", "Output/Validation"), ("L7", "Delivery"), ("L8", "Governance"),
    ("L9", "AI 信任"), ("L10", "安全/隐私"), ("L11", "运维/恢复"),
    ("L12", "文档/上手"), ("L13", "生态/标准"), ("L14", "隐私/法务"),
    ("L15", "可靠性/事件/BCP"), ("L16", "可访问性/i18n/人因"), ("L17", "产品价值"),
    ("L18", "开源治理/社区"), ("L19", "商业/支持/供应商"), ("L20", "伦理/保证/项目"),
]


class LayerReportError(Exception):
    """报告聚合错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "LAYER-REPORT-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(root: str, rel: str) -> Dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_wiki_report(root: str = ".") -> Dict[str, Any]:
    from core import wiki_compiler as wc
    pages_doc, rest = wc.build(root)
    issues = wc.check(root)
    files = {}
    for rel in ("wiki/pages.json", "wiki/INDEX.json", "wiki/GRAPH.json",
                "wiki/llms.txt", "wiki/mcp.json"):
        path = Path(root) / rel
        if path.is_file():
            files[rel] = {"digest": _sha_file(path), "size": path.stat().st_size}
    return {"schema": "nf-wiki-report/1",
            "pages": len(pages_doc.get("pages") or {}),
            "expected": rest.get("expected"),
            "files": files, "issues": issues,
            "ok": not issues, "note": "由 wiki 投影现算（committed==实时重算）"}


def build_spec_report(root: str = ".") -> Dict[str, Any]:
    from core import spec_compiler as sc
    intent = _json(root, INTENT)
    if not intent:
        raise LayerReportError("缺 %s（修复指引：补样例 intent）" % INTENT)
    bundle = sc.compile_intent(intent, root, INTENT)
    issues = sc.validate_bundle(bundle, root)
    return {"schema": "nf-spec-report/1",
            "intent": INTENT,
            "bundle_digest": sc.render(bundle) and hashlib.sha256(
                sc.render(bundle).encode("utf-8")).hexdigest(),
            "specs": len(bundle.get("specs") or []),
            "tasks": len(bundle.get("tasks") or []),
            "issues": issues, "ok": not issues,
            "note": "由样例 intent 现算（committed==实时重算）"}


def _layer_row(lid: str, name: str, spec: tuple, have) -> Dict[str, Any]:
    """单层 QA 行：covered 但证据缺件时如实降为 partial（并给缺件清单）。"""
    evidence, status, owner, next_step = spec
    present = [rel for rel in evidence if have(rel)]
    if status == "covered" and len(present) != len(evidence):
        status, owner, next_step = "partial", "maintainers", "补缺证据：%s" % (
            [rel for rel in evidence if rel not in present])
    return {"layer": lid, "name": name, "status": status,
            "evidence": evidence, "present": present,
            "owner": owner, "next": next_step}


def _layer_summary(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """按状态词表统计行数（缺的状态记 0）。"""
    return {status: sum(1 for row in rows if row["status"] == status) for status in STATUSES}


def build_qa_layers(root: str = ".") -> Dict[str, Any]:
    r = Path(root)
    have = lambda rel: (r / rel).is_file()
    rows: List[Dict[str, Any]] = []
    mapping = {
        "L0": (["protocol/assertions.json", "protocol/production/contract.schema.json"],
               "covered", "", ""),
        "L1": (["results/wiki-report.json"], "covered", "", ""),
        "L2": (["results/spec-report.json"], "covered", "", ""),
        "L3": (["desktop/tests/test_context_packer_contract.py"], "partial",
               "maintainers", "补 context-report.json"),
        "L4": (["results/adapter/adapter-report.json"], "covered", "", ""),
        "L5": (["results/assembly/sample-document.assembly.json"], "covered", "", ""),
        "L6": (["results/output/output-report.json"], "covered", "", ""),
        "L7": (["results/delivery/delivery-report.json"], "covered", "", ""),
        "L8": (["results/governance/report.json", "results/governance/audit.json"],
               "covered", "", ""),
        "L9": (["results/ai/model-card.json", "results/ai/aibom.cdx.json"],
               "covered", "", ""),
        "L10": (["docs/security/THREAT_MODEL.md", "results/cq/scan.json"], "partial",
                "security", "威胁模型有；红队矩阵未做（S15 open）"),
        "L11": (["results/reverse/FAILURE_ARCHAEOLOGY.md", "results/stability/report.json"],
                "partial", "operations", "故障注入矩阵未系统化；长稳 soak 未做"),
        "L12": (["results/docs_claims_report.json"], "covered", "", ""),
        "L13": (["results/interop", "results/ai/aibom.cdx.json"], "covered", "", ""),
        "L14": (["docs/privacy", "docs/legal", "LEGAL.md"], "covered", "", ""),
        "L15": (["docs/sre"], "partial", "operations", "IR/BCP 演练记录未系统化"),
        "L16": (["docs/a11y", "docs/i18n"], "covered", "", ""),
        "L17": (["docs/product"], "partial", "product", "用户访谈/试点属外部 OPEN"),
        "L18": (["GOVERNANCE.md", "CONTRIBUTING.md", "SECURITY.md"], "covered", "", ""),
        "L19": (["docs/product/GTM.md", "docs/legal/VENDOR_REGISTER.md"], "partial",
                "product", "定价/SLA/供应商退出未外部验证"),
        "L20": (["docs/assurance/ASSURANCE_CASE.md", "protocol/raid.json"], "covered", "", ""),
    }
    for lid, name in LAYERS:
        rows.append(_layer_row(lid, name, mapping[lid], have))
    summary = _layer_summary(rows)
    return {"schema": "nf-qa-layers/1", "layers": rows, "summary": summary,
            "status_vocabulary": list(STATUSES),
            "note": "§13A.2 L0–L20 映射既有 QA 产物；未做的层如实 partial（不写成 covered）",
            "claims_boundary": ["分层 QA 映射是内部证据索引，不是认证",
                                "partial 层保持 partial，不因收口消失"]}


def _write(path: Path, doc: Dict[str, Any]) -> None:
    from core import atomic_write
    atomic_write.write_text(path, json.dumps(doc, ensure_ascii=False, indent=2,
                                             sort_keys=True) + "\n")


def write(root: str = ".") -> Dict[str, Any]:
    wiki = build_wiki_report(root)
    spec = build_spec_report(root)
    _write(Path(root) / WIKI_REPORT_REL, wiki)
    _write(Path(root) / SPEC_REPORT_REL, spec)
    # QA 映射依赖前两件是否在场，必须后算（否则 L1/L2 会因先算而误判 partial）
    qa = build_qa_layers(root)
    _write(Path(root) / QA_REL, qa)
    return {"wiki": wiki, "spec": spec, "qa": qa}


def _check_one_report(root: str, rel: str, doc: Dict[str, Any]) -> List[str]:
    """在盘报告与实时重算逐字对比 → 0/1 条 issue。"""
    path = Path(root) / rel
    if not path.is_file():
        return ["缺 %s（修复指引：跑 write()）" % rel]
    try:
        committed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["%s 不可解析：%s" % (rel, exc)]
    if json.dumps(committed, ensure_ascii=False, sort_keys=True) != \
            json.dumps(doc, ensure_ascii=False, sort_keys=True):
        return ["%s 与实时重算不一致（修复指引：重跑 write）" % rel]
    return []


def _qa_layer_issues(qa: Dict[str, Any]) -> List[str]:
    """QA 层：必须恰为 L0–L20、status 合法、partial/gap/open 带 owner+next。"""
    issues: List[str] = []
    rows = qa.get("layers") or []
    ids = [row["layer"] for row in rows]
    if ids != [lid for lid, _ in LAYERS]:
        issues.append("QA 层必须恰为 L0–L20（当前 %s）" % ids)
    for row in rows:
        if row["status"] not in STATUSES:
            issues.append("%s status 非法" % row["layer"])
        if row["status"] in ("partial", "gap", "open"):
            if not row.get("owner") or not row.get("next"):
                issues.append("%s partial/gap/open 缺 owner/next" % row["layer"])
    return issues


def _boundary_issues(qa: Dict[str, Any]) -> List[str]:
    """claims_boundary 必须写明「不是认证」。"""
    boundary = " ".join(str(x) for x in qa.get("claims_boundary") or [])
    if "不是认证" not in boundary:
        return ["claims_boundary 必须写明不是认证"]
    return []


def check(root: str = ".") -> List[str]:
    issues: List[str] = []
    live_wiki = build_wiki_report(root)
    live_spec = build_spec_report(root)
    live_qa = build_qa_layers(root)
    for rel, doc in ((WIKI_REPORT_REL, live_wiki), (SPEC_REPORT_REL, live_spec),
                     (QA_REL, live_qa)):
        issues.extend(_check_one_report(root, rel, doc))
    issues.extend(_qa_layer_issues(live_qa))
    if not live_wiki.get("ok") or not live_spec.get("ok"):
        issues.append("wiki/spec 报告含 issues（修复指引：先修 wiki/spec 校验）")
    issues.extend(_boundary_issues(live_qa))
    return issues
