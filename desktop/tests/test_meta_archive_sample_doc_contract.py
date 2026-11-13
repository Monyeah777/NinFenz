#!/usr/bin/env python3
"""docs/meta/档案.md 契约：历史快照样例必须「来源/差异/非计划」三声明齐 + 正文仍可复现。

为什么必须有：这份文件是 nf assemble 需求 --save docs/meta/档案.md 的旧版遗留快照，
内容是一份带「待回填/待确认」的需求澄清稿——若不加声明，读者会把它当成现行计划件或真实需求。
本轮加了来源、与现行渲染器的唯一差异（旧版二次加引号）、复现命令，并明说「不是计划/承诺/不据此执行」，
同时原样保留正文（15 行），避免把历史快照伪造成现版输出。

范围：只判本文与 assemble_plan/当前渲染结果事实自洽（不改渲染器、不重写正文）。
同族判据：test_doc_hygiene.py / test_doc_reachability.py / test_assemble_*.py。
契约：标题 + 最后更新 + 复核、来源命令、差异说明、复现命令、非计划声明、
正文起始为「需求澄清稿」且保留待回填/待确认、现行渲染为单层引号（对照）。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "meta" / "档案.md"
PLAN = ROOT / "desktop" / "src" / "core" / "assemble_plan.py"
QUOTED = '""' + "需求" + '""'


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"需求澄清快照不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("需求澄清快照为空")
    return text


def archive_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 样例：nf assemble 生成的需求澄清稿"):
        issues.append("缺标题「# 样例：nf assemble 生成的需求澄清稿（历史快照，非计划件）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    if "历史快照" not in text:
        issues.append("缺「历史快照」口径")
    if "不是计划" not in text or "不据此执行" not in text:
        issues.append("缺「非计划/不据此执行」声明")
    if "nf assemble 需求 --save docs/meta/档案.md" not in text:
        issues.append("缺来源命令")
    if '""需求""' not in text:
        issues.append("缺旧版二次引号差异说明")
    if "python scripts/nf.py assemble 需求 --save /tmp/arch_sample.md" not in text:
        issues.append("缺复现命令")
    if "需求澄清稿" not in text:
        issues.append("缺正文起始「需求澄清稿」")
    if "（待回填" not in text or "（待确认" not in text:
        issues.append("正文应保留待回填/待确认原样")
    if not PLAN.is_file():
        issues.append("assemble_plan.py 缺失")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class MetaArchiveSampleTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_sample_matches_contract(self):
        self.assertEqual([], archive_issues(self.text), "需求澄清快照不满足契约")

    def test_current_renderer_uses_single_quotes(self):
        out_path = ROOT.parent / "arch_sample_check.md"
        proc = subprocess.run(
            [sys.executable, "scripts/nf.py", "assemble", "需求", "--save", str(out_path)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180, check=False)
        self.assertEqual(0, proc.returncode, proc.stderr[-400:])
        out = out_path.read_text(encoding="utf-8")
        self.assertIn("一句话需求：需求", out)
        self.assertNotIn(QUOTED, out)

    def test_contract_catches_mutations(self):
        """变异自证：去非计划声明 / 去来源 / 去差异 / 去复现命令。"""
        no_decl = self.text.replace("不据此执行", "可据此执行")
        self.assertTrue(any("非计划" in i for i in archive_issues(no_decl)))
        no_src = self.text.replace("nf assemble 需求 --save docs/meta/档案.md", "生成")
        self.assertTrue(any("来源" in i for i in archive_issues(no_src)))
        no_diff = self.text.replace('""需求""', '"需求"')
        self.assertTrue(any("二次引号" in i for i in archive_issues(no_diff)))
        no_cmd = self.text.replace(
            "python scripts/nf.py assemble 需求 --save /tmp/arch_sample.md", "重跑")
        self.assertTrue(any("复现命令" in i for i in archive_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_arch.md")


if __name__ == "__main__":
    unittest.main()
