#!/usr/bin/env python3
"""IDL 元工具对照（可选：jsonschema 标准实现交叉验证）+ 生产平面 schema 门禁（WP-01）。

上半部分（`SchemaReferenceTest`）为 43 追加 · IDL 元工具对照：仓库校验器为自实现
JSON-schema 子集（零第三方红线）。本测试仅当环境装有标准实现 jsonschema 时执行：
① schema 文件本身是合法 draft 2020-12；② 代表实例（M00 machine_contract）在标准实现下
零错误——与子集校验器结论一致。未安装则跳过（不触碰 verify 零第三方依赖红线）。

下半部分（`ProductionSchemaGateTest`，始终执行）为 NF-Final WP-01：`protocol/production/`
五件核心 schema（nf-contract/1、nf-wiki-page/1、nf-spec/1、nf-task/1、nf-assembly/1）的
字段契约判据——命名/版本、fail-closed、正样例过、反样例按**预期原因**被拒、未知字段拒、
pattern 锚定、摘要 pattern 单一来源；并用「弱化 schema → 对应反例变绿」做变异自证，
证明这些断言不是同义反复。
"""
import copy
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover - 可选对照依赖
    jsonschema = None
    Draft202012Validator = None

from core import schema_lint as sl  # noqa: E402


@unittest.skipIf(jsonschema is None, "jsonschema 未安装（可选对照依赖）")
class SchemaReferenceTest(unittest.TestCase):
    def test_schema_files_valid_draft2020(self):
        files = sorted(glob.glob(os.path.join(ROOT, "protocol", "schema", "*.json")))
        self.assertGreaterEqual(len(files), 5, "schema 面件数异常：%s" % files)
        for f in files:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            Draft202012Validator.check_schema(data)   # 不合规即抛（N12：有显式件数前提）

    def test_representative_instance_matches_reference(self):
        contract = sl.load_schema(ROOT, "contract.schema.json")
        m00 = os.path.join(ROOT, "04_模块库", "通用类", "M00_数据槽总线.md")
        with open(m00, encoding="utf-8") as fh:
            parsed = sl._fence_yaml(fh.read(), "machine_contract")
        self.assertIsNotNone(parsed)
        errors = list(Draft202012Validator(contract).iter_errors(parsed["machine_contract"]))
        self.assertEqual(errors, [])


# ---- WP-01：生产平面五件 schema 门禁（始终执行） ----

from core import json_schema as _js  # noqa: E402

PROD_SCHEMA_DIR = os.path.join(ROOT, "protocol", "production")
PROD_FIX = os.path.join(ROOT, "desktop", "tests", "fixtures", "production", "schemas")

#: schema 文件 → (正样例, 数据版本名)
PROD_SCHEMAS = {
    "contract.schema.json": ("contract.json", "nf-contract/1"),
    "wiki-page.schema.json": ("wiki-page.json", "nf-wiki-page/1"),
    "spec.schema.json": ("spec.json", "nf-spec/1"),
    "task.schema.json": ("task.json", "nf-task/1"),
    "assembly.schema.json": ("assembly.json", "nf-assembly/1"),
}

#: 反例文件 → (对应 schema, 期望错误片段)；片段取自 core.json_schema 的固定文案
PROD_INVALID = {
    "contract-unknown-field.json": ("contract.schema.json", "多余字段"),
    "contract-bad-digest.json": ("contract.schema.json", "不匹配 pattern"),
    "contract-missing-acceptance.json": ("contract.schema.json", "缺必填字段"),
    "wiki-page-bad-type.json": ("wiki-page.schema.json", "不在枚举内"),
    "wiki-page-empty-citations.json": ("wiki-page.schema.json", "元素数 < 1"),
    "wiki-page-unknown-relation.json": ("wiki-page.schema.json", "不在枚举内"),
    "spec-bad-kind.json": ("spec.schema.json", "不在枚举内"),
    "spec-missing-digest.json": ("spec.schema.json", "缺必填字段"),
    "spec-version-zero.json": ("spec.schema.json", ">="),
    "task-slot-bad-id.json": ("task.schema.json", "不匹配 pattern"),
    "task-budget-zero-tokens.json": ("task.schema.json", ">="),
    "task-unknown-output-kind.json": ("task.schema.json", "不在枚举内"),
    "assembly-missing-fallback.json": ("assembly.schema.json", "缺必填字段"),
    "assembly-bad-pipeline.json": ("assembly.schema.json", "不匹配 pattern"),
    "assembly-step-bad-id.json": ("assembly.schema.json", "不匹配 pattern"),
}

