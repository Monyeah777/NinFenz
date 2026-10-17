"""断言表（数据化断言）正式与否定用例。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import assertions as A  # noqa: E402


def _mk(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _decl(**over):
    d = {"schema": A.SCHEMA, "severity_vocabulary": list(A.SEVERITIES),
         "kind_vocabulary": list(A.KINDS), "assertions": []}
    d.update(over)
    return d


class TestAssertionsRealRepo(unittest.TestCase):
    def test_table_is_legal_and_green(self):
        self.assertEqual(A.scan(str(ROOT))[0], [])
        results, issues = A.run(str(ROOT))
        self.assertEqual(issues, [])
        self.assertGreaterEqual(len(results), 4)
        self.assertTrue(all(r["ok"] for r in results))

    def test_kind_vocabulary_is_closed_set(self):
        decl = A.load(str(ROOT))
        self.assertEqual(tuple(decl["kind_vocabulary"]), tuple(A.KINDS))


class TestAssertionsNegatives(unittest.TestCase):
    def _write(self, tmp, doc):
        _mk(tmp, A.DECL_REL, json.dumps(doc, ensure_ascii=False))
        return tmp

    def test_missing_fix_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._write(tmp, _decl(assertions=[{"id": "x", "severity": "fail",
                                            "kind": "regex_absent",
                                            "params": {"globs": [], "pattern": "a"},
                                            "message": "m"}]))
        self.assertTrue(any("缺 fix" in i for i in A.scan(tmp)[0]))

    def test_unknown_kind_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._write(tmp, _decl(assertions=[{"id": "x", "severity": "fail",
                                            "kind": "magic", "params": {},
                                            "message": "m", "fix": "f"}]))
        self.assertTrue(any("封闭集" in i for i in A.scan(tmp)[0]))

    def test_kind_vocabulary_drift_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._write(tmp, _decl(kind_vocabulary=["regex_absent"]))
        self.assertTrue(any("kind 词表" in i for i in A.scan(tmp)[0]))

    def test_duplicate_id_and_bad_severity_are_fail(self):
        tmp = tempfile.mkdtemp()
        row = {"id": "x", "severity": "maybe", "kind": "regex_absent",
               "params": {"globs": [], "pattern": "a"}, "message": "m", "fix": "f"}
        self._write(tmp, _decl(assertions=[row, dict(row)]))
        issues = A.scan(tmp)[0]
        self.assertTrue(any("id 重复" in i for i in issues))
        self.assertTrue(any("severity 越词表" in i for i in issues))

    def test_fail_severity_blocks_run(self):
        tmp = tempfile.mkdtemp()
        _mk(tmp, "a.txt", "C:\\Users\\secret")
        self._write(tmp, _decl(assertions=[{
            "id": "no-abs", "severity": "fail", "kind": "regex_absent",
            "params": {"globs": ["a.txt"], "pattern": "[A-Za-z]:"},
            "message": "m", "fix": "去掉绝对路径"}]))
        results, issues = A.run(tmp)
        self.assertFalse(results[0]["ok"])
        self.assertTrue(any("不通过" in i for i in issues))

    def test_warn_severity_does_not_block(self):
        tmp = tempfile.mkdtemp()
        _mk(tmp, "a.txt", "x")
        self._write(tmp, _decl(assertions=[{
            "id": "w", "severity": "warn", "kind": "regex_present",
            "params": {"path": "a.txt", "patterns": ["nope"]},
            "message": "m", "fix": "f"}]))
        results, issues = A.run(tmp)
        self.assertEqual(issues, [])
        self.assertFalse(results[0]["ok"])

    def test_json_value_ops(self):
        tmp = tempfile.mkdtemp()
        _mk(tmp, "d.json", json.dumps({"properties": {"a": 1, "b": 2}}))
        self._write(tmp, _decl(assertions=[{
            "id": "j", "severity": "fail", "kind": "json_value",
            "params": {"path": "d.json", "key": "properties", "op": "contains_keys",
                       "value": ["a", "b"]}, "message": "m", "fix": "f"}]))
        self.assertEqual(A.run(tmp)[1], [])
        self._write(tmp, _decl(assertions=[{
            "id": "j", "severity": "fail", "kind": "json_value",
            "params": {"path": "d.json", "key": "properties", "op": "contains_keys",
                       "value": ["zzz"]}, "message": "m", "fix": "f"}]))
        self.assertTrue(A.run(tmp)[1])

    def test_unknown_op_is_fail(self):
        tmp = tempfile.mkdtemp()
        _mk(tmp, "d.json", json.dumps({"x": 1}))
        self._write(tmp, _decl(assertions=[{
            "id": "j", "severity": "fail", "kind": "json_value",
            "params": {"path": "d.json", "key": "x", "op": "wat"},
            "message": "m", "fix": "f"}]))
        self.assertTrue(any("未知 op" in i for i in A.run(tmp)[1]))


class TestCapabilityFace(unittest.TestCase):
    """能力面：挂账（断言 → 能力）+ 覆盖（能力 → check）+ **空洞检测能红**。"""

    def test_real_repo_capabilities_cover_every_check(self):
        issues, stats = A.capability_report(str(ROOT))
        self.assertEqual(issues, [])
        self.assertTrue(stats["declared"])
        self.assertEqual(stats["covered"], stats["checks"])
        self.assertGreaterEqual(stats["capabilities"], 15)
        self.assertTrue(stats["aggregate_present"])
        self.assertEqual(stats["mapped_assertions"], stats["assertions"])

    def test_aggregate_only_checks_are_reported_not_hidden(self):
        # 32/36 目前只被聚合器压着（拆聚合门之前，这是诚实状态而不是静默通过）
        self.assertEqual(A.capability_report(str(ROOT))[1]["aggregate_only"], [32, 36])

    def _write_decl(self, tmp, doc):
        _mk(tmp, A.DECL_REL, json.dumps(doc, ensure_ascii=False))

    def _stub(self, tmp, checks=("check1", "check2")):
        _mk(tmp, "verify.sh", "".join("%s(){ :; }\n" % c for c in checks))

    def test_table_without_capability_face_stays_backward_compatible(self):
        tmp = tempfile.mkdtemp()
        self._write_decl(tmp, _decl(assertions=[{
            "id": "x", "severity": "fail", "kind": "regex_absent",
            "params": {"globs": [], "pattern": "a"}, "message": "m", "fix": "f"}]))
        self.assertEqual(A.scan(tmp)[0], [])

    def test_uncovered_check_is_a_hole(self):
        tmp = tempfile.mkdtemp()
        self._stub(tmp)
        self._write_decl(tmp, _decl(
            capability_vocabulary=[A.AGGREGATE_CAPABILITY, "CAP_X"],
            capability_index={A.AGGREGATE_CAPABILITY: [1], "CAP_X": [1]}))
        issues = A.scan(tmp)[0]
        self.assertTrue(any("能力空洞" in i and "2" in i for i in issues), issues)

    def test_index_referencing_missing_check_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._stub(tmp)
        self._write_decl(tmp, _decl(
            capability_vocabulary=[A.AGGREGATE_CAPABILITY, "CAP_X"],
            capability_index={A.AGGREGATE_CAPABILITY: [1, 2], "CAP_X": [9]}))
        issues = A.scan(tmp)[0]
        self.assertTrue(any("不存在的 check" in i and "9" in i for i in issues), issues)

    def test_assertion_without_capability_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._stub(tmp)
        self._write_decl(tmp, _decl(
            capability_vocabulary=[A.AGGREGATE_CAPABILITY, "CAP_X"],
            capability_index={A.AGGREGATE_CAPABILITY: [2], "CAP_X": [1]},
            assertions=[{"id": "bare", "severity": "fail", "kind": "regex_absent",
                         "params": {"globs": [], "pattern": "a"},
                         "message": "m", "fix": "f"}]))
        issues = A.scan(tmp)[0]
        self.assertTrue(any("未挂能力" in i and "bare" in i for i in issues), issues)

    def test_assertion_capability_outside_vocabulary_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._stub(tmp)
        self._write_decl(tmp, _decl(
            capability_vocabulary=[A.AGGREGATE_CAPABILITY, "CAP_X"],
            capability_index={A.AGGREGATE_CAPABILITY: [2], "CAP_X": [1]},
            assertions=[{"id": "row", "severity": "fail", "kind": "regex_absent",
                         "params": {"globs": [], "pattern": "a"}, "message": "m",
                         "fix": "f", "capability": "CAP_NOPE"}]))
        issues = A.scan(tmp)[0]
        self.assertTrue(any("越词表" in i and "CAP_NOPE" in i for i in issues), issues)

    def test_missing_aggregate_capability_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._stub(tmp)
        self._write_decl(tmp, _decl(capability_vocabulary=["CAP_X"],
                                    capability_index={"CAP_X": [1, 2]}))
        issues = A.scan(tmp)[0]
        self.assertTrue(any("聚合器" in i for i in issues), issues)

    def test_empty_capability_is_fail(self):
        tmp = tempfile.mkdtemp()
        self._stub(tmp)
        self._write_decl(tmp, _decl(
            capability_vocabulary=[A.AGGREGATE_CAPABILITY, "CAP_X"],
            capability_index={A.AGGREGATE_CAPABILITY: [1, 2], "CAP_X": []}))
        issues = A.scan(tmp)[0]
        self.assertTrue(any("没有任何 check" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
