#!/usr/bin/env python3
"""trust.bundle 判据：Merkle 族向量逐条 + 单 claim 验证（O(log n) / 只读一条）+ 篡改矩阵。

为什么有它：A1 的验收是「只凭 bundle + 单条 proof 验证任一 claim」，且删/改/重排/跨包拼接
必须可检测。本件用冻结向量钉 Merkle 口径，再用**受控访问的 claims 容器**证明单 claim 验证
不遍历全包；篡改矩阵逐行给出期望失败原因。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_schema  # noqa: E402
from core.trust import bundle as tb  # noqa: E402

VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"
BUNDLE_ID = "a" * 64


def _merkle_vectors():
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    return [v for v in doc["vectors"] if v["family"] == "merkle"]


def _claim(n):
    return {"id": f"C-{n:03d}", "type": "evidence", "subject_digest": "b" * 64,
            "payload_digest": "c" * 64}


def _bundle(count=8, bundle_id=BUNDLE_ID):
    return tb.build_bundle(bundle_id, "protocol/trust/claim-bundle.schema.json",
                           [_claim(i) for i in range(count)])


class GuardedClaims(list):
    """记录下标访问；迭代即断言失败（证明单 claim 验证不遍历 claims）。"""

    def __init__(self, items, allowed):
        super().__init__(items)
        self.allowed = allowed
        self.accessed = []

    def __getitem__(self, index):
        self.accessed.append(index)
        assert index in self.allowed, f"越界读取 claims[{index}]"
        return super().__getitem__(index)

    def __iter__(self):
        raise AssertionError("verify_claim 不得遍历全部 claims")


class MerkleVectorTest(unittest.TestCase):
    def test_vectors_match(self):
        for vec in _merkle_vectors():
            if not vec["expected"].get("valid"):
                leaves = [tb.leaf_hash(s.encode()) for s in vec["input"]["leaves_utf8"]]
                with self.assertRaises(IndexError):
                    tb.inclusion_proof(leaves, int(vec["input"]["index"]))
                continue
            payloads = [s.encode() for s in vec["input"]["leaves_utf8"]]
            leaves = [tb.leaf_hash(p) for p in payloads]
            self.assertEqual(vec["expected"]["leaf_hashes"], [leaf.hex() for leaf in leaves],
                             vec["id"])
            root = tb.merkle_root(leaves)
            self.assertEqual(vec["expected"]["root"], root.hex(), vec["id"])
            for proof in vec["expected"]["proofs"]:
                got = tb.inclusion_proof(leaves, proof["index"])
                self.assertEqual(proof["proof"], got, vec["id"])
                self.assertEqual(root.hex(), tb.fold_proof(leaves[proof["index"]].hex(), got),
                                 vec["id"])


class BuildTest(unittest.TestCase):
    def test_bundle_matches_frozen_schema(self):
        schema = tb.load_schema(str(ROOT))
        built = _bundle()
        self.assertEqual("nf-claim-bundle/1", schema["properties"]["schema"]["const"])
        self.assertEqual([], json_schema.json_schema_check(built, schema))

    def test_deterministic(self):
        self.assertEqual(_bundle(), _bundle())

    def test_bundle_id_changes_root(self):
        """bundle_id 进叶：同 claims 换包根必不同（跨包拼接的判据基础）。"""
        other = _bundle(bundle_id="e" * 64)
        self.assertNotEqual(_bundle()["merkle_root"], other["merkle_root"])

    def test_bad_inputs_fail_with_guidance(self):
        bad_calls = [
            lambda: tb.build_bundle("short", "c", [_claim(0)]),
            lambda: tb.build_bundle(BUNDLE_ID, "", [_claim(0)]),
            lambda: tb.build_bundle(BUNDLE_ID, "c", []),
        ]
        for call in bad_calls:
            with self.assertRaises(ValueError) as ctx:
                call()
            self.assertIn("修复指引", str(ctx.exception))

    def test_missing_schema_raises_with_guidance(self):
        with self.assertRaises(ValueError) as ctx:
            tb.load_schema(str(ROOT / "no_such_root_for_claim_bundle"))
        self.assertIn("修复指引", str(ctx.exception))


class SingleClaimTest(unittest.TestCase):
    def test_verify_claim_reads_only_one_claim(self):
        bundle = _bundle(count=16)
        guarded = GuardedClaims(bundle["claims"], allowed={7})
        probe = dict(bundle)
        probe["claims"] = guarded
        got = tb.verify_claim(probe, 7, bundle["inclusion_proofs"][7])
        self.assertTrue(got["ok"], got)
        self.assertEqual([7], guarded.accessed, "单 claim 验证读取了其它 claim")

    def test_proof_sidecar_and_lookup_agree(self):
        bundle = _bundle(count=5)
        via_bundle = tb.verify_claim(bundle, 3)
        via_sidecar = tb.verify_claim(bundle, 3, bundle["inclusion_proofs"][3])
        self.assertEqual(via_bundle, via_sidecar)
        self.assertTrue(via_sidecar["ok"])

    def test_proof_length_is_logarithmic(self):
        for count in (1, 2, 3, 8, 64, 1024):
            bundle = _bundle(count=count)
            for index in (0, count - 1):
                proof = bundle["inclusion_proofs"][index]["proof"]
                self.assertLessEqual(len(proof), count.bit_length(), f"n={count}")
                self.assertTrue(tb.verify_claim(bundle, index)["ok"])


class TamperMatrixTest(unittest.TestCase):
    def setUp(self):
        self.bundle = _bundle(count=6)
        self.schema = tb.load_schema(str(ROOT))

    def test_tampered_claim_leaf_mismatch(self):
        bad = copy.deepcopy(self.bundle)
        bad["claims"][2]["payload_digest"] = "d" * 64
        got = tb.verify_claim(bad, 2)
        self.assertEqual({"ok": False, "reason": "LEAF-MISMATCH"}, got)
        self.assertFalse(tb.verify_bundle(bad)["ok"])

    def test_tampered_bundle_id_leaf_mismatch(self):
        bad = copy.deepcopy(self.bundle)
        bad["bundle_id"] = "e" * 64
        self.assertEqual("LEAF-MISMATCH", tb.verify_claim(bad, 0)["reason"])

    def test_tampered_proof_hash_root_mismatch(self):
        bad = copy.deepcopy(self.bundle)
        steps = bad["inclusion_proofs"][1]["proof"]
        steps[-1]["hash"] = "f" * 64 if steps[-1]["hash"] != "f" * 64 else "e" * 64
        self.assertEqual("ROOT-MISMATCH", tb.verify_claim(bad, 1)["reason"])

    def test_bad_side_and_bad_index(self):
        bad = copy.deepcopy(self.bundle)
        bad["inclusion_proofs"][0]["proof"][0]["side"] = "up"
        self.assertEqual("PROOF-INVALID", tb.verify_claim(bad, 0)["reason"])
        bad2 = copy.deepcopy(self.bundle)
        bad2["inclusion_proofs"][0]["index"] = 1
        self.assertEqual("PROOF-MISSING", tb.verify_claim(bad2, 0)["reason"])
        self.assertEqual("PROOF-INDEX-MISMATCH",
                         tb.verify_claim(bad2, 0, bad2["inclusion_proofs"][0])["reason"])

    def test_forged_root_rejected(self):
        bad = copy.deepcopy(self.bundle)
        bad["merkle_root"] = "0" * 64
        self.assertEqual("ROOT-MISMATCH", tb.verify_claim(bad, 0)["reason"])
        self.assertFalse(tb.verify_bundle(bad)["ok"])

    def test_cross_bundle_splice_rejected(self):
        other = _bundle(bundle_id="e" * 64)
        spliced = copy.deepcopy(self.bundle)
        spliced["merkle_root"] = other["merkle_root"]
        spliced["inclusion_proofs"] = other["inclusion_proofs"]
        self.assertEqual("LEAF-MISMATCH", tb.verify_claim(spliced, 0)["reason"])
        self.assertFalse(tb.verify_bundle(spliced)["ok"])

    def test_reorder_and_delete_detected(self):
        swapped = copy.deepcopy(self.bundle)
        swapped["claims"][1], swapped["claims"][2] = swapped["claims"][2], swapped["claims"][1]
        self.assertFalse(tb.verify_bundle(swapped)["ok"])
        deleted = copy.deepcopy(self.bundle)
        del deleted["claims"][2]
        self.assertFalse(tb.verify_bundle(deleted)["ok"])

    def test_duplicate_claim_id_detected(self):
        bad = copy.deepcopy(self.bundle)
        bad["claims"][1]["id"] = bad["claims"][0]["id"]
        issues = tb.verify_bundle(bad)["issues"]
        self.assertTrue(any("id 重复" in issue for issue in issues), issues)

    def test_missing_proof_coverage_detected(self):
        bad = copy.deepcopy(self.bundle)
        bad["inclusion_proofs"].pop(2)
        issues = tb.verify_bundle(bad)["issues"]
        self.assertTrue(any("未覆盖" in issue for issue in issues), issues)

    def test_valid_bundle_passes(self):
        self.assertTrue(tb.verify_bundle(self.bundle, self.schema)["ok"])


if __name__ == "__main__":
    unittest.main()
