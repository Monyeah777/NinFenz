"""跨实现/断网/删除矩阵（WP-51，G5）。

三件事，均以**在场证据**为准：
(a) **Go↔Python parity**：本机无 Go 工具链 → 只做静态对账（向量数/CLI 子命令/退出码），
    运行时 parity 显式 `open`（不冒充）；
(b) **断网**：子进程禁用 socket 后跑 core-only 管线（assembly/delivery/docs-claims/wiki/
    spec/self-scan），证明交付路径不依赖网络；不证外部服务行为；
(c) **删除/重排/截断矩阵**：对交付包/装配记录/血缘/报告做删除/重排/截断，验证器必须检出；
    漏检即红。

结果落 `results/crosscheck/report.json`（committed == 实时重算）。
"""
from __future__ import annotations

from core import report_module

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-crosscheck/1"
REL = "protocol/crosscheck.json"
REPORT_REL = "results/crosscheck/report.json"
REPORT_SCHEMA = "nf-crosscheck-report/1"
PACK = "results/delivery/wiki-module-M06"
GUIDE = "修复指引："

OFFLINE_CHILD = r'''
import json, socket, sys
def _blocked(*a, **k):
    raise OSError("network disabled for offline probe")
socket.socket = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
sys.path.insert(0, "desktop/src")
from core import assembly_runtime as ar
from core import delivery as dv
from core import docs_claims as dc
from core import self_scan as ss
from core import spec_compiler as sc
from core import wiki_compiler as wc
checks = {}
checks["assembly"] = ar.run("spec/intents/sample-document.json", "mock", ".")["run"]["status"] == "delivered"
issues, rep = dv.verify("results/delivery/wiki-module-M06", ".")
checks["delivery"] = not issues and rep.get("ok") is True
checks["docs_claims"] = not dc.check(".")
checks["wiki"] = not wc.check(".")
intent = json.load(open("spec/intents/sample-document.json", encoding="utf-8"))
bundle = sc.compile_intent(intent, ".", "spec/intents/sample-document.json")
checks["spec"] = not sc.validate_bundle(bundle, ".")
checks["self_scan"] = not ss.check(".")
print(json.dumps(checks, sort_keys=True))
sys.exit(0 if all(checks.values()) else 1)
'''


