#!/usr/bin/env python3
"""Trust Fabric schema 门禁（WP-01/21/23/30/31/32/33）：13 件 IDL、正/反样例与变异自证。

判据（计划 §7.2 数据与协议 / §12.2 禁止项 / §14.3 DoD）：
1. 13 件 trust schema 在 protocol/trust/，文件名、$id、数据版本名（nf-xxx/1）三者一致；
2. 每件有正样例（过）与反样例（拒），且反例失败原因命中预期（不是碰巧被拒）；
3. 变异自证：弱化 additionalProperties / pattern / minItems 后，对应负例必须变绿
   —— 证明测试不是同义反复；
4. 校验器面：用仓内 core.json_schema 叶子件（纯标准库）判定；它上报的
   "不支持关键字" 必须为空（schema 不得依赖未实现语义）；装了 jsonschema 时
   与标准 draft 2020-12 实现同判（可选对照，缺依赖则跳过）。

失败即意味 IDL 与计划 §7.2 的不变量脱钩（例如未知字段默认放行、锚集合可为空）。
"""
import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_schema as js  # noqa: E402

SCHEMA_DIR = ROOT / "protocol" / "trust"
FIX = ROOT / "desktop" / "tests" / "fixtures" / "trust" / "schemas"
VALID = FIX / "valid"
INVALID = FIX / "invalid"

#: schema 文件 → (正样例, 数据版本名)
SCHEMAS = {
    "entity.schema.json": ("entity.json", "nf-entity/1"),
    "dsse.schema.json": ("dsse.json", "nf-dsse/1"),
    "process.schema.json": ("process.json", "nf-process/1"),
    "claim-bundle.schema.json": ("claim-bundle.json", "nf-claim-bundle/1"),
    "anchor.schema.json": ("anchor.json", "nf-anchor/1"),
    "policy.schema.json": ("policy.json", "nf-trust-policy/1"),
    "verify.schema.json": ("verify.json", "nf-verify/1"),
    "keys.schema.json": ("keys.json", "nf-issuer-registry/1"),
    "chain-head.schema.json": ("chain-head.json", "nf-chain-head/1"),
    "type-registry.schema.json": ("type-registry.json", "nf-type-registry/1"),
    "model-card.schema.json": ("model-card.json", "nf-model-card/1"),
    "context-lineage.schema.json": ("context-lineage.json", "nf-context-lineage/1"),
    "human-review.schema.json": ("human-review.json", "nf-human-review/1"),
}

#: 反例文件 → (对应 schema, 期望错误片段)。片段取自 core.json_schema 的错误消息（固定文案）。
INVALID_CASES = {
    "entity-unknown-field.json": ("entity.schema.json", "多余字段"),
    "entity-bad-digest.json": ("entity.schema.json", "不匹配 pattern"),
    "dsse-empty-signatures.json": ("dsse.schema.json", "元素数 < 1"),
    "dsse-bad-payload.json": ("dsse.schema.json", "不匹配 pattern"),
    "process-prev-empty.json": ("process.schema.json", "不匹配 pattern"),
    "process-step-zero.json": ("process.schema.json", ">="),
    "claim-bundle-missing-proofs.json": ("claim-bundle.schema.json", "缺必填字段"),
    "claim-bundle-bad-side.json": ("claim-bundle.schema.json", "不在枚举内"),
    "anchor-empty.json": ("anchor.schema.json", "元素数 < 1"),
    "anchor-unknown-kind.json": ("anchor.schema.json", "oneOf"),
    "anchor-missing-token.json": ("anchor.schema.json", "oneOf"),
    "policy-unknown-alg.json": ("policy.schema.json", "不在枚举内"),
    "policy-level-t5.json": ("policy.schema.json", "不在枚举内"),
    "verify-no-scoring-false.json": ("verify.schema.json", "应为常量"),
    "verify-issue-missing-fix.json": ("verify.schema.json", "缺必填字段"),
    "keys-bad-keyid.json": ("keys.schema.json", "不匹配 pattern"),
    "keys-empty-keys.json": ("keys.schema.json", "元素数 < 1"),
    "keys-unknown-status.json": ("keys.schema.json", "不在枚举内"),
    "keys-bad-time.json": ("keys.schema.json", "不匹配 pattern"),
    "chain-head-bad-kind.json": ("chain-head.schema.json", "不在枚举内"),
    "chain-head-bad-digest.json": ("chain-head.schema.json", "不匹配 pattern"),
    "type-registry-empty-ref-kinds.json": ("type-registry.schema.json", "元素数 < 1"),
    "type-registry-bad-ref-kind.json": ("type-registry.schema.json", "不在枚举内"),
    "model-card-unregistered.json": ("model-card.schema.json", "应为常量"),
    "model-card-bad-digest.json": ("model-card.schema.json", "不匹配 pattern"),
    "context-lineage-bad-head.json": ("context-lineage.schema.json", "不匹配 pattern"),
    "context-lineage-missing-prev.json": ("context-lineage.schema.json", "缺必填字段"),
    "human-review-bad-decision.json": ("human-review.schema.json", "不在枚举内"),
    "human-review-not-human.json": ("human-review.schema.json", "应为常量"),
}

