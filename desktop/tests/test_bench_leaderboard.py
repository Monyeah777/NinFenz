# -*- coding: utf-8 -*-
"""公开 benchmark 榜回归（T6.3）——「可提交、可复算、可排序、空榜诚实」四件套。

判据分五层
----------
1. **schema 落地**：`protocol/schema/bench_result.schema.json` 在仓内 schema 子集内、是合法
   draft 2020-12、必填字段覆盖任务清单；
2. **结果行校验**：合法行收、非法行拒（缺字段 / 证据缺席 / 摘要不符 / 数字不自洽 / verdict
   自相矛盾 / profile 不在册 / 同提交重复 / 元数据不一致），且**非法输入不写半份榜**；
3. **排序**：按 profile 分组，pass 优先 → 检出率降序 → 误报率升序 → 提交 id 升序（全确定）；
4. **空榜诚实**：无模型结果时榜面显式「尚无真实模型结果」，且不把 baseline 当模型成绩混排；
5. **防漂移**：`--check` 对「结果文件 / 基线报告 / 榜单」三方对账；结果改了不重生成即红。

跑法：python -m pytest desktop/tests/test_bench_leaderboard.py -q
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))

import bench_leaderboard as bl  # noqa: E402

try:  # 可选对照依赖（仓库标准校验器为零第三方）
    import jsonschema
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover
    jsonschema = None
    Draft202012Validator = None


# ---------------------------------------------------------------- 临时仓夹具
def _evidence(root: Path, slug: str, profile: str) -> Path:
    path = root / bl.EVIDENCE_REL / ("%s__%s.json" % (slug, profile))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"evidence": "reproducible"}\n', encoding="utf-8")
    return path


def _write_result(root: Path, submission_id: str = "acme/bench@2026-10",
                  profile: str = "techdoc-strict", cases: int = 80,
                  clean: int = 20, detected: int = 74, fp: int = 1,
                  filename: str = "", drops: tuple = (), **over) -> tuple:
    slug = bl._slug(submission_id)
    ev = _evidence(root, slug, profile)
    det = round(detected / cases, 4)
    fpr = round(fp / clean, 4)
    row = {
        "schema": bl.RESULT_KIND, "submission_id": submission_id,
        "model": "bench-model", "provider": "Acme", "version": "2026-10-26",
        "date": "2026-10-26", "profile": profile,
        "cases": cases, "clean_cases": clean, "detected": detected,
        "false_positives": fp, "detection_rate": det, "fp_rate": fpr,
        "verdict": "pass" if det >= 0.9 and fpr <= 0.1 else "fail",
        "evidence_path": str(ev.relative_to(root)).replace("\\", "/"),
        "contract_digest": bl._sha_file(ev),
    }
    row.update(over)
    for key in drops:
        row.pop(key, None)
    name = filename or ("%s__%s.json" % (slug, profile))
    path = root / bl.RESULTS_REL / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path, row


def _baseline_report(root: Path, tech: tuple = (80, 80, 20, 0),
                     reg: tuple = (72, 72, 20, 0), schema: str = "") -> Path:
    def totals(cases: int, detected: int, clean: int, fp: int) -> dict:
        return {"negatives": cases, "detected": detected, "clean_cases": clean,
                "fail_flagged_clean": fp,
                "detection_rate": round(detected / cases, 4),
                "fp_rate": round(fp / clean, 4)}

    doc = {"schema": schema or bl.BASELINE_KIND,
           "profiles": {"techdoc-strict": {"totals": totals(*tech)},
                        "regulatory-strict": {"totals": totals(*reg)}}}
    path = root / bl.BASELINE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


class SchemaLandingTest(unittest.TestCase):
    def test_schema_is_valid_and_in_repo_subset(self):
        from core import schema_lint as sl

        issues, _schemas = sl.check_schema_files(str(ROOT))
        self.assertEqual([], issues)
        schema = sl.load_schema(str(ROOT), bl.SCHEMA_NAME)
        self.assertIsNotNone(schema, "schema 未登记：%s" % bl.SCHEMA_NAME)
        self.assertEqual([], sl.subset_key_violations(schema))
        if Draft202012Validator is not None:
            Draft202012Validator.check_schema(schema)

    def test_schema_required_fields_cover_task_list(self):
        from core import schema_lint as sl

        schema = sl.load_schema(str(ROOT), bl.SCHEMA_NAME)
        required = set(schema.get("required") or [])
        for field in ("model", "provider", "version", "date", "profile", "cases",
                      "detected", "false_positives", "detection_rate", "fp_rate",
                      "verdict", "evidence_path", "contract_digest"):
            self.assertIn(field, required, "schema 缺任务清单字段：%s" % field)
        self.assertEqual(bl.RESULT_KIND, schema["properties"]["schema"]["enum"][0])


class CollectTest(unittest.TestCase):
    """2 结果行校验：合法收、非法拒。"""

    def test_valid_rows_are_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            _write_result(root)
            _write_result(root, submission_id="acme/bench@2026-10",
                          profile="regulatory-strict", cases=72, detected=68)
            rows, errors = bl.collect_rows(root, bl._schema(), bl._registry())
            self.assertEqual([], errors, errors)
            self.assertEqual(2, len(rows))

    def test_invalid_rows_are_rejected(self):
        cases = [
            ("missing_provider", {"drops": ("provider",)}),
            ("bad_schema_kind", {"schema": "nf-bench-result/999"}),
            ("evidence_missing", {"evidence_path": "results/bench/evidence/nope.json"}),
            ("digest_mismatch", {"contract_digest": "sha256:" + "0" * 64}),
            ("rate_inconsistent", {"detection_rate": 0.5}),
            ("verdict_inconsistent", {"verdict": "fail"}),
            ("profile_unknown", {"profile": "nope-strict"}),
            ("filename_mismatch", {"filename": "not-a-profile-row.json"}),
            ("empty_model", {"model": ""}),
        ]
        for name, over in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    kw = dict(over)
                    _write_result(root, **kw)
                    _rows, errors = bl.collect_rows(root, bl._schema(), bl._registry())
                    self.assertTrue(errors, "%s 应被拒收（错误为空）" % name)

    def test_duplicate_submission_profile_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_result(root)
            _write_result(root, filename="dupe__techdoc-strict.json")
            _rows, errors = bl.collect_rows(root, bl._schema(), bl._registry())
            self.assertTrue(any("重复" in e for e in errors), errors)

    def test_same_submission_metadata_must_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_result(root, model="model-a")
            _write_result(root, profile="regulatory-strict", cases=72,
                          detected=68, model="model-b")
            _rows, errors = bl.collect_rows(root, bl._schema(), bl._registry())
            self.assertTrue(any("元数据不一致" in e for e in errors), errors)

    def test_readme_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / bl.RESULTS_REL).mkdir(parents=True)
            (root / bl.RESULTS_REL / "README.md").write_text("# r\n", encoding="utf-8")
            rows, errors = bl.collect_rows(root, bl._schema(), bl._registry())
            self.assertEqual(([], []), (rows, errors))


class BaselineTest(unittest.TestCase):
    def test_baseline_rows_are_derived_with_live_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = _baseline_report(root)
            rows, errors = bl.baseline_rows(root, bl._registry())
            self.assertEqual([], errors, errors)
            self.assertEqual(["regulatory-strict", "techdoc-strict"],
                             [r["profile"] for r in rows])
            for row in rows:
                self.assertEqual("nf-gate-defect-bench/baseline", row["submission_id"])
                self.assertEqual(bl._sha_file(report), row["contract_digest"])
                self.assertTrue((root / row["evidence_path"]).is_file())

    def test_baseline_inconsistent_totals_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _baseline_report(root)
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["profiles"]["techdoc-strict"]["totals"]["detection_rate"] = 0.5
            path.write_text(json.dumps(doc), encoding="utf-8")
            _rows, errors = bl.baseline_rows(root, bl._registry())
            self.assertTrue(any("detection_rate" in e for e in errors), errors)

    def test_baseline_missing_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            _rows, errors = bl.baseline_rows(Path(tmp), bl._registry())
            self.assertTrue(any("gate_defect_bench" in e for e in errors), errors)

    def test_real_repo_baseline_matches_bench_report(self):
        """真仓基线必须与 T5.3 台架报告一致（跨波次回归：报告改了而榜没重生成会被这里抓住）。"""
        rows, errors = bl.baseline_rows(bl.ROOT, bl._registry())
        self.assertEqual([], errors, errors)
        got = {r["profile"]: (r["cases"], r["detected"], r["false_positives"]) for r in rows}
        self.assertEqual({"techdoc-strict": (80, 80, 0),
                          "regulatory-strict": (72, 72, 0)}, got)


class RenderTest(unittest.TestCase):
    """3 排序 + 4 空榜诚实。"""

    def test_empty_board_is_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            doc = bl.build(root)
            self.assertEqual([], doc["errors"], doc["errors"])
            self.assertEqual([], doc["models"])
            text = doc["text"]
            self.assertIn("尚无真实模型结果", text)
            self.assertIn("诚实空榜", text)
            self.assertIn("baseline ≠ 模型成绩", text)
            self.assertEqual(0, text.count("| 1 |"), "空榜不得出现伪造排名行")
            self.assertEqual(2, len(doc["baselines"]))

    def test_sorted_by_rate_then_fp_then_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            _write_result(root, submission_id="z/low@1", cases=80, detected=72)   # 0.90
            _write_result(root, submission_id="a/high@1", cases=80, detected=80, fp=2)  # 1.00 fp .10
            _write_result(root, submission_id="m/mid@1", cases=80, detected=76)   # 0.95
            doc = bl.build(root)
            self.assertEqual([], doc["errors"], doc["errors"])
            text = doc["text"]
            order = [text.index(s) for s in ("a/high@1", "m/mid@1", "z/low@1")]
            self.assertEqual(sorted(order), order, "排序应为检出率降序：%r" % order)

    def test_tie_break_prefers_lower_fp_then_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_result(root, submission_id="b/one@1", cases=80, detected=80, fp=1)
            _write_result(root, submission_id="a/two@1", cases=80, detected=80, fp=1)
            _write_result(root, submission_id="c/zero@1", cases=80, detected=80, fp=0)
            doc = bl.build(root)
            text = doc["text"]
            order = [text.index(s) for s in ("c/zero@1", "a/two@1", "b/one@1")]
            self.assertEqual(sorted(order), order, "同率同误报须按提交 id 升序：%r" % order)


class CheckDriftTest(unittest.TestCase):
    """5 防漂移：--check 三方对账。"""

    def test_write_then_check_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            _write_result(root)
            _doc, errors = bl.write_board(root)
            self.assertEqual([], errors, errors)
            self.assertEqual([], bl.check(root))
            self.assertTrue((root / bl.BOARD_REL).is_file())

    def test_drift_when_result_changes_without_regen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            path, _row = _write_result(root, detected=74)
            self.assertEqual([], bl.write_board(root)[1])
            data = json.loads(path.read_text(encoding="utf-8"))
            data["detected"] = 78
            data["detection_rate"] = round(78 / data["cases"], 4)
            path.write_text(json.dumps(data), encoding="utf-8")
            problems = bl.check(root)
            self.assertTrue(any("漂移" in p for p in problems), problems)

    def test_drift_when_board_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            problems = bl.check(root)
            self.assertTrue(any("缺失" in p for p in problems), problems)

    def test_invalid_input_blocks_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            _write_result(root)
            self.assertEqual([], bl.write_board(root)[1])
            before = (root / bl.BOARD_REL).read_text(encoding="utf-8")
            _write_result(root, evidence_path="results/bench/evidence/nope.json",
                          filename="bad__techdoc-strict.json",
                          submission_id="bad/row@1")
            _doc, errors = bl.write_board(root)
            self.assertTrue(errors, "非法输入应阻断写盘")
            self.assertEqual(before, (root / bl.BOARD_REL).read_text(encoding="utf-8"))

    def test_real_repo_board_is_fresh_and_honest(self):
        self.assertEqual([], bl.check(bl.ROOT), "真仓榜单陈旧：请跑 bench_leaderboard.py --write")
        board = (bl.ROOT / bl.BOARD_REL).read_text(encoding="utf-8")
        models = bl.build(bl.ROOT)["models"]
        if not models:
            self.assertIn("尚无真实模型结果", board)


class CliTest(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "bench_leaderboard.py"), *args],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            timeout=300)

    def test_cli_write_and_check_on_temp_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            _write_result(root)
            proc = self._run("--root", tmp, "--write", "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-800:])
            doc = json.loads(proc.stdout)
            self.assertTrue(doc["ok"])
            self.assertEqual(1, doc["models"])
            self.assertTrue((root / bl.BOARD_REL).is_file())
            self.assertEqual(0, self._run("--root", tmp, "--check").returncode)

    def test_cli_check_exits_nonzero_on_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _baseline_report(root)
            path, row = _write_result(root, detected=74)
            self.assertEqual(0, self._run("--root", tmp, "--write").returncode)
            row["detected"] = 70
            row["detection_rate"] = round(70 / row["cases"], 4)
            path.write_text(json.dumps(row), encoding="utf-8")
            proc = self._run("--root", tmp, "--check")
            self.assertEqual(1, proc.returncode)
            self.assertIn("漂移", proc.stderr)

    def test_real_repo_check_passes(self):
        self.assertEqual(0, self._run("--check").returncode)


if __name__ == "__main__":
    unittest.main()
