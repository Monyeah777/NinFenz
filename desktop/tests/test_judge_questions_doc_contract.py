#!/usr/bin/env python3
"""docs/ccos/judge-design-questions.md 契约：11 问齐 + 比例棘轮活绑定 + 结果件新鲜。

为什么必须有：这份速查是「新判据提交前必过」的口径，它的可信度靠三个可复核事实：① 十一问齐全；
② 第五问的硬约束（比例 ≤ 0.36）与常量、登记表真实一致；③ 文中承诺「命令行 --check 为红即陈旧」
必须真成立。本轮实测 judge_red_evidence.py --check 为红（新增测试模块后登记表未重算）——按纪律
--write 重建后转绿；本判据把「登记表 == 现场」「比例 ≤ 0.36」「11 问齐」都活绑定，防止再出现
「文档说可复算、结果件其实陈旧」。

范围：只判本文与红证据登记/辅助脚本事实自洽（不改口径）。同族判据：
test_judge_red_evidence.py（4 例，比例棘轮）/ judge_mutation_probe / gate_probe /
test_doc_hygiene.py / test_doc_examples.py。
契约：状态行 + 最后更新位 + 复核、11 问标题齐、0.36 常量与实测验算、
登记表新鲜（committed == 现场）、6 个辅助脚本在场、现状对照 + 复现两命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))

import judge_red_evidence as jr  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "judge-design-questions.md"
TEST = ROOT / "desktop" / "tests" / "test_judge_red_evidence.py"
SCRIPTS = ("judge_red_evidence.py", "capability_inventory.py", "core_judge_map.py",
           "judge_mutation_probe.py", "gate_probe.py")
QUESTIONS = ("一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、",
             "十一、")
SECTIONS = ("## 用法", "## 第五问的硬约束", "## 现状对照", "## 相关", "## 怎么查这些数",
            "## 复现与引用口径")
RATIO_LIMIT = 0.36


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"判据设计十一问不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("判据设计十一问为空")
    return text


def registry() -> dict:
    return json.loads((ROOT / jr.OUT_REL).read_text(encoding="utf-8"))


def judge_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 判据设计十一问"):
        issues.append("缺标题「# 判据设计十一问（速查）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for q in QUESTIONS:
        if ("## " + q) not in text:
            issues.append(f"缺问：{q}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if "0.36" not in text:
        issues.append("未写比例上限 0.36")
    if "0.36" not in TEST.read_text(encoding="utf-8"):
        issues.append("测试常量 0.36 已变")
    reg = registry()
    ratio = reg["without_evidence"] / reg["modules"]
    if ratio > RATIO_LIMIT:
        issues.append(f"无硬证据比例越线：{ratio:.3f} > {RATIO_LIMIT}")
    if "0.264" not in text:
        issues.append("未写实测比例 0.264")
    for label in ("534", "232", "161", "141"):
        if label not in text:
            issues.append(f"现状数字缺要素：{label}")
    fresh = jr.render(jr.collect(ROOT)) == jr.render(reg)
    if not fresh:
        issues.append("红证据登记表陈旧（须 judge_red_evidence.py --write）")
    for name in SCRIPTS:
        if not (ROOT / "scripts" / name).is_file():
            issues.append(f"缺辅助脚本：{name}")
        if name not in text:
            issues.append(f"正文缺辅助脚本：{name}")
    n_cases = TEST.read_text(encoding="utf-8").count("def test")
    if n_cases != 4:
        issues.append(f"test_judge_red_evidence 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写判据数（{n_cases} 例）")
    for cmd in ("python scripts/judge_red_evidence.py --check",
                "python -m pytest desktop/tests/test_judge_red_evidence.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class JudgeDesignQuestionsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_judge_questions_match_contract(self):
        self.assertEqual([], judge_issues(self.text), "判据设计十一问不满足契约")

    def test_registry_live(self):
        reg = registry()
        self.assertEqual(534, reg["modules"])
        self.assertEqual(232, reg["with_evidence"])
        self.assertEqual(161, reg["suspect"])
        self.assertEqual(141, reg["without_evidence"])
        self.assertLessEqual(reg["without_evidence"] / reg["modules"], RATIO_LIMIT)
        self.assertEqual(jr.render(jr.collect(ROOT)), jr.render(reg))

    def test_contract_catches_mutations(self):
        """变异自证：缺一问 / 去比例上限 / 数字回退 / 去脚本 / 去新鲜度命令。"""
        no_q = self.text.replace("## 十一、", "## 十二、")
        self.assertTrue(any("十一" in i for i in judge_issues(no_q)))
        no_ratio = self.text.replace("0.36", "0.40")
        self.assertTrue(any("0.36" in i for i in judge_issues(no_ratio)))
        old_n = self.text.replace("534", "500")
        self.assertTrue(any("534" in i for i in judge_issues(old_n)))
        no_script = self.text.replace("gate_probe.py", "某探针")
        self.assertTrue(any("gate_probe.py" in i for i in judge_issues(no_script)))
        no_cmd = self.text.replace("python scripts/judge_red_evidence.py --check", "跑检查")
        self.assertTrue(any("--check" in i for i in judge_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_judge.md")


if __name__ == "__main__":
    unittest.main()