try:  # 可选对照依赖（pyproject ci extra）；核心运行面不依赖它
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover - 无依赖环境的预期路径
    Draft202012Validator = None


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _check(instance, schema):
    """仓内叶子校验器：返回 (错误清单, 不支持关键字清单)。"""
    unsupported = []
    errors = js.json_schema_check(instance, schema, unsupported=unsupported)
    return errors, unsupported


def _walk(node, key):
    """递归收集某关键字的所有取值。"""
    out = []
    if isinstance(node, dict):
        if key in node:
            out.append(node[key])
        for value in node.values():
            out.extend(_walk(value, key))
    elif isinstance(node, list):
        for value in node:
            out.extend(_walk(value, key))
    return out


class TrustSchemaMetaTest(unittest.TestCase):
    """13 件 schema 的元结构与计划不变量。"""

    @classmethod
    def setUpClass(cls):
        cls.docs = {name: _read(SCHEMA_DIR / name) for name in SCHEMAS}

    def test_all_thirteen_present_and_exact(self):
        on_disk = sorted(p.name for p in SCHEMA_DIR.glob("*.json"))
        self.assertEqual(sorted(SCHEMAS), on_disk, "protocol/trust 的 schema 集合必须恰为 13 件")

    def test_id_schema_and_versioned_name(self):
        for name, (_sample, versioned) in SCHEMAS.items():
            doc = self.docs[name]
            self.assertEqual("https://ninfenz.dev/trust/" + name, doc.get("$id"), name)
            self.assertEqual(
                "https://json-schema.org/draft/2020-12/schema", doc.get("$schema"), name
            )
            self.assertEqual("object", doc.get("type"), name)
            self.assertEqual(versioned, doc["properties"]["schema"]["const"],
                             f"{name} 的数据版本名与文件不符")

    def test_fail_closed_by_default(self):
        for name in SCHEMAS:
            doc = self.docs[name]
            self.assertIs(False, doc.get("additionalProperties"), f"{name} 未封未知字段")
            self.assertTrue(doc.get("required"), f"{name} 缺 required")

    def test_no_placeholder_debt(self):
        for name in SCHEMAS:
            text = (SCHEMA_DIR / name).read_text(encoding="utf-8")
            for word in ("TODO", "FIXME", "NotImplemented"):
                self.assertNotIn(word, text, f"{name} 含 {word}（trust 路径不允许占位债）")

    def test_validators_need_no_unsupported_keyword(self):
        """仓内叶子件必须能完整兑现 schema 语义（不支持关键字上报为空）。"""
        for name, (sample, _v) in SCHEMAS.items():
            _errors, unsupported = _check(_read(VALID / sample), self.docs[name])
            self.assertEqual([], unsupported, f"{name} 使用了叶子件不支持的语义")

    def test_patterns_are_anchored(self):
        for name, doc in self.docs.items():
            for pat in _walk(doc, "pattern"):
                self.assertTrue(pat.startswith("^") and pat.endswith("$"),
                                f"{name} 的 pattern 未锚定：{pat!r}")

    def test_digest_and_timestamp_formats_single_source(self):
        digest_pats = set()
        for doc in self.docs.values():
            for pat in _walk(doc, "pattern"):
                if re.fullmatch(r"\^\[0-9a-f\]\{64\}\$", pat):
                    digest_pats.add(pat)
        self.assertEqual({"^[0-9a-f]{64}$"}, digest_pats, "摘要 pattern 必须唯一且为小写 hex")
        ts_pat = "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
        entity_pats = set(_walk(self.docs["entity.schema.json"], "pattern"))
        self.assertIn(ts_pat, entity_pats, "时间戳 pattern 必须为 UTC 秒级 ISO-8601")

    def test_claim_bundle_invariants(self):
        doc = self.docs["claim-bundle.schema.json"]
        self.assertIn("bundle_id", doc["required"], "bundle_id 必填（叶域分隔/splice 防护）")
        ref = doc["properties"]["bundle_id"]["$ref"]
        self.assertEqual("#/$defs/digest", ref)
        self.assertEqual("^[0-9a-f]{64}$", doc["$defs"]["digest"]["pattern"])
        proof = doc["properties"]["inclusion_proofs"]["items"]["properties"]["proof"]
        self.assertEqual(64, proof["maxItems"], "proof 深度上限 64（O(log n) 与 DoS 上限）")
        self.assertEqual(1, doc["properties"]["claims"]["minItems"])

    def test_anchor_is_closed_four_way_oneof(self):
        anchor = self.docs["anchor.schema.json"]
        self.assertEqual(1, anchor["properties"]["anchors"]["minItems"])
        variants = anchor["$defs"]["anchor"]["oneOf"]
        self.assertEqual(4, len(variants), "四类锚（rfc3161/STH/witness/git-commit）")
        kinds = sorted(v["properties"]["kind"]["const"] for v in variants)
        self.assertEqual(["git-commit", "rfc3161", "transparency-sth", "witness"], kinds)

    def test_dsse_minimum_one_signature(self):
        doc = self.docs["dsse.schema.json"]
        self.assertEqual(1, doc["properties"]["signatures"]["minItems"])
        self.assertIn("signatures", doc["required"])

    def test_policy_levels_and_no_scoring(self):
        levels = self.docs["policy.schema.json"]["properties"]["required_level"]["enum"]
        self.assertEqual(["T0", "T1", "T2", "T3", "T4"], levels)
        self.assertIs(True, self.docs["verify.schema.json"]["properties"]["no_scoring"]["const"],
                      "no_scoring 必须恒为 true（不把评分写回运行时）")

    def test_process_step_and_prev(self):
        doc = self.docs["process.schema.json"]
        self.assertEqual(1, doc["properties"]["step"]["minimum"])
        self.assertIn("prev", doc["required"])

    def test_human_review_invariants(self):
        doc = self.docs["human-review.schema.json"]
        self.assertEqual("human",
                         doc["properties"]["reviewer"]["properties"]["kind"]["const"])
        self.assertEqual(["approve", "reject", "escalate"],
                         doc["properties"]["decision"]["enum"])
        self.assertIn("rationale", doc["required"])

    def test_context_lineage_invariants(self):
        doc = self.docs["context-lineage.schema.json"]
        seg = doc["$defs"]["segment"]
        self.assertEqual(["seq", "role", "content_digest", "prev", "digest"], seg["required"])
        self.assertEqual(["system", "user", "assistant", "tool"],
                         seg["properties"]["role"]["enum"])
        self.assertEqual(1, doc["properties"]["segments"]["minItems"])

    def test_model_card_pinned_invariants(self):
        doc = self.docs["model-card.schema.json"]
        protocol = doc["properties"]["eval_protocol"]["properties"]
        self.assertIs(True, protocol["pre_registered"]["const"])
        self.assertIs(True, protocol["score_forbidden"]["const"])
        self.assertIn("model_digest", doc["required"])

    def test_type_registry_invariants(self):
        doc = self.docs["type-registry.schema.json"]
        item = doc["$defs"]["type"]
        self.assertEqual(["id", "allowed_issuer_kinds", "allowed_ref_kinds",
                          "compose_with", "max_refs"], item["required"])
        self.assertIs(False, item["additionalProperties"])
        self.assertEqual(1, item["properties"]["allowed_issuer_kinds"]["minItems"])

    def test_chain_head_statement_invariants(self):
        doc = self.docs["chain-head.schema.json"]
        self.assertEqual(["schema", "subject_kind", "subject_digest"], doc["required"])
        self.assertEqual(["bundle", "process-chain", "card", "event"],
                         doc["properties"]["subject_kind"]["enum"])
        self.assertIn("issued_at", doc["properties"])

    def test_keys_registry_minimum_invariants(self):
        doc = self.docs["keys.schema.json"]
        self.assertIn("issuers", doc["required"])
        issuer = doc["$defs"]["issuer"]
        self.assertEqual(["id", "kind", "keys"], issuer["required"])
        self.assertEqual(1, issuer["properties"]["keys"]["minItems"])
        key = doc["$defs"]["key"]
        self.assertEqual(["keyid", "alg", "status", "not_before", "not_after"],
                         key["required"])
        self.assertEqual(["hmac-sha256", "ed25519", "ecdsa-p256"],
                         key["properties"]["alg"]["enum"])
        self.assertEqual(["active", "retired", "revoked"],
                         key["properties"]["status"]["enum"])


