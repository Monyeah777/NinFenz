#!/usr/bin/env python3
"""trust 自审计契约：机器件（SELF_AUDIT.json）与 CLAIM_MATRIX/门禁真源互相绑定。

为什么有它：自审计报告最容易变成「自己写结论自己信」——本件把 P0=0、P1 有 owner、
UNSUPPORTED=0、维度覆盖 S0–S12、门禁数字与 quality_baseline 一致这些结论**逐条机检**，
并对人读件做同源核对；变异自证保证判据不是同义反复。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import quality_baseline as qb  # noqa: E402

AUDIT = ROOT / "results" / "trust" / "SELF_AUDIT.json"
AUDIT_MD = ROOT / "docs" / "trust" / "SELF_AUDIT.md"
MATRIX = ROOT / "results" / "trust" / "CLAIM_MATRIX.md"
DIMENSIONS = (
    "S0_requirements", "S1_code_holes", "S2_judgement_holes", "S3_crypto",
    "S4_chain_order", "S5_types_compat", "S6_test_gaps", "S7_doc_overclaim",
    "S8_deps", "S9_path_dos", "S10_privacy", "S11_observability", "S12_unknown",
)
STATUSES = {"red", "amber", "green"}
SEVERITIES = {"P0", "P1", "P2"}
F_STATUSES = {"open", "fixed", "accepted"}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def _matrix_counts():
    text = MATRIX.read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or "| 状态" in line or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit():
            rows.append(cells[5])
    return {
        "todo": sum(1 for s in rows if s.startswith("TODO")),
        "partial": sum(1 for s in rows if s.startswith("PARTIAL")),
        "unsupported": sum(1 for s in rows if "UNSUPPORTED" in s),
    }


def audit_issues(doc, md_text="") -> list:
    issues = []
    if doc.get("schema") != "nf-trust-self-audit/1":
        issues.append("schema 名称不符")
    if not HEX40.match(str(doc.get("head") or "")):
        issues.append("head 不是 40 位 commit sha")
    if not UTC.match(str(doc.get("scanned_at") or "")):
        issues.append("scanned_at 不是 UTC 秒级 ISO-8601")
    dims = doc.get("dimensions") or {}
    if list(dims) != list(DIMENSIONS):
        issues.append("维度不是 S0-S12 全集/顺序")
    findings = {f.get("id"): f for f in doc.get("findings") or []}
    for dim, body in dims.items():
        if dim not in DIMENSIONS:
            issues.append(f"未知维度：{dim}")
            continue
        if body.get("status") not in STATUSES:
            issues.append(f"{dim} 状态越界：{body.get('status')}")
        for fid in body.get("findings") or []:
            if fid not in findings:
                issues.append(f"{dim} 引用了不存在的发现：{fid}")
    for fid, item in findings.items():
        if item.get("severity") not in SEVERITIES:
            issues.append(f"{fid} severity 越界")
        if item.get("status") not in F_STATUSES:
            issues.append(f"{fid} status 越界")
        if not str(item.get("evidence") or "").strip():
            issues.append(f"{fid} 缺 evidence")
        if not str(item.get("fix") or "").strip():
            issues.append(f"{fid} 缺 fix")
        if item.get("severity") == "P0":
            issues.append(f"{fid} 是 P0（P0 必须为 0 才能收口）")
        if (item.get("severity") == "P1" and item.get("status") == "open"
                and not str(item.get("owner") or "").strip()):
            issues.append(f"{fid} 是 open P1 但没有 owner")
        for key in ("file", "test"):
            rel = str(item.get(key) or "")
            if not rel:
                continue
            candidates = (ROOT / rel, ROOT / "desktop" / "tests" / rel)
            if not any(path.is_file() for path in candidates):
                issues.append(f"{fid} 的 {key} 不在场：{rel}")
    stop = doc.get("stop") or {}
    p0 = sum(1 for f in findings.values() if f.get("severity") == "P0")
    p1_open_owned = [f for f in findings.values()
                     if f.get("severity") == "P1" and f.get("status") == "open" and f.get("owner")]
    counts = _matrix_counts()
    if stop.get("p0") != p0:
        issues.append("stop.p0 与 findings 计数不一致")
    if stop.get("p1_open_with_owner") != len(p1_open_owned):
        issues.append("stop.p1_open_with_owner 与 findings 不一致")
    if stop.get("claims_unsupported") != counts["unsupported"]:
        issues.append("stop.claims_unsupported 与 CLAIM_MATRIX 不一致")
    s0_open = [f for f in findings.values()
               if f.get("dim") == "S0_requirements" and f.get("severity") == "P1"
               and f.get("status") == "open"]
    if len(s0_open) != counts["todo"] + counts["partial"]:
        issues.append("S0 的 open P1 数不等于 CLAIM_MATRIX TODO+PARTIAL 行数")
    if counts["unsupported"] != 0:
        issues.append("CLAIM_MATRIX 仍有 UNSUPPORTED")
    gate = doc.get("gate") or {}
    if f"PASS={qb.EXPECTED_PASS}" not in str(gate.get("verify") or ""):
        issues.append("gate.verify 与 quality_baseline.EXPECTED_PASS 不一致")
    if "FAIL=0" not in str(gate.get("verify") or ""):
        issues.append("gate.verify 未写 FAIL=0")
    if not str(gate.get("dotnet") or "").startswith("not-run"):
        issues.append("gate.dotnet 不得写成 ok（本机无 SDK）")
    if "全量未跑" not in str(gate.get("tests") or ""):
        issues.append("gate.tests 未如实写「全量未跑」")
    if md_text:
        for token in ("# Trust Fabric 自审计", *DIMENSIONS, "P0 = 0",
                      "UNSUPPORTED claims = 0", "python scripts/trust_self_audit.py --check"):
            if token not in md_text:
                issues.append(f"人读件缺要素：{token}")
        body = md_text.split("## 不改写的历史结论")[0]
        if "不可抵赖" in body and "不是" not in body:
            issues.append("人读件出现不可抵赖的正面声明")
    return issues


class SelfAuditContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(AUDIT.read_text(encoding="utf-8"))
        cls.md = AUDIT_MD.read_text(encoding="utf-8")

    def test_audit_consistent(self):
        self.assertEqual([], audit_issues(self.doc, self.md), "自审计与人读件不满足契约")

    def test_contract_catches_mutations(self):
        import copy

        def mutate(fn):
            bad = copy.deepcopy(self.doc)
            fn(bad)
            return audit_issues(bad, self.md)

        def drop_dim(doc):
            doc["dimensions"].pop("S6_test_gaps")

        def bad_status(doc):
            doc["dimensions"]["S5_types_compat"]["status"] = "ok"

        def add_p0(doc):
            doc["findings"].append({"id": "F-099", "dim": "S1_code_holes",
                                    "severity": "P0", "file": "", "evidence": "x",
                                    "fix": "y", "test": "", "owner": "", "status": "open"})

        def strip_owner(doc):
            for f in doc["findings"]:
                if f["severity"] == "P1" and f["status"] == "open":
                    f["owner"] = ""
                    break

        def broken_claims(doc):
            doc["stop"]["claims_unsupported"] = 1

        def broken_gate(doc):
            doc["gate"]["verify"] = "PASS=1 FAIL=1"

        def ghost_ref(doc):
            doc["dimensions"]["S0_requirements"]["findings"].append("F-404")

        for fn, needle in ((drop_dim, "维度"), (bad_status, "状态越界"),
                           (add_p0, "P0"), (strip_owner, "owner"),
                           (broken_claims, "claims_unsupported"),
                           (broken_gate, "gate.verify"), (ghost_ref, "不存在")):
            issues = mutate(fn)
            self.assertTrue(any(needle in issue for issue in issues),
                            f"{fn.__name__} 变异未被抓到：{issues[:3]}")
        self.assertTrue(any("人读件缺要素" in i or "维度" in i
                            for i in audit_issues(self.doc, "# 空文")))


if __name__ == "__main__":
    unittest.main()
