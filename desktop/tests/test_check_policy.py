"""单对象策略体检（cc_check）单测——封闭词表、可复算 verdict、坏策略必须拒。

判据覆盖：ok/invalid 两态各自可达；warn 不改判定；policy_digest 稳定（判据版本随结论走）；
坏策略（schema/kind/severity/fix/pattern/field/n/digest）全部带指引拒绝；非 UTF-8 对象不崩。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import check_policy as cp


def _policy(rules, pid="p-1"):
    return {"schema": cp.SCHEMA, "id": pid, "rules": rules}


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_check_t_")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.obj = self.tmp / "doc.md"
        self.obj.write_text("本内容由 AI 生成\n\n正文一行。\n", encoding="utf-8")

    def _write_policy(self, policy):
        path = self.tmp / "policy.json"
        path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
        return str(path)


class TestValidate(_Base):
    def test_valid_policy_passes(self):
        self.assertEqual(cp.validate(_policy([
            {"id": "a", "kind": "utf8", "fix": "另存为 UTF-8"}])), [])

    def test_bad_schema(self):
        issues = cp.validate({"rules": [{"id": "a", "kind": "utf8", "fix": "x"}]})
        self.assertTrue(any("schema 不匹配" in i for i in issues), issues)
        self.assertTrue(all("修复指引" in i for i in issues), issues)

    def test_empty_rules(self):
        issues = cp.validate({"schema": cp.SCHEMA, "rules": []})
        self.assertTrue(any("缺 rules" in i for i in issues), issues)

    def test_unknown_kind(self):
        issues = cp.validate(_policy([{"id": "a", "kind": "made-up", "fix": "x"}]))
        self.assertTrue(any("不在词表" in i for i in issues), issues)

    def test_missing_fix(self):
        issues = cp.validate(_policy([{"id": "a", "kind": "utf8"}]))
        self.assertTrue(any("缺 fix" in i for i in issues), issues)

    def test_duplicate_id(self):
        issues = cp.validate(_policy([
            {"id": "a", "kind": "utf8", "fix": "x"},
            {"id": "a", "kind": "utf8", "fix": "x"}]))
        self.assertTrue(any("重复" in i for i in issues), issues)

    def test_bad_regex(self):
        issues = cp.validate(_policy([
            {"id": "a", "kind": "regex_present", "pattern": "(", "fix": "x"}]))
        self.assertTrue(any("不是合法正则" in i for i in issues), issues)

    def test_bad_severity_and_field(self):
        issues = cp.validate(_policy([
            {"id": "a", "kind": "count_at_least", "field": "pages", "n": 1,
             "severity": "fatal", "fix": "x"}]))
        self.assertTrue(any("severity" in i for i in issues), issues)
        self.assertTrue(any("field 不在词表" in i for i in issues), issues)

    def test_bad_digest(self):
        issues = cp.validate(_policy([
            {"id": "a", "kind": "digest_pin", "sha256": "abc", "fix": "x"}]))
        self.assertTrue(any("64 位" in i for i in issues), issues)


class TestCheck(_Base):
    def test_ok(self):
        res = cp.check(str(self.obj), _policy([
            {"id": "disclose", "kind": "regex_present", "pattern": "AI", "fix": "加披露"}],
            pid="demo"))
        self.assertEqual(res["verdict"], "ok", res["findings"])
        self.assertEqual(res["policy_id"], "demo")
        self.assertEqual(len(res["policy_digest"]), 64)

    def test_fail_makes_invalid(self):
        res = cp.check(str(self.obj), _policy([
            {"id": "forbid", "kind": "regex_absent", "pattern": "AI", "fix": "删掉"}])
        )
        self.assertEqual(res["verdict"], "invalid")
        self.assertEqual(res["failed"], 1)
        self.assertEqual(res["findings"][0]["fix"], "删掉")

    def test_warn_does_not_flip_verdict(self):
        res = cp.check(str(self.obj), _policy([
            {"id": "len", "kind": "count_at_least", "field": "lines", "n": 99,
             "severity": "warn", "fix": "写长一点"}])
        )
        self.assertEqual(res["verdict"], "ok")
        self.assertEqual(res["warned"], 1)

    def test_digest_pin(self):
        import hashlib
        digest = hashlib.sha256(self.obj.read_bytes()).hexdigest()
        good = cp.check(str(self.obj), _policy([
            {"id": "pin", "kind": "digest_pin", "sha256": digest, "fix": "别改"}])
        )
        self.assertEqual(good["verdict"], "ok")
        bad = cp.check(str(self.obj), _policy([
            {"id": "pin", "kind": "digest_pin", "sha256": "0" * 64, "fix": "别改"}])
        )
        self.assertEqual(bad["verdict"], "invalid")

    def test_non_utf8_object_does_not_crash(self):
        raw = self.tmp / "bin.dat"
        raw.write_bytes(b"\xff\xfe\x00\x01")
        res = cp.check(str(raw), _policy([
            {"id": "u", "kind": "utf8", "fix": "另存为 UTF-8"}])
        )
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("不是合法 UTF-8" in f["detail"] for f in res["findings"]),
                        res["findings"])

    def test_policy_digest_stable(self):
        pol = _policy([{"id": "u", "kind": "utf8", "fix": "x"}])
        self.assertEqual(cp.policy_digest(pol), cp.policy_digest(json.loads(
            json.dumps(pol, sort_keys=True))))

    def test_missing_object(self):
        with self.assertRaises(ValueError) as ctx:
            cp.check(str(self.tmp / "nope.md"), _policy([
                {"id": "u", "kind": "utf8", "fix": "x"}]))
        self.assertIn("修复指引", str(ctx.exception))


class TestLoad(_Base):
    def test_load_ok(self):
        path = self._write_policy(_policy([{"id": "u", "kind": "utf8", "fix": "x"}]))
        self.assertEqual(cp.load(path)["schema"], cp.SCHEMA)

    def test_load_bad_json(self):
        path = self.tmp / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            cp.load(str(path))
        self.assertIn("修复指引", str(ctx.exception))

    def test_load_invalid_policy(self):
        path = self._write_policy({"schema": cp.SCHEMA, "rules": []})
        with self.assertRaises(ValueError) as ctx:
            cp.load(path)
        self.assertIn("修复指引", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
