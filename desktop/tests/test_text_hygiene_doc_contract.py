#!/usr/bin/env python3
"""docs/text-hygiene.md 契约：文本卫生文档必须「5 条规则 / 4399 文本 / 1240 JSON / 269070 键」自洽。

为什么必须有：这页是「编码与标识面」的口径来源——四类编码缺陷 + 一条版本形态，任何一条漏记，
读者就会以为「没检查」或「检查了别的」。本轮发现真实漏记：实现里有第 5 条 SemVer 形态规则
（semver_issue，versions_checked=111），正文此前完全没提；已补并加「§现状对照」「§复现与引用口径」。

范围：只判本文与 core/text_hygiene 实现/扫描统计事实自洽（不改实现）。
同族判据：test_text_hygiene.py / test_doc_hygiene.py / test_live_doc_counts.py。
契约：最后更新位 + 复核、5 条规则（含 SemVer）、不产 WARN 口径、扫描统计逐值、
排除面与二进制跳过、现状对照 + 复现两命令。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import text_hygiene as th  # noqa: E402

DOC = ROOT / "docs" / "text-hygiene.md"
SECTIONS = ("## 是什么", "## 判据", "## 怎么用", "## 现状对照",
            "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"文本卫生文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("文本卫生文档为空")
    return text


def stats() -> dict:
    _issues, data = th.scan(str(ROOT))
    return data


def hygiene_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 编码与标识面卫生"):
        issues.append("缺标题「# 编码与标识面卫生（text-hygiene）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    rules = ("UTF-8", "LF", "唯一", "NFC", "SemVer")
    for rule in rules:
        if rule not in text:
            issues.append(f"规则缺：{rule}")
    if "**5**" not in text:
        issues.append("未写 5 条规则")
    if "不产 WARN" not in text:
        issues.append("缺「不产 WARN」纪律")
    s = stats()
    for key, label in (("text", "**4399**"), ("json", "**1240**"),
                       ("keys_checked", "**269070**"),
                       ("versions_checked", "**111**")):
        if key not in s:
            issues.append(f"扫描 stats 缺键：{key}")
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    if s.get("bom") != 0 or s.get("crlf") != 0:
        issues.append(f"BOM/CRLF 非零（{s.get('bom')}/{s.get('crlf')}）")
    if "BOM **0**" not in text or "CRLF **0**" not in text:
        issues.append("未写 BOM/CRLF 为 0")
    if "违规 **0**" not in text:
        issues.append("未写违规 0")
    if not hasattr(th, "semver_issue"):
        issues.append("实现缺 semver_issue")
    if ".rivet" not in text:
        issues.append("缺排除面说明（.rivet）")
    positions = [text.find(sec) for sec in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("cd desktop/src && python -m core.text_hygiene ../..",
                "python scripts/nf.py doctor"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class TextHygieneDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_hygiene_matches_contract(self):
        self.assertEqual([], hygiene_issues(self.text), "文本卫生文档不满足契约")

    def test_scan_live(self):
        s = stats()
        self.assertEqual(0, s["issues"])
        self.assertEqual(0, s["bom"])
        self.assertEqual(0, s["crlf"])
        self.assertGreater(s["versions_checked"], 0)
        self.assertFalse(th.semver_issue("1.2.3"))

    def test_contract_catches_mutations(self):
        """变异自证：漏 SemVer 规则 / 统计回退 / 缺不产 WARN / 缺排除面 / 缺命令。"""
        no_semver = self.text.replace("SemVer", "版本")
        self.assertTrue(any("SemVer" in i for i in hygiene_issues(no_semver)))
        old = self.text.replace("**4399**", "**4300**")
        self.assertTrue(any("4399" in i for i in hygiene_issues(old)))
        no_warn = self.text.replace("不产 WARN", "偶发 WARN")
        self.assertTrue(any("不产 WARN" in i for i in hygiene_issues(no_warn)))
        no_ex = self.text.replace(".rivet", "隐藏目录")
        self.assertTrue(any(".rivet" in i for i in hygiene_issues(no_ex)))
        no_cmd = self.text.replace("python scripts/nf.py doctor", "体检")
        self.assertTrue(any("doctor" in i for i in hygiene_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_hygiene.md")


if __name__ == "__main__":
    unittest.main()
