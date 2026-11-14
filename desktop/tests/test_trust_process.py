#!/usr/bin/env python3
"""trust.process 判据：process 向量族逐条 + prev 链/seq/创世约定 + 删改重排反例。

为什么有它：A2 的验收是「步骤前向绑定，删/改/重排可检测」。本件用冻结向量钉摘要口径与
失败原因，并用 append/validate 两面覆盖结构（schema）与链序（prev/seq）两层判据。
"""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_schema  # noqa: E402
from core.trust import process as tp  # noqa: E402
from core.trust.canonical import canonical_bytes  # noqa: E402

VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"
ACTOR = {"id": "nf:agent:t", "kind": "agent"}
AUTH = {"kind": "human", "digest": "d" * 64}
STATE = ["1" * 64, "2" * 64, "3" * 64]


def _process_vectors():
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    return [v for v in doc["vectors"] if v["family"] == "process"]


def _chain(count=3):
    steps = []
    for index in range(count):
        steps.append(tp.append_step(steps, "proc-test", ACTOR, AUTH, STATE[index % 3],
                                    "task-step"))
    return steps


class VectorParityTest(unittest.TestCase):
    def test_process_vectors(self):
        vectors = _process_vectors()
        self.assertGreaterEqual(len(vectors), 4)
        for vec in vectors:
            self.assertEqual(vec["expected"], tp.verify_chain(vec["input"]["steps"]),
                             vec["id"])


class ChainBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tp.load_schema(str(ROOT))

    def test_built_chain_is_valid_and_schema_compliant(self):
        steps = _chain()
        result = tp.verify_chain(steps)
        self.assertTrue(result["valid"], result)
        self.assertEqual(steps[-1]["prev"], result["digests"][-2])
        self.assertEqual(result["digests"][-1], result["head"])
        for step in steps:
            self.assertEqual([], json_schema.json_schema_check(step, self.schema))
        self.assertEqual([], tp.validate_steps(steps, self.schema))

    def test_genesis_prev_is_zero_digest(self):
        self.assertEqual(tp.ZERO_DIGEST, tp.chain_head([]))
        self.assertEqual("0" * 64, _chain(1)[0]["prev"])
        self.assertEqual(1, _chain(1)[0]["step"])

    def test_deterministic(self):
        self.assertEqual(_chain(), _chain())

    def test_chain_head_raises_on_bad_chain(self):
        steps = _chain()
        steps[1]["state_digest"] = "9" * 64
        with self.assertRaises(ValueError) as ctx:
            tp.chain_head(steps)
        self.assertIn("修复指引", str(ctx.exception))

    def test_append_step_guards(self):
        steps = _chain(1)
        with self.assertRaises(ValueError):
            tp.append_step(steps, "proc-test", ACTOR, AUTH, "bad", "task-step")
        steps[0]["prev"] = "ABC"
        with self.assertRaises(ValueError) as ctx:
            tp.append_step(steps, "proc-test", ACTOR, AUTH, "1" * 64, "task-step")
        self.assertIn("修复指引", str(ctx.exception))


class DigestRuleTest(unittest.TestCase):
    def test_domain_separation(self):
        step = _chain(1)[0]
        plain = hashlib.sha256(canonical_bytes(step)).hexdigest()
        self.assertNotEqual(plain, tp.step_digest(step))
        self.assertEqual(tp.step_digest(step), tp.verify_chain([step])["digests"][0])

    def test_field_changes_change_digest(self):
        step = _chain(1)[0]
        base = tp.step_digest(step)
        for patch in ({"process_id": "proc-other"}, {"type": "other-step"},
                      {"state_digest": "f" * 64}):
            self.assertNotEqual(base, tp.step_digest({**step, **patch}), patch)

    def test_missing_fields_fail_closed(self):
        step = _chain(1)[0]
        for field in tp.STEP_FIELDS:
            broken = {k: v for k, v in step.items() if k != field}
            with self.assertRaises(ValueError) as ctx:
                tp.step_digest(broken)
            self.assertIn("修复指引", str(ctx.exception), field)
        with self.assertRaises(ValueError):
            tp.step_digest("not-a-step")


class TamperMatrixTest(unittest.TestCase):
    def test_tampered_state_digest_detected(self):
        steps = _chain()
        steps[1]["state_digest"] = "9" * 64
        self.assertEqual({"valid": False, "reason": "PREV-MISMATCH"}, tp.verify_chain(steps))

    def test_deleted_middle_detected(self):
        steps = _chain()
        del steps[1]
        self.assertEqual({"valid": False, "reason": "SEQ-ORDER"}, tp.verify_chain(steps))

    def test_reorder_detected(self):
        steps = _chain()
        steps[1], steps[2] = steps[2], steps[1]
        self.assertEqual({"valid": False, "reason": "SEQ-ORDER"}, tp.verify_chain(steps))

    def test_bad_prev_format_detected(self):
        steps = _chain()
        steps[1]["prev"] = "ABC"
        self.assertEqual({"valid": False, "reason": "PREV-FORMAT"}, tp.verify_chain(steps))

    def test_wrong_genesis_prev_detected(self):
        steps = _chain()
        steps[0]["prev"] = "1" * 64
        self.assertEqual({"valid": False, "reason": "PREV-MISMATCH"}, tp.verify_chain(steps))

    def test_non_object_step_detected(self):
        steps = _chain()
        steps[1] = "oops"
        self.assertEqual({"valid": False, "reason": "STEP-NOT-OBJECT"}, tp.verify_chain(steps))

    def test_empty_chain_rejected(self):
        self.assertEqual({"valid": False, "reason": "STEPS-EMPTY"}, tp.verify_chain([]))

    def test_local_recompute_boundary_is_honest(self):
        """就地改摘要后重算，链仍自洽——这是 G2 签名/外锚存在的理由，不是缺陷。"""
        steps = _chain(1)
        steps[0]["state_digest"] = "9" * 64
        self.assertTrue(tp.verify_chain(steps)["valid"])
        extended = [steps[0], tp.append_step(steps, "p", ACTOR, AUTH, "2" * 64, "task-step")]
        self.assertTrue(tp.verify_chain(extended)["valid"])


class SchemaStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tp.load_schema(str(ROOT))

    def test_unknown_field_and_bad_enums_caught(self):
        steps = _chain()
        extra = copy.deepcopy(steps)
        extra[0]["unexpected_extension"] = 1
        self.assertTrue(any("多余字段" in issue for issue in tp.validate_steps(extra, self.schema)))
        bad_actor = copy.deepcopy(steps)
        bad_actor[0]["actor"] = {"id": "x", "kind": "robot"}
        self.assertTrue(any("枚举" in issue for issue in tp.validate_steps(bad_actor, self.schema)))
        bad_seq = copy.deepcopy(steps)
        bad_seq[0]["step"] = 2
        self.assertTrue(any("应为 1" in issue for issue in tp.validate_steps(bad_seq, self.schema)))

    def test_weakening_schema_confirms_keyword_carries_rejection(self):
        steps = _chain(1)
        steps[0]["unexpected_extension"] = 1
        weakened = copy.deepcopy(self.schema)
        weakened.pop("additionalProperties")
        self.assertEqual([], [i for i in tp.validate_steps(steps, weakened) if "多余字段" in i])
        self.assertTrue(any("多余字段" in issue
                            for issue in tp.validate_steps(steps, self.schema)))

    def test_missing_schema_raises_with_guidance(self):
        with self.assertRaises(ValueError) as ctx:
            tp.load_schema(str(ROOT / "no_such_root_for_process"))
        self.assertIn("修复指引", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
