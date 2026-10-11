# -*- coding: utf-8 -*-
"""P-A5 差分自证：规则层路由（DAG/朴素/半朴素三后端）必须与影响图闭包同结果。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_datalog as gd  # noqa: E402
from core import gate_faces as gf    # noqa: E402
from core import gate_graph as gg    # noqa: E402


def _expected(root, changed_modules, experts):
    dep = gg.module_deps(root)
    affected = gg.closure(dep, changed_modules)
    out = set()
    for eid, e in experts.items():
        mod = str(e.get("module") or "").strip()
        stem = Path(mod).stem if mod else eid
        if stem in affected or stem in changed_modules:
            out.add(eid)
    return out


class DatalogRouteTest(unittest.TestCase):
    CASES = (["gate_graph"], ["gate_faces"], ["nfal_rules"], ["gate_cache", "gate_router"], ())

    def test_rules_match_closure_for_real_repo(self):
        experts = gf.load_manifest(str(ROOT))
        self.assertGreaterEqual(len(experts), 4)
        bad = []
        for changed in self.CASES:
            got, _res = gd.routed(str(ROOT), changed, experts=experts, backend="dag")
            want = _expected(str(ROOT), list(changed), experts)
            if set(got) != want:
                bad.append((changed, sorted(want), got))
        self.assertEqual([], bad, "规则层与闭包分歧：%s" % bad[:2])

    def test_three_backends_agree_on_route(self):
        experts = gf.load_manifest(str(ROOT))
        for changed in (["gate_graph"], ["gate_cache", "gate_router"]):
            a, _ = gd.routed(str(ROOT), changed, experts=experts, backend="dag")
            b, _ = gd.routed(str(ROOT), changed, experts=experts, backend="naive")
            c, _ = gd.routed(str(ROOT), changed, experts=experts, backend="seminaive")
            self.assertEqual(a, b, changed)
            self.assertEqual(a, c, changed)

    def test_graph_stats_present(self):
        experts = gf.load_manifest(str(ROOT))
        _hits, got = gd.routed(str(ROOT), ["gate_graph"], experts=experts, backend="dag")
        self.assertEqual("OK", got["status"])
        self.assertGreater(got["graph"]["nodes"], 100)
        self.assertGreater(got["graph"]["edges"], 100)


if __name__ == "__main__":
    unittest.main()
