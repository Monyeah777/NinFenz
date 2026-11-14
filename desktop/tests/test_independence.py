#!/usr/bin/env python3
"""生产/治理双平面边界判据（方案 §5.5 IN-01/IN-02）：正例 + 变异自证。

为什么有它：边界如果只写在文档里，下一次「生产顺手 import 治理」没人拦；本件把
`protocol/independence.json` 的归属登记变成可复算判据，并用临时仓逐类注入证明：
1) 真仓三平面闭包零交叉、在盘报告 == 实时重算；
2) 正/反 import 边（生产→治理、治理→生产、共享→生产）都能红；
3) **未登记的中间模块**也逃不掉（闭包遍历全部 core 模块，不是只看清单内一跳）；
4) 登记表本身：缺模块、跨平面重复、动态导入未登记白名单都红；
5) 在盘报告漂移即红（report 必须由 --write 重算）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import independence as ind  # noqa: E402

PLANES = {"production": ["maker"], "governance": ["auditor"], "shared": ["prims"]}


def _mk(tmp, modules, planes=None, dynamic_allow=None):
    """搭一个最小仓：desktop/src/core/*.py + protocol/independence.json。"""
    core = Path(tmp) / "desktop" / "src" / "core"
    core.mkdir(parents=True, exist_ok=True)
    (core / "__init__.py").write_text("", encoding="utf-8")
    for name, text in modules.items():
        (core / (name + ".py")).write_text(text, encoding="utf-8")
    proto = Path(tmp) / "protocol"
    proto.mkdir(parents=True, exist_ok=True)
    doc = {"schema": ind.SCHEMA, "planes": planes or PLANES,
           "dynamic_allow": dynamic_allow or {}}
    (proto / "independence.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return tmp


def _codes(issues):
    return "\n".join(issues)


class RealRepoTest(unittest.TestCase):
    def test_repo_clean(self):
        issues, stats = ind.scan(str(ROOT))
        self.assertEqual([], issues)
        self.assertEqual(0, stats["forbidden_edges"])
        self.assertGreaterEqual(stats["production"], 20)
        self.assertGreaterEqual(stats["governance"], 5)
        self.assertGreaterEqual(stats["shared"], 10)

    def test_committed_report_matches_recompute(self):
        self.assertEqual([], ind.check_committed(str(ROOT)))

    def test_registry_valid(self):
        doc = ind.load(str(ROOT))
        self.assertEqual([], ind.validate(doc, str(ROOT)))
        allow = doc.get("dynamic_allow") or {}
        self.assertTrue(allow, "动态导入白名单不能为空（否则 exporter 一类无法通过）")


class MutationTest(unittest.TestCase):
    def test_production_importing_governance_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": "from core import auditor\n", "auditor": "",
                      "prims": ""})
            issues, stats = ind.scan(tmp)
            self.assertTrue(issues, "生产 import 治理必须红")
            self.assertEqual(1, stats["forbidden_edges"])
            self.assertIn("maker", _codes(issues))

    def test_governance_importing_production_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": "", "auditor": "from core import maker\n", "prims": ""})
            issues, _ = ind.scan(tmp)
            self.assertTrue(any("governance" in i for i in issues), issues)

    def test_shared_importing_production_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": "", "auditor": "", "prims": "from core import maker\n"})
            issues, _ = ind.scan(tmp)
            self.assertTrue(any("shared" in i for i in issues), issues)

    def test_transitive_leak_via_undeclared_middle_module_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": "from core import util\n", "auditor": "",
                      "prims": "", "util": "from core import auditor\n"})
            issues, _ = ind.scan(tmp)
            self.assertTrue(issues, "未登记中间模块的跨平面闭包也必须红")
            self.assertIn("util", _codes(issues), "路径须写明经过 util")

    def test_missing_module_in_registry_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": "", "auditor": "", "prims": ""},
                planes={"production": ["maker"], "governance": ["auditor"],
                        "shared": ["prims", "ghost"]})
            issues, _ = ind.scan(tmp)
            self.assertTrue(any("ghost" in i for i in issues), issues)

    def test_duplicate_plane_membership_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": "", "auditor": "", "prims": ""},
                planes={"production": ["maker"], "governance": ["auditor"],
                        "shared": ["prims", "maker"]})
            issues, _ = ind.scan(tmp)
            self.assertTrue(any("同时登记" in i or "互斥" in i for i in issues), issues)

    def test_dynamic_import_red_unless_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": 'import importlib\nimportlib.import_module("x")\n',
                      "auditor": "", "prims": ""})
            issues, _ = ind.scan(tmp)
            self.assertTrue(any("动态导入" in i for i in issues), issues)
            with tempfile.TemporaryDirectory() as tmp2:
                _mk(tmp2, {"maker": 'import importlib\nimportlib.import_module("x")\n',
                           "auditor": "", "prims": ""},
                    dynamic_allow={"maker": "测试用：按名构造，另有 golden 测试"})
                issues2, _ = ind.scan(tmp2)
                self.assertEqual([], issues2)

    def test_report_drift_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk(tmp, {"maker": "", "auditor": "", "prims": ""})
            issues, _doc = ind.write(tmp)
            self.assertEqual([], issues)
            self.assertEqual([], ind.check_committed(tmp))
            report = Path(tmp) / ind.REPORT_REL
            report.write_text(report.read_text(encoding="utf-8") + " ", encoding="utf-8")
            self.assertTrue(ind.check_committed(tmp), "报告被手改必须红")


if __name__ == "__main__":
    unittest.main()
