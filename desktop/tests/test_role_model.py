# -*- coding: utf-8 -*-
"""职能坐标（`core/role_model` · ADR-0006）回归 —— 三条可判定性 + 变异自证。

判据落点：`layer_model.scan` 折入本模块 issues（L11）→ check27 纯度面 → 机器可读报告，
**不新增 check 序号**（ADR-0002）。本件同时给 ①②③ 各配**变异自证**（写坏必红、写对必绿）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import role_model as rm  # noqa: E402

WITH_SELF = '''"""一件判据（测试用）：判据面，只读。"""
x = 1
'''
NO_SELF = "x = 1" + chr(10)
WRITER = '''"""一件判据（测试用）：判据面，只读。"""
from core import atomic_write


def scan(root="."):
    return [], {}


def write(root="."):
    atomic_write.write_text(root + "/x", "x")
'''


def _mk(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _roles(**kw):
    d = {"vocabulary": list(rm.ROLES), "kernel_roles": list(rm.KERNEL_ROLES),
         "rules": [{"id": "R-core", "role": "auto", "globs": ["desktop/src/core/*.py"]},
                   {"id": "R-catch", "role": "support", "globs": ["**"]}],
         "overrides": {}, "write_exceptions": {}}
    d.update(kw)
    return d


def _scene(tmp, files=None, roles=None, write_projection=True):
    _mk(tmp, "protocol/LAYERS.json",
        json.dumps({"schema": "nf-layers/1", "roles": roles if roles is not None else _roles()},
                   ensure_ascii=False))
    _mk(tmp, "docs/layers.md", "# layers")
    for rel, text in (files or {"desktop/src/core/a.py": WITH_SELF}).items():
        _mk(tmp, rel, text)
    if write_projection:
        rm.write(tmp)
    return tmp


class RealRepoTest(unittest.TestCase):
    def test_scan_clean(self):
        issues, stats = rm.scan(str(ROOT))
        self.assertEqual(issues, [], issues)
        self.assertGreater(stats["kernel"], 100)
        self.assertEqual(0, stats["uncovered"])

    def test_projection_is_current(self):
        self.assertEqual([], rm._projection_drift(str(ROOT)))

    def test_verify_writers_all_registered(self):
        roles = rm.load(str(ROOT))
        exc = roles.get("write_exceptions") or {}
        self.assertGreaterEqual(len(exc), 1)


class CoverageTest(unittest.TestCase):
    def test_all_files_get_a_coordinate(self):
        with tempfile.TemporaryDirectory() as d:
            _scene(d, files={"desktop/src/core/a.py": WITH_SELF, "README.md": "# r"})
            issues, stats = rm.scan(d)
            self.assertEqual([], [i for i in issues if "覆盖缺口" in i], issues)
            self.assertEqual(0, stats["uncovered"])

    def test_coverage_gap_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            roles = _roles(rules=[{"id": "R-core", "role": "auto",
                                   "globs": ["desktop/src/core/*.py"]}])
            _scene(d, files={"README.md": "# r", "desktop/src/core/a.py": WITH_SELF},
                   roles=roles)
            issues, _ = rm.scan(d)
            self.assertTrue(any("覆盖缺口" in i for i in issues), issues)

    def test_core_py_without_self_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            _scene(d, files={"desktop/src/core/a.py": NO_SELF})
            issues, _ = rm.scan(d)
            self.assertTrue(any("无自述" in i for i in issues), issues)

    def test_kernel_in_catch_all_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            roles = _roles(rules=[{"id": "R-catch", "role": "verify", "globs": ["**"]}])
            _scene(d, files={"README.md": "# r"}, roles=roles)
            issues, _ = rm.scan(d)
            self.assertTrue(any("落兜底规则" in i for i in issues), issues)


class RuleDriftTest(unittest.TestCase):
    def test_empty_rule_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            roles = _roles(rules=[{"id": "R-dead", "role": "app", "globs": ["nowhere/**"]},
                                  {"id": "R-catch", "role": "support", "globs": ["**"]}])
            _scene(d, roles=roles, files={"README.md": "# r"})
            issues, _ = rm.scan(d)
            self.assertTrue(any("规则空转" in i for i in issues), issues)

    def test_projection_drift_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            _scene(d)
            _mk(d, "desktop/src/core/b.py", WITH_SELF)
            issues, _ = rm.scan(d)
            self.assertTrue(any("与实时重算不一致" in i for i in issues), issues)


class KernelConsistencyTest(unittest.TestCase):
    def test_unregistered_writer_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            _scene(d, files={"desktop/src/core/w.py": WRITER})
            issues, _ = rm.scan(d)
            self.assertTrue(any("写盘入口未登记" in i for i in issues), issues)

    def test_registered_writer_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            issues, _ = _chan(d, "core/w.py（测试：冻结基线）")
            self.assertEqual([], [i for i in issues if "写入口" in i], issues)

    def test_stale_write_exception_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            roles = _roles(write_exceptions={"desktop/src/core/a.py": "已不存在的写入口"})
            _scene(d, roles=roles)
            issues, _ = rm.scan(d)
            self.assertTrue(any("写例外已失效" in i for i in issues), issues)


class OverrideTest(unittest.TestCase):
    def test_override_wins_over_rule(self):
        with tempfile.TemporaryDirectory() as d:
            roles = _roles(overrides={"desktop/src/core/a.py": {"role": "prod",
                                                                "why": "测试覆盖"}})
            _scene(d, roles=roles)
            files = rm.files_of(d)
            co = rm.coordinate(d, "desktop/src/core/a.py", rm._rule_hits(roles, files),
                               roles["overrides"])
            self.assertEqual("prod", co["role"])
            self.assertEqual("override", co["rule"])



def _chan(tmp, owner, exc=None, mk_artifact=True):
    """写通道场景：roles.write_exceptions + 写入口模块 + 落点件 + data_contracts 登记。"""
    roles = _roles(write_exceptions=exc or {
        "desktop/src/core/w.py": {"why": "测试：冻结基线", "artifact": "protocol/x.json"}})
    _mk(tmp, "protocol/LAYERS.json",
        json.dumps({"schema": "nf-layers/1", "roles": roles}, ensure_ascii=False))
    _mk(tmp, "docs/layers.md", "# layers")
    _mk(tmp, "desktop/src/core/w.py", WRITER)
    if mk_artifact:
        _mk(tmp, "protocol/x.json", "{}")
    _mk(tmp, "protocol/data_contracts.json",
        json.dumps({"contracts": ([{"artifact": "protocol/x.json", "owner": owner}]
                                    if owner else [])}, ensure_ascii=False))
    rm.write(tmp)
    return rm.scan(tmp)


class WriteChannelTest(unittest.TestCase):
    """D3：写通道必须声明落点件，且该件已在 data_contracts 登记、owner 点名模块。"""

    def test_channel_without_artifact_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            issues, _ = _chan(d, "core/w.py", exc={"desktop/src/core/w.py": {"why": "只写了理由"}})
            self.assertTrue(any("未声明落点件" in i for i in issues), issues)

    def test_channel_without_registration_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            issues, _ = _chan(d, "")
            self.assertTrue(any("未在 protocol/data_contracts.json 登记" in i for i in issues), issues)

    def test_channel_owner_must_name_module(self):
        with tempfile.TemporaryDirectory() as d:
            issues, _ = _chan(d, "机制维护（check 即 owner）")
            self.assertTrue(any("owner 未点名" in i for i in issues), issues)

    def test_channel_missing_artifact_file_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            issues, _ = _chan(d, "core/w.py", mk_artifact=False)
            self.assertTrue(any("落点件不在场" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
