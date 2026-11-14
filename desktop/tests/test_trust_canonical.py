#!/usr/bin/env python3
"""trust.canonical 判据：与向量集 canonical/domain 族逐条对齐，且与既有签名口径逐字节一致。

为什么有它：canonical 是信任层所有摘要/签名的地基——排序、分隔、Unicode、类型闸门任何一处
漂移都会让「同输入同摘要」在不同语言/不同时间失效。本件做三件事：
1. 吃冻结向量（results/trust/trust_vectors.json）逐条对齐正/反例；
2. 与 **既有** 签名实现（attest.canonical / evidence.canonical）逐字节对照——信任层可单点，
   但不得改变已入仓签名口径；
3. 变异自证：证明「改用默认 json.dumps」会得到不同字节（判据不是同义反复）。
"""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import attest, evidence  # noqa: E402
from core.trust import canonical as tc  # noqa: E402

VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"


def _vectors(family):
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    return [v for v in doc["vectors"] if v["family"] == family]


def _materialize_nonfinite(value):
    """向量用 {"nonfinite": "NaN"} 占位（JSON 不能直接写 NaN）；测试侧还原成真 NaN。"""
    if isinstance(value, dict):
        return {key: float("nan") if key == "nonfinite" else _materialize_nonfinite(sub)
                for key, sub in value.items()}
    if isinstance(value, list):
        return [_materialize_nonfinite(sub) for sub in value]
    return value


class VectorParityTest(unittest.TestCase):
    def test_canonical_vectors(self):
        for vec in _vectors("canonical"):
            value = vec["input"]["value"]
            if vec["expected"]["valid"]:
                raw = tc.canonical_bytes(value)
                self.assertEqual(vec["expected"]["canonical_utf8"], raw.decode(), vec["id"])
                self.assertEqual(vec["expected"]["sha256"], tc.digest_of(value), vec["id"])
            else:
                probe = _materialize_nonfinite(value)
                with self.assertRaises(ValueError) as ctx:
                    tc.canonical_bytes(probe)
                self.assertIn(vec["expected"]["reason"], str(ctx.exception), vec["id"])

    def test_domain_vectors(self):
        for vec in _vectors("domain"):
            tag = vec["input"]["tag"]
            payload = (vec["input"].get("payload_utf8") or "").encode()
            if vec["expected"]["tag_ok"]:
                got = tc.domain_digest(tag, payload)
                self.assertEqual(vec["expected"]["digest"], got, vec["id"])
                self.assertNotEqual(vec["expected"].get("distinct_from"), got, vec["id"])
            else:
                with self.assertRaises(ValueError) as ctx:
                    tc.domain_digest(tag, payload)
                self.assertIn("修复指引", str(ctx.exception), vec["id"])


class ExistingImplParityTest(unittest.TestCase):
    """信任层可以单点，但既有签名口径不得变。"""

    def test_same_bytes_as_attest_and_evidence(self):
        payloads = [
            {"b": 1, "a": 2},
            {"名": "值", "nested": [1, True, None, "x"]},
            {"refs": [{"kind": "evidence", "digest": "a" * 64}], "schema": "nf-entity/1"},
        ]
        for obj in payloads:
            want = tc.canonical_bytes(obj)
            self.assertEqual(want, attest.canonical(obj))
            self.assertEqual(want, evidence.canonical(obj))


class StrictnessTest(unittest.TestCase):
    def test_rejects_every_non_json_type(self):
        bad = [1.5, float("nan"), float("inf"), {"x": 1.5}, {"x": b"bytes"},
               {"x": {1, 2}}, (1, 2), {"x": (1, 2)}, {"x": object()}]
        for value in bad:
            with self.assertRaises(ValueError, msg=repr(value)):
                tc.canonical_bytes(value)

    def test_rejects_non_string_keys(self):
        for value in [{1: "x"}, {None: "x"}]:
            with self.assertRaises(ValueError) as ctx:
                tc.canonical_bytes(value)
            self.assertIn("修复指引", str(ctx.exception))

    def test_rejects_non_finite_even_if_float_slip(self):
        with self.assertRaises(ValueError):
            tc.canonical_text({"x": math.inf})

    def test_accepts_json_scalars_and_big_ints(self):
        cases = [0, -1, 2 ** 63 + 1, True, False, None, "中文", [], {}, [[1], {"a": [2]}]]
        for value in cases:
            self.assertIsInstance(tc.canonical_text(value), str)

    def test_strictness_is_observable(self):
        """变异自证：默认 json.dumps 与 canonical 字节不同（否则判据无意义）。"""
        obj = {"b": 1, "a": "中"}
        self.assertNotEqual(json.dumps(obj).encode(), tc.canonical_bytes(obj))
        self.assertNotEqual(json.dumps(obj, ensure_ascii=False).encode(),
                            tc.canonical_bytes(obj))


class DomainRuleTest(unittest.TestCase):
    def test_tag_and_digest_helpers(self):
        self.assertTrue(tc.is_tag("nf:claim-bundle:v1:leaf"))
        self.assertFalse(tc.is_tag("nf:claim-bundle:leaf"))
        self.assertFalse(tc.is_tag("NF:claim-bundle:v1:leaf"))
        self.assertTrue(tc.is_digest("a" * 64))
        self.assertFalse(tc.is_digest("A" * 64))
        self.assertFalse(tc.is_digest("a" * 63))

    def test_separator_prevents_concatenation_ambiguity(self):
        tag = "nf:claim-bundle:v1:leaf"
        left = tc.domain_digest(tag, b"ab")
        right = tc.domain_digest(tag, b"a\x00b")
        self.assertNotEqual(left, right)

    def test_payload_must_be_bytes(self):
        with self.assertRaises(ValueError) as ctx:
            tc.domain_digest("nf:claim-bundle:v1:leaf", "str")
        self.assertIn("修复指引", str(ctx.exception))

    def test_unknown_tag_is_rejected(self):
        with self.assertRaises(ValueError):
            tc.domain_digest("nf:Claim-Bundle:v1:leaf", b"x")


if __name__ == "__main__":
    unittest.main()
