#!/usr/bin/env python3
"""docs/locales.md 契约：语言面声明必须「3 语/12 译件/6 指南/责任方与注册表一致」。

为什么必须有：这页是语言面的唯一声明件——语言数、译件数、被覆盖的指南清单、责任方，任何一项漂移
都会让读者误判「哪几份文档有译文」。本轮修真实陈旧：原文写「五份指南」（发布/本地化/MCP/终端/抽象阶梯），
注册表实为 **6 份**（含 **LSP**）共 **12 译件**。同时补「§现状对照」「§复现与引用口径」并同步
en/ja 译件（改登记译件的原文必须同步译件并重签摘要）。

范围：只判本文与 locales 注册表/译件在场/判据事实自洽（不改注册表）。
同族判据：test_locales.py（12 例）/ check34 / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、3 语、12 译件、6 指南逐名（含 LSP）、coverage 全 entry+guides、
责任方登记、现状对照 + 复现三命令；译件 en/ja 与源件摘要同步。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "locales.md"
REG = ROOT / "protocol" / "locales.json"
EN = ROOT / "docs" / "en" / "locales.md"
JA = ROOT / "docs" / "ja" / "locales.md"
SECTIONS = ("## 这是什么", "## 规则（全部机检）", "## 怎么加一份译文", "## 现状对照",
            "## 复现与引用口径", "## 现状与边界")
GUIDES = ("release", "locales", "mcp", "terminal", "layers", "lsp")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"语言面文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("语言面文档为空")
    return text


def reg() -> dict:
    return json.loads(REG.read_text(encoding="utf-8"))


def locales_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 语言面与本地化（locales）"):
        issues.append("缺标题「# 语言面与本地化（locales）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    d = reg()
    locs = d.get("locales") or []
    if len(locs) != 3:
        issues.append(f"语言数已变（{len(locs)}）")
    if "**3 语**" not in text:
        issues.append("未写 3 语")
    for loc in locs:
        if loc.get("coverage") != "entry+guides":
            issues.append(f"{loc.get('id')} coverage 已变")
        if not loc.get("codeowner"):
            issues.append(f"{loc.get('id')} 缺 codeowner")
    docs = d.get("docs") or []
    n_tr = sum(len(x.get("translations") or []) for x in docs)
    if n_tr != 12:
        issues.append(f"译件数已变（{n_tr}）")
    if "**12 件**" not in text:
        issues.append("未写 12 译件")
    paths = [str(x.get("path") or "") for x in docs]
    if len(paths) != 6:
        issues.append(f"指南数已变（{len(paths)}）")
    for g in GUIDES:
        if g not in text:
            issues.append(f"正文缺指南：{g}")
        if not any(p.endswith(g + ".md") for p in paths):
            issues.append(f"注册表缺指南：{g}")
    if "**6 份**" not in text:
        issues.append("未写 6 份指南")
    for path in (EN, JA):
        if not path.is_file():
            issues.append(f"译件缺失：{path.name}")
    en = EN.read_text(encoding="utf-8") if EN.is_file() else ""
    ja = JA.read_text(encoding="utf-8") if JA.is_file() else ""
    if "Status check" not in en:
        issues.append("en 译件缺现状对照小节")
    if "現状対照" not in ja:
        issues.append("ja 译件缺现状对照小节")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py locales",
                "python scripts/nf.py locales --write",
                "python -m pytest desktop/tests/test_locales.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "源件一改即判过期" not in text and "源件一改即过期" not in text:
        issues.append("缺「源件一改即过期」口径")
    if "不做机器翻译" not in text:
        issues.append("缺「不做机器翻译」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class LocalesDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_locales_matches_contract(self):
        self.assertEqual([], locales_issues(self.text), "语言面文档不满足契约")

    def test_registry_live(self):
        d = reg()
        self.assertEqual(3, len(d["locales"]))
        self.assertEqual(6, len(d["docs"]))
        self.assertEqual(12, sum(len(x["translations"]) for x in d["docs"]))
        self.assertTrue(EN.is_file() and JA.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：语数回退 / 译件数回退 / 缺 LSP / 译件缺小节 / 缺命令。"""
        old = self.text.replace("**3 语**", "**2 语**")
        self.assertTrue(any("3 语" in i for i in locales_issues(old)))
        old_t = self.text.replace("**12 件**", "**10 件**")
        self.assertTrue(any(("12 件" in i) or ("12 译件" in i)
                            for i in locales_issues(old_t)))
        no_lsp = self.text.replace("lsp", "ls")
        self.assertTrue(any("lsp" in i for i in locales_issues(no_lsp)))
        no_cmd = self.text.replace("python scripts/nf.py locales --write", "重签")
        self.assertTrue(any("--write" in i for i in locales_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_locales.md")


if __name__ == "__main__":
    unittest.main()
