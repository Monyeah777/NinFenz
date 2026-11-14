#!/usr/bin/env python3
"""patterns/INDEX.md 契约：整页生成物必须与 `nf patterns reindex` 幂等、计数与真源一致。

为什么必须有：这页是 7 个实践包的投影，**整页由 reindex 重建**——手改会被覆盖，但此前没有判据
盯着「reindex 是否真的幂等」「现状计数是否与真源一致」。本轮把「现状对照」也做成**生成内容**
（实践包数 / 规则总数 / 状态分布 / 包 id 全部实时算出），
并加本判据：实跑 reindex 后文件必须逐字节不变。

范围：只判 INDEX.md 与真源 frontmatter/渲染器事实自洽（不新增 pattern）。
同族判据：test_patterns.py（格式与可证性）/ test_doc_hygiene.py。
契约：标题 + 最后更新 + 整体生成物声明、生成区含 现状对照/复现口径、计数与 entries 实时算得一致、
包 id 逐个在场、reindex 幂等（子进程实跑后文件不变）、patterns verify 通过。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "INDEX.md"


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"patterns INDEX 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("patterns INDEX 为空")
    return text


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "scripts/nf.py", "patterns", *args],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180, check=False)


def index_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF Patterns 索引"):
        issues.append("缺标题「# NF Patterns 索引」")
    if "最后更新：2026-11-14" not in text:
        issues.append("缺「最后更新：2026-11-14（复核）」")
    if "整体是生成物" not in text:
        issues.append("缺「整页是生成物、手改会被覆盖」声明")
    for section in ("## Pattern 登记表", "## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    rows = pat.entries(str(ROOT))
    total = len(rows)
    rules = sum(len(pat._as_list(e["fm"].get("rules"))) for e in rows)
    if f"| 实践包 | **{total}** |" not in text:
        issues.append(f"现状包数与真源不一致（应为 {total}）")
    if f"| 规则总数 | **{rules}** |" not in text:
        issues.append(f"现状规则总数与真源不一致（应为 {rules}）")
    for e in rows:
        pid = str(e["fm"].get("id") or e["dir"])
        if pid not in text:
            issues.append(f"缺包 id：{pid}")
    if "python scripts/nf.py patterns verify" not in text:
        issues.append("复现口径缺 patterns verify")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PatternsIndexTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_index_matches_contract(self):
        self.assertEqual([], index_issues(self.text), "patterns INDEX 不满足契约")

    def test_reindex_is_idempotent(self):
        before = DOC.read_bytes()
        proc = run("reindex")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(before, DOC.read_bytes(), "reindex 改动了文件（生成区不幂等）")

    def test_patterns_verify_passes(self):
        proc = run("verify")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_contract_catches_mutations(self):
        """变异自证：计数改错 / 缺生成物声明 / 缺包 id / 缺段落。"""
        bad = self.text.replace("| 规则总数 | **21** |", "| 规则总数 | **19** |")
        self.assertTrue(any("规则总数" in i for i in index_issues(bad)))
        no_gen = self.text.replace("整体是生成物", "部分是生成物")
        self.assertTrue(any("生成物" in i for i in index_issues(no_gen)))
        no_id = self.text.replace("worktree-vs-index", "wt")
        self.assertTrue(any("包 id" in i for i in index_issues(no_id)))
        no_sec = self.text.replace("## 现状对照", "## 附注")
        self.assertTrue(any("现状对照" in i for i in index_issues(no_sec)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_patterns_index.md")


if __name__ == "__main__":
    unittest.main()
