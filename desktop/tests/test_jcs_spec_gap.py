# -*- coding: utf-8 -*-
"""P-C1：canonical JSON 面的**规范-实现分歧**判据（RFC 8785 vs 仓库口径）。

发现（2026-10-11）：core/attest.canonical 用 Python 字符串排序（**码点序**），
而 RFC 8785 §3.2.3 要求按 **UTF-16 码元序** 排键。两者在「星平面键 vs U+E000..U+FFFF 键」
上顺序相反 ⇒ 同一文档在两套实现下得到**不同规范化字节**（跨语言摘要会分叉）。
本判据把这个分歧**钉死**：将来若有人把仓库口径改成 JCS，这里会红并提示更新 §23.29。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import attest  # noqa: E402


def _utf16_key(s: str) -> bytes:
    """RFC 8785 §3.2.3：按 UTF-16 码元序列排序。"""
    return s.encode("utf-16-be")


class JcsSpecGapTest(unittest.TestCase):
    def test_ascii_case_agrees(self):
        doc = {"b": 1, "a": 2}
        self.assertEqual('{"a":2,"b":1}', attest.canonical(doc).decode("utf-8"))

    def test_astral_key_order_differs_from_spec(self):
        doc = {"\ufffd": 1, "\U0001F600": 2}          # FFFD（BMP） vs 😀（星平面）
        repo = attest.canonical(doc).decode("utf-8")
        keys = sorted(doc, key=_utf16_key)
        jcs = json.dumps({k: doc[k] for k in keys}, ensure_ascii=False, separators=(",", ":"))
        self.assertNotEqual(
            repo, jcs,
            "仓库口径已与 JCS 一致——请更新本记录与计划 §23.29（SPEC-GAP 已闭合）")
        self.assertTrue(repo.startswith('{"\ufffd"'), repo)
        self.assertTrue(jcs.startswith('{"\U0001F600"'), jcs)

    def test_number_and_escape_forms_match_spec(self):
        doc = {"n": [1, 1.5, 1e30], "s": "x\ny"}
        got = attest.canonical(doc).decode("utf-8")
        self.assertEqual('{"n":[1,1.5,1e+30],"s":"x\\ny"}', got)


    def test_integer_valued_float_differs_from_spec(self):
        """差异类 B（D-10 影响评估实测 7/79 文档命中）：Python 发 1.0，JCS 发 1。"""
        repo = attest.canonical({"v": 1.0}).decode("utf-8")
        self.assertEqual('{"v":1.0}', repo)
        self.assertNotEqual('{"v":1}', repo,
                            "仓库口径已与 JCS 数值形态一致——请更新计划 §23.31 与 D-10")

    def test_exponent_leading_zero_differs_from_spec(self):
        """差异类 B 之二：Python 1e-07，ES6/JCS 1e-7。"""
        repo = attest.canonical({"v": 1e-07}).decode("utf-8")
        self.assertEqual('{"v":1e-07}', repo)
        self.assertNotEqual('{"v":1e-7}', repo,
                            "指数形态已变——请更新计划 §23.31 与 D-10")


if __name__ == "__main__":
    unittest.main()
