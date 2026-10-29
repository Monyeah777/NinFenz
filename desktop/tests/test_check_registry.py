#!/usr/bin/env python3
# ruff: noqa: E402, E501, RUF100, UP031, UP032
"""判据登记册（架构方案 01）单测：R1/R2/R3/#17 + 导出对拍 + 变异夹具。

纪律：只测判据本身（真仓 + 合成根 + 注入变异），不在测试里跑真门禁；
真仓的绿灯由 `verify.sh` 的 check35（判据账本段）与 `scripts/gen_check_registry.py
--check` 守着。每条判据都必须能红（变异夹具），否则「活性」只是空转。
"""

import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import check_registry as cr
from core import quality_baseline as qb


def _doc():
    return cr.load(str(ROOT))


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


class RegistryShapeTest(unittest.TestCase):
    """登记册形状：不手抄、条数=EXPECTED_CHECKS、字段齐、派生稳定。"""

    def test_committed_registry_matches_derive(self):
        self.assertEqual(
            cr.derive(str(ROOT)),
            _doc()["checks"],
            "登记册 != 实时派生（修复指引：python scripts/gen_check_registry.py --write）",
        )

    def test_registry_ids_cover_verify_checks(self):
        self.assertEqual(set(range(1, int(qb.EXPECTED_CHECKS) + 1)), cr.ids_of(_doc()))

    def test_registry_schema_wellformed(self):
        self.assertEqual([], cr.validate(_doc()))
        for row in cr.derive(str(ROOT)):
            self.assertEqual(set(cr.FIELDS), set(row))
            self.assertTrue(row["name"], row)
            self.assertIn(row["kind"], cr.KINDS)
            self.assertIn(row["severity"], cr.SEVERITIES)
            self.assertTrue(
                row["reads"] or row["module"] == "verify.sh" or row["module"].startswith("tests.")
            )

    def test_bash_checks_declare_verify_sh_entry(self):
        """bash 原生判据的入口必须是 verify.sh 的 checkN()（不是自指 verify.sh）。"""
        for row in cr.derive(str(ROOT)):
            if row["module"] == "verify.sh":
                self.assertEqual("check%d" % row["id"], row["entry"], row)


class R1ConsistencyTest(unittest.TestCase):
    """R1：四处 id 集合 == 登记册；差集点名到「哪处多/少」。"""

    def test_four_lists_equal_real_tree(self):
        lists = cr.four_lists(str(ROOT))
        want = set(range(1, int(qb.EXPECTED_CHECKS) + 1))
        for name in cr.SOURCES:
            self.assertEqual(
                want, lists[name], "清单 %s 与 check1-%d 不等" % (name, int(qb.EXPECTED_CHECKS))
            )

    def test_r1_green_on_real_tree(self):
        issues, stats = cr.consistency(str(ROOT))
        self.assertEqual([], issues)
        self.assertEqual(int(qb.EXPECTED_CHECKS), stats["registry"])

    def test_injection_missing_registry_entry_is_fail(self):
        """变异夹具：删登记册一条 → R1 必须红，并点名四处「多 17」。"""
        doc = _doc()
        doc["checks"] = [r for r in doc["checks"] if r["id"] != 17]
        issues, _stats = cr.consistency(str(ROOT), doc=doc)
        self.assertTrue(issues, "删一条登记册条目 R1 必须红")
        self.assertTrue(any("多 17" in i for i in issues), issues)

    def test_injection_ghost_registry_entry_is_fail(self):
        """变异夹具：登记册多一条不在四处 → R1 必须红，并点名「少 99」。"""
        doc = json.loads(json.dumps(_doc()))
        ghost = dict(doc["checks"][0])
        ghost.update({"id": 99, "name": "ghost"})
        doc["checks"] = doc["checks"] + [ghost]
        issues, _stats = cr.consistency(str(ROOT), doc=doc)
        self.assertTrue(issues)
        self.assertTrue(any("少 99" in i for i in issues), issues)

    def test_engine_list_covers_41_42(self):
        """历史缺口回归：引擎清单（REGISTRY ∪ PENDING）必须含 check41/42。"""
        ids = cr.gate_engine_ids(str(ROOT))
        self.assertIn(41, ids)
        self.assertIn(42, ids)


class R2ActivityTest(unittest.TestCase):
    """R2：module.entry 可用 + 字段真被读（灰度 WARN）。"""

    def test_r2_green_on_real_tree(self):
        warns, stats = cr.activity(str(ROOT))
        self.assertEqual([], warns)
        self.assertGreaterEqual(stats["entries"], int(qb.EXPECTED_CHECKS))

    def test_injection_bad_module_is_warn(self):
        """变异夹具：module 不存在 → R2 必须 WARN（灰度不判死）。"""
        doc = json.loads(json.dumps(_doc()))
        doc["checks"][0]["module"] = "core.no_such_module_xyz"
        doc["checks"][0]["entry"] = "scan"
        warns, _stats = cr.activity(str(ROOT), doc=doc)
        self.assertTrue(warns)
        self.assertTrue(any("no_such_module_xyz" in w for w in warns), warns)

    def test_injection_dead_field_is_warn(self):
        """变异夹具：引入一个无人读取的字段 → R2 必须把「死字段」WARN 出来。"""
        with mock.patch.object(cr, "FIELDS", cr.FIELDS + ("ghost_field",)):
            warns, stats = cr.activity(str(ROOT))
        self.assertIn("ghost_field", stats["dead_fields"])
        self.assertTrue(any("ghost_field" in w for w in warns), warns)

    def test_every_declared_field_is_really_read(self):
        counts = cr._field_reads(str(ROOT))
        for field in cr.FIELDS:
            self.assertGreater(counts[field], 0, f"字段 {field!r} 无代码读取（死字段）")


