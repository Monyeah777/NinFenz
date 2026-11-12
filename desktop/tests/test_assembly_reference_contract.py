#!/usr/bin/env python3
"""skills/ninfenz/references/assembly.md 契约：装配参考必须「骨架/编号/验收三真源对得上」。

为什么必须有：这是外部 agent 装配时的操作手册——它若写错骨架段数、漏掉编号第二条通道、或把
--check 的 exit 2 误读成「通过」，产物就会不合规。实测本轮补的真缺口：§3 只写了 M91–M99 一条
编号通道（01 §6 R2 / 02 §8.3 是两条：机制段 + 类内段），且缺「裸号索引不变量」与「参考与机检
面」段。本轮补齐并把三真源（指令包骨架 / 01·02 编号 / CLI 退出码）立成机检断言。

范围：只判本文件与其引用真源的自洽（不改装配流程语义）。同族判据：
test_doc_truth.TestSkillCommandFace（skills/** 命令须在 CLI 注册表）/ test_skill_md_contract.py
（SKILL 入口）/ test_module_namespace.py（裸号不变量）/ check14 ⑤（编号门禁）。
契约：六步循环 + §0–§6 按序、编号两条通道与裸号不变量在场、八段骨架 ↔ 指令包「## 0 到 ## 7」、
CLI exit 2 两条口径 ↔ nf.py 源码、验收真源命令在场、命令面核心命令在场。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "skills" / "ninfenz" / "references" / "assembly.md"
PACK = ROOT / "docs" / "agent" / "agent_组装指令包_v0.2.md"
PROTOCOL = ROOT / "01_核心协议.md"
REGISTRY = ROOT / "02_联动注册表.md"
NF = ROOT / "scripts" / "nf.py"
NS_TEST = ROOT / "desktop" / "tests" / "test_module_namespace.py"
TICK = chr(96)
EIGHT_RANGE = "八段骨架（" + TICK + "## 0" + TICK + "–" + TICK + "## 7" + TICK + "）"
SECTIONS = ("## 0. 本文件怎么用", "## 1. 判断需求", "## 2. 取货", "## 3. 装配",
            "## 4. 执行与输出", "## 5. 验收", "## 6. 参考与机检面")
MARKERS = ("M91–M99", "类内段", "categories", "裸号索引不变量", "check14 ⑤",
           "test_module_namespace", "八段骨架", "## 0", "## 7",
           "agent_组装指令包_v0.2.md", "--check", "--trace", "--rounds",
           "未执行验收", "未执行漂移断言", "verify.sh", "nf conformance",
           "market --list", "assemble --check")


def load_text(path: Path = REF) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"assembly.md 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("assembly.md 为空")
    return text


def cycle_claim(text: str) -> bool:
    return all(tok in text for tok in ("读", "判", "配", "装", "执", "验")) and "→" in text


def assembly_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NinFenz AI 装配流程"):
        issues.append("缺标题「# NinFenz AI 装配流程」")
    if not cycle_claim(text):
        issues.append("缺「读 → 判 → 配 → 装 → 执 → 验」运行循环声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("§0–§6 顺序不对")
    for marker in MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    if "M91–M99" not in text or "类内段" not in text:
        issues.append("编号通道不全（应为机制段 M91–M99 + 类内段两条）")
    pack = PACK.read_text(encoding="utf-8")
    if "## 0 到 ## 7" not in pack:
        issues.append("指令包骨架声明漂移（应含「## 0 到 ## 7」）")
    if "八段骨架" not in pack:
        issues.append("指令包未声明八段骨架")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    for token in ("M91-M99", "类内段"):
        if token not in protocol:
            issues.append(f"01 §6 R2 缺编号通道要素：{token}")
    registry = REGISTRY.read_text(encoding="utf-8")
    if "类内段" not in registry:
        issues.append("02 §8.3 缺类内段口径")
    nf = NF.read_text(encoding="utf-8")
    for token in ("未执行验收", "未执行漂移断言"):
        if token not in nf:
            issues.append(f"CLI 源码缺退出码口径：{token}")
    if not NS_TEST.is_file():
        issues.append("缺裸号索引不变量回归测试：test_module_namespace.py")
    if EIGHT_RANGE not in text:
        issues.append("八段骨架未与段号范围绑定（应写八段骨架 ## 0–## 7）")
    if len(text.splitlines()) < 60:
        issues.append("文件过短（§0–§6 内容不足）")
    return issues


class AssemblyReferenceContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_assembly_reference_matches_contract(self):
        self.assertEqual([], assembly_issues(self.text), "assembly.md 不满足契约")

    def test_truth_sources_agree(self):
        self.assertIn("## 0 到 ## 7", PACK.read_text(encoding="utf-8"))
        self.assertIn("八段骨架", PACK.read_text(encoding="utf-8"))
        self.assertIn("M91-M99", PROTOCOL.read_text(encoding="utf-8"))
        self.assertIn("类内段", REGISTRY.read_text(encoding="utf-8"))
        self.assertIn("未执行验收", NF.read_text(encoding="utf-8"))
        self.assertIn("未执行漂移断言", NF.read_text(encoding="utf-8"))

    def test_numbering_channels_both_present(self):
        self.assertIn("M91–M99", self.text)
        self.assertIn("类内段", self.text)
        self.assertIn("categories", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：编号只留一段 / 骨架段数漂移 / 退出码口径缺 / 缺段 / 命令缺。"""
        one_channel = self.text.replace("类内段", "扩展段")
        self.assertTrue(any("类内段" in i or "通道" in i
                            for i in assembly_issues(one_channel)))
        six = self.text.replace(EIGHT_RANGE, "六段骨架（## 0–## 5）", 1)
        self.assertTrue(any("八段" in i for i in assembly_issues(six)))
        no_exit = self.text.replace("未执行漂移断言", "漂移断言")
        self.assertTrue(any("漂移断言" in i or "退出码" in i
                            for i in assembly_issues(no_exit)))
        no_section = self.text.replace("## 6. 参考与机检面（先看这里再交付）", "## 6. 参考")
        self.assertTrue(any("缺段" in i for i in assembly_issues(no_section)))
        no_cmd = self.text.replace("python scripts/nf.py market --list", "nf market")
        self.assertTrue(any("market --list" in i for i in assembly_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_assembly.md")


if __name__ == "__main__":
    unittest.main()
