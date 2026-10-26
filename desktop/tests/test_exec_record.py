"""T6.2 · 执行记录 schema 与 `nf domain record` 校验（M2 证据）。

七种必测：合法记录 / artifact 缺失 / sha256 不符 / check_rc!=0 / executor=assembler /
date 非法 / package 未登记；另测模板「未执行」、schema 元校验、--write 幂等、CLI 形状。
本环境无模型 API key：测试只用仓库内既有 artifact 构造**校验夹具**，不产生真实执行记录。
"""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import exec_record as er  # noqa: E402

ARTIFACT = "docs/完整版样本_西幻生存流P03.md"
PACKAGE = "西幻生存领域包"
SCRIPT = ROOT / "scripts" / "nf.py"

try:
    import jsonschema
    from jsonschema import Draft202012Validator as Validator
except Exception:  # pragma: no cover - 可选对照依赖
    jsonschema = None
    Validator = None


def _sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _record(**over):
    base = {
        "schema": "nf-exec-record/1",
        "run_id": "run-20261020-p03-001",
        "package": PACKAGE,
        "executor": {"model": "gpt-4o", "provider": "openai", "version": "2024-11-20"},
        "date": "2026-10-20",
        "profile": "techdoc-strict",
        "brief": "西幻生存流完整版：以生存与经济为核心",
        "artifact": {"path": ARTIFACT, "sha256": _sha256(ARTIFACT)},
        "contract_digest": "sha256:" + "a" * 64,
        "check_rc": 0,
        "notes": "夹具：不在测试里伪造真实运行。",
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merged = dict(base[k])
            merged.update(v)
            base[k] = merged
        else:
            base[k] = v
    return base


class ValidRecordTest(unittest.TestCase):
    def test_valid_record_passes(self):
        res = er.validate_record(ROOT, _record(), source_path="fixture.json")
        self.assertEqual("pass", res["status"], res["issues"])
        self.assertEqual([], res["issues"])
        self.assertEqual("PASS", res["verdict"])

    def test_schema_is_valid_draft2020(self):
        if jsonschema is None:
            self.skipTest("jsonschema 未安装（可选对照依赖）")
        data = json.loads((ROOT / "protocol" / "schema" / "exec_record.schema.json")
                          .read_text(encoding="utf-8"))
        Validator.check_schema(data)
        self.assertEqual("nf-exec-record/1", data["properties"]["schema"]["enum"][0])
        self.assertIn("artifact", data["required"])
        # 与 repo 零第三方子集校验器口径一致：合法记录零违例、坏记录有违例
        schema = er.schema_lint.load_schema(str(ROOT), er.SCHEMA_NAME)
        self.assertEqual([], er.schema_lint.subset_validate(_record(), schema))
        bad = _record(check_rc=1)
        self.assertTrue(er.schema_lint.subset_validate(bad, schema))


class NegativeCaseTest(unittest.TestCase):
    """七种负例（合法已在上组）：逐条断言机器码，防只报自然语言。"""

    def _codes(self, rec):
        res = er.validate_record(ROOT, rec, source_path="fixture.json")
        self.assertEqual("fail", res["status"])
        return res, res["codes"]

    def test_artifact_missing(self):
        res, codes = self._codes(_record(artifact={"path": "no/such/artifact.md"}))
        self.assertIn("artifact_missing", codes, res["issues"])

    def test_sha256_mismatch(self):
        rec = _record()
        rec["artifact"]["sha256"] = "0" * 64
        res, codes = self._codes(rec)
        self.assertIn("sha256_mismatch", codes, res["issues"])

    def test_check_rc_nonzero(self):
        res, codes = self._codes(_record(check_rc=1))
        self.assertIn("check_rc_nonzero", codes, res["issues"])

    def test_executor_assembler_is_not_model(self):
        res, codes = self._codes(_record(executor={"model": "nf-assembler",
                                                   "provider": "nf-cli",
                                                   "version": "1.1.0"}))
        self.assertIn("executor_not_model", codes, res["issues"])

    def test_executor_agent_is_not_model(self):
        res, codes = self._codes(_record(executor={"model": "codex-agent",
                                                   "provider": "openai",
                                                   "version": "1"}))
        self.assertIn("executor_not_model", codes, res["issues"])

    def test_date_invalid(self):
        res, codes = self._codes(_record(date="2026-13-40"))
        self.assertIn("date_invalid", codes, res["issues"])
        res, codes = self._codes(_record(date="2026/10/20"))
        self.assertIn("date_invalid", codes, res["issues"])

    def test_package_unregistered(self):
        res, codes = self._codes(_record(package="不存在的域包"))
        self.assertIn("package_unregistered", codes, res["issues"])


class TemplateTest(unittest.TestCase):
    def test_template_reports_not_executed(self):
        res = er.check_file(ROOT, "protocol/exec_records/_TEMPLATE.json")
        self.assertEqual("not-executed", res["status"], res["issues"])
        self.assertEqual("NOT_EXECUTED", res["verdict"])
        self.assertEqual([], res["issues"])
        self.assertTrue(res["template"])

    def test_template_flag_alone_is_enough(self):
        rec = _record()
        rec["template"] = True
        rec["artifact"]["path"] = "no/such/artifact.md"     # 模板不参与复算
        res = er.validate_record(ROOT, rec)
        self.assertEqual("not-executed", res["status"])

    def test_scan_counts_template_as_not_executed(self):
        res = er.scan(ROOT)
        self.assertGreaterEqual(res["count"], 1)
        self.assertEqual(1, res["not-executed"])
        self.assertIn(res["status"] if "status" in res else "ok", ("ok", "pass", "fail", "not-executed"))


class WriteRecordTest(unittest.TestCase):
    """--write 落盘：临时 root 内建最小协议面（schema + registry），不写真实仓库。"""

    def _root(self, tmp):
        root = Path(tmp)
        (root / "protocol" / "schema").mkdir(parents=True)
        (root / "protocol" / "exec_records").mkdir(parents=True)
        (root / "desktop" / "src" / "core").mkdir(parents=True)
        for rel in ("protocol/schema/exec_record.schema.json",
                    "desktop/src/core/registry.json"):
            (root / rel).write_text((ROOT / rel).read_text(encoding="utf-8"),
                                    encoding="utf-8")
        art = root / "artifact.md"
        art.write_text("real run artifact fixture\n", encoding="utf-8")
        rec = _record(artifact={"path": "artifact.md",
                                "sha256": hashlib.sha256(art.read_bytes()).hexdigest()})
        src = root / "incoming.json"
        src.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return root, src

    def test_write_validates_then_writes_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, src = self._root(tmp)
            first = er.write_record(root, str(src))
            self.assertTrue(first["written"], first["issues"])
            self.assertEqual("protocol/exec_records/%s.json" % first["run_id"], first["target"])
            self.assertTrue((root / first["target"]).is_file())
            again = er.write_record(root, str(src))
            self.assertTrue(again["written"])
            self.assertTrue(again["idempotent"])

    def test_write_rejects_invalid_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, src = self._root(tmp)
            bad = json.loads(src.read_text(encoding="utf-8"))
            bad["check_rc"] = 3
            src.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            res = er.write_record(root, str(src))
            self.assertFalse(res["written"])
            self.assertEqual("fail", res["status"])


class CliShapeTest(unittest.TestCase):
    """CLI：`nf domain record [--check/--write/--json]`（同进程，不 fork subprocess）。"""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("nf_record_probe", SCRIPT)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["nf_record_probe"] = mod
        spec.loader.exec_module(mod)
        cls.nf = mod
        cls.parser = mod._build_parser()

    def _run(self, *argv):
        buf, err = io.StringIO(), io.StringIO()
        args = self.parser.parse_args(["domain", "record", *argv])
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = self.nf._cmd_domain(args)
        return rc, buf.getvalue(), err.getvalue()

    def test_parser_flags(self):
        ns = self.parser.parse_args(["domain", "record", "--check", "x.json",
                                     "--write", "y.json", "--json"])
        self.assertEqual("x.json", ns.check)
        self.assertEqual("y.json", ns.write)
        self.assertTrue(ns.json)

    def test_cli_check_json_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "rec.json"
            p.write_text(json.dumps(_record(), ensure_ascii=False), encoding="utf-8")
            rc, out, err = self._run("--check", str(p), "--json")
            self.assertEqual(0, rc, err)
            doc = json.loads(out)
            self.assertEqual("pass", doc["status"])
            self.assertEqual("domain-record", doc["kind"])

    def test_cli_check_fail_rc1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "rec.json"
            rec = _record(check_rc=1)
            p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            rc, _out, err = self._run("--check", str(p))
            self.assertEqual(1, rc)
            self.assertIn("[FAIL]", err if err else _out)

    def test_cli_scan_reports_template_not_executed(self):
        rc, out, _err = self._run()
        self.assertEqual(0, rc)
        self.assertIn("未执行", out)


if __name__ == "__main__":
    unittest.main()
