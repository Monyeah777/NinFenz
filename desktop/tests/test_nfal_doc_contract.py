#!/usr/bin/env python3
"""docs/nfal.md 契约：NFA-L 文档必须「5 子命令/6 函数/6 码/110 条迁移」与实现一致。

为什么必须有：这页是 guard 命令层的唯一语法与判据说明——封闭函数集、类型词、诊断码、
散文 advisory、以及「仓内迁移是否完成」，任何一项漂移都会让写 condition 的人判错。
本轮补可核现状：5 子命令 / 6 封闭函数 / 9 类型词 / 6 诊断码 + A0201 / 迁移 110/110 / 判据 44 例，
并补「§现状对照」「§复现与引用口径」。

范围：只判本文与 nfal 实现/管线声明/判据事实自洽（不改实现）。
同族判据：test_nfal.py（26）/ test_nfal_cli.py（6）/ test_nfal_rules.py（12）/ test_doc_hygiene.py。
契约：最后更新位 + 复核、5 子命令、6 函数、9 类型、6 码 + A0201、迁移 110/110 散文 0、
44 例、现状对照 + 复现三命令、abstain 不折算为 pass 口径。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "nfal.md"
CORE = ROOT / "desktop" / "src" / "core" / "nfal.py"
SECTIONS = ("## 是什么", "## 怎么用", "## 命令层语法（封闭）", "## 类型与判决（fail-closed）",
            "## 编辑器面（nf lsp）", "## 仓内迁移状态", "## 现状对照",
            "## 复现与引用口径", "## 边界（不宣称）")
SUBS = ("parse", "check", "build", "eval", "schema-check")
FUNCS = ("size", "contains", "has", "startsWith", "int", "string")
CODES = ("E0201", "E0202", "E0301", "E0302", "E0304", "E0310")
TYPES = ("string", "integer", "number", "boolean", "array", "object",
         "event", "state", "untyped")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"NFA-L 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("NFA-L 文档为空")
    return text


def conditions() -> dict:
    total = expr = prose = 0
    files = list(ROOT.glob("03_管线库/*.md")) + list(ROOT.glob("community/*/pipelines/*.md"))
    for f in files:
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            s = ln.strip()
            if not s.startswith("condition:"):
                continue
            val = s.split(":", 1)[1].strip()
            total += 1
            if val.startswith("="):
                expr += 1
            else:
                prose += 1
    return {"files": len(files), "total": total, "expr": expr, "prose": prose}


def nfal_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NFA-L"):
        issues.append("缺标题「# NFA-L · NF 装配语言」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for s in SUBS:
        if s not in text:
            issues.append(f"缺子命令：{s}")
    if "**5 个子命令**" not in text:
        issues.append("未写 5 个子命令")
    for fn in FUNCS:
        if fn not in text:
            issues.append(f"缺封闭函数：{fn}")
    if "**6 个**" not in text:
        issues.append("未写 6 个封闭函数")
    for t in TYPES:
        if t not in text:
            issues.append(f"缺类型词：{t}")
    if "**9 个**" not in text:
        issues.append("未写 9 个类型词")
    core = CORE.read_text(encoding="utf-8")
    for code in CODES:
        if code not in core:
            issues.append(f"实现缺诊断码：{code}")
        if code not in text:
            issues.append(f"正文缺诊断码：{code}")
    for marker in ("A0201", "nfal-guard", "abstain"):
        if marker not in text:
            issues.append(f"缺口径：{marker}")
    c = conditions()
    if c["prose"] != 0:
        issues.append(f"仍有散文 condition（{c['prose']}）")
    if c["expr"] != c["total"]:
        issues.append(f"迁移未完成：expr {c['expr']} / total {c['total']}")
    if "**110/110**" not in text:
        issues.append("未写迁移 110/110")
    if "散文 0 条" not in text:
        issues.append("未写「散文 0 条」")
    if "**44 例**" not in text:
        issues.append("未写 44 例判据")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py nfal help",
                "python scripts/nf.py nfal parse",
                "python -m pytest desktop/tests/test_nfal.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不折算为 pass" not in text:
        issues.append("缺「abstain 不折算为 pass」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class NfalDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_nfal_matches_contract(self):
        self.assertEqual([], nfal_issues(self.text), "NFA-L 文档不满足契约")

    def test_pipeline_migration_live(self):
        c = conditions()
        self.assertEqual(110, c["total"])
        self.assertEqual(110, c["expr"])
        self.assertEqual(0, c["prose"])
        self.assertEqual(114, c["files"])

    def test_contract_catches_mutations(self):
        """变异自证：缺子命令 / 缺函数 / 缺码 / 迁移口径回退 / 缺命令。"""
        no_sub = self.text.replace("schema-check", "schema")
        self.assertTrue(any("schema-check" in i for i in nfal_issues(no_sub)))
        no_fn = self.text.replace("startsWith", "starts")
        self.assertTrue(any("startsWith" in i for i in nfal_issues(no_fn)))
        no_code = self.text.replace("E0304", "E0303")
        self.assertTrue(any("E0304" in i for i in nfal_issues(no_code)))
        bad_mig = self.text.replace("**110/110**", "**90/110**")
        self.assertTrue(any("110/110" in i for i in nfal_issues(bad_mig)))
        no_cmd = self.text.replace("python scripts/nf.py nfal parse", "解析")
        self.assertTrue(any("nfal parse" in i for i in nfal_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_nfal.md")


if __name__ == "__main__":
    unittest.main()