DIGEST_PATTERN = "^[0-9a-f]{64}$"
CANONICAL_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _prod_read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _prod_check(instance, schema):
    """仓内叶子校验器 → (错误清单, 不支持关键字清单)。"""
    unsupported = []
    errors = _js.json_schema_check(instance, schema, unsupported=unsupported)
    return errors, unsupported


def _walk_key(node, key):
    out = []
    if isinstance(node, dict):
        if key in node:
            out.append(node[key])
        for value in node.values():
            out.extend(_walk_key(value, key))
    elif isinstance(node, list):
        for value in node:
            out.extend(_walk_key(value, key))
    return out


class ProductionSchemaGateTest(unittest.TestCase):
    """WP-01 五件生产 schema：字段契约 + 正反样例 + 变异自证。"""

    @classmethod
    def setUpClass(cls):
        cls.docs = {name: _prod_read(os.path.join(PROD_SCHEMA_DIR, name))
                    for name in PROD_SCHEMAS}

    def test_all_five_present_and_exact(self):
        on_disk = sorted(p for p in os.listdir(PROD_SCHEMA_DIR) if p.endswith(".json"))
        self.assertEqual(sorted(PROD_SCHEMAS), on_disk,
                         "protocol/production 的 schema 集合必须恰为 5 件")

    def test_id_schema_and_versioned_name(self):
        for name, (_sample, versioned) in PROD_SCHEMAS.items():
            doc = self.docs[name]
            self.assertEqual("https://ninfenz.dev/production/" + name, doc.get("$id"), name)
            self.assertEqual(CANONICAL_DRAFT, doc.get("$schema"), name)
            self.assertEqual("object", doc.get("type"), name)
            self.assertEqual(versioned, doc["properties"]["schema"]["const"],
                             "%s 的数据版本名与文件不符" % name)
            self.assertTrue(str(doc.get("description") or "").strip(), name + " 缺 description")

    def test_fail_closed_by_default(self):
        for name, doc in self.docs.items():
            self.assertIs(False, doc.get("additionalProperties"), "%s 未封未知字段" % name)
            self.assertTrue(doc.get("required"), "%s 缺 required" % name)

    def test_no_placeholder_debt(self):
        for name in PROD_SCHEMAS:
            with open(os.path.join(PROD_SCHEMA_DIR, name), encoding="utf-8") as fh:
                text = fh.read()
            for word in ("TODO", "FIXME", "NotImplemented"):
                self.assertNotIn(word, text, "%s 含 %s（schema 不允许占位债）" % (name, word))

    def test_valid_samples_pass_and_validator_supports_them(self):
        for name, (sample, _v) in PROD_SCHEMAS.items():
            instance = _prod_read(os.path.join(PROD_FIX, "valid", sample))
            errors, unsupported = _prod_check(instance, self.docs[name])
            self.assertEqual([], errors, "%s 正样例被拒：%s" % (name, errors))
            self.assertEqual([], unsupported, "%s 使用了叶子件不支持的语义" % name)

    def test_invalid_samples_rejected_with_expected_reason(self):
        for fname, (schema_name, expect) in PROD_INVALID.items():
            instance = _prod_read(os.path.join(PROD_FIX, "invalid", fname))
            errors, _unsupported = _prod_check(instance, self.docs[schema_name])
            self.assertTrue(errors, "%s 反样例未被拒（判据失明）" % fname)
            self.assertTrue(any(expect in e for e in errors),
                            "%s 的失败原因未命中预期 %r：%s" % (fname, expect, errors))

    def test_unknown_field_rejected_everywhere(self):
        for name, (sample, _v) in PROD_SCHEMAS.items():
            instance = _prod_read(os.path.join(PROD_FIX, "valid", sample))
            instance = dict(instance)
            instance["surprise"] = 1
            errors, _u = _prod_check(instance, self.docs[name])
            self.assertTrue(any("多余字段" in e for e in errors),
                            "%s 未拒未知字段：%s" % (name, errors))

    def test_patterns_are_anchored(self):
        for name, doc in self.docs.items():
            for pat in _walk_key(doc, "pattern"):
                self.assertTrue(str(pat).startswith("^") and str(pat).endswith("$"),
                                "%s 的 pattern 未锚定：%r" % (name, pat))

    def test_digest_pattern_single_source(self):
        seen = set()
        for doc in self.docs.values():
            digest = (doc.get("$defs") or {}).get("digest")
            if digest:
                seen.add(digest.get("pattern"))
        self.assertEqual({DIGEST_PATTERN}, seen, "摘要 pattern 必须唯一且为小写 hex")

    def test_mutation_self_proof(self):
        """弱化 schema 后，对应反例必须变绿——证明反例断言不是同义反复。"""
        cases = (
            ("contract.schema.json", "contract-unknown-field.json",
             lambda d: d.update({"additionalProperties": True})),
            ("wiki-page.schema.json", "wiki-page-empty-citations.json",
             lambda d: d["properties"]["citations"].update({"minItems": 0})),
            ("spec.schema.json", "spec-missing-digest.json",
             lambda d: d["required"].remove("digest")),
            ("task.schema.json", "task-budget-zero-tokens.json",
             lambda d: d["properties"]["budget"]["properties"]["max_tokens"]
             .update({"minimum": 0})),
            ("assembly.schema.json", "assembly-step-bad-id.json",
             lambda d: d["$defs"]["step"]["properties"]["id"].pop("pattern")),
        )
        for schema_name, invalid_name, weaken in cases:
            instance = _prod_read(os.path.join(PROD_FIX, "invalid", invalid_name))
            base_errors, _u = _prod_check(instance, self.docs[schema_name])
            self.assertTrue(base_errors, "%s 基线未红，变异自证无意义" % schema_name)
            mutated = copy.deepcopy(self.docs[schema_name])
            weaken(mutated)
            errors, _u2 = _prod_check(instance, mutated)
            self.assertEqual([], errors,
                             "%s 弱化后 %s 仍被拒——反例与判据绑死（同义反复）"
                             % (schema_name, invalid_name))

    @unittest.skipIf(jsonschema is None, "jsonschema 未安装（可选对照依赖）")
    def test_standard_validator_agrees(self):
        """标准 draft 2020-12 实现与仓内叶子件同判（可选对照，缺依赖跳过）。"""
        for name, (sample, _v) in PROD_SCHEMAS.items():
            doc = self.docs[name]
            Draft202012Validator.check_schema(doc)
            instance = _prod_read(os.path.join(PROD_FIX, "valid", sample))
            self.assertEqual([], list(Draft202012Validator(doc).iter_errors(instance)),
                             "%s 正样例在标准实现下被拒" % name)
            for fname, (schema_name, _expect) in PROD_INVALID.items():
                if schema_name != name:
                    continue
                bad = _prod_read(os.path.join(PROD_FIX, "invalid", fname))
                self.assertTrue(list(Draft202012Validator(doc).iter_errors(bad)),
                                "%s 反样例在标准实现下被放行" % fname)


if __name__ == "__main__":
    unittest.main()
