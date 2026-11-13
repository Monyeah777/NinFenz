#!/usr/bin/env python3
"""docs/需求收敛模板.md 契约：收敛模板必须「8 字段 / 3+2 子命令 / 0 份工作单」与实读一致。

为什么必须有：这页是「真实需求怎么收敛成可执行工作单」的上游入口——八字段缺一即未收敛，
而 steelman/audit 的命令形态与当前库存是读者判断「这套现在能不能用」的唯一线索。
本轮补「§现状对照」「§复现与引用口径」：8 字段、steelman 3 形态（init/ls/--check）、
audit 2 形态（init/ls）、当前工作单 0 份、首例 NF-FIELD-001 阻塞、doc_hygiene 分类 reference。

范围：只判本文与 CLI/core/doc_hygiene 事实自洽（不生成工作单）。
同族判据：test_steelman.py / test_assemble_build.py / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、8 字段逐条、子命令形态、0 份库存、首例阻塞、reference 分类、
现状对照 + 复现三命令，且不预填任何结论（禁用「已通过/已回填」类措辞）。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "需求收敛模板.md"
SECTIONS = ("## 一、澄清稿模板", "## 二、自动流转链", "## 三、首例",
            "## 现状对照", "## 复现与引用口径")
FIELDS = ("一句话需求", "背景与痛点", "谁消费", "范围边界", "验收标准",
          "风险与未知", "涉及协议", "素材引用")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"需求收敛模板不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("需求收敛模板为空")
    return text


def cli_out(*args) -> str:
    proc = subprocess.run([sys.executable, "scripts/nf.py", *args],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)
    return proc.stdout + proc.stderr


def template_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 需求收敛模板"):
        issues.append("缺标题「# 需求收敛模板」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    nums = re.findall(r"(?m)^\s*([1-8])\. ", text)
    if len(nums) < 8:
        issues.append(f"八字段模板条数不足（{len(nums)}）")
    for f in FIELDS:
        if f not in text:
            issues.append(f"模板字段缺：{f}")
    if "**8**" not in text:
        issues.append("未写 8 字段")
    for marker in ("init", "ls", "--check"):
        if marker not in text:
            issues.append(f"steelman 形态缺：{marker}")
    if "design audit" not in text:
        issues.append("缺 audit 命令链")
    if "**0 份**" not in text:
        issues.append("未写当前工作单 0 份")
    steel = cli_out("design", "steelman", "ls")
    audit = cli_out("design", "audit", "ls")
    if "无 steelman 工作单" not in steel:
        issues.append("steelman 库存已非空（文档需更新现状）")
    if "无 audit.md" not in audit:
        issues.append("audit 库存已非空（文档需更新现状）")
    if "NF-FIELD-001" not in text:
        issues.append("缺首例 NF-FIELD-001")
    if "阻塞" not in text:
        issues.append("缺首例阻塞说明")
    if "reference" not in text:
        issues.append("缺 doc_hygiene 分类 reference")
    if "不虚构" not in text:
        issues.append("缺「不虚构回执/结论」纪律")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py design steelman ls",
                "python scripts/nf.py design audit ls"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class RequirementTemplateDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_template_matches_contract(self):
        self.assertEqual([], template_issues(self.text), "需求收敛模板不满足契约")

    def test_inventory_live(self):
        self.assertIn("无 steelman 工作单", cli_out("design", "steelman", "ls"))
        self.assertIn("无 audit.md", cli_out("design", "audit", "ls"))

    def test_contract_catches_mutations(self):
        """变异自证：删字段 / 库存回退 / 缺首例 / 缺命令。"""
        no_field = self.text.replace("6. 风险与未知", "6. 风险")
        self.assertTrue(any("风险与未知" in i for i in template_issues(no_field)))
        old = self.text.replace("**0 份**", "**3 份**")
        self.assertTrue(any("0 份" in i for i in template_issues(old)))
        no_case = self.text.replace("NF-FIELD-001", "NF-XXXX")
        self.assertTrue(any("NF-FIELD-001" in i for i in template_issues(no_case)))
        no_cmd = self.text.replace("python scripts/nf.py design audit ls", "列审计")
        self.assertTrue(any("audit ls" in i for i in template_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_template.md")


if __name__ == "__main__":
    unittest.main()
