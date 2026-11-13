#!/usr/bin/env python3
"""COCKPIT_PROTOCOL.md 契约：驾驶舱协议必须「硬规则有界 / 边界 fail-closed / 口径可核」。

为什么必须有：这是驾驶舱唯一的回合协议件（模型按它输出一个 JSON turn），此前只有
「docs/meta-cockpit/README.md 里点名过它」这一条存在性判据——协议正文的硬规则
（3 原子 / 8 轮 / 1 次重规划 / stop 语义 / deadline / 凭据防护 / 离线盲评四值结论）
与 core 常量没有任何对账。本轮补「§现状对照」「§复现与引用口径」并加本判据。

范围：只判本文与 core 常量/CLI 事实自洽（不改运行时）。
同族判据：test_meta_cockpit.py（含 manifest 新鲜度）/ test_meta_cockpit_doc_contract.py。
契约：标题 + 输入/输出/硬规则三段、8 条硬规则逐条在场、3 原子 / 8 轮 / 1 次重规划、
stop 语义、deadline cooperative、凭据防护 fail-closed、盲评四值结论、
「给人看 ≠ 给模型指令」的分隔说明、现状对照 + 复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import context_pack  # noqa: E402

BASE = ROOT / "desktop" / "src" / "core" / "meta_cockpit"
DOC = BASE / "COCKPIT_PROTOCOL.md"
ATOMS = BASE / "meta_atoms.json"
DIFF = BASE / "DIFFERENTIATION.md"
HARD = ("每轮最多 3 个原子", "不输出 score", "stop=true", "原子必须存在于",
        "下一轮重新读", "立刻改道", "最多 8 轮", "deadline")
CONCLUSIONS = ("guided-better", "baseline-better", "inconclusive", "insufficient-evidence")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"驾驶舱协议不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("驾驶舱协议为空")
    return text


def protocol_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 活体认知驾驶舱协议"):
        issues.append("缺标题「# 活体认知驾驶舱协议（单轮）」")
    for section in ("## 输入", "## 输出（严格 JSON）", "## 硬规则", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    for rule in HARD:
        if rule not in text:
            issues.append(f"硬规则缺：{rule}")
    atoms = json.loads(ATOMS.read_text(encoding="utf-8"))["atoms"]
    if len(atoms) != 33:
        issues.append(f"原子数已变（{len(atoms)}）")
    if "**33**" not in text:
        issues.append("现状未写 33 原子")
    if "**3**" not in text:
        issues.append("现状未写单轮 3 原子上限")
    if "**8**" not in text:
        issues.append("现状未写 8 轮上限")
    if "**1 次**" not in text:
        issues.append("现状未写 1 次重规划")
    if "fail-closed" not in text:
        issues.append("缺 fail-closed 边界")
    for word in CONCLUSIONS:
        if word not in text:
            issues.append(f"盲评结论缺：{word}")
    if "不是给模型的回合指令" not in text:
        issues.append("缺「口径索引 ≠ 回合指令」分隔说明")
    if "给人看" not in text:
        issues.append("缺「给人看」定位说明")
    if not DIFF.is_file():
        issues.append("DIFFERENTIATION.md 缺失")
    for cmd in ("python scripts/nf.py cockpit --prompt",
                "python -m pytest desktop/tests/test_meta_cockpit.py",
                "python -m core.meta_cockpit.build_atom_menu"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class CockpitProtocolDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_protocol_matches_contract(self):
        self.assertEqual([], protocol_issues(self.text), "驾驶舱协议不满足契约")

    def test_limits_live(self):
        self.assertEqual(33, len(json.loads(ATOMS.read_text(encoding="utf-8"))["atoms"]))
        self.assertEqual(8000, context_pack.UNIT_LIMIT)
        self.assertTrue(DIFF.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：删硬规则 / 轮数漂移 / 缺结论 / 缺分隔说明 / 缺命令。"""
        no_rule = self.text.replace("最多 8 轮", "轮数不限")
        self.assertTrue(any("硬规则缺" in i for i in protocol_issues(no_rule)))
        bad = self.text.replace("**8**", "**12**")
        self.assertTrue(any("8 轮" in i for i in protocol_issues(bad)))
        no_concl = self.text.replace("insufficient-evidence", "unknown")
        self.assertTrue(any("insufficient-evidence" in i for i in protocol_issues(no_concl)))
        no_sep = self.text.replace("不是给模型的回合指令", "也是给模型的回合指令")
        self.assertTrue(any("分隔说明" in i for i in protocol_issues(no_sep)))
        no_cmd = self.text.replace("python -m core.meta_cockpit.build_atom_menu", "重生菜单")
        self.assertTrue(any("build_atom_menu" in i for i in protocol_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_protocol.md")


if __name__ == "__main__":
    unittest.main()
