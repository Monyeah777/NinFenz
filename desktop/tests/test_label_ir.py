"""标注 IR v0（core/label_ir.py + nf label CLI）判据。

为什么只测这些：本模块的价值全在「形状与缺口如实」——能证的是声明齐不齐，不能证载体里有没有。
故判据集中在：档位必需项、形状闸门、以及「自称已写入」必须变成 warning 而不是被当成功。
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "nf.py"


def _label_ir():
    spec = importlib.util.spec_from_file_location("nf_label_ir",
                                                 ROOT / "desktop" / "src" / "core"
                                                 / "label_ir.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _minimal_items():
    return [
        {"face": "explicit", "kind": "text", "where": "start", "value": "AI 生成"},
        {"face": "implicit", "kind": "metadata", "key": "AIGC", "value": "1"},
    ]


class TestBuild(unittest.TestCase):
    def test_build_is_deterministic(self):
        m = _label_ir()
        a = m.build("a.png", "0" * 64, items=_minimal_items())
        b = m.build("a.png", "0" * 64, items=_minimal_items())
        self.assertEqual(a, b)
        self.assertEqual("nf-label/1", a["schema"])
        self.assertEqual(m.STANDARD, a["standard"])

    def test_build_has_no_timestamp(self):
        m = _label_ir()
        doc = m.build("a.png", "0" * 64)
        text = json.dumps(doc, ensure_ascii=False)
        for key in ("created_at", "issued_at", "timestamp"):
            self.assertNotIn(key, text, "IR 不得含时间戳（否则不可复现）")

    def test_carrier_defaults_to_not_embedded(self):
        m = _label_ir()
        doc = m.build("a.png", "0" * 64)
        self.assertFalse(doc["carrier"]["embedded"])


class TestRules(unittest.TestCase):
    def test_minimal_rules(self):
        m = _label_ir()
        self.assertEqual(["E1", "I2"], [r["id"] for r in m.rules("minimal")])

    def test_full_rules_include_minimal(self):
        m = _label_ir()
        ids = [r["id"] for r in m.rules("full")]
        self.assertEqual(["E1", "E2", "E3", "I1", "I2"], ids)

    def test_unknown_level_raises_with_guidance(self):
        m = _label_ir()
        with self.assertRaises(ValueError) as ctx:
            m.rules("maximal")
        self.assertIn("修复指引", str(ctx.exception))


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.m = _label_ir()
        self.doc = self.m.build("a.png", "0" * 64, items=_minimal_items())

    def test_minimal_passes(self):
        res = self.m.validate(self.doc)
        self.assertEqual("ok", res["verdict"])
        self.assertEqual(["E1", "I2"], [a["rule"] for a in res["applied"]])

    def test_full_reports_missing_rules(self):
        res = self.m.validate({**self.doc, "level": "full"})
        self.assertEqual("invalid", res["verdict"])
        self.assertEqual(["E2", "E3", "I1"], res["missing"])

    def test_bad_digest_fails(self):
        res = self.m.validate({**self.doc, "object": {"path": "a", "digest": "zz"}})
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("sha256", " ".join(res["issues"]))

    def test_schema_mismatch_fails(self):
        res = self.m.validate({**self.doc, "schema": "nf-label/9"})
        self.assertEqual("invalid", res["verdict"])

    def test_unknown_kind_fails(self):
        bad = dict(self.doc)
        bad["explicit"] = [{"kind": "hologram", "where": "start", "value": "x"}]
        res = self.m.validate(bad)
        self.assertEqual("invalid", res["verdict"])

    def test_carrier_self_claim_is_warning_not_success(self):
        res = self.m.validate({**self.doc, "carrier": {"embedded": True}})
        self.assertEqual("ok", res["verdict"], "形状没错，不因此判死")
        self.assertTrue(res["warnings"], "自称已写入载体必须留下 warning")
        self.assertIn("自称", " ".join(res["warnings"]))

    def test_top_level_must_be_object(self):
        self.assertEqual("invalid", self.m.validate([1, 2])["verdict"])


class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "label", *args],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def test_ir_then_validate_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            items = Path(td, "items.json")
            items.write_text(json.dumps(_minimal_items(), ensure_ascii=False), encoding="utf-8")
            out = Path(td, "a.json")
            proc = self._run("ir", "STRATEGY.md", "--items", str(items), "--out", str(out))
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            self.assertTrue(out.is_file())
            proc = self._run("validate", str(out), "--json")
            self.assertEqual(0, proc.returncode)
            self.assertEqual("ok", json.loads(proc.stdout)["verdict"])

    def test_validate_invalid_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td, "bad.json")
            bad.write_text(json.dumps({"schema": "nope"}), encoding="utf-8")
            proc = self._run("validate", str(bad), "--json")
            self.assertEqual(1, proc.returncode)
            self.assertEqual("invalid", json.loads(proc.stdout)["verdict"])

    def test_missing_object_is_usage_error(self):
        proc = self._run("ir", "does/not/exist.txt")
        self.assertEqual(2, proc.returncode)


if __name__ == "__main__":
    unittest.main()
