"""asset_contract._REPO_FILES 的新鲜度判据（2026-10-23）。

历史缺口：仓库件集合按 root 进程级缓存、无 generation；新增文件在缓存未清前不可见。
现口径：缓存只在一次 `scan()` 作用域内有效；直接 `resolve()` 一律现算。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import asset_contract as ac  # noqa: E402
from core import conformance_scan as csc  # noqa: E402


class RepoFilesFreshnessTest(unittest.TestCase):
    def test_direct_resolve_sees_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "protocol" / "schema").mkdir(parents=True)
            (root / "protocol" / "schema" / "a.json").write_text("{}", encoding="utf-8")
            ac.clear_repo_files_cache()
            spec = {"glob": "protocol/schema/*.json"}
            self.assertEqual(["protocol/schema/a.json"], ac.resolve(str(root), spec))
            (root / "protocol" / "schema" / "b.json").write_text("{}", encoding="utf-8")
            self.assertEqual(["protocol/schema/a.json", "protocol/schema/b.json"],
                             ac.resolve(str(root), spec),
                             "新增文件被进程级缓存吞掉（新鲜度回归）")

    def test_cache_is_scoped_to_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "protocol" / "schema").mkdir(parents=True)
            (root / "protocol" / "schema" / "a.json").write_text("{}", encoding="utf-8")
            spec = {"glob": "protocol/schema/*.json"}
            ac._begin_repo_scope()
            try:
                self.assertEqual(["protocol/schema/a.json"], ac.resolve(str(root), spec))
                (root / "protocol" / "schema" / "b.json").write_text("{}", encoding="utf-8")
                self.assertEqual(["protocol/schema/a.json"], ac.resolve(str(root), spec),
                                 "同一次 scan 内应复用清单")
            finally:
                ac._end_repo_scope()
            self.assertEqual(["protocol/schema/a.json", "protocol/schema/b.json"],
                             ac.resolve(str(root), spec),
                             "scan 结束后缓存必须清空")

    def test_schema_document_cache_is_mtime_size_keyed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = root / "schema.json"
            schema.write_text('{"type":"object"}', encoding="utf-8")
            one, err = ac._schema_doc(str(root), "schema.json")
            self.assertIsNone(err)
            self.assertEqual("object", one["type"])
            two, err = ac._schema_doc(str(root), "schema.json")
            self.assertIsNone(err)
            self.assertIs(one, two)
            schema.write_text('{"type":"object","required":[]}', encoding="utf-8")
            changed, err = ac._schema_doc(str(root), "schema.json")
            self.assertIsNone(err)
            self.assertEqual([], changed["required"])

    def test_memory_glob_matches_pathlib_face(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = ["a/x.json", "a/y.json", "a/deep/z.json", "b/q.txt"]
            for rel in files:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("{}", encoding="utf-8")
            pattern = "a/**/*.json"
            want = sorted(p.relative_to(root).as_posix()
                          for p in root.glob(pattern) if p.is_file())
            got = sorted(rel for rel in files if csc.match_rel(rel, pattern))
            self.assertEqual(want, got)


if __name__ == "__main__":
    unittest.main()
