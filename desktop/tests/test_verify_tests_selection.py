"""受影响测试选片（verify_tests.select_affected）判据：**纯函数**，不打桩也不跑全量。

为什么要有它：选片逻辑此前没有判据——它是「本地修复回路」的地基（29 分钟 → 一两分钟），
但它一旦漏选，红会**无声消失**。判据钉四件事：四类规则各自生效、硬兜底面绝不漏、
常驻集永远在、空变更只跑常驻集。
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_tests.py"


def _vt():
    spec = importlib.util.spec_from_file_location("nf_verify_tests", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


IDS = [
    "tests.test_alpha.Alpha.test_a",
    "tests.test_beta.Beta.test_b",
    "tests.test_purity_scan.Purity.test_p",
]
SOURCES = {
    "test_alpha": "from core import evidence\n",
    "test_beta": 'DOC = "docs/ccos/abi-v0.md"\n',
    "test_purity_scan": "import purity_scan\n",
}


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.vt = _vt()

    def _mods(self, keep):
        return {self.vt.module_of(t) for t in keep}

    def test_clean_tree_runs_only_always_modules(self):
        keep, why = self.vt.select_affected(IDS, [], SOURCES)
        self.assertEqual({"test_purity_scan"}, self._mods(keep))
        self.assertIn("干净树", why)

    def test_changed_test_file_selects_that_module(self):
        keep, why = self.vt.select_affected(IDS, ["desktop/tests/test_alpha.py"], SOURCES)
        self.assertIn("test_alpha", self._mods(keep))
        self.assertNotIn("test_beta", self._mods(keep))
        self.assertIn("测试件", why)

    def test_docs_change_selects_doc_referencing_tests(self):
        keep, why = self.vt.select_affected(IDS, ["docs/ccos/abi-v0.md"], SOURCES)
        self.assertIn("test_beta", self._mods(keep), "引用 docs/ 的测试必须被选中")
        self.assertIn("文本引用", why)

    def test_cli_change_selects_referencing_tests(self):
        sources = dict(SOURCES)
        sources["test_alpha"] = 'NF = "scripts/nf.py"\n'
        keep, _why = self.vt.select_affected(IDS, ["scripts/nf.py"], sources)
        self.assertIn("test_alpha", self._mods(keep))

    def test_core_change_uses_reverse_closure(self):
        keep, why = self.vt.select_affected(IDS, ["desktop/src/core/evidence.py"], SOURCES)
        self.assertIn("test_alpha", self._mods(keep), "import 该 core 模块的测试必须被选中")
        self.assertIn("core", why)

    def test_hard_fallback_protocol_goes_full(self):
        keep, why = self.vt.select_affected(IDS, ["protocol/RECEIPTS.json"], SOURCES)
        self.assertEqual(set(IDS), set(keep))
        self.assertIn("硬兜底面", why)

    def test_hard_fallback_verify_sh_goes_full(self):
        keep, _why = self.vt.select_affected(IDS, ["verify.sh"], SOURCES)
        self.assertEqual(set(IDS), set(keep))

    def test_hard_fallback_self_edit_goes_full(self):
        keep, _why = self.vt.select_affected(IDS, ["scripts/verify_tests.py"], SOURCES)
        self.assertEqual(set(IDS), set(keep))

    def test_always_modules_survive_any_rule(self):
        for changed in (["desktop/tests/test_alpha.py"], ["scripts/nf.py"],
                        ["desktop/src/core/evidence.py"]):
            keep, _why = self.vt.select_affected(IDS, changed, SOURCES)
            self.assertIn("test_purity_scan", self._mods(keep), changed)

    def test_windows_separators_are_normalized(self):
        keep, _why = self.vt.select_affected(IDS, ["desktop\\tests\\test_alpha.py"], SOURCES)
        self.assertIn("test_alpha", self._mods(keep))

    def test_selection_is_deterministic(self):
        a = self.vt.select_affected(IDS, ["scripts/nf.py"], SOURCES)
        b = self.vt.select_affected(IDS, ["scripts/nf.py"], SOURCES)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
