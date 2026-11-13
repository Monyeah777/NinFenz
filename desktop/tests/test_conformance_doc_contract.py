#!/usr/bin/env python3
"""docs/conformance.md 契约：一致性报告文档必须「契约条数/现场 root/门禁规模与报告实读一致」。

为什么必须有：这份文档是「可归档的第二维护者视角」的入口——它写的契约条数与门禁规模直接决定读者
对「封缄产物覆盖多少」的判断。本轮修两处真实陈旧：契约表写 10 条（实为 27）、边界写 verify.sh 35 道
（实为 check1-42）。旧值会让读者低估一致性面、也误判门禁规模。本判据把 27 契约 id、verdict/root、
冻结链、门禁规模、现状对照与复现口径全部活绑定。

范围：只判本文与 conformance_report / release_gate / verify.sh 事实自洽（不改契约）。同族判据：
test_conformance_run.py / test_conformance_scan.py / test_audit.py（冻链条）/
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位、27 契约 id 全在且与报告相等、verdict/root 与报告一致、check1-42 门禁规模、
冻结链三环、现状对照 + 复现两命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import release_gate  # noqa: E402

DOC = ROOT / "docs" / "conformance.md"
REPORT = ROOT / "protocol" / "conformance_report.json"
VERIFY = ROOT / "verify.sh"
SECTIONS = ("## 是什么", "## 契约表", "## 怎么用", "## 现状对照", "## 复现与引用口径",
            "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"一致性报告文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("一致性报告文档为空")
    return text


def report() -> dict:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def conformance_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 一致性报告工件"):
        issues.append("缺标题「# 一致性报告工件（conformance）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    rep = report()
    ids = [c.get("id") for c in rep.get("contracts") or []]
    if len(ids) != 27:
        issues.append(f"契约条数已变（{len(ids)}）")
    if "27 条" not in text:
        issues.append("未写 27 条契约")
    for cid in ids:
        if cid not in text:
            issues.append(f"正文缺契约：{cid}")
    if rep.get("verdict") != "conformant":
        issues.append(f"报告 verdict 已变：{rep.get('verdict')}")
    if "27/27 conformant" not in text:
        issues.append("未写 27/27 conformant")
    root = str(rep.get("root") or "")
    if root and root[:16] not in text:
        issues.append(f"正文缺现场 root 前缀：{root[:16]}")
    verify = VERIFY.read_text(encoding="utf-8")
    if "check42" not in verify:
        issues.append("verify.sh 未到 check42")
    if "check1-42" not in text:
        issues.append("未写现行门禁规模 check1-42")
    stale_gate = [ln for ln in text.splitlines()
                  if "35 道" in ln and "当时" not in ln]
    if stale_gate:
        issues.append("仍写旧门禁规模「35 道」")
    new_chain = list(release_gate.DEFAULT_FREEZE_CHAIN)
    if len(new_chain) != 3:
        issues.append(f"冻链条环数已变（{len(new_chain)}）")
    for step in new_chain:
        bare = step.replace("python scripts/nf.py ", "")
        if step not in text and bare not in text:
            issues.append(f"冻结链缺环：{step}")
    if "DEFAULT_FREEZE_CHAIN" not in text:
        issues.append("未点名冻结链真源")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py conformance",
                "python -m pytest desktop/tests/test_conformance_run.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不得宣称" not in text:
        issues.append("缺「verdict != conformant 不得宣称可提交」纪律")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ConformanceDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_conformance_doc_matches_contract(self):
        self.assertEqual([], conformance_issues(self.text), "一致性报告文档不满足契约")

    def test_report_live(self):
        rep = report()
        self.assertEqual(27, len(rep["contracts"]))
        self.assertEqual("conformant", rep["verdict"])
        self.assertEqual(3, len(release_gate.DEFAULT_FREEZE_CHAIN))

    def test_contract_catches_mutations(self):
        """变异自证：契约数回退 / root 缺失 / 门禁规模回退 / 缺冻结链 / 缺命令。"""
        old_n = self.text.replace("27 条", "10 条")
        self.assertTrue(any("27 条" in i for i in conformance_issues(old_n)))
        no_root = self.text.replace("c94a8576675b749e", "deadbeef")
        self.assertTrue(any("root" in i for i in conformance_issues(no_root)))
        old_v = self.text.replace("check1-42", "check1-35")
        self.assertTrue(any("check1-42" in i for i in conformance_issues(old_v)))
        no_chain = self.text.replace("DEFAULT_FREEZE_CHAIN", "某链")
        self.assertTrue(any("冻结链真源" in i
                            for i in conformance_issues(no_chain)))
        no_cmd = self.text.replace("python scripts/nf.py conformance", "跑一致性")
        self.assertTrue(any("conformance" in i for i in conformance_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_conformance.md")


if __name__ == "__main__":
    unittest.main()
