# -*- coding: utf-8 -*-
"""门禁清单（`protocol/gates.json`）回归 —— T2.3 第一步：**登记面可判定**。

判据分三层（对应 task 的三条验收）
--------------------------------
1. **合法性**：schema `nf-gates/1`、12 字段不多不少、id kebab、kind/assert 机制同源；
2. **全覆盖**：manifest 的 legacy_check 恰好 1-45，且 `core.gate_engine` 的
   REGISTRY ∪ PENDING **也**恰好覆盖 1-45（check41/42 曾两边都不在、43-45 为 W9 新接入）；
3. **只增不减棘轮**：`BASELINE` 冻结点对 (legacy_check, id)；不得删除、不得改绑。
   新增 gate 只能在末尾追加（同时更新 `scripts/gate_manifest.py` 的 IDS 与本表）。

为什么棘轮要冻在测试里（而不是只靠 `--check`）
--------------------------------------------
`--check` 是"manifest 与 verify.sh 当前一致"；棘轮是"**历史 id 不许消失**"。两者缺一：
只有 --check 时，删掉一条 check + 重抽 manifest 可以自洽；只有棘轮时，改标题/段位
不会被发现。故两道都要。

跑法
----
    python -m unittest tests.test_gate_manifest -v      # 在 desktop/ 下（门禁口径）
    python -m pytest desktop/tests/test_gate_manifest.py -q   # 仓根（本任务口径）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))

import gate_manifest as gm  # noqa: E402

#: 冻结基线：(legacy_check, id)。新增 gate 追加；已有序号不得改绑/删除。
BASELINE = (
    (1, "core-dirs"),
    (2, "dup-ids-official"),
    (3, "invariant-anchors"),
    (4, "visibility-boundary"),
    (5, "quality-gate-action"),
    (6, "entry-navigation"),
    (7, "community-pack-structure"),
    (8, "community-asset-baseline"),
    (9, "module-asset-addressable"),
    (10, "ext-closure-redlines"),
    (11, "asset-three-way-reconcile"),
    (12, "desktop-unittest-compileall"),
    (13, "protocol-version-migration"),
    (14, "community-protocol-registration"),
    (15, "composition-references"),
    (16, "contract-arbitration"),
    (17, "quality-governance"),
    (18, "export-contract"),
    (19, "export-schema-shape"),
    (20, "doc-completeness"),
    (21, "registry-reference-graph"),
    (22, "export-spec-hygiene"),
    (23, "asset-supply-chain"),
    (24, "module-lifecycle"),
    (25, "knowledge-signature"),
    (26, "semantic-conflict"),
    (27, "architecture-purity"),
    (28, "idl-schema"),
    (29, "conformance-grading"),
    (30, "extension-bump-migration"),
    (31, "golden-generation"),
    (32, "quality-depth"),
    (33, "new-faces-summary"),
    (34, "library-face"),
    (35, "deepening-face"),
    (36, "governance-face"),
    (37, "knowledge-layer"),
    (38, "output-automation"),
    (39, "terminal-surface"),
    (40, "asset-contracts"),
    (41, "build-isolation"),
    (42, "provenance-nonfalsifiable"),
    (43, "contract-semantics"),
    (44, "registry-cid"),
    (45, "content-security"),
    (46, "privacy-airgap"),
    (47, "cli-map"),
)

_ALL_CHECKS = set(range(1, 48))
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _manifest() -> dict:
    return gm._manifest(ROOT)


class SchemaTest(unittest.TestCase):
    """第 1 层：形状合法（不多不少 12 字段 / id 合规 / 断言机制与 kind 同源）。"""

    def test_schema_and_top_level_documented(self) -> None:
        doc = _manifest()
        self.assertEqual(gm.SCHEMA, doc.get("schema"))
        self.assertEqual(47, doc["source"]["check_count"])
        self.assertEqual(list(gm.NULL_FIELDS), doc.get("null_fields"))
        self.assertTrue(doc.get("notes"), "null 字段必须有说明（不写假声明）")

    def test_every_gate_has_exactly_the_twelve_fields(self) -> None:
        bad = []
        for gate in _manifest()["gates"]:
            if set(gate) != set(gm.FIELDS):
                bad.append((gate.get("legacy_check"),
                            sorted(set(gm.FIELDS) - set(gate)),
                            sorted(set(gate) - set(gm.FIELDS))))
        self.assertEqual([], bad, "字段集漂移：%s" % bad)

    def test_ids_are_kebab_and_unique(self) -> None:
        gates = _manifest()["gates"]
        ids = [g["id"] for g in gates]
        self.assertEqual(len(ids), len(set(ids)), "id 重复：%s" % ids)
        bad = [i for i in ids if not isinstance(i, str) or not _ID_RE.match(i)]
        self.assertEqual([], bad, "id 不是 kebab-case：%s" % bad)

    def test_kind_and_assert_mechanism_are_sourced(self) -> None:
        bad = []
        for gate in _manifest()["gates"]:
            kind = gate["kind"]
            if kind not in gm.KINDS:
                bad.append("%s: 未知 kind %r" % (gate["id"], kind))
                continue
            mech = (gate.get("assert") or [{}])[0].get("type")
            if mech != gm.KINDS[kind]:
                bad.append("%s: assert=%r ≠ KINDS[%s]=%r"
                           % (gate["id"], mech, kind, gm.KINDS[kind]))
            out = gate.get("output") or {}
            if not out.get("verdict_lines"):
                bad.append("%s: output.verdict_lines 为空" % gate["id"])
            if gate.get("segment") not in ("A", "B", "C", "D"):
                bad.append("%s: segment=%r" % (gate["id"], gate.get("segment")))
            if gate.get("tier") not in ("static", "tests"):
                bad.append("%s: tier=%r" % (gate["id"], gate.get("tier")))
        self.assertEqual([], bad, "\n".join(bad))

    def test_null_fields_are_actually_null(self) -> None:
        """第一步刻意不声明三字段；若有人填了值，须同时把它从 null_fields 移除。"""
        doc = _manifest()
        declared = set(doc.get("null_fields") or [])
        self.assertEqual(set(gm.NULL_FIELDS), declared)
        still_null = set()
        filled = []
        for gate in doc["gates"]:
            for field in declared:
                if gate.get(field) is None:
                    still_null.add(field)
                else:
                    filled.append((gate["id"], field))
        self.assertEqual([], filled, "字段已填但仍列在 null_fields：%s" % filled)
        self.assertEqual(declared, still_null)


class CoverageTest(unittest.TestCase):
    """第 2 层：47/47 全覆盖（manifest 与引擎登记面各自成立）。"""

    def test_manifest_covers_all_47_checks(self) -> None:
        checks = sorted(g["legacy_check"] for g in _manifest()["gates"])
        self.assertEqual(sorted(_ALL_CHECKS), checks,
                         "manifest 缺 check：%s" % sorted(_ALL_CHECKS - set(checks)))

    def test_engine_registry_plus_pending_covers_all_47(self) -> None:
        from core import gate_engine

        gate_engine.build_registry()
        covered = set(gate_engine.REGISTRY) | set(gate_engine.PENDING)
        self.assertEqual(_ALL_CHECKS, covered,
                         "引擎覆盖缺口（REGISTRY∪PENDING）：%s"
                         % sorted(_ALL_CHECKS - covered))
        overlap = set(gate_engine.REGISTRY) & set(gate_engine.PENDING)
        self.assertEqual(set(), overlap, "既迁入又 pending：%s" % sorted(overlap))

    def test_coverage_block_is_derived_and_gap_free(self) -> None:
        cov = gm.build(ROOT)["coverage"]
        self.assertEqual([], cov["gaps"], "manifest 覆盖缺口：%s" % cov["gaps"])
        self.assertEqual([], cov["orphans"], "引擎登记了不存在的 check：%s" % cov["orphans"])
        self.assertEqual(47, cov["gates"])
        self.assertEqual(_ALL_CHECKS, set(cov["migrated"]) | set(cov["pending"]))

    def test_projection_matches_verify_sh(self) -> None:
        """`--check` 的同一判据在进程内跑：id/legacy/title/segment/kind 与真源一致。"""
        self.assertEqual([], gm.check(ROOT))


class RatchetTest(unittest.TestCase):
    """第 3 层：只增不减——历史 (编号, id) 不得删除、不得改绑。"""

    def test_baseline_pairs_never_disappear_or_rebind(self) -> None:
        current = {g["legacy_check"]: g["id"] for g in _manifest()["gates"]}
        broken = [(n, i, current.get(n)) for n, i in BASELINE if current.get(n) != i]
        self.assertEqual([], broken, "历史 gate 被删除或改绑：%s" % broken)
        self.assertGreaterEqual(len(current), len(BASELINE),
                                "gate 总数不得减少（当前 %d < 基线 %d）"
                                % (len(current), len(BASELINE)))

    def test_id_registry_is_append_only(self) -> None:
        """`scripts/gate_manifest.py` 的 IDS 与冻结基线同源（新增只能追加）。"""
        frozen = dict(BASELINE)
        re_bound = [(n, frozen[n], gm.IDS.get(n)) for n in frozen
                    if gm.IDS.get(n) != frozen[n]]
        self.assertEqual([], re_bound, "IDS 改绑历史 id：%s" % re_bound)
        self.assertGreaterEqual(len(gm.IDS), len(BASELINE))

    def test_extract_is_deterministic(self) -> None:
        """同输入同字节：抽取面不含时间戳/随机序（否则每跑都脏 diff）。"""
        a = json.dumps(gm.build(ROOT), ensure_ascii=False, sort_keys=True)
        b = json.dumps(gm.build(ROOT), ensure_ascii=False, sort_keys=True)
        self.assertEqual(a, b, "抽取结果不确定（含时间/随机面）")


class CliTest(unittest.TestCase):
    """验收口径：`python scripts/gate_manifest.py --check` 退出 0。"""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "gate_manifest.py"), *args],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=180)

    def test_check_exits_zero(self) -> None:
        proc = self._run("--check")
        self.assertEqual(0, proc.returncode, "stderr=%s" % proc.stderr[-800:])
        self.assertIn("差分通过", proc.stdout)

    def test_check_json_is_machine_readable(self) -> None:
        proc = self._run("--check", "--json")
        self.assertEqual(0, proc.returncode, "stderr=%s" % proc.stderr[-800:])
        doc = json.loads(proc.stdout)
        self.assertEqual("nf-gate-manifest-check/1", doc["schema"])
        self.assertTrue(doc["ok"])
        self.assertEqual([], doc["diffs"])


if __name__ == "__main__":
    unittest.main()