class TrustSchemaSamplesTest(unittest.TestCase):
    """正/反样例（仓内叶子校验器判定）。"""

    @classmethod
    def setUpClass(cls):
        cls.docs = {name: _read(SCHEMA_DIR / name) for name in SCHEMAS}

    def test_fixture_sets_are_complete(self):
        valid_on_disk = sorted(p.name for p in VALID.glob("*.json"))
        self.assertEqual(sorted(s for s, _v in SCHEMAS.values()), valid_on_disk)
        invalid_on_disk = sorted(p.name for p in INVALID.glob("*.json"))
        self.assertEqual(sorted(INVALID_CASES), invalid_on_disk,
                         "反例目录里有未登记件（或登记件缺失）")

    def test_valid_samples_pass(self):
        for name, (sample, _v) in SCHEMAS.items():
            errors, unsupported = _check(_read(VALID / sample), self.docs[name])
            self.assertEqual([], errors, f"{name} 正样例未通过：{errors}")
            self.assertEqual([], unsupported)

    def test_invalid_samples_rejected_with_expected_reason(self):
        for fixture, (schema_name, expect) in INVALID_CASES.items():
            errors, _unsupported = _check(_read(INVALID / fixture), self.docs[schema_name])
            self.assertTrue(errors, f"{fixture} 未被拒绝（fail-closed 失效）")
            self.assertTrue(any(expect in e for e in errors),
                            f"{fixture} 的拒绝原因不含 {expect!r}：{errors[:3]}")

    def test_unknown_top_field_rejected_for_every_schema(self):
        for name, (sample, _v) in SCHEMAS.items():
            obj = _read(VALID / sample)
            obj["unexpected_extension"] = {"x": 1}
            errors, _unsupported = _check(obj, self.docs[name])
            self.assertTrue(any("多余字段" in e for e in errors),
                            f"{name} 未拒绝顶层未知字段：{errors}")

    def test_cross_schema_samples_rejected(self):
        for name, (sample, _v) in SCHEMAS.items():
            obj = _read(VALID / sample)
            for other, doc in self.docs.items():
                if other == name:
                    continue
                errors, _unsupported = _check(obj, doc)
                self.assertTrue(errors, f"{sample} 的正样例被 {other} 误接受")


