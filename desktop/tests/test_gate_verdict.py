#!/usr/bin/env python3
"""gate_verdict 判据：内容寻址判定缓存的三条纪律与安全边界。"""
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import disk_cache  # noqa: E402
from core import gate_verdict as gv  # noqa: E402


def _node():
    """每个用例一个唯一节点名：缓存是全局的，判据之间不得互相命中。"""
    return "t_" + uuid.uuid4().hex[:12]


def _root(tmp):
    r = Path(tmp)
    (r / "src").mkdir(parents=True, exist_ok=True)
    (r / "src" / "a.txt").write_text("v1", encoding="utf-8", newline="\n")
    (r / "code.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
    return r


def _counter():
    calls = []

    def compute():
        calls.append(1)
        return {"rc": 0, "n": len(calls)}

    return compute, calls


class CacheTest(unittest.TestCase):
    """命中/失效三态。"""

    def test_miss_then_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp)
            compute, calls = _counter()
            node = _node()
            v1, hit1 = gv.verdict(node, ["src/a.txt"], compute, root=str(root),
                                  code_files=["code.py"])
            v2, hit2 = gv.verdict(node, ["src/a.txt"], compute, root=str(root),
                                  code_files=["code.py"])
            self.assertFalse(hit1)
            self.assertTrue(hit2)
            self.assertEqual(v1, v2)
            self.assertEqual(len(calls), 1)

    def test_content_change_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp)
            compute, calls = _counter()
            node = _node()
            gv.verdict(node, ["src/a.txt"], compute, root=str(root), code_files=["code.py"])
            (root / "src" / "a.txt").write_text("v2", encoding="utf-8", newline="\n")
            _v, hit = gv.verdict(node, ["src/a.txt"], compute, root=str(root),
                                 code_files=["code.py"])
            self.assertFalse(hit)
            self.assertEqual(len(calls), 2)

    def test_code_change_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp)
            compute, calls = _counter()
            node = _node()
            gv.verdict(node, ["src/a.txt"], compute, root=str(root), code_files=["code.py"])
            (root / "code.py").write_text("x = 2\n", encoding="utf-8", newline="\n")
            _v, hit = gv.verdict(node, ["src/a.txt"], compute, root=str(root),
                                 code_files=["code.py"])
            self.assertFalse(hit)
            self.assertEqual(len(calls), 2)

    def test_absent_file_is_stable_then_invalidates_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp)
            compute, calls = _counter()
            node = _node()
            files = ["src/a.txt", "src/nope.txt"]
            _v1, hit1 = gv.verdict(node, files, compute, root=str(root), code_files=["code.py"])
            _v2, hit2 = gv.verdict(node, files, compute, root=str(root), code_files=["code.py"])
            self.assertFalse(hit1)
            self.assertTrue(hit2, "缺席清单稳定时必须能命中")
            (root / "src" / "nope.txt").write_text("now", encoding="utf-8", newline="\n")
            _v3, hit3 = gv.verdict(node, files, compute, root=str(root), code_files=["code.py"])
            self.assertFalse(hit3, "缺席者出现必须换键")
            self.assertEqual(len(calls), 2)


class SafetyTest(unittest.TestCase):
    """安全边界：FAIL 如实缓存、坏条目当未命中、标签按节点分。"""

    def test_failed_verdict_is_cached_as_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp)
            node = _node()
            calls = []

            def compute():
                calls.append(1)
                return {"rc": 1}

            _v1, hit1 = gv.verdict(node, ["src/a.txt"], compute, root=str(root),
                                   code_files=["code.py"])
            v2, hit2 = gv.verdict(node, ["src/a.txt"], compute, root=str(root),
                                  code_files=["code.py"])
            self.assertFalse(hit1)
            self.assertTrue(hit2)
            self.assertEqual(v2["rc"], 1, "红判定不得被缓存洗成绿")

    def test_bad_entry_shape_is_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp)
            node = _node()
            ckey, entry, tag = gv.key_and_entry(node, ["src/a.txt"], root=str(root),
                                                code_files=["code.py"])
            disk_cache.store(tag, ckey, {"nope": 1})
            (hit, _v), _k, _e, _t = gv.lookup(node, ["src/a.txt"], root=str(root),
                                              code_files=["code.py"])
            self.assertFalse(hit, "形状不对的条目一律当未命中")

    def test_tag_is_per_node(self):
        self.assertNotEqual(gv.tag_for("a"), gv.tag_for("b"))
        self.assertEqual(gv.tag_for("a"), gv.tag_for("a"))
        self.assertTrue(gv.tag_for("a").startswith(gv.TAG_PREFIX + "/"))

    def test_tag_sanitizes_separators(self):
        self.assertNotIn("/", gv.tag_for("a/b").split("/", 1)[1])


class DiskIsolationTest(unittest.TestCase):
    """两个节点互不裁剪：各自标签各自条目。"""

    def test_two_nodes_do_not_evict_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root(tmp)
            compute, calls = _counter()
            n1, n2 = _node(), _node()
            gv.verdict(n1, ["src/a.txt"], compute, root=str(root), code_files=["code.py"])
            gv.verdict(n2, ["src/a.txt"], compute, root=str(root), code_files=["code.py"])
            before = len(calls)
            _v1, h1 = gv.verdict(n1, ["src/a.txt"], compute, root=str(root),
                                 code_files=["code.py"])
            _v2, h2 = gv.verdict(n2, ["src/a.txt"], compute, root=str(root),
                                 code_files=["code.py"])
            self.assertTrue(h1 and h2)
            self.assertEqual(len(calls), before)


if __name__ == "__main__":
    unittest.main()
