#!/usr/bin/env python3
"""迁移指南契约：4 签名文档 / 15 历史面 / 3 影响度必须与实现一致。

为什么必须有：这页是「改契约前后怎么核」的唯一入口——签名面、历史面、影响度词表任何一项漂移，
读者就会拿错工具或以为某类文件不可查。本轮补「§现状对照」「§复现与引用口径」，把 4 个根文档、
2 个 protocol 契约、9 个 schema、以及 3 值影响度词表与 core 常量/CLI 实读绑定。

范围：只判本文与 knowledge_sig/contract_history/CLI 事实自洽（不改实现）。
同族判据：test_m4_census_contract.py（本页在普查清单内）/ test_doc_hygiene.py（how-to 分类）/
test_live_doc_counts.py。
契约：标题 + ⛔ 紧跟标题 + 最后更新 + 复核、四段流程在文、文档 4 / 可复现 1、历史面 4+2+9=15、
影响度 3 值、命令三形态、现状对照 + 复现三命令、doc_hygiene 分类 how-to。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import contract_history as ch  # noqa: E402

DOC = ROOT / "docs" / "迁移指南-基于nf-sig-diff.md"
SECTIONS = ("## 一、何时用", "## 二、标准流程", "## 三、契约演进时间线",
            "## 四、与既有门禁的关系", "## 现状对照", "## 复现与引用口径")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"迁移指南不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("迁移指南为空")
    return text


def sig_out() -> str:
    proc = subprocess.run([sys.executable, "scripts/nf.py", "sig", "--verify"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)
    return proc.stdout + proc.stderr


def guide_issues(text: str) -> list:
    issues = []
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# 迁移指南"):
        issues.append("缺标题「# 迁移指南 · 基于 nf sig / nf diff」")
    elif len(lines) < 2 or "⛔" not in lines[1]:
        issues.append("⛔ 操作指令必须紧跟标题（doc_hygiene 判据）")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    roots = sorted(ch.ROOT_CONTRACTS)
    if len(roots) != 4:
        issues.append(f"根契约数已变（{len(roots)}）")
    for rel in roots:
        if rel not in text:
            issues.append(f"正文缺根契约：{rel}")
    if len(ch.PROTOCOL_CONTRACTS) != 2:
        issues.append(f"protocol 契约数已变（{len(ch.PROTOCOL_CONTRACTS)}）")
    schemas = sorted((ROOT / "protocol" / "schema").glob("*.json"))
    if len(schemas) != 9:
        issues.append(f"schema 数已变（{len(schemas)}）")
    if "**15**" not in text:
        issues.append("未写历史面合计 15")
    if "**9**" not in text:
        issues.append("未写 schema 9")
    for word in ("editorial", "additive", "bump"):
        if word not in text:
            issues.append(f"影响度词表缺：{word}")
    if "**3** 值" not in text:
        issues.append("未写影响度 3 值")
    out = sig_out()
    if "文档 4" not in out:
        issues.append("sig --verify 文档数不再是 4")
    if "可复现" not in out:
        issues.append("sig --verify 缺可复现结论")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py sig --verify",
                "python scripts/nf.py diff --history"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class MigrationGuideDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_guide_matches_contract(self):
        self.assertEqual([], guide_issues(self.text), "迁移指南不满足契约")

    def test_faces_live(self):
        self.assertEqual(4, len(ch.ROOT_CONTRACTS))
        self.assertEqual(2, len(ch.PROTOCOL_CONTRACTS))
        self.assertEqual(9, len(list((ROOT / "protocol" / "schema").glob("*.json"))))
        self.assertIn("文档 4", sig_out())

    def test_contract_catches_mutations(self):
        """变异自证：⛔ 位置 / 历史面回退 / 缺影响度词 / 缺命令。"""
        first, second = self.text.splitlines()[0], self.text.splitlines()[1]
        broken = self.text.replace(first + "\n" + second,
                                   first + "\n\n" + second)
        self.assertTrue(any("紧跟标题" in i for i in guide_issues(broken)))
        old = self.text.replace("**15**", "**12**")
        self.assertTrue(any("15" in i for i in guide_issues(old)))
        no_word = self.text.replace("editorial", "minor")
        self.assertTrue(any("editorial" in i for i in guide_issues(no_word)))
        no_cmd = self.text.replace("python scripts/nf.py diff --history 20",
                                   "看历史")
        self.assertTrue(any("--history" in i for i in guide_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_guide.md")


if __name__ == "__main__":
    unittest.main()
