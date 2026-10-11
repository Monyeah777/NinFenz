#!/usr/bin/env python3
"""风格棘轮（Z2）回归测试。

覆盖三层：
1. compare 纯函数：新增/上升 = FAIL；下降 = WARN；工具跑不成/缺基线 = fail-closed。
2. 基线形状：schema / select / counts 在场（防「基线被换成空壳」的假绿）。
3. 真实仓库：当前命中 == 基线（本机无 ruff 则跳过并写明理由，不静默吞）。
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("nf_style_check",
 ROOT / "scripts" / "style_check.py")
assert _spec is not None and _spec.loader is not None
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


class CompareTest(unittest.TestCase):
    """纯函数比对（不依赖 ruff 是否在场）。"""

    def test_new_key_is_fail(self):
        base = {"counts": {"a.py::E501": 1}, "tool_version": "v"}
        cur = {"counts": {"a.py::E501": 1, "b.py::W291": 2}, "meta": {"version": "v"}}
        issues, _warns, _s = sc.compare(cur, base)
        self.assertTrue(any("新增风格命中" in i and "W291" in i for i in issues), issues)

    def test_count_up_is_fail(self):
        base = {"counts": {"a.py::E501": 1}, "tool_version": "v"}
        cur = {"counts": {"a.py::E501": 3}, "meta": {"version": "v"}}
        issues, _warns, _s = sc.compare(cur, base)
        self.assertTrue(any("上升" in i and "1 → 3" in i for i in issues), issues)

    def test_count_down_is_warn_only(self):
        base = {"counts": {"a.py::E501": 3}, "tool_version": "v"}
        cur = {"counts": {"a.py::E501": 1}, "meta": {"version": "v"}}
        issues, warns, _s = sc.compare(cur, base)
        self.assertEqual([], issues, issues)
        self.assertTrue(any("下降" in w for w in warns), warns)

    def test_equal_is_clean(self):
        base = {"counts": {"a.py::E501": 1}, "tool_version": "v"}
        cur = {"counts": {"a.py::E501": 1}, "meta": {"version": "v"}}
        issues, warns, _s = sc.compare(cur, base)
        self.assertEqual([], issues)
        self.assertEqual([], warns)

    def test_tool_error_is_fail_closed(self):
        cur = {"counts": {}, "meta": {"error": "ruff 不在"}}
        issues, _warns, _s = sc.compare(cur, {"counts": {"a.py::E501": 1}})
        self.assertTrue(any("未跑成" in i for i in issues), issues)

    def test_missing_baseline_is_fail_closed(self):
        cur = {"counts": {"a.py::E501": 1}, "meta": {"version": "v"}}
        issues, _warns, _s = sc.compare(cur, {})
        self.assertTrue(any("缺风格基线" in i for i in issues), issues)

    def test_version_drift_is_warn(self):
        base = {"counts": {"a.py::E501": 1}, "tool_version": "0.16.8"}
        cur = {"counts": {"a.py::E501": 1}, "meta": {"version": "0.99.0"}}
        issues, warns, _s = sc.compare(cur, base)
        self.assertEqual([], issues)
        self.assertTrue(any("版本与基线不同" in w for w in warns), warns)


class BaselineShapeTest(unittest.TestCase):
    def test_baseline_shape(self):
        doc = sc.load_baseline()
        self.assertTrue(doc, "缺 protocol/style_baseline.json（修复指引：--write 冻结）")
        self.assertEqual(sc.SCHEMA, doc.get("schema"))
        self.assertEqual(sc.SELECT,
 doc.get("select"),
 "基线的规则集与脚本分叉（同一门两套 select）")
        self.assertIn("counts", doc)
        self.assertTrue(doc["counts"], "基线 counts 为空 = 空壳基线（假绿）")


class RealRepoTest(unittest.TestCase):
    def test_real_repo_is_at_baseline(self):
        cur = sc.current()
        if (cur.get("meta") or {}).get("error"):
            self.skipTest("本机无 ruff：%s" % cur["meta"]["error"])
        issues, _warns, stats = sc.compare(cur, sc.load_baseline())
        self.assertEqual([], issues[:5], "风格棘轮未过（%s）：%s" % (stats, issues[:5]))


if __name__ == "__main__":
    unittest.main()
