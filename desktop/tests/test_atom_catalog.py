"""原子目录 v2 + 不变量 A1–A5 + 候选健康 B1–B5 判据（P4）。

判据重点：
① v2 是**派生视图**，不回写 v1（v1 文件 digest 不变）；
② A1–A5 每条都有反例 fixture：引用不存在/成环/自引用、契约缺字段、witness 空泛词、id 前缀错、
   新增死码——全部必须红并指名到原子；
③ 存量死码记债后为 warning（可见但不阻塞），**新增**死码必须 fail-closed；
④ 候选健康 B1–B5 各自可触发，输出 candidate-insufficient；不给候选排序、不打分。
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import atom_catalog as ac  # noqa: E402
from core.meta_cockpit import candidate_health as ch  # noqa: E402

ATOMS = ROOT / "desktop/src/core/meta_cockpit/meta_atoms.json"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CatalogTest(unittest.TestCase):
    def test_catalog_builds_33_atoms(self):
        cat = ac.build(str(ROOT))
        self.assertEqual(33, cat["count"])
        self.assertEqual("nf/atom-catalog/2", cat["schema"])

    def test_catalog_has_required_v2_fields(self):
        cat = ac.build(str(ROOT))
        for atom in cat["atoms"]:
            for field in ("id", "meta_level", "composed_of", "aliases", "tags",
                          "status", "version", "contract", "success_witness",
                          "failure_modes"):
                self.assertIn(field, atom)
            self.assertTrue(atom["success_witness"]["observe"])
            self.assertTrue(atom["success_witness"]["falsifier"])

    def test_build_does_not_mutate_v1(self):
        before = _digest(ATOMS)
        ac.build(str(ROOT))
        self.assertEqual(before, _digest(ATOMS))

    def test_build_is_deterministic(self):
        self.assertEqual(json.dumps(ac.build(str(ROOT)), sort_keys=True),
                         json.dumps(ac.build(str(ROOT)), sort_keys=True))


class InvariantTest(unittest.TestCase):
    def _cat(self) -> dict:
        cat = json.loads(json.dumps(ac.build(str(ROOT))))
        cat["atom_debt"] = [a["id"] for a in cat["atoms"]]   # 基线：不因存量死码失败
        return cat

    def test_current_state_passes(self):
        inv = ac.invariants(ac.build(str(ROOT)))
        self.assertTrue(inv["ok"], inv["violations"][:3])

    def test_a1_missing_reference(self):
        cat = self._cat()
        cat["atoms"][0]["composed_of"] = ["no.such.atom"]
        inv = ac.invariants(cat)
        self.assertFalse(inv["ok"])
        self.assertTrue(any(v["code"] == "A1" and v["atom"] == cat["atoms"][0]["id"]
                            for v in inv["violations"]))

    def test_a1_self_reference(self):
        cat = self._cat()
        aid = cat["atoms"][0]["id"]
        cat["atoms"][0]["composed_of"] = [aid]
        self.assertTrue(any(v["code"] == "A1" and "自引用" in v["detail"]
                            for v in ac.invariants(cat)["violations"]))

    def test_a1_cycle(self):
        cat = self._cat()
        a, b = cat["atoms"][0]["id"], cat["atoms"][1]["id"]
        cat["atoms"][0]["composed_of"] = [b]
        cat["atoms"][1]["composed_of"] = [a]
        self.assertTrue(any(v["code"] == "A1" and "成环" in v["detail"]
                            for v in ac.invariants(cat)["violations"]))

    def test_a2_bad_contract(self):
        cat = self._cat()
        cat["atoms"][0]["contract"]["cost"] = "free"
        cat["atoms"][0]["contract"]["adds"] = "not-a-list"
        codes = [v["code"] for v in ac.invariants(cat)["violations"]]
        self.assertIn("A2", codes)

    def test_a3_vague_witness(self):
        cat = self._cat()
        cat["atoms"][0]["success_witness"]["observe"] = "更好"
        self.assertTrue(any(v["code"] == "A3" and "空泛词" in v["detail"]
                            for v in ac.invariants(cat)["violations"]))

    def test_a5_bad_prefix(self):
        cat = self._cat()
        cat["atoms"][0]["id"] = "x.wrong-prefix"
        self.assertTrue(any(v["code"] == "A5" for v in ac.invariants(cat)["violations"]))

    def test_a5_duplicate_id(self):
        cat = self._cat()
        cat["atoms"][1]["id"] = cat["atoms"][0]["id"]
        self.assertTrue(any(v["code"] == "A5" and "id 重复" in v["detail"]
                            for v in ac.invariants(cat)["violations"]))

    def test_a4_new_dead_atom_fails_closed(self):
        """新增死码必须红：注掉一个原子的所有引用，A4 立刻判违规。"""
        cat = self._cat()
        cat["atom_debt"] = []
        cat["pack_references"] = []
        victim = cat["atoms"][0]["id"]
        cat["atoms"][1]["composed_of"] = []
        inv = ac.invariants(cat)
        self.assertFalse(inv["ok"])
        self.assertTrue(any(v["code"] == "A4" and v["atom"] == victim
                            for v in inv["violations"]))

    def test_a4_debt_becomes_warning(self):
        """已记债的死码只 WARN（可追溯），并且**真实仓当前零死码**（债已随方法包还清）。"""
        cat = self._cat()
        cat["pack_references"] = []
        cat["atoms"][1]["composed_of"] = []
        victim = cat["atoms"][0]["id"]
        cat["atom_debt"] = [victim]
        inv = ac.invariants(cat)
        # 记债的原子只 WARN、不进违规；未记债的其它死码仍按 fail-closed 判红
        self.assertTrue(any(w["code"] == "A4" and w["atom"] == victim
                            for w in inv["warnings"]))
        self.assertNotIn(victim, [v["atom"] for v in inv["violations"]])
        real = ac.invariants(ac.build(str(ROOT)))
        self.assertEqual([], [w for w in real["warnings"] if w["code"] == "A4"],
                         "真实仓仍有无引用的死码：要么接入，要么写进 atom_debt.json")
        self.assertEqual([], [v for v in real["violations"] if v["code"] == "A4"])


class CandidateHealthTest(unittest.TestCase):
    def _cand(self, **kwargs) -> dict:
        base = {"id": "c1", "produces": ["x"], "anchors": ["a"], "repairs": ["k1"], "cost": 1}
        base.update(kwargs)
        return base

    def test_good_candidates(self):
        res = ch.assess([self._cand(), self._cand(id="c2", produces=["y"])], 10, ["k1"])
        self.assertEqual("candidate-ok", res["verdict"])
        self.assertEqual([], res["reasons"])

    def test_empty_candidates(self):
        res = ch.assess([], 10)
        self.assertEqual("candidate-insufficient", res["verdict"])
        self.assertEqual("B0", res["reasons"][0]["code"])

    def test_b1_no_produces(self):
        res = ch.assess([self._cand(produces=[])], 10, ["k1"])
        self.assertIn("B1", [r["code"] for r in res["reasons"]])

    def test_b2_no_anchors(self):
        res = ch.assess([self._cand(anchors=[])], 10, ["k1"])
        self.assertIn("B2", [r["code"] for r in res["reasons"]])

    def test_b3_repair_coverage_zero(self):
        res = ch.assess([self._cand(repairs=["other"])], 10, ["k1"])
        self.assertIn("B3", [r["code"] for r in res["reasons"]])

    def test_b4_diversity_collapse(self):
        same = [self._cand(id="c1"), self._cand(id="c2"), self._cand(id="c3")]
        res = ch.assess(same, 10)
        self.assertIn("B4", [r["code"] for r in res["reasons"]])

    def test_b5_all_over_budget(self):
        res = ch.assess([self._cand(cost=99), self._cand(id="c2", cost=50)], 10)
        self.assertIn("B5", [r["code"] for r in res["reasons"]])

    def test_bad_input_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            ch.assess("not-a-list", 1)
        self.assertIn("修复指引", str(ctx.exception))

    def test_no_ranking_or_score_keys(self):
        res = ch.assess([self._cand()], 10, ["k1"])
        text = json.dumps(res).lower()
        for key in ("score", "rank", "grade"):
            self.assertNotIn('"' + key, text)


if __name__ == "__main__":
    unittest.main()
