#!/usr/bin/env python3
"""docs/fde-sample/run.md 契约：照做步骤必须「命令原文/期望输出/退出码与脚本实跑一致」。

为什么必须有：这是客户侧唯一照着执行的文档——六步里任何一条命令写错、期望串与真实输出不符、
或把「全量 verify.sh（30–85 分钟）」当成中游面复核的必需步骤，第三方就会在错误的地方等、
在错误的地方判红。本判据把「生成器两命令的期望串」「gates 五行」「两条出口命令的期望串」
「六步框架」「变更记录」全部活绑定。

范围：只判本文与 fde_sample_run/gates/stats/geo 事实自洽（不重跑 --run）。
同族判据：test_fde_sample_doc_contract.py（README 五门）/ test_fde_deliverable_doc_contract.py /
test_json_shape_contracts.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、六步标题在文、--run 期望串与脚本输出格式一致、--check 期望串、
gates 五行、步骤 5 两条命令与期望串、--checks-only 时间预算口径、变更记录含本轮行。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "fde-sample" / "run.md"
SCRIPT = ROOT / "scripts" / "fde_sample_run.py"
GATES = ROOT / "docs" / "fde-sample" / "evidence" / "gates.txt"
SECTIONS = ("## 步骤 0", "## 步骤 1", "## 步骤 2", "## 步骤 3", "## 步骤 4", "## 步骤 5",
            "## 步骤 6", "## 变更记录")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"FDE 照做步骤不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("FDE 照做步骤为空")
    return text


def run_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 照做步骤"):
        issues.append("缺标题「# 照做步骤（FDE 样例 · 命令原文）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    script = SCRIPT.read_text(encoding="utf-8")
    if "== FDE 样例已跑 ==" not in script:
        issues.append("脚本缺 --run 输出头")
    if "== FDE 样例自检 ==" not in script:
        issues.append("脚本缺 --check 输出头")
    if "== FDE 样例已跑 ==  证据 4 件 → docs/fde-sample/evidence/" not in text:
        issues.append("步骤 1 期望串与脚本不符")
    if "== FDE 样例自检 ==  门 5 · 证据件 4" not in text:
        issues.append("步骤 3 期望串与脚本不符")
    gates = GATES.read_text(encoding="utf-8")
    for g in ("G1", "G2", "G3", "G4", "G5"):
        if ("[PASS] " + g) not in gates:
            issues.append(f"gates.txt 缺 PASS：{g}")
        if g not in text:
            issues.append(f"正文缺门：{g}")
    if "python scripts/nf.py stats --check" not in text:
        issues.append("步骤 5 缺 stats --check")
    if "python scripts/geo_export.py --check" not in text:
        issues.append("步骤 5 缺 geo_export --check")
    if "标准 370 条 · 被绑定 70 条 · 生成物 8 件" not in text:
        issues.append("步骤 5 缺 geo_export 期望串")
    if "模式：check（只校验）" not in text:
        issues.append("步骤 5 缺 stats 期望串")
    if "bash verify.sh --checks-only" not in text:
        issues.append("缺 --checks-only 快路径口径")
    if "30–85 分钟" not in text:
        issues.append("缺全量档时间预算")
    if "| 2026-11-13 | 复核" not in text:
        issues.append("变更记录缺本轮行")
    if "docs/interop-thirdparty.md" not in text:
        issues.append("步骤 6 缺第三方卡片入口")
    if "results/interop-thirdparty-status.md" not in text:
        issues.append("步骤 6 缺回填文件")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class FdeRunDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_run_doc_matches_contract(self):
        self.assertEqual([], run_issues(self.text), "FDE 照做步骤不满足契约")

    def test_expected_strings_live(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("== FDE 样例已跑 ==", script)
        self.assertIn("== FDE 样例自检 ==", script)
        self.assertIn("== FDE 样例已跑 ==  证据 4 件 → docs/fde-sample/evidence/",
                      self.text)
        self.assertIn("== FDE 样例自检 ==  门 5 · 证据件 4", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：期望串错 / 缺门 / 缺 --checks-only / 缺时间预算 / 缺变更行。"""
        bad = self.text.replace("证据 4 件 → docs/fde-sample/evidence/", "证据 3 件")
        self.assertTrue(any("步骤 1" in i for i in run_issues(bad)))
        no_g = self.text.replace("G4", "GX")
        self.assertTrue(any("G4" in i for i in run_issues(no_g)))
        no_fast = self.text.replace("bash verify.sh --checks-only", "bash verify.sh")
        self.assertTrue(any("--checks-only" in i for i in run_issues(no_fast)))
        no_budget = self.text.replace("30–85 分钟", "若干分钟")
        self.assertTrue(any("时间预算" in i for i in run_issues(no_budget)))
        no_row = self.text.replace("| 2026-11-13 | 复核", "")
        self.assertTrue(any("变更记录" in i for i in run_issues(no_row)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_run.md")


if __name__ == "__main__":
    unittest.main()
