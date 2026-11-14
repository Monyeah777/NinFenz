"""文档 claims 一致性（WP-50，G5）：声明数字/措辞必须与门禁实测一致。

为什么：仓库文档里 PASS=/check 标签/「认证」措辞容易被手改成过期或夸大——门禁绿但文案绿
是两回事。本模块：
- 只核登记文档（`protocol/docs_claims.json`）里的**当前声明**：PASS=/check 标签/baseline_*；
  期望值**只来自 `quality_baseline` 常量**（文档不得自证）；
- VERSION-MATRIX 历史行 PASS=NN 不算当前（该文件只核 check_label 与 baseline_* keys）；
- 禁用「认证/合规」措辞（同行为否定语境才放行）；
- 结果落 `results/docs_claims_report.json`（committed == 实时重算）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from core import quality_baseline as qb

SCHEMA = "nf-docs-claims/1"
REL = "protocol/docs_claims.json"
REPORT_REL = "results/docs_claims_report.json"
REPORT_SCHEMA = "nf-docs-claims-report/1"
GUIDE = "修复指引："


class ClaimsError(Exception):
    """声明登记错误（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "CLAIMS-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ClaimsError("缺 %s（修复指引：补文档声明登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ClaimsError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise ClaimsError("registry schema 必须 %s" % SCHEMA)
    return doc


def _expected() -> Dict[str, Any]:
    return {"pass_count": int(qb.EXPECTED_PASS), "check_label": str(qb.CHECK_LABEL),
            "baseline_checks": int(qb.EXPECTED_CHECKS),
            "baseline_pass": int(qb.EXPECTED_PASS)}


def build(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    expected = _expected()
    patterns = reg.get("patterns") or {}
    claims: List[Dict[str, Any]] = []
    violations: List[Dict[str, Any]] = []
    for item in reg.get("documents") or []:
        rel = str(item.get("rel"))
        path = Path(root) / rel
        if not path.is_file():
            violations.append({"doc": rel, "kind": "missing-doc",
                               "detail": "登记文档不在场（修复指引：补文件或去掉登记）"})
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, 1):
            if "pass_count" in (item.get("kinds") or []):
                for m in re.finditer(patterns["pass_count"], line):
                    value = int(m.group(1))
                    ok = value == expected["pass_count"]
                    claims.append({"doc": rel, "line": lineno, "kind": "pass_count",
                                   "value": value, "expected": expected["pass_count"], "ok": ok})
                    if not ok:
                        violations.append({"doc": rel, "line": lineno, "kind": "pass_count",
                                            "detail": "PASS=%d 与实测 PASS=%d 不一致（修复指引：同步文档数字）"
                                                      % (value, expected["pass_count"])})
            if "check_label" in (item.get("kinds") or []):
                for m in re.finditer(patterns["check_label"], line):
                    value = str(m.group(0))
                    ok = value == expected["check_label"]
                    claims.append({"doc": rel, "line": lineno, "kind": "check_label",
                                   "value": value, "expected": expected["check_label"], "ok": ok})
                    if not ok:
                        violations.append({"doc": rel, "line": lineno, "kind": "check_label",
                                            "detail": "check 标签 %s 与实测 %s 不一致（修复指引：同步文档标签）"
                                                      % (value, expected["check_label"])})
            if "baseline_keys" in (item.get("kinds") or []):
                for m in re.finditer(patterns["baseline_keys"], line):
                    key, raw = m.group(1), int(m.group(2))
                    ok = raw == expected[key]
                    claims.append({"doc": rel, "line": lineno, "kind": "baseline_keys",
                                   "value": raw, "expected": expected[key], "ok": ok,
                                   "key": key})
                    if not ok:
                        violations.append({"doc": rel, "line": lineno, "kind": "baseline_keys",
                                            "detail": "%s=%d 与实测 %d 不一致（修复指引：同步矩阵数字）"
                                                      % (key, raw, expected[key])})
            for phrase in reg.get("forbidden_claims") or []:
                if re.search(phrase, line):
                    negative = [w for w in reg.get("negative_context") or [] if w in line]
                    if not negative:
                        violations.append({"doc": rel, "line": lineno, "kind": "forbidden-claim",
                                            "detail": "禁用措辞「%s」出现在非否定语境"
                                                      "（修复指引：删掉认证/合规表述或改为否定语境）" % phrase})
    report = {"schema": REPORT_SCHEMA, "expected": expected,
              "claims": claims, "violations": violations,
              "counts": {"documents": len(reg.get("documents") or []),
                         "claims": len(claims),
                         "ok": sum(1 for c in claims if c["ok"]),
                         "violations": len(violations)},
              "note": "期望值只来自 quality_baseline；committed == 实时重算"}
    return report


def render(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root: str = ".") -> Path:
    from core import atomic_write
    path = Path(root) / REPORT_REL
    atomic_write.write_text(path, render(build(root)))
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
        issues.append("文档声明报告与实时重算不一致（修复指引：重跑 write）")
    if live.get("violations"):
        for item in live["violations"][:5]:
            issues.append("%s 第%s行：%s" % (item.get("doc"), item.get("line"), item.get("detail")))
    if int((live.get("counts") or {}).get("claims") or 0) < 10:
        issues.append("当前声明条数过少（<10），登记文档可能失效")
    boundary = " ".join(str(x) for x in load_registry(root).get("claims_boundary") or [])
    if "不替代" not in boundary:
        issues.append("claims_boundary 必须写明不替代外部合规审查")
    return issues
