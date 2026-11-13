#!/usr/bin/env python3
"""docs/meta-cockpit/功能解析.md 契约：功能拆解必须「33 原子/10·5 节点/3·5 约束与资产一致」。

为什么必须有：这是驾驶舱的功能拆解长文——原子数、元梯度层级、两条管线的节点数、单轮约束
（3 原子 / 5 候选）、以及「不产评分」纪律，任何一项漂移都会让外部读者误判系统能力与边界。
本轮补可核锚（33 原子按前缀 k10/m6/e6/i6/c5、M0–M4、10/5 节点、max_atoms=3 / candidate_limit=5、
execute_atom 所在件、13 例）与「§现状对照」「§复现与引用口径」；并把「14 个方法节点」标为
**待澄清（仅 release notes 复述、无机读真源）**，不以文档互引当证据。

范围：只判本文与 meta_cockpit 资产/代码常量/判据事实自洽（不改实现）。
同族判据：test_meta_cockpit.py（13）/ test_meta_cockpit_doc_contract.py（README）/
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、33 原子与前缀分布、M0–M4、10 节点/5 节点、3/5 约束、execute_atom、
13 例、14 节点待澄清、现状对照 + 复现两命令、「不产评分」纪律。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "meta-cockpit" / "功能解析.md"
BASE = ROOT / "desktop" / "src" / "core" / "meta_cockpit"
ATOMS = BASE / "meta_atoms.json"
PIPELINE = BASE / "cognition_pipeline.json"
META = BASE / "cognition_meta_pipeline.json"
CHOICE = BASE / "constrained_choice.py"
RUNTIME = BASE / "meta_atom_runtime.py"
README = ROOT / "docs" / "meta-cockpit" / "README.md"
SECTIONS = ("## 一句话定位", "## 现状对照", "## 复现与引用口径",
            "## 与提示词工程的区别", "## 总体架构", "## 关键安全边界", "## 使用入口")
PREFIX = {"k": 10, "m": 6, "e": 6, "i": 6, "c": 5}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"功能解析文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("功能解析文档为空")
    return text


def facts() -> dict:
    atoms = json.loads(ATOMS.read_text(encoding="utf-8"))["atoms"]
    prefix = {}
    for a in atoms:
        head = a["id"].split(".")[0]
        prefix[head] = prefix.get(head, 0) + 1
    return {"total": len(atoms), "prefix": prefix,
            "content": len(json.loads(PIPELINE.read_text(encoding="utf-8"))["nodes"]),
            "meta": len(json.loads(META.read_text(encoding="utf-8"))["nodes"])}


def analysis_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 认知驾驶舱功能解析"):
        issues.append("缺标题「# NF 认知驾驶舱功能解析」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    f = facts()
    if f["total"] != 33:
        issues.append(f"原子数已变（{f['total']}）")
    if f["prefix"] != PREFIX:
        issues.append(f"前缀分布已变：{f['prefix']}")
    if "**33**" not in text:
        issues.append("未写 33 原子")
    for k, n in PREFIX.items():
        if k + str(n) not in text:
            issues.append(f"缺前缀分布：{k}{n}")
    for lvl in ("M0", "M4"):
        if lvl not in text:
            issues.append(f"缺元梯度层级：{lvl}")
    if "M0–M4" not in text:
        issues.append("未写 M0–M4")
    if f["content"] != 10:
        issues.append(f"内容管线节点数已变（{f['content']}）")
    if "**10 节点**" not in text:
        issues.append("未写 10 节点内容管线")
    if f["meta"] != 5:
        issues.append(f"元管线节点数已变（{f['meta']}）")
    if "**5 节点**" not in text:
        issues.append("未写 5 节点元管线")
    choice = CHOICE.read_text(encoding="utf-8")
    if "candidate_limit" in choice and "5" not in choice.split("candidate_limit")[1][:8]:
        issues.append("candidate_limit 不再是 5")
    if "max_atoms" in choice and "3" not in choice.split("max_atoms")[1][:8]:
        issues.append("max_atoms 不再是 3")
    if "**max_atoms=3**" not in text or "**candidate_limit=5**" not in text:
        issues.append("未写 3/5 单轮约束")
    if "execute_atom" not in text:
        issues.append("缺 execute_atom 口径")
    if not RUNTIME.is_file():
        issues.append("meta_atom_runtime.py 缺失")
    if "**13 例**" not in text:
        issues.append("未写 13 例判据")
    if "待澄清" not in text or "14 个方法节点" not in text:
        issues.append("缺「14 个方法节点待澄清」说明")
    if "不产评分" not in text:
        issues.append("缺「不产评分」纪律")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py cockpit --prompt",
                "python -m pytest desktop/tests/test_meta_cockpit.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "README" not in text and not README.is_file():
        issues.append("同目录 README 缺失")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class CockpitAnalysisDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_analysis_matches_contract(self):
        self.assertEqual([], analysis_issues(self.text), "功能解析文档不满足契约")

    def test_facts_live(self):
        f = facts()
        self.assertEqual(33, f["total"])
        self.assertEqual(PREFIX, f["prefix"])
        self.assertEqual(10, f["content"])
        self.assertEqual(5, f["meta"])

    def test_contract_catches_mutations(self):
        """变异自证：原子数回退 / 前缀分布回退 / 节点数回退 / 缺 14 待澄清 / 缺命令。"""
        old_a = self.text.replace("**33**", "**31**")
        self.assertTrue(any("33" in i for i in analysis_issues(old_a)))
        old_p = self.text.replace("k10", "k9")
        self.assertTrue(any("k10" in i for i in analysis_issues(old_p)))
        old_c = self.text.replace("**10 节点**", "**9 节点**")
        self.assertTrue(any("10 节点" in i for i in analysis_issues(old_c)))
        no_14 = self.text.replace("待澄清", "已确认")
        self.assertTrue(any("待澄清" in i for i in analysis_issues(no_14)))
        no_cmd = self.text.replace("python scripts/nf.py cockpit --prompt", "跑一轮")
        self.assertTrue(any("cockpit --prompt" in i for i in analysis_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_analysis.md")


if __name__ == "__main__":
    unittest.main()
