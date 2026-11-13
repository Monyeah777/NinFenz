#!/usr/bin/env python3
"""驾驶舱说明契约：33 原子/10 节点/5 节点/六类义务必须与资产一致。

为什么必须有：这是驾驶舱唯一的公开说明——原子数、内容管线与元管线的节点数、
六类义务、A/B 子命令、「不产 score/grade」边界，任何一项漂移都会让外部读者误判
这套系统到底跑什么、不跑什么。本轮补可核现状（33 原子两处一致 / 内容管线 10 节点 /
元管线 5 节点 / 六类义务 / 13 例 / CLI 补全旗标）与「§现状对照」「§复现与引用口径」。

范围：只判本文与 meta_cockpit 资产/CLI/判据事实自洽（不改实现）。
同族判据：test_meta_cockpit.py（13 例）/ test_doc_hygiene.py / test_doc_reachability.py。
契约：最后更新位 + 复核、33 原子、10 节点、5 节点、六类义务、A/B 七子命令、13 例、
协议两件在盘、现状对照 + 复现三命令、「不产 score/grade」边界。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "meta-cockpit" / "README.md"
BASE = ROOT / "desktop" / "src" / "core" / "meta_cockpit"
ATOMS = BASE / "meta_atoms.json"
CONTRACTS = BASE / "atom_contracts.json"
PIPELINE = BASE / "cognition_pipeline.json"
META = BASE / "cognition_meta_pipeline.json"
PROTOCOL = BASE / "COCKPIT_PROTOCOL.md"
DIFF = BASE / "DIFFERENTIATION.md"
SECTIONS = ("## 运行面", "## 现状对照", "## 复现与引用口径", "## 运行时结构", "## 边界")
OBLIGATIONS = ("结构", "关系", "风险", "综合", "证据", "开放问题")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"驾驶舱说明不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("驾驶舱说明为空")
    return text


def counts() -> dict:
    a = json.loads(ATOMS.read_text(encoding="utf-8"))["atoms"]
    c = json.loads(CONTRACTS.read_text(encoding="utf-8"))["contracts"]
    p = json.loads(PIPELINE.read_text(encoding="utf-8"))["nodes"]
    m = json.loads(META.read_text(encoding="utf-8"))["nodes"]
    return {"atoms": len(a), "contracts": len(c), "content": len(p), "meta": len(m)}


def cockpit_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 元认知生产驾驶舱"):
        issues.append("缺标题「# 元认知生产驾驶舱」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    c = counts()
    if c["atoms"] != 33 or c["contracts"] != 33:
        issues.append(f"原子数不一致（{c['atoms']} vs {c['contracts']}）")
    if "**33**" not in text and "33 个原子" not in text:
        issues.append("未写 33 原子")
    if c["content"] != 10:
        issues.append(f"内容管线节点数已变（{c['content']}）")
    if "**10 节点**" not in text:
        issues.append("未写 10 节点内容管线")
    if c["meta"] != 5:
        issues.append(f"元管线节点数已变（{c['meta']}）")
    if "**5 节点**" not in text:
        issues.append("未写 5 节点元管线")
    for o in OBLIGATIONS:
        if o not in text:
            issues.append(f"义务缺：{o}")
    if "**6 类**" not in text:
        issues.append("未写 6 类义务")
    subs = ("preregister", "packets", "analyze", "save", "verify", "index", "audit")
    for s in subs:
        if s not in text:
            issues.append(f"A/B 子命令缺：{s}")
    if "**13 例**" not in text:
        issues.append("未写 13 例判据")
    for p in (PROTOCOL, DIFF):
        if not p.is_file():
            issues.append(f"协议件缺失：{p.name}")
    if "COCKPIT_PROTOCOL.md" not in text or "DIFFERENTIATION.md" not in text:
        issues.append("正文未点名两协议件")
    if "不产 score/grade" not in text and "不产" not in text:
        issues.append("缺「不产 score/grade」边界")
    if "handoff-out" not in text or "injections" not in text:
        issues.append("CLI 补全旗标缺失（--handoff-out / --injections）")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py cockpit --prompt",
                "python scripts/nf.py cockpit-ab preregister",
                "python -m pytest desktop/tests/test_meta_cockpit.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class MetaCockpitDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_cockpit_matches_contract(self):
        self.assertEqual([], cockpit_issues(self.text), "驾驶舱说明不满足契约")

    def test_assets_live(self):
        c = counts()
        self.assertEqual(33, c["atoms"])
        self.assertEqual(33, c["contracts"])
        self.assertEqual(10, c["content"])
        self.assertEqual(5, c["meta"])
        self.assertTrue(PROTOCOL.is_file() and DIFF.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：原子数回退 / 节点数回退 / 缺义务 / 缺子命令 / 缺命令。"""
        old_a = self.text.replace("**33**", "**31**").replace("33 个原子", "31 个原子")
        self.assertTrue(any("33" in i for i in cockpit_issues(old_a)))
        old_c = self.text.replace("**10 节点**", "**8 节点**")
        self.assertTrue(any("10 节点" in i for i in cockpit_issues(old_c)))
        no_o = self.text.replace("开放问题", "开放")
        self.assertTrue(any("开放问题" in i for i in cockpit_issues(no_o)))
        no_s = self.text.replace("packets", "pack")
        self.assertTrue(any("packets" in i for i in cockpit_issues(no_s)))
        no_cmd = self.text.replace("python scripts/nf.py cockpit-ab preregister",
                                   "预注册")
        self.assertTrue(any("preregister" in i for i in cockpit_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_cockpit.md")


if __name__ == "__main__":
    unittest.main()
