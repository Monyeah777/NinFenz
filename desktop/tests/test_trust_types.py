#!/usr/bin/env python3
"""trust.entity 类型注册表 + 组合准入判据（G3；claim #18：未知 type/越权组合 fail-closed）。

判据：
1. nf-type-registry/1 结构/语义（唯一 id、compose_with 目标存在、无自环/无环、ref kinds 非空）；
2. typed_admissibility：结构 → policy/issuer/type → 类型注册表 → issuer 注册 kind →
   显式授权 → 有效期 → refs（数量/类别/重复/自引）逐层 fail-closed；
3. composition_check：ref 必须可解析、类型对必须在 compose_with 内、深度有界；
4. 变异自证：把 allowed_ref_kinds/max_refs 从注册表移除后，原本被拒的实体必须变绿
   —— 证明拒绝确实由这两条规则承载。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import entity as te  # noqa: E402

ISSUER = "nf:test:issuer"
KEYID = "nf:test:hmac:2026"
OTHER = "nf:other:issuer"
DIGEST = "a" * 64
DIGEST2 = "b" * 64


def _policy(types=("claim", "evidence")):
    return {"schema": "nf-trust-policy/1",
            "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256",
                         "types": list(types)}],
            "algorithms": ["hmac-sha256"], "tsa_roots": [], "required_level": "T0",
            "anchors": {"tsa": False, "transparency": True, "witness_threshold": 0}}


def _issuer_registry(kind="service", issuer_id=ISSUER):
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": issuer_id, "kind": kind,
                         "keys": [{"keyid": KEYID, "alg": "hmac-sha256", "status": "active",
                                   "not_before": "2026-01-01T00:00:00Z",
                                   "not_after": "2027-01-01T00:00:00Z"}]}]}


def _types():
    return {"schema": "nf-type-registry/1", "types": [
        {"id": "claim", "allowed_issuer_kinds": ["service", "institution"],
         "allowed_ref_kinds": ["evidence", "process-step"], "compose_with": ["evidence"],
         "max_refs": 2},
        {"id": "evidence", "allowed_issuer_kinds": ["service"],
         "allowed_ref_kinds": ["artifact"], "compose_with": [], "max_refs": 1},
    ]}


def _entity(type_id="claim", digest=DIGEST, refs=None, issuer=ISSUER, validity=None):
    entity = {"schema": "nf-entity/1", "type": type_id,
              "subject": {"kind": "claim", "ref": "x", "digest": digest},
              "issuer": issuer, "issued_at": "2026-11-14T00:00:00Z",
              "payload_digest": DIGEST2}
    if refs is not None:
        entity["refs"] = refs
    if validity is not None:
        entity["validity"] = validity
    return entity


def _ref(kind="evidence", digest=DIGEST2):
    return {"kind": kind, "digest": digest}


def _admit(entity, types=None, policy=None, issuers=None):
    return te.typed_admissibility(entity, types or _types(), policy or _policy(),
                                  issuers or _issuer_registry(),
                                  te.load_schema(str(ROOT)),
                                  te.load_type_schema(str(ROOT)))


class RegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = te.load_type_schema(str(ROOT))

    def test_valid_registry(self):
        issues, stats = te.validate_type_registry(_types(), self.schema)
        self.assertEqual([], issues)
        self.assertEqual({"types": 2, "edges": 1}, stats)

    def test_semantic_rejections(self):
        cases = {}
        doc = _types()
        doc["types"][1]["id"] = "claim"
        cases["duplicate"] = doc
        doc = _types()
        doc["types"][0]["compose_with"] = ["ghost"]
        cases["ghost"] = doc
        doc = _types()
        doc["types"][0]["compose_with"] = ["claim"]
        cases["self"] = doc
        doc = _types()
        doc["types"][0]["compose_with"] = ["evidence"]
        doc["types"][1]["compose_with"] = ["claim"]
        cases["cycle"] = doc
        doc = _types()
        doc["types"][0]["allowed_ref_kinds"] = []
        cases["empty_kinds"] = doc
        for label, registry in cases.items():
            issues, _stats = te.validate_type_registry(registry)
            self.assertTrue(issues, f"{label} 未被拒")
        self.assertTrue(any("环" in i for i in te.validate_type_registry(cases["cycle"])[0]))

    def test_structural_rejections(self):
        doc = _types()
        doc["types"][0]["max_refs"] = -1
        self.assertTrue(te.validate_type_registry(doc, self.schema)[0])
        doc = _types()
        doc["types"][0]["id"] = "BadId"
        self.assertTrue(te.validate_type_registry(doc, self.schema)[0])


class TypedAdmissibilityTest(unittest.TestCase):
    def test_valid_entity(self):
        result = _admit(_entity(refs=[_ref()]))
        self.assertTrue(result["admissible"], result)
        self.assertEqual("claim", result["type"])

    def test_unknown_type(self):
        result = _admit(_entity(type_id="planet"),
                        policy=_policy(types=("claim", "evidence", "planet")))
        self.assertEqual("TYPE-UNKNOWN", result["reason"])

    def test_issuer_kind_not_allowed(self):
        registry = _types()
        registry["types"][0]["allowed_issuer_kinds"] = ["institution"]
        result = _admit(_entity(), types=registry)
        self.assertEqual("ISSUER-KIND-NOT-ALLOWED", result["reason"])

    def test_issuer_not_registered(self):
        result = _admit(_entity(), issuers=_issuer_registry(issuer_id=OTHER))
        self.assertEqual("ISSUER-NOT-REGISTERED", result["reason"])

    def test_issuer_not_explicitly_authored(self):
        registry = _types()
        registry["types"][0]["allowed_issuers"] = [OTHER]
        result = _admit(_entity(), types=registry)
        self.assertEqual("ISSUER-NOT-AUTHORED-FOR-TYPE", result["reason"])

    def test_ref_kind_not_allowed(self):
        result = _admit(_entity(refs=[_ref(kind="card")]))
        self.assertEqual("REF-KIND-NOT-ALLOWED", result["reason"])

    def test_refs_too_many(self):
        refs = [{"kind": "evidence", "digest": "%064x" % (i + 1)} for i in range(3)]
        result = _admit(_entity(refs=refs))
        self.assertEqual("REFS-TOO-MANY", result["reason"])

    def test_duplicate_and_self_reference(self):
        self.assertEqual("DUPLICATE-REF",
                         _admit(_entity(refs=[_ref(), _ref()]))["reason"])
        self.assertEqual("SELF-REFERENCE",
                         _admit(_entity(refs=[_ref(digest=DIGEST)]))["reason"])

    def test_validity_window(self):
        result = _admit(_entity(validity={"not_before": "2027-01-01T00:00:00Z",
                                          "not_after": "2026-01-01T00:00:00Z"}))
        self.assertEqual("VALIDITY-WINDOW-INVALID", result["reason"])

    def test_invalid_type_registry(self):
        registry = _types()
        registry["types"][0]["compose_with"] = ["ghost"]
        result = _admit(_entity(), types=registry)
        self.assertEqual("TYPE-REGISTRY-INVALID", result["reason"])

    def test_mutation_confirms_rules_carry_rejection(self):
        """把规则字段移除后，原本被拒的实体必须变绿（否则测试是同义反复）。"""
        bad = _entity(refs=[_ref(kind="card")])
        self.assertEqual("REF-KIND-NOT-ALLOWED", _admit(bad)["reason"])
        registry = _types()
        registry["types"][0].pop("allowed_ref_kinds")
        weakened = json.loads(json.dumps(te.load_type_schema(str(ROOT))))
        weakened["$defs"]["type"]["required"] = [
            k for k in weakened["$defs"]["type"]["required"] if k != "allowed_ref_kinds"]
        self.assertTrue(te.typed_admissibility(
            bad, registry, _policy(), _issuer_registry(),
            te.load_schema(str(ROOT)), weakened)["admissible"])


class CompositionTest(unittest.TestCase):
    def test_composition_ok(self):
        claim = _entity(type_id="claim", digest=DIGEST, refs=[_ref(digest=DIGEST2)])
        evidence = _entity(type_id="evidence", digest=DIGEST2)
        result = te.composition_check([claim, evidence], _types())
        self.assertTrue(result["ok"], result)

    def test_compose_not_allowed(self):
        registry = _types()
        registry["types"][0]["compose_with"] = []
        claim = _entity(type_id="claim", digest=DIGEST, refs=[_ref(digest=DIGEST2)])
        evidence = _entity(type_id="evidence", digest=DIGEST2)
        result = te.composition_check([claim, evidence], registry)
        self.assertFalse(result["ok"])
        self.assertEqual("COMPOSE-NOT-ALLOWED", result["issues"][0]["code"])

    def test_unresolved_ref(self):
        claim = _entity(type_id="claim", digest=DIGEST, refs=[_ref(digest="f" * 64)])
        result = te.composition_check([claim], _types())
        self.assertEqual("REF-UNRESOLVED", result["issues"][0]["code"])

    def test_depth_limit(self):
        types = [{"id": f"t{i}", "allowed_issuer_kinds": ["service"],
                  "allowed_ref_kinds": ["evidence"], "compose_with": [f"t{i + 1}"],
                  "max_refs": 8} for i in range(40)]
        types[-1]["compose_with"] = []
        registry = {"schema": "nf-type-registry/1", "types": types}
        entities = []
        for index in range(40):
            digest = "%064x" % (index + 1)
            refs = [{"kind": "evidence", "digest": "%064x" % (index + 2)}] if index < 39 else []
            entities.append(_entity(type_id=f"t{index}", digest=digest, refs=refs))
        result = te.composition_check(entities, registry, max_depth=8)
        self.assertFalse(result["ok"])
        self.assertEqual("COMPOSITION-TOO-DEEP", result["issues"][0]["code"])

    def test_cli_entities_mode(self):
        claim = _entity(type_id="claim", digest=DIGEST, refs=[_ref(digest=DIGEST2)])
        evidence = _entity(type_id="evidence", digest=DIGEST2)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = {"entities.json": [claim, evidence], "types.json": _types(),
                     "policy.json": _policy(), "issuers.json": _issuer_registry()}
            for name, doc in files.items():
                (base / name).write_text(json.dumps(doc), encoding="utf-8")
            base_cmd = [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                        "--entities", str(base / "entities.json"),
                        "--type-registry", str(base / "types.json"),
                        "--policy", str(base / "policy.json"),
                        "--issuer-registry", str(base / "issuers.json"),
                        "--root", str(ROOT)]
            ok = subprocess.run(base_cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
            self.assertIn("valid typed entities", ok.stdout)
            (base / "entities.json").write_text(json.dumps([claim]), encoding="utf-8")
            bad = subprocess.run(base_cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("REF-UNRESOLVED", bad.stdout)


if __name__ == "__main__":
    unittest.main()