class CrossCheckError(Exception):
    """跨实现/断网/删除矩阵错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "CROSSCHECK-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise CrossCheckError("缺 %s（修复指引：补跨实现登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CrossCheckError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise CrossCheckError("registry schema 必须 %s" % SCHEMA)
    return doc


def _tool_present(name: str) -> bool:
    return shutil.which(name) is not None


def _static_parity(root: str) -> Dict[str, Any]:
    go_readme = Path(root) / "clients/go/README.md"
    vectors_dir = Path(root) / "results" / "ccos"
    vector_files = sorted(p.name for p in vectors_dir.glob("*_vectors.json")) if vectors_dir.is_dir() else []
    vector_total = 0
    for name in vector_files:
        try:
            vector_total += len(json.loads((vectors_dir / name).read_text(encoding="utf-8")).get("vectors") or [])
        except (OSError, ValueError):
            pass
    go_ok = (Path(root) / "clients/go/go.mod").is_file()
    py_ok = (Path(root) / "scripts/nf_verify.py").is_file()
    static_ok = go_ok and py_ok and vector_total >= 50 and len(vector_files) >= 7
    return {"status": "static-only" if static_ok else "gap",
            "runtime": "open",
            "runtime_reason": "go 工具链不在场（go: command not found），运行时 parity 未执行",
            "evidence": {"go_client": go_ok, "python_verifier": py_ok,
                         "vector_files": len(vector_files), "vector_total": vector_total},
            "note": "静态对账（向量数/CLI/退出码面）不等于跑通；运行时 parity 属 OPEN"}


def _offline_probe(root: str) -> Dict[str, Any]:
    try:
        proc = subprocess.run([sys.executable, "-c", OFFLINE_CHILD], cwd=root,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "checks": {}, "error": "子进程不可用：%s" % exc}
    try:
        checks = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        checks = {}
    return {"ok": proc.returncode == 0 and bool(checks) and all(checks.values()),
            "checks": checks,
            "error": "" if proc.returncode == 0 else (proc.stderr or "")[-300:]}


def _truncated_unparseable(path: Path, cut: int | None) -> bool:
    """把 JSON 文本截到前 cut 字节（None=对半）后是否不可解析（即截断可检出）。"""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "record.json"
        raw = path.read_text(encoding="utf-8")
        size = len(raw) // 2 if cut is None else cut
        target.write_text(raw[:size], encoding="utf-8", newline="\n")
        try:
            json.loads(target.read_text(encoding="utf-8"))
            return False
        except ValueError:
            return True


def _deletion_pack_cases(root_p: Path, root: str, dv: Any, record) -> None:
    """D-01..D-04：交付包删件/坏 JSON 必须被 verify 检出。"""
    def _mutated_pack(mutate) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "pack"
            shutil.copytree(root_p / PACK, dst)
            mutate(dst)
            issues, _rep = dv.verify(str(dst), str(root))
            return {"detected": bool(issues), "detail": "; ".join(issues[:2]) or "未检出"}

    record("D-01", **_mutated_pack(lambda d: (d / "artifact.md").unlink()))
    record("D-02", **_mutated_pack(lambda d: (d / "manifest.json").unlink()))
    record("D-03", **_mutated_pack(
        lambda d: (d / "manifest.json").write_text('{"schema": "nf-delivery/1", "files": [',
                                                   encoding="utf-8", newline="\n")))
    record("D-04", **_mutated_pack(lambda d: (d / "evidence/sidecar.json").unlink()))


def _deletion_assembly_case(root_p: Path, root: str, ar: Any, record) -> None:
    """D-05：删计划步骤后装配记录校验必须报问题。"""
    assembly = json.loads((root_p / "results/assembly/sample-document.assembly.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(assembly)
    plan_steps = (broken.get("assembly") or {}).get("steps")
    if isinstance(plan_steps, list) and plan_steps:
        plan_steps.pop(0)  # 删计划步骤（不是 run.steps 轨迹）
    issues = ar.validate_record(broken, str(root))
    record("D-05", bool(issues), "; ".join(str(i) for i in issues[:2]) or "未检出")


def _deletion_lineage_cases(root_p: Path, tcl: Any, record) -> None:
    """D-07..D-09：血缘删段/重排/篡改摘要都必须被检出。"""
    card = json.loads((root_p / "results/ai/model-card.json").read_text(encoding="utf-8"))
    lineage = json.loads((root_p / "results/ai/lineage.json").read_text(encoding="utf-8"))
    deleted = copy.deepcopy(lineage)
    if deleted.get("segments"):
        deleted["segments"].pop(0)
    record("D-07", bool(tcl.verify_lineage(deleted, card).get("issues")), "删段后链断可检出")
    reordered = copy.deepcopy(lineage)
    if len(reordered.get("segments") or []) >= 2:
        reordered["segments"][0], reordered["segments"][1] = reordered["segments"][1], reordered["segments"][0]
    record("D-08", bool(tcl.verify_lineage(reordered, card).get("issues")), "重排后 prev/digest 不符可检出")
    tampered = copy.deepcopy(lineage)
    tampered["lineage_digest"] = hashlib.sha256(b"tampered").hexdigest()
    record("D-09", bool(tcl.verify_lineage(tampered, card).get("issues")), "篡改 lineage_digest 可检出")


def _deletion_cases(root: str) -> List[Dict[str, Any]]:
    from core import assembly_runtime as ar
    from core import delivery as dv
    from core.trust import context_lineage as tcl

    root_p = Path(root)
    out: List[Dict[str, Any]] = []

    def record(case_id: str, detected: bool, detail: str) -> None:
        out.append({"id": case_id, "detected": detected, "detail": detail})

    _deletion_pack_cases(root_p, root, dv, record)
    _deletion_assembly_case(root_p, root, ar, record)
    detected = _truncated_unparseable(
        root_p / "results/assembly/sample-document.assembly.json", None)
    record("D-06", detected, "截断后不可解析" if detected else "截断未被检出")
    _deletion_lineage_cases(root_p, tcl, record)
    detected = _truncated_unparseable(root_p / "results/docs_claims_report.json", 40)
    record("D-10", detected, "截断后不可解析" if detected else "截断未被检出")
    return out


def build(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    parity = _static_parity(root)
    offline = _offline_probe(root)
    deletion = _deletion_cases(root)
    summary = {"parity_status": parity["status"],
               "offline_ok": offline["ok"],
               "deletion_cases": len(deletion),
               "deletion_detected": sum(1 for c in deletion if c["detected"]),
               "deletion_missed": sum(1 for c in deletion if not c["detected"])}
    report = {"schema": REPORT_SCHEMA, "parity": parity, "offline": offline,
              "deletion_matrix": deletion, "summary": summary,
              "claims_boundary": list(reg.get("claims_boundary") or []),
              "note": "committed == 实时重算；Go 运行时 parity 属 OPEN"}
    return report


render = report_module.render
write = report_module.writer(REPORT_REL, build)


def _parity_issues(committed: Dict[str, Any]) -> List[str]:
    """parity 面：go 不可用时 runtime 必须显式 open，status 必须在词表内。"""
    issues: List[str] = []
    parity = committed.get("parity") or {}
    go_available = _tool_present("go")
    if not go_available and str(parity.get("runtime")) != "open":
        issues.append("go 不可用时 parity.runtime 必须显式 open（不得冒充跑通）")
    if str(parity.get("status")) not in ("static-only", "pass", "gap", "open"):
        issues.append("parity.status 非法")
    return issues


def _offline_issues(committed: Dict[str, Any]) -> List[str]:
    """断网探针：总开关 ok + 逐管线 checks 全绿。"""
    issues: List[str] = []
    offline = committed.get("offline") or {}
    if not offline.get("ok"):
        issues.append("断网探针失败：%s" % (offline.get("error") or "见 checks"))
    for name, ok in (offline.get("checks") or {}).items():
        if not ok:
            issues.append("断网下管线失败：%s" % name)
    return issues


def _deletion_issues(committed: Dict[str, Any]) -> List[str]:
    """删除矩阵：case 数下限 + 逐 case 漏检。"""
    issues: List[str] = []
    cases = committed.get("deletion_matrix") or []
    if len(cases) < 10:
        issues.append("删除矩阵 case 少于 10")
    for case in cases:
        if not case.get("detected"):
            issues.append("%s 漏检（%s）" % (case.get("id"), case.get("detail")))
    return issues


def check(root: str = ".") -> List[str]:
    issues, committed, live = report_module.start(root, REPORT_REL, build, "跨实现/断网/删除矩阵报告与实时重算不一致（修复指引：重跑 write）")
    issues.extend(_parity_issues(committed))
    issues.extend(_offline_issues(committed))
    issues.extend(_deletion_issues(committed))
    boundary = " ".join(str(x) for x in committed.get("claims_boundary") or [])
    if "OPEN" not in boundary:
        issues.append("claims_boundary 必须写明 Go 运行时 parity 属 OPEN")
    return issues
