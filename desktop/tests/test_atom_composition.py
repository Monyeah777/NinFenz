"""原子组合覆盖层判据（闭包 D-02）：v1 不许改，组合关系走覆盖层，且 A1 必须有内容。

为什么（2026-11-08）：v1 的 composed_of 全空，导致 A1（引用闭合）平凡通过——等于没查。
本覆盖层让 13 个复合原子有真实组合关系，A1 才第一次真的在检查东西。

判据：
① 覆盖层合法：id 唯一、composed_of 非空、必须写 why；
② 引用闭合：引用的原子必须存在、无自引用、无环（A1 真检查）；
③ 不变量：composed_of 非空数 ≥ 8、死码显著下降（≤2）；
④ v1 仍未被修改（digest 不变）。
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import atom_catalog as ac  # noqa: E402

ATOMS = ROOT / "desktop/src/core/meta_cockpit/meta_atoms.json"
OVERLAY = ROOT / "protocol/atom_composition.json"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OverlayTest(unittest.TestCase):
    def test_overlay_is_valid(self):
        doc = json.loads(OVERLAY.read_text(encoding="utf-8"))
        self.assertEqual("nf-atom-composition/1", doc["schema"])
        self.assertGreaterEqual(len(doc["compositions"]), 8)

    def test_overlay_entries_have_why(self):
        doc = json.loads(OVERLAY.read_text(encoding="utf-8"))
        for item in doc["compositions"]:
            self.assertTrue(item.get("why"), item["id"])
            self.assertTrue(item.get("composed_of"), item["id"])

    def test_catalog_merges_overlay(self):
        cat = ac.build(str(ROOT))
        nonempty = [a for a in cat["atoms"] if a["composed_of"]]
        self.assertGreaterEqual(len(nonempty), 8)

    def test_v1_not_mutated(self):
        before = _digest(ATOMS)
        ac.build(str(ROOT))
        self.assertEqual(before, _digest(ATOMS))

    def test_composition_source_recorded(self):
        cat = ac.build(str(ROOT))
        self.assertEqual("protocol/atom_composition.json", cat["composition_source"])


class A1RealCheckTest(unittest.TestCase):
    def _cat(self) -> dict:
        cat = json.loads(json.dumps(ac.build(str(ROOT))))
        cat["atom_debt"] = [a["id"] for a in cat["atoms"]]
        return cat

    def test_unknown_reference_is_caught(self):
        cat = self._cat()
        for atom in cat["atoms"]:
            if atom["composed_of"]:
                atom["composed_of"].append("no.such.atom")
                break
        inv = ac.invariants(cat)
        self.assertTrue(any(v["code"] == "A1" for v in inv["violations"]), inv["violations"][:2])

    def test_self_reference_is_caught(self):
        cat = self._cat()
        target = next(a for a in cat["atoms"] if a["composed_of"])
        target["composed_of"] = [target["id"]]
        self.assertTrue(any("自引用" in v["detail"] for v in ac.invariants(cat)["violations"]))

    def test_cycle_is_caught(self):
        cat = self._cat()
        target = next(a for a in cat["atoms"] if a["composed_of"])
        child = target["composed_of"][0]
        for atom in cat["atoms"]:
            if atom["id"] == child:
                atom["composed_of"] = [target["id"]]
        self.assertTrue(any("成环" in v["detail"] for v in ac.invariants(cat)["violations"]))


class DeadCodeShrinkTest(unittest.TestCase):
    def test_dead_code_shrank(self):
        inv = ac.invariants(ac.build(str(ROOT)))
        self.assertLessEqual(inv["counts"]["dead"], 2, inv["counts"])
        self.assertGreaterEqual(inv["counts"]["composed_of_nonempty"], 8)

    def test_remaining_debt_is_recorded(self):
        doc = json.loads((ROOT / "protocol/criteria/atom_debt.json").read_text(encoding="utf-8"))
        self.assertLessEqual(len(doc["atoms"]), 2)
        for item in doc["atoms"]:
            self.assertTrue(item.get("reason"), item["id"])


if __name__ == "__main__":
    unittest.main()
