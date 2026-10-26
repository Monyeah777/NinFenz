"""T2.1 · 域隔离与契约 schema 落地（Wave2）单测。

覆盖四件交付的判据面：
1. schema meta：10 个 protocol/schema/*.json 是合法 draft 2020-12，且四个 schema 接受可选
   `domain`、contract 的事件名 pattern 拒非法名；
2. 跨域门：校园需求 check 西幻 P03 样本 → FAIL；同域样本 → PASS；未声明域不判死；
3. 层序闭包：例外表被读取，登记项只产生 WARN（0 FAIL）；不传例外表则同 4 条倒挂 FAIL；
4. registry 模块实例仍可通过 module.schema（域字段可选、V1 只增不删）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import assemble_build as ab  # noqa: E402
from core import assemble_plan as ap  # noqa: E402
from core import layer_closure as lc  # noqa: E402

try:
    import jsonschema
    from jsonschema import Draft202012Validator as Validator
except Exception:  # pragma: no cover - 可选对照依赖（仓库标准校验器为零第三方）
    jsonschema = None
    Validator = None


def _schema(name):
    return json.loads((ROOT / "protocol" / "schema" / name).read_text(encoding="utf-8"))


def _sample_p03():
    return (ROOT / "docs" / "完整版样本_西幻生存流P03.md").read_text(encoding="utf-8")


class SchemaMetaTest(unittest.TestCase):
    """protocol/schema 面件数的元校验 + domain/事件名词法的增量语义。"""

    @unittest.skipIf(jsonschema is None, "jsonschema 未安装（可选对照依赖）")
    def test_all_schemas_are_valid_draft2020(self):
        files = sorted((ROOT / "protocol" / "schema").glob("*.json"))
        # T6.2/T6.3（2026-10-26）：新增 exec_record.schema.json 与
        # bench_result.schema.json，面件数 9 → 11；断言只增不减，防 schema 静默消失。
        names = [f.name for f in files]
        self.assertGreaterEqual(
            len(files), 11, "protocol/schema 面件数应 ≥11：%s" % names)
        self.assertIn("exec_record.schema.json", names)
        self.assertIn("bench_result.schema.json", names)
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            Validator.check_schema(data)          # 不是合法 draft 2020-12 即抛
            self.assertEqual("https://json-schema.org/draft/2020-12/schema",
                             data.get("$schema"), "方言声明漂移：%s" % f.name)

    @unittest.skipIf(jsonschema is None, "jsonschema 未安装（可选对照依赖）")
    def test_four_schemas_accept_optional_domain(self):
        cases = {
            "asset.schema.json": {
                "file": "用户自定义/TECH_RULES.md", "key": "TECH_RULES",
                "source": "05 台账", "module": "M90", "version": "1.0",
                "status": "active", "added": "2026-09-07",
            },
            "module.schema.json": {
                "id": "M40", "name": "关系深度", "category": "情感", "source": "社区包",
            },
            "pipeline.schema.json": {
                "id": "P02", "name": "校园情感流",
                "structure": {"type": "linear", "flow": []}, "layers": [],
            },
            "protocol.schema.json": {
                "protocol": {"schema_version": "2"},
                "package": {
                    "id": "校园情感领域包", "name": "校园情感领域包", "pipeline": "P02",
                    "module_id_range": [], "categories": ["情感"],
                    "dependencies": {"core_only": True, "core_modules": [],
                                     "cross_package": []},
                    "modules": [],
                    "assets": {"count": 0, "readme": "README.md"},
                    "mount_layers": {},
                },
            },
        }
        for name, base in cases.items():
            schema = _schema(name)

            def _with_domain(value, base=base, nested=(name == "protocol.schema.json")):
                if nested:
                    return {"protocol": base["protocol"],
                            "package": dict(base["package"], domain=value)}
                return dict(base, domain=value)

            Validator(schema).validate(base)                                  # 域缺省合法（向后兼容）
            Validator(schema).validate(_with_domain("校园情感领域包"))        # 显式域合法
            for bad in (3, ""):
                with self.assertRaises(jsonschema.ValidationError,
                                       msg="%s 的 domain 应拒 %r" % (name, bad)):
                    Validator(schema).validate(_with_domain(bad))

    @unittest.skipIf(jsonschema is None, "jsonschema 未安装（可选对照依赖）")
    def test_contract_event_name_lexical(self):
        schema = _schema("contract.schema.json")
        valid = {
            "schema": "1", "conformance": "L2", "id": "M80", "name": "输出质检门",
            "category": "通用", "layer": "P80", "inputs": [], "outputs": [],
            "events": {"publish": ["narrative_event"], "subscribe": ["tick_day"]},
            "interfaces": [], "io_types": {"outputs": {}, "inputs": {}},
        }
        Validator(schema).validate(valid)
        for bad_name in ("Tick_Day", "全角事件", "1_start", "a" * 41):
            with self.assertRaises(jsonschema.ValidationError,
                                   msg="事件名 %r 应被拒" % bad_name):
                Validator(schema).validate(dict(
                    valid, events={"publish": [bad_name], "subscribe": []}))
            with self.assertRaises(jsonschema.ValidationError,
                                   msg="订阅侧事件名 %r 应被拒" % bad_name):
                Validator(schema).validate(dict(
                    valid, events={"publish": [], "subscribe": [bad_name]}))

    @unittest.skipIf(jsonschema is None, "jsonschema 未安装（可选对照依赖）")
    def test_registry_modules_still_validate(self):
        schema = _schema("module.schema.json")
        reg = json.loads((ROOT / "desktop" / "src" / "core" / "registry.json")
                         .read_text(encoding="utf-8"))
        v = Validator(schema)
        for entry in reg.get("modules", []):
            v.validate(entry)                 # 存量模块不因新增可选域而失配（V1 只增不删）
            v.validate(dict(entry, domain="官方核心"))


class DomainGateTest(unittest.TestCase):
    """T1.2 W2 跨域门：需求域 vs 产物声明域。"""

    def setUp(self):
        self.sample = _sample_p03()
        self.campus = ap.plan("帮我组装一个校园情感世界的完整版")
        self.fantasy = ap.plan("西幻生存+生存+单世界")

    def test_cross_domain_sample_fails(self):
        issues, stats = ap.check(self.sample, self.campus)
        self.assertTrue(any("跨域装配" in i for i in issues),
                        "校园需求 check 西幻 P03 样本应判跨域 FAIL，实得：%s" % issues)
        self.assertFalse(stats["domain"]["ok"])
        self.assertEqual("P02", stats["domain"]["expected"]["pipeline"])
        self.assertIn("P03", stats["domain"]["declared"]["pipelines"])

    def test_same_domain_sample_passes(self):
        issues, stats = ap.check(self.sample, self.fantasy)
        self.assertEqual([], issues)
        self.assertTrue(stats["domain"]["ok"])

    def test_same_domain_build_passes(self):
        text, _ = ab.build(str(ROOT), "帮我组装一个校园情感世界的完整版", self.campus)
        issues, stats = ap.check(text, self.campus)
        self.assertEqual([], issues)
        self.assertTrue(stats["domain"]["ok"])

    def test_undeclared_domain_is_not_fatal(self):
        text = "\n".join("## %d. 段" % i for i in range(8)) + "\n"
        issues, stats = ap.check(text, self.campus)
        self.assertEqual([], issues, "产物未声明域不得判死（WARN 记账）")
        self.assertFalse(stats["domain"]["checked"])
        self.assertIn("产物未声明域", stats["domain"]["reason"])

    def test_explicit_expected_pipeline_overrides_plan(self):
        # T5.2 起允许集由 plan 决定（scoped）；expected_pipeline 只覆盖「需求域 vs 声明域」比较，
        # 不重算允许集——故同域判定用同域 plan，跨域判定用异域 plan（或 --loose）。
        issues, _ = ap.check(self.sample, self.fantasy, expected_pipeline="P03")
        self.assertEqual([], issues, "显式声明 P03 且 plan 域一致时不应判跨域")
        issues, stats = ap.check(self.sample, self.fantasy, expected_pipeline="P02")
        self.assertTrue(any("跨域装配" in i for i in issues))
        self.assertEqual("P02", stats["domain"]["expected"]["pipeline"])


class LayerClosureTest(unittest.TestCase):
    """T1.2 W1 层序闭包：例外表读取 + 只 WARN 不 FAIL。"""

    def test_exception_table_loaded(self):
        ex = lc.load_exceptions(str(ROOT))
        self.assertEqual(5, len(ex), "报告登记的 5 条例外应全在表内")
        self.assertIn(("M06", "M20"), ex)
        self.assertTrue(ex[("M06", "M20")]["reason"])
        self.assertTrue(ex[("M06", "M20")]["evidence"])

    def test_scan_warns_for_registered_inversions(self):
        fails, warns, stats = lc.scan(str(ROOT))
        self.assertEqual([], fails, "已登记例外不得判 FAIL")
        self.assertEqual(4, stats["backward"], "基线实测 4 条层序倒挂")
        self.assertEqual(4, stats["warned"])
        self.assertEqual(0, stats["fails"])
        self.assertTrue(all("层序闭包例外 WARN" in w for w in warns))
        # 双向耦合另一向 rank 已满足：登记但不消耗 → 清账时必须可见
        self.assertEqual(["M12←M13"], stats["unused"])

    def test_unregistered_inversions_fail(self):
        fails, warns, stats = lc.scan(str(ROOT), exceptions={})
        self.assertEqual(4, len(fails), "无例外表时 4 条倒挂应判 FAIL")
        self.assertTrue(all("层序闭包违例" in f and "修复指引" in f for f in fails))
        self.assertEqual(0, stats["warned"])

    def test_malformed_exception_table_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "protocol"
            d.mkdir()
            bad = d / "layer_exceptions.json"
            bad.write_text('{"schema": "nf-layer-exceptions/1", "exceptions": [{"consumer": "M06"}]}',
                           encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                lc.load_exceptions(tmp)
            self.assertIn("修复指引", str(ctx.exception))
            bad.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                lc.load_exceptions(tmp)


if __name__ == "__main__":
    unittest.main()