class R3ReadSurfaceTest(unittest.TestCase):
    """R3：观测读面 ⊆ 声明 reads；只在 memo 观测模式开（本组用注入观测面）。"""

    def _doc_with_reads(self, reads):
        doc = json.loads(json.dumps(_doc()))
        doc["checks"] = [r for r in doc["checks"] if r["id"] == 23]
        doc["checks"][0]["reads"] = reads
        return doc

    def test_covered_reads_pass(self):
        doc = self._doc_with_reads(["desktop/**"])
        face = {"files": ["desktop/src/core/x.py"], "dirs": []}
        with mock.patch("core.subcheck_cache.read_face", return_value=face):
            warns, stats = cr.read_surface(str(ROOT), doc=doc)
        self.assertEqual([], warns)
        self.assertEqual(1, stats["observed"])

    def test_injection_out_of_declared_reads_is_warn(self):
        """变异夹具：读到声明外文件 → R3 必须 WARN 并列出越界件。"""
        doc = self._doc_with_reads(["desktop/**"])
        face = {"files": ["desktop/src/core/x.py", "protocol/outside.json"], "dirs": []}
        with mock.patch("core.subcheck_cache.read_face", return_value=face):
            warns, _stats = cr.read_surface(str(ROOT), doc=doc)
        self.assertTrue(warns)
        self.assertTrue(any("protocol/outside.json" in w for w in warns), warns)

    def test_no_observation_is_reported_not_faked(self):
        doc = self._doc_with_reads(["desktop/**"])
        with mock.patch("core.subcheck_cache.read_face", return_value=None):
            warns, stats = cr.read_surface(str(ROOT), doc=doc)
        self.assertEqual([], warns, "无观测不得假装违规，也不得假装合规")
        self.assertEqual(0, stats["observed"])
        self.assertEqual(1, stats["skipped"])


class ExperimentGuardTest(unittest.TestCase):
    """#17：改 *_baseline.json 必须有同日四行实验单（FAIL）。"""

    def test_no_baseline_change_is_silent(self):
        issues, stats = cr.experiment_guard(str(ROOT), changed=[])
        self.assertEqual([], issues)
        self.assertEqual(0, stats["changed"])

    def test_injection_baseline_change_without_sheet_is_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues, _stats = cr.experiment_guard(tmp, changed=["protocol/x_baseline.json"])
        self.assertTrue(issues)
        self.assertTrue(any("无同日实验单" in i for i in issues), issues)

    def test_injection_sheet_missing_line_is_fail(self):
        today = datetime.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                f"changes/unreleased/{today}-partial.md",
                "# 实验单\n\n- 假设：x\n- 指标：y\n- 阈值：z\n",
            )
            _write(
                tmp,
                "protocol/check_registry.json",
                json.dumps(
                    {
                        "schema": cr.SCHEMA,
                        "checks": [
                            {
                                "id": 1,
                                "name": "x",
                                "module": "verify.sh",
                                "entry": "check1",
                                "kind": "prescriptive",
                                "reads": [],
                                "writes": [],
                                "severity": "fail",
                                "since": "v2.30",
                                "experiment": "exp-1",
                            }
                        ],
                    }
                ),
            )
            issues, _stats = cr.experiment_guard(tmp, changed=["protocol/x_baseline.json"])
        self.assertTrue(issues)
        self.assertTrue(any("缺行" in i and "回滚点" in i for i in issues), issues)

    def test_same_day_full_sheet_passes(self):
        today = datetime.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            _write(
                tmp,
                f"changes/unreleased/{today}-full.md",
                "# 实验单\n\n- 假设：x\n- 指标：y\n- 阈值：z\n- 回滚点：git revert\n",
            )
            _write(
                tmp,
                "protocol/check_registry.json",
                json.dumps(
                    {
                        "schema": cr.SCHEMA,
                        "checks": [
                            {
                                "id": 1,
                                "name": "x",
                                "module": "verify.sh",
                                "entry": "check1",
                                "kind": "prescriptive",
                                "reads": [],
                                "writes": [],
                                "severity": "fail",
                                "since": "v2.30",
                                "experiment": "exp-1",
                            }
                        ],
                    }
                ),
            )
            issues, stats = cr.experiment_guard(tmp, changed=["protocol/x_baseline.json"])
        self.assertEqual([], issues)
        self.assertEqual(1, stats["changed"])


if __name__ == "__main__":
    unittest.main()
