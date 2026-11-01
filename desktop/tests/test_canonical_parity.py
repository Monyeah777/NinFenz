#!/usr/bin/env python3
"""规范化字节编码的**跨实现一致性**（审计 Z1 F5：canonical 3 套）。

scripts/nf_verify.py 是**独立验证器**（刻意不 import core，供仓库外验证回执），
故它的 canonical_bytes 与 core 的 attest.canonical 是「同一语义、两份文件」。本判据用
夹具把两者钉在一起（审计修订建议 2：跨实现用夹具钉住），并检查 core 内不再有第三份内联实现。
"""
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import attest  # noqa: E402

_spec = importlib.util.spec_from_file_location("nf_verify_script",
 ROOT / "scripts" / "nf_verify.py")
assert _spec is not None and _spec.loader is not None
nf_verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nf_verify)

CORPUS = (
    {},
    {"b": 1, "a": 2},
    {"nested": {"z": [1, 2, {"y": None}], "a": True}},
    [1, 2, 3],
    {"unicode": "宁封子 · NinFenz", "cjk": "中"},
    {"num": 1.5, "neg": -0.0, "big": 10 ** 20},
    {"empty_list": [], "empty_str": "", "null": None},
)


class CanonicalParityTest(unittest.TestCase):
    def test_core_and_standalone_verifier_agree_byte_for_byte(self):
        for obj in CORPUS:
            self.assertEqual(attest.canonical(obj), nf_verify.canonical_bytes(obj),
                             "两份 canonical 语义分叉：%r" % (obj,))

    def test_encoding_is_sorted_and_compact(self):
        # 口径自证：键排序 + 紧凑分隔符 + UTF-8（否则摘要会随构造顺序/空格漂移）。
        self.assertEqual(b'{"a":1,"b":2}', attest.canonical({"b": 2, "a": 1}))
        s = "宁封子 · NinFenz"
        self.assertEqual(s, json.loads(attest.canonical(s).decode("utf-8")),
                         "UTF-8 中文须原样往返（不转义）")
        with self.assertRaises(TypeError):
            attest.canonical({"bad": object()})       # 不可序列化即抛，不静默

    def test_digest_convention_matches_external_computation(self):
        obj = {"chosen": "A01", "state": {"step": 3}}
        want = "sha256:" + hashlib.sha256(
            json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        from core import terminal
        self.assertEqual(want, terminal.surface_digest(obj))

    def test_core_has_no_third_inline_copy(self):
        for rel in ("desktop/src/core/workloop.py", "desktop/src/core/terminal.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("attest.canonical", text, "%s 未走单一实现" % rel)
            self.assertNotIn('separators=(",", ":")', text,
                             "%s 仍有内联 canonical 拷贝（Z1）" % rel)


if __name__ == "__main__":
    unittest.main()