class TrustSchemaMutationProbeTest(unittest.TestCase):
    """变异自证：弱化 schema 后负例必须变绿。"""

    @classmethod
    def setUpClass(cls):
        cls.entity = _read(SCHEMA_DIR / "entity.schema.json")
        cls.anchor = _read(SCHEMA_DIR / "anchor.schema.json")
        cls.valid_entity = _read(VALID / "entity.json")
        cls.unknown = copy.deepcopy(cls.valid_entity)
        cls.unknown["unexpected_extension"] = 1
        cls.bad_digest = copy.deepcopy(cls.valid_entity)
        cls.bad_digest["payload_digest"] = "ABC"
        cls.empty_anchors = _read(INVALID / "anchor-empty.json")

    def test_dropping_additional_properties_turns_negative_green(self):
        weakened = copy.deepcopy(self.entity)
        weakened.pop("additionalProperties")
        errors, _u = _check(self.unknown, weakened)
        self.assertEqual([], errors, "去掉 additionalProperties 后未知字段仍被拒——负例不靠该关键字")
        self.assertTrue(_check(self.unknown, self.entity)[0])

    def test_dropping_digest_pattern_turns_negative_green(self):
        weakened = copy.deepcopy(self.entity)
        weakened["$defs"]["digest"].pop("pattern")
        errors, _u = _check(self.bad_digest, weakened)
        self.assertEqual([], errors, "去掉 digest pattern 后坏摘要仍被拒——格式判据不靠 pattern")
        self.assertTrue(_check(self.bad_digest, self.entity)[0])

    def test_dropping_anchor_min_items_turns_negative_green(self):
        weakened = copy.deepcopy(self.anchor)
        weakened["properties"]["anchors"].pop("minItems")
        errors, _u = _check(self.empty_anchors, weakened)
        self.assertEqual([], errors, "去掉 minItems 后空锚集合仍被拒——至少一锚不靠 minItems")
        self.assertTrue(_check(self.empty_anchors, self.anchor)[0])


@unittest.skipIf(Draft202012Validator is None, "jsonschema 未安装（可选对照依赖）")
class TrustSchemaReferenceParityTest(unittest.TestCase):
    """标准 draft 2020-12 实现与仓内叶子件对样例同判（仅对照）。"""

    @classmethod
    def setUpClass(cls):
        cls.docs = {name: _read(SCHEMA_DIR / name) for name in SCHEMAS}

    def test_schemas_are_valid_draft_2020_12(self):
        for doc in self.docs.values():
            Draft202012Validator.check_schema(doc)  # 不合规即抛

    def test_parity_on_valid_samples(self):
        for name, (sample, _v) in SCHEMAS.items():
            validator = Draft202012Validator(self.docs[name])
            errors = list(validator.iter_errors(_read(VALID / sample)))
            self.assertEqual([], errors, f"{name} 正样例在标准实现下报错：{errors[:2]}")

    def test_parity_on_invalid_samples(self):
        for fixture, (schema_name, _expect) in INVALID_CASES.items():
            validator = Draft202012Validator(self.docs[schema_name])
            errors = list(validator.iter_errors(_read(INVALID / fixture)))
            self.assertTrue(errors, f"{fixture} 在标准实现下未被拒绝")


if __name__ == "__main__":
    unittest.main()
