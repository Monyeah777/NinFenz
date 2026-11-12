#!/usr/bin/env python3
"""docs/45_质量纵深收口总档契约：总档必须「结构/挂账口径不变 + 五维数字现状 + 版本口径 + 复现」。

为什么必须有：这是 45 波次（W1-W20 + A1-A5）的合成收口总档——它写「check1-31/PASS=49 /
declared 30/30 / MCP 25 单测 / drill 7 主线 / 资产键 55 档」，且标题的 v2.10.0 易被当成产品
版本号（现行产品版本 1.0.5，六面统一；VERSION-MATRIX 未列该波次号）。不标现状，读者会拿旧水位
当质量结论、把波次号当产品版本。本轮补状态横幅、版本口径、现状对照、复现命令，并把各面数字
与「挂账三项仍成立」立成机检断言。

范围：只判本文与门禁/注册/测试/资产事实自洽（不改收口结构）。同族判据：
test_mcp_runtime.py（68 例）/ test_round_drill.py / test_payload_proposal_contract.py
（A1 载荷）/ test_doc_hygiene.py / test_doc_examples.py。
契约：定位 + 版本口径、收口表 10 行、五维段、挂账三项（含仍待标注）、现状对照、复现口径、
现行数字（PASS=75 / check1-42 / 443·438 / 68 例 / 8 集 / 台账 103）与实读一致。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

DOC = ROOT / "docs" / "45_质量纵深收口总档.md"
NF = ROOT / "scripts" / "nf.py"
REG = ROOT / "protocol" / "event_registry.json"
PROV = ROOT / "05_资产库" / "provenance.json"
MCP_TEST = ROOT / "desktop" / "tests" / "test_mcp_runtime.py"
FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "execution"
PYPROJECT = ROOT / "pyproject.toml"
SECTIONS = ("## 收口内容", "## 五维水位", "## 挂账", "## 现状对照", "## 复现与引用口径")
ROWS = ("W1", "W2-W4", "W5", "A1", "A2", "A3", "A4", "A5", "工程闸")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"收口总档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("收口总档为空")
    return text


def current_facts() -> dict:
    reg = json.loads(REG.read_text(encoding="utf-8")).get("events") or {}
    declared = sum(1 for e in reg.values() if e.get("payload_status") == "declared")
    prov = json.loads(PROV.read_text(encoding="utf-8")).get("assets") or []
    n_mcp = MCP_TEST.read_text(encoding="utf-8").count("def test")
    n_sets = len(list(FIXTURES.glob("*_drill_cases.json")))
    version = ""
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        if line.startswith("version ="):
            version = line.split("=", 1)[1].strip().strip('"')
            break
    return {"events": len(reg), "declared": declared, "ledger": len(prov),
            "mcp_tests": n_mcp, "sets": n_sets, "version": version}


def master_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 45 · 质量纵深收口总档"):
        issues.append("缺标题「# 45 · 质量纵深收口总档」")
    if "历史收口总档" not in text:
        issues.append("缺「历史收口总档」状态声明")
    if "波次号" not in text:
        issues.append("缺「v2.10.0 是波次号」版本口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for row in ROWS:
        if row not in text:
            issues.append(f"收口表缺段：{row}")
    for marker in ("untyped", "E3", "端壳"):
        if marker not in text:
            issues.append(f"挂账缺项：{marker}")
    if "仍待" not in text:
        issues.append("缺「仍待」如实标注")
    facts = current_facts()
    for marker in ("check1-42", "PASS=75", "443", "438", "68 例", "8 集", "台账 103"):
        if marker not in text:
            issues.append(f"现状对照缺要素：{marker}")
    if str(facts["declared"]) not in text:
        issues.append(f"declared 数与实读不符（{facts['declared']}）")
    if str(facts["mcp_tests"]) not in text:
        issues.append(f"MCP 单测数与实读不符（{facts['mcp_tests']}）")
    if str(facts["sets"]) not in text:
        issues.append(f"演练集数与实读不符（{facts['sets']}）")
    if facts["version"] and facts["version"] not in text:
        issues.append(f"产品版本与 pyproject 不符（{facts['version']}）")
    if "v2.10.0 是 45 波次的内部波次号" not in text and "波次号" not in text:
        issues.append("缺波次号 ≠ 产品版本口径")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("stats", "asset"):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append(f"CLI 缺子命令：nf {sub}")
    for cmd in ("python scripts/nf.py stats --check", "python scripts/nf.py asset verify",
                "bash verify.sh --checks-only"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class MasterClosureContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_master_matches_contract(self):
        self.assertEqual([], master_issues(self.text), "收口总档不满足契约")

    def test_facts_live(self):
        facts = current_facts()
        self.assertEqual(443, facts["events"])
        self.assertEqual(438, facts["declared"])
        self.assertEqual(68, facts["mcp_tests"])
        self.assertEqual(8, facts["sets"])
        self.assertEqual(3, facts["ledger"])

    def test_contract_catches_mutations(self):
        """变异自证：去状态 / 缺收口段 / 水位回退 / 缺挂账仍待 / 版本口径缺失 / 缺复现命令。"""
        no_status = self.text.replace("历史收口总档", "总档")
        self.assertTrue(any("历史收口总档" in i for i in master_issues(no_status)))
        no_row = self.text.replace("工程闸", "工程门")
        self.assertTrue(any("工程闸" in i for i in master_issues(no_row)))
        old_water = self.text.replace("PASS=75", "PASS=49").replace("check1-42", "check1-31")
        self.assertTrue(any("PASS=75" in i or "check1-42" in i
                            for i in master_issues(old_water)))
        no_pending = self.text.replace("仍待", "已完成")
        self.assertTrue(any("仍待" in i for i in master_issues(no_pending)))
        no_version = self.text.replace("波次号", "版本")
        self.assertTrue(any("波次号" in i for i in master_issues(no_version)))
        no_cmd = self.text.replace("bash verify.sh --checks-only", "跑门禁")
        self.assertTrue(any("verify.sh" in i for i in master_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_master.md")


if __name__ == "__main__":
    unittest.main()
