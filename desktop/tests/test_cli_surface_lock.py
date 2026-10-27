"""CLI 命令面 golden 锁（`desktop/tests/fixtures/cli_surface.json`）。

判据：实时 `_build_parser()` 的「根旗标 + 79 命令（顺序/别名/help/旗标/嵌套）」与夹具逐项相等。
**改面必须显式重生成**（`python scripts/make_cli_surface.py`）并在评审里说明——拆包/重构不得改命令面。
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = HERE / "fixtures" / "cli_surface.json"
sys.path.insert(0, str(ROOT / "scripts"))
from cli_surface_lib import SCHEMA, serialize  # noqa: E402


def _load_nf():
    spec = importlib.util.spec_from_file_location("nf_surface_probe",
                                                  ROOT / "scripts" / "nf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _diff(fixture, live):
    """→ 可读差异列表（命令面级，不 dump 全量 JSON）。"""
    out = []
    f = {c["name"]: c for c in fixture["commands"]}
    l = {c["name"]: c for c in live["commands"]}
    if [c["name"] for c in fixture["commands"]] != [c["name"] for c in live["commands"]]:
        out.append("命令顺序/集合变化：夹具 %d 条，实测 %d 条；仅夹具 %s；仅实测 %s"
                   % (len(f), len(l), sorted(set(f) - set(l)), sorted(set(l) - set(f))))
    if fixture["root_flags"] != live["root_flags"]:
        out.append("根旗标变化：夹具 %s / 实测 %s"
                   % ([x["option"] for x in fixture["root_flags"]],
                      [x["option"] for x in live["root_flags"]]))
    for name in sorted(set(f) & set(l)):
        a, b = f[name], l[name]
        for key in ("aliases", "help", "flags", "nested"):
            if a.get(key) != b.get(key):
                out.append("命令 %s 的 %s 变化" % (name, key))
    return out


class CliSurfaceLockTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.live = serialize(_load_nf()._build_parser())

    def test_fixture_schema_and_coverage(self):
        self.assertEqual(SCHEMA, self.fixture.get("schema"))
        self.assertGreaterEqual(len(self.fixture["commands"]), 79,
                                "夹具命令面塌缩（判据可能失效）")
        self.assertGreaterEqual(len(self.fixture["root_flags"]), 3)

    def test_fixture_matches_live_surface(self):
        diffs = _diff(self.fixture, self.live)
        self.assertEqual([], diffs,
                         "CLI 命令面与 golden 夹具不一致（拆包/重构不得改面；确属有意改面请重跑 "
                         "scripts/make_cli_surface.py 并在评审说明）：\n" + "\n".join(diffs))
