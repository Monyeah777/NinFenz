#!/usr/bin/env python3
"""原子层单测（门禁能力化重构 · 步骤1）：每个原子至少一正一反两例 + 纯度断言。

纯度断言守三件事（对应设计文档 §5.2 与 §4.1）：
1. 源码里**没有** PASS/FAIL/WARN/SKIP 这类判定态字面量——原子只回数据；
2. 原子不反向依赖上层（core 上层 / scripts / tui / nf）——它必须是可被外部复用的叶子；
3. 公开函数都有 docstring（本仓口径：没有文档的公开面等于没有约束）。
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.atoms import code as code_atom  # noqa: E402
from core.atoms import fs as fs_atom  # noqa: E402
from core.atoms import hash as hash_atom  # noqa: E402
from core.atoms import proc as proc_atom  # noqa: E402
from core.atoms import sets as sets_atom  # noqa: E402
from core.atoms import struct as struct_atom  # noqa: E402
from core.atoms import text as text_atom  # noqa: E402

ATOMS_DIR = ROOT / "desktop" / "src" / "core" / "atoms"
VERDICT_WORDS = {"PASS", "FAIL", "WARN", "SKIP"}
#: 原子允许依赖的同层叶子件（其余 core 模块一律算反向依赖，会破坏「能力层可自由复用」）。
ALLOWED_CORE = {"repo_face", "json_doc", "json_schema", "lazy_yaml", "atoms"}


def _verdict_like(value) -> bool:
    """返回值里是否夹带判定态（递归查字符串元素）。"""
    if isinstance(value, str):
        return value.strip().upper() in VERDICT_WORDS
    if isinstance(value, dict):
        return any(_verdict_like(k) or _verdict_like(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(_verdict_like(item) for item in value)
    return False


class _TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text="x", encoding="utf-8"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)
        return path


class FsAtomsTest(_TmpCase):
    def test_file_exists_true_for_file_false_for_missing(self):
        path = self.write("a.txt")
        self.assertTrue(fs_atom.file_exists(path))
        self.assertFalse(fs_atom.file_exists(self.root / "nope.txt"))

    def test_dir_exists_true_for_dir_false_for_missing(self):
        (self.root / "sub").mkdir()
        self.assertTrue(fs_atom.dir_exists(self.root / "sub"))
        self.assertFalse(fs_atom.dir_exists(self.root / "nope"))
        self.assertFalse(fs_atom.dir_exists(self.write("plain.txt")))

    def test_read_text_roundtrip_and_absent_and_undecodable(self):
        self.assertEqual(fs_atom.read_text(self.write("a.txt", "正文\n")), "正文\n")
        self.assertIsNone(fs_atom.read_text(self.root / "nope.txt"))
        bad = self.root / "bad.bin"
        bad.write_bytes(b"\xff\xfe\x00")
        self.assertIsNone(fs_atom.read_text(bad))

    def test_iter_entries_sorted_and_missing_dir(self):
        (self.root / "b_dir").mkdir()
        self.write("a.txt", "abc")
        entries = fs_atom.iter_entries(self.root)
        self.assertEqual([name for name, _, _ in entries], ["a.txt", "b_dir"])
        self.assertEqual(entries[0][1:], (False, 3))
        self.assertTrue(entries[1][1])
        self.assertEqual(fs_atom.iter_entries(self.root / "nope"), [])

    def test_walk_files_lists_posix_rels_and_honours_skip(self):
        self.write("keep/a.txt")
        self.write("skip/b.txt")
        rels = fs_atom.walk_files(self.root, skip=("skip",))
        self.assertEqual(rels, ["keep/a.txt"])
        self.assertEqual(fs_atom.walk_files(self.root), ["keep/a.txt", "skip/b.txt"])


class HashAtomsTest(_TmpCase):
    def test_sha256_bytes_known_vector(self):
        self.assertEqual(hash_atom.sha256_bytes(b"abc"),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_sha256_file_matches_bytes_and_absent_is_none(self):
        path = self.write("a.txt", "abc")
        self.assertEqual(hash_atom.sha256_file(path), hash_atom.sha256_bytes(b"abc"))
        self.assertIsNone(hash_atom.sha256_file(self.root / "nope.txt"))

    def test_tree_digest_stable_and_content_sensitive(self):
        self.write("a.txt", "one")
        first = hash_atom.tree_digest(self.root)
        self.assertEqual(first, hash_atom.tree_digest(self.root))
        self.write("a.txt", "two")
        self.assertNotEqual(first, hash_atom.tree_digest(self.root))
        self.assertIsNone(hash_atom.tree_digest(self.root / "nope"))


class StructAtomsTest(_TmpCase):
    def test_json_load_validated_accepts_expected_shape(self):
        path = self.write("d.json", '{"a": 1}')
        self.assertEqual(struct_atom.json_load_validated(path, dict), {"a": 1})
        self.assertEqual(struct_atom.json_load_validated(path, (dict, list)), {"a": 1})

    def test_json_load_validated_none_for_bad_shape_bad_json_and_absent(self):
        path = self.write("l.json", "[1, 2]")
        self.assertIsNone(struct_atom.json_load_validated(path, dict))
        broken = self.write("b.json", "{not json")
        self.assertIsNone(struct_atom.json_load_validated(broken, dict))
        self.assertIsNone(struct_atom.json_load_validated(self.root / "nope.json", dict))

    def test_json_schema_validate_reports_fields_and_passes_valid(self):
        schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}
        issues = struct_atom.json_schema_validate({"a": "x"}, schema)
        self.assertEqual(issues, [])
        broken = struct_atom.json_schema_validate({}, schema)
        self.assertTrue(broken)
        self.assertIn("a", broken[0])

    def test_json_schema_validate_rejects_non_object_schema_with_guidance(self):
        with self.assertRaises(ValueError) as ctx:
            struct_atom.json_schema_validate({}, ["not", "a", "schema"])
        self.assertIn("修复指引", str(ctx.exception))

    def test_yaml_load_safe_roundtrip_absent_and_bad(self):
        path = self.write("p.yaml", "a: 1\nb:\n  - x\n")
        self.assertEqual(struct_atom.yaml_load_safe(path), {"a": 1, "b": ["x"]})
        self.assertIsNone(struct_atom.yaml_load_safe(self.root / "nope.yaml"))
        broken = self.write("b.yaml", "a: [1,\n")
        self.assertIsNone(struct_atom.yaml_load_safe(broken))


class SetsAtomsTest(unittest.TestCase):
    def test_reconcile_reports_only_in_and_counts(self):
        got = sets_atom.reconcile({"a": ["x", "y"], "b": ["y"], "c": ["y", "z"]})
        self.assertEqual(got["only_in"], {"a": ["x"], "b": [], "c": ["z"]})
        self.assertEqual(got["counts"], {"a": 2, "b": 1, "c": 2})

    def test_reconcile_disjoint_sets(self):
        got = sets_atom.reconcile({"a": ["x"], "b": ["y"]})
        self.assertEqual(got["only_in"], {"a": ["x"], "b": ["y"]})

    def test_subset_lists_missing_and_no_missing(self):
        self.assertEqual(sets_atom.subset(["a", "b", "c"], ["a", "c"]), ["b"])
        self.assertEqual(sets_atom.subset(["a"], ["a", "b"]), [])


class TextAtomsTest(unittest.TestCase):
    def test_keyword_both_ways_reports_missing_side(self):
        got = text_atom.keyword_both_ways("alpha beta", "alpha", ["alpha", "beta"])
        self.assertEqual(got, [("b", "beta")])
        self.assertEqual(
            text_atom.keyword_both_ways("alpha", "alpha beta", ["beta"]), [("a", "beta")])

    def test_keyword_both_ways_silent_when_aligned_or_absent_on_both(self):
        self.assertEqual(text_atom.keyword_both_ways("alpha beta", "beta alpha", ["alpha"]), [])
        self.assertEqual(text_atom.keyword_both_ways("x", "y", ["alpha"]), [])

    def test_regex_absent_returns_hits_with_line_numbers(self):
        hits = text_atom.regex_absent("ok\nBAD 1\nok\nBAD 2\n", r"^BAD")
        self.assertEqual([number for number, _ in hits], [2, 4])
        self.assertEqual(text_atom.regex_absent("ok\n", r"^BAD"), [])

    def test_regex_absent_bad_pattern_raises_with_guidance(self):
        with self.assertRaises(ValueError) as ctx:
            text_atom.regex_absent("x", "(")
        self.assertIn("修复指引", str(ctx.exception))


class CodeAtomsTest(_TmpCase):
    def test_parse_py_ok_syntax_error_and_absent(self):
        self.assertIsNotNone(code_atom.parse_py(self.write("m.py", "x = 1\n")))
        self.assertIsNone(code_atom.parse_py(self.write("bad.py", "def (\n")))
        self.assertIsNone(code_atom.parse_py(self.root / "nope.py"))

    def test_find_calls_filtered_sorted_and_none_tree(self):
        tree = code_atom.parse_py(self.write("m.py", "b()\na()\nb()\n"))
        self.assertEqual(code_atom.find_calls(tree, {"a", "b"}), [("b", 1), ("a", 2), ("b", 3)])
        self.assertEqual(code_atom.find_calls(tree, {"a"}), [("a", 2)])
        self.assertEqual(code_atom.find_calls(None), [])


class ProcAtomsTest(unittest.TestCase):
    def test_run_capture_success(self):
        got = proc_atom.run_capture([sys.executable, "-c", "print('hi')"])
        self.assertEqual(got["code"], 0)
        self.assertEqual(got["out"].strip(), "hi")

    def test_run_capture_nonzero_and_unlaunchable(self):
        failing = proc_atom.run_capture([sys.executable, "-c", "raise SystemExit(3)"])
        self.assertEqual(failing["code"], 3)
        missing_bin = str(Path(tempfile.gettempdir()) / "nope-binary-x")
        self.assertIsNone(proc_atom.run_capture([missing_bin])["code"])

    def test_run_twice_returns_both_results(self):
        calls = []
        got = proc_atom.run_twice(lambda: calls.append(1) or len(calls))
        self.assertEqual(got, (1, 2))


class AtomsPurityTest(unittest.TestCase):
    def test_sources_carry_no_verdict_literals(self):
        offenders = []
        for path in sorted(ATOMS_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and node.value.strip() in VERDICT_WORDS):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_no_upward_imports(self):
        offenders = []
        for path in sorted(ATOMS_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module] + [f"{node.module}.{alias.name}"
                                             for alias in node.names]
                for name in names:
                    parts = name.split(".")
                    if parts[0] != "core":
                        continue
                    if len(parts) > 1 and parts[1] not in ALLOWED_CORE:
                        offenders.append(f"{path.name}:{name}")
        self.assertEqual(offenders, [])

    def test_representative_results_are_data_not_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "a.txt"
            sample.write_text("abc", encoding="utf-8")
            results = [
                fs_atom.file_exists(root / "nope.txt"),
                fs_atom.read_text(sample),
                fs_atom.iter_entries(root),
                hash_atom.sha256_file(sample),
                hash_atom.tree_digest(root),
                struct_atom.json_load_validated(root / "nope.json", dict),
                struct_atom.json_schema_validate({"a": 1}, {"type": "object"}),
                struct_atom.yaml_load_safe(root / "nope.yaml"),
                sets_atom.reconcile({"a": ["x"]}),
                sets_atom.subset(["a"], []),
                text_atom.keyword_both_ways("a", "b", ["a"]),
                text_atom.regex_absent("a", "b"),
                code_atom.parse_py(sample),
                code_atom.find_calls(None),
                proc_atom.run_capture([sys.executable, "-c", "pass"]),
            ]
            for value in results:
                self.assertFalse(_verdict_like(value), f"原子返回了判定态：{value!r}")

    def test_public_functions_are_documented(self):
        undocumented = []
        for path in sorted(ATOMS_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if (isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
                        and not ast.get_docstring(node)):
                    undocumented.append(f"{path.name}:{node.name}")
        self.assertEqual(undocumented, [])


if __name__ == "__main__":
    unittest.main()
