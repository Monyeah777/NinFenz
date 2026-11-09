"""台账表格自洽判据：序号连续、红绿不混（第 198 轮）。

由来（第 181 轮）：`release-conclusion.md` 的绿表里曾混着两条红，其中 `cb4ce9e9` 还占了序号 10，
与真正的第 10 个绿重号。当时靠人工 + 日志比对才查出来——本件把这类「表内自洽」变成常驻判据。

边界：只查**表内**自洽（序号、红绿不交叠），不查与日志一致（日志在仓库外，判据不得依赖外部状态）。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "ccos" / "release-conclusion.md"


def parse_green_rows(text: str) -> list:
    """→ [(序, HEAD)]；输入不合法时抛 ValueError（供变异自证使用）。"""
    if "## 绿结论台账" not in text:
        raise ValueError("文档里找不到「## 绿结论台账」小节")
    seg = text[text.index("## 绿结论台账"):]
    end = seg.find("\n## ", 1)
    if end > 0:
        seg = seg[:end]
    rows = re.findall(r"^\|\s*(\d+)\s*\|\s*`([0-9a-f]{6,12})`", seg, re.MULTILINE)
    if not rows:
        raise ValueError("绿表里没有解析到任何行（表头或格式变了？）")
    return [(int(n), h) for n, h in rows]


def parse_red_heads(text: str) -> list:
    """→ 红表里的 HEAD 列表；缺红表时抛 ValueError。"""
    if "## 红结论台账" not in text:
        raise ValueError("文档里找不到「## 红结论台账」小节")
    seg = text[text.index("## 红结论台账"):]
    end = seg.find("\n## ", 1)
    if end > 0:
        seg = seg[:end]
    return re.findall(r"^\|\s*`([0-9a-f]{6,12})`", seg, re.MULTILINE)


class LedgerTablesTest(unittest.TestCase):
    def _text(self) -> str:
        return DOC.read_text(encoding="utf-8")

    def test_green_numbering_is_contiguous(self):
        rows = parse_green_rows(self._text())
        numbers = [n for n, _ in rows]
        self.assertEqual(list(range(1, len(rows) + 1)), numbers,
                         "绿表序号必须从 1 连续递增（重号/跳号说明混进了别的行）")

    def test_red_heads_do_not_appear_in_green(self):
        text = self._text()
        green = {h for _, h in parse_green_rows(text)}
        red = set(parse_red_heads(text))
        self.assertTrue(red, "红表为空（判据可能已失效）")
        self.assertEqual(set(), green & red, "同一 HEAD 不能既在绿表又在红表")

    def test_parser_rejects_malformed_input(self):
        """变异自证：缺小节 / 空表必须抛错，而不是静默返回空列表。"""
        with self.assertRaises(ValueError):
            parse_green_rows("没有小节" * 3)
        with self.assertRaises(ValueError):
            parse_green_rows("## 绿结论台账\n\n| 序 | HEAD |\n" * 2)
        with self.assertRaises(ValueError):
            parse_red_heads("没有小节" * 3)


if __name__ == "__main__":
    unittest.main()
