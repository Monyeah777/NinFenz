#!/usr/bin/env python3
"""docs/quickstart.md 契约：五分钟入口必须「6 步 ↔ 脚本 6 步 / 300s / check39 挂载 / Python 3.11」。

为什么必须有：这是新克隆者的唯一入口——步数、slug 序列、墙钟上限、Python 版本任一项漂移，
轻则照做失败，重则「入口本身不可信」。本轮修一处真漂移（文中写 Python ≥ 3.10，而 pyproject 是
>= 3.11），并补「§现状对照」「§复现与引用口径」；判据把文档与脚本双向绑定，且校验 doc 里不得
出现会被脚本误认为「第 7 步标记」的字面量。

范围：只判本文与 quickstart_check.sh / verify.sh / pyproject 事实自洽（不改脚本）。
同族判据：quickstart_check.sh 自身审计（check39 调用）/ test_doc_hygiene.py /
test_live_doc_counts.py。
契约：最后更新位 + 复核、6 步、6 个 nf-step 标记、slug 序列、300 s、≥3.11、check39、
现状对照 + 复现两命令、三方对齐口径。
"""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "quickstart.md"
SCRIPT = ROOT / "scripts" / "quickstart_check.sh"
VERIFY = ROOT / "verify.sh"
PYPROJECT = ROOT / "pyproject.toml"
SECTIONS = ("## 一条命令自检", "## 6 步（逐条复制粘贴）", "## 现状对照",
            "## 复现与引用口径", "## 判据挂载")
SLUGS = ("version", "doctor", "demo", "assemble", "reproducible", "check")
MARK = "<!-- nf-step:"
SH_MARK = "# nf-step:"


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"快速开始文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("快速开始文档为空")
    return text


def doc_slugs(text: str) -> list:
    return re.findall(r"<!--\s*nf-step:\s*\d+\s+([a-z0-9-]+)\s*-->", text)


def sh_slugs() -> list:
    return re.findall(r"#\s*nf-step:\s*\d+\s+([a-z0-9-]+)", SCRIPT.read_text(encoding="utf-8"))


def quick_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 五分钟可复现入口"):
        issues.append("缺标题「# 五分钟可复现入口（quickstart）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    if text.count(MARK) != 6:
        issues.append(f"文档 nf-step 标记数不是 6（{text.count(MARK)}）")
    if doc_slugs(text) != list(SLUGS):
        issues.append(f"文档 slug 序列已变：{doc_slugs(text)}")
    if sh_slugs() != list(SLUGS):
        issues.append(f"脚本 slug 序列已变：{sh_slugs()}")
    if "**6**" not in text:
        issues.append("未写 6 步")
    if "300 s" not in text and "300 秒" not in text:
        issues.append("缺 300 s 墙钟上限")
    with open(PYPROJECT, "rb") as fh:
        py = tomllib.load(fh)["project"]["requires-python"]
    if "3.11" not in py:
        issues.append(f"pyproject 要求已变：{py}")
    if "≥ 3.11" not in text:
        issues.append("未写 Python ≥ 3.11")
    if "Python ≥ 3.10" in text:
        issues.append("仍残留 Python 3.10 口径")
    if "check39" not in text:
        issues.append("缺 check39 挂载口径")
    if "check39" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("verify.sh 缺 check39")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("bash scripts/quickstart_check.sh --audit",
                "bash scripts/quickstart_check.sh"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "三方对齐" not in text:
        issues.append("缺「三方对齐」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class QuickstartDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_quickstart_matches_contract(self):
        self.assertEqual([], quick_issues(self.text), "快速开始文档不满足契约")

    def test_doc_and_script_aligned(self):
        self.assertEqual(6, self.text.count(MARK))
        self.assertEqual(list(SLUGS), doc_slugs(self.text))
        self.assertEqual(list(SLUGS), sh_slugs())
        with open(PYPROJECT, "rb") as fh:
            self.assertIn("3.11", tomllib.load(fh)["project"]["requires-python"])

    def test_contract_catches_mutations(self):
        """变异自证：缺步标记 / slug 漂移 / 回退 3.10 / 缺 check39 / 缺命令。"""
        no_step = self.text.replace("<!-- nf-step: 6 check -->", "")
        self.assertTrue(any("标记数" in i for i in quick_issues(no_step)))
        bad_slug = self.text.replace("nf-step: 2 doctor", "nf-step: 2 health")
        self.assertTrue(any("slug" in i for i in quick_issues(bad_slug)))
        old_py = self.text.replace("**Python ≥ 3.11**", "**Python ≥ 3.10**")
        self.assertTrue(any("3.10" in i or "3.11" in i for i in quick_issues(old_py)))
        no_c = self.text.replace("check39", "check38")
        self.assertTrue(any("check39" in i for i in quick_issues(no_c)))
        no_cmd = self.text.replace("bash scripts/quickstart_check.sh --audit", "审计")
        self.assertTrue(any("--audit" in i for i in quick_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_quickstart.md")


if __name__ == "__main__":
    unittest.main()
