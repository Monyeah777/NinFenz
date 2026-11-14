#!/usr/bin/env python3
"""trust.entity 判据：向量 entity 族逐条对齐 + 结构/准入 fail-closed + 变异自证。

为什么有它：实体准入是 A4 的落点——「未知类型/越权组合默认放行」是计划点名的 P0 风险。
本件吃冻结向量（entity 族）逐条对齐，并用变异自证证明拒绝确实来自 schema/策略两处判据，
而不是碰巧失败。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import entity as te  # noqa: E402

VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"


def _entity_vectors():
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    return [v for v in doc["vectors"] if v["family"] == "entity"]


class VectorParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = te.load_schema(str(ROOT))

    def test_entity_vectors(self):
        vectors = _entity_vectors()
        self.assertGreaterEqual(len(vectors), 5)
        for vec in vectors:
            got = te.admissibility(vec["input"]["entity"], vec["input"]["policy"], self.schema)
            self.assertEqual(vec["expected"], got, vec["id"])


class FailClosedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = te.load_schema(str(ROOT))
        cls.policy = {
            "schema": "nf-trust-policy/1",
            "issuers": [{"id": "nf:local", "keyid": "k", "alg": "ed25519",
                         "types": ["claim", "evidence"]}],
            "algorithms": ["ed25519"],
            "tsa_roots": [],
            "required_level": "T2",
            "anchors": {"tsa": True, "transparency": False, "witness_threshold": 0},
        }
        cls.entity = {
            "schema": "nf-entity/1", "type": "claim",
            "subject": {"kind": "claim", "ref": "results/trust/demo/x.json",
                        "digest": "a" * 64},
            "issuer": "nf:local", "issued_at": "2026-11-14T00:00:00Z",
            "payload_digest": "b" * 64,
        }

    def test_unknown_field_is_schema_invalid(self):
        bad = {**self.entity, "unexpected": 1}
        self.assertTrue(te.validate_entity(bad, self.schema))
        got = te.admissibility(bad, self.policy, self.schema)
        self.assertEqual(te.REASON_SCHEMA, got["reason"])

    def test_unknown_issuer(self):
        bad = {**self.entity, "issuer": "nf:evil"}
        self.assertEqual({"admissible": False, "reason": te.REASON_ISSUER},
                         te.admissibility(bad, self.policy, self.schema))

    def test_type_not_allowed(self):
        bad = {**self.entity, "type": "process-step"}
        self.assertEqual({"admissible": False, "reason": te.REASON_TYPE},
                         te.admissibility(bad, self.policy, self.schema))

    def test_policy_shape_invalid(self):
        for policy in ({}, {"issuers": "nf:local"}, {"issuers": [{}]}):
            self.assertEqual({"admissible": False, "reason": te.REASON_POLICY},
                             te.admissibility(self.entity, policy, self.schema))

    def test_uppercase_digest_and_bad_timestamp_rejected(self):
        for patch in ({"payload_digest": "A" * 64},
                      {"issued_at": "2026-11-14T00:00:00"},
                      {"type": "Claim"},
                      {"type": "claim "}):
            got = te.admissibility({**self.entity, **patch}, self.policy, self.schema)
            self.assertEqual({"admissible": False, "reason": te.REASON_SCHEMA}, got, patch)

    def test_missing_schema_argument_fails_loudly(self):
        with self.assertRaises(ValueError) as ctx:
            te.validate_entity(self.entity)
        self.assertIn("修复指引", str(ctx.exception))
        with self.assertRaises(ValueError):
            te.admissibility(self.entity, self.policy)


class SchemaLoadTest(unittest.TestCase):
    def test_loads_frozen_schema(self):
        schema = te.load_schema(str(ROOT))
        self.assertEqual("nf-entity/1", schema["properties"]["schema"]["const"])
        self.assertIs(False, schema["additionalProperties"])
        self.assertEqual(te.ENTITY_SCHEMA_REL, "protocol/trust/entity.schema.json")

    def test_missing_schema_root_raises_with_guidance(self):
        with self.assertRaises(ValueError) as ctx:
            te.load_schema(str(ROOT / "no_such_root_for_trust_entity"))
        self.assertIn("修复指引", str(ctx.exception))

    def test_resolve_issuer_requires_exact_id(self):
        policy = {"issuers": [{"id": "nf:local", "types": ["claim"]}]}
        self.assertEqual("nf:local", te.resolve_issuer(policy, "nf:local")["id"])
        self.assertIsNone(te.resolve_issuer(policy, "nf:local "))
        self.assertIsNone(te.resolve_issuer(policy, ""))


class MutationProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = te.load_schema(str(ROOT))
        cls.policy = {"issuers": [{"id": "nf:local", "types": ["claim"]}]}
        cls.entity = {
            "schema": "nf-entity/1", "type": "claim",
            "subject": {"kind": "claim", "ref": "r/x.json", "digest": "a" * 64},
            "issuer": "nf:local", "issued_at": "2026-11-14T00:00:00Z",
            "payload_digest": "b" * 64, "unexpected": 1,
        }

    def test_weakening_schema_confirms_keyword_carries_rejection(self):
        weakened = copy.deepcopy(self.schema)
        weakened.pop("additionalProperties")
        self.assertEqual([], te.validate_entity(self.entity, weakened))
        self.assertTrue(te.validate_entity(self.entity, self.schema))

    def test_removing_types_confirms_policy_carries_rejection(self):
        entity = {k: v for k, v in self.entity.items() if k != "unexpected"}
        narrowed = {"issuers": [{"id": "nf:local", "types": []}]}
        got = te.admissibility(entity, narrowed, self.schema)
        self.assertEqual(te.REASON_TYPE, got["reason"])
        self.assertTrue(te.admissibility(entity, self.policy, self.schema)["admissible"])


if __name__ == "__main__":
    unittest.main()
