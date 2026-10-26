#!/usr/bin/env python3
"""演练保真度（`core/drill_fidelity.py`）回归测试 —— 动态可执行面。

断言：量化口径（执行演练 + 回合回放 + 总口径）、不达标即 FAIL、**无载体即 FAIL**、
真仓保真度 100%。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import drill_fidelity as df  # noqa: E402


def _exec_set(tmp: str, name: str, cases) -> None:
    p = Path(tmp) / "desktop/tests/fixtures/execution" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": "nf-drill-cases/1", "pipeline": "P01",
                             "real_ids": ["M00"], "semantics": {}, "source_text": "",
                             "cases": cases}, ensure_ascii=False), encoding="utf-8")


def _round(tmp: str, name: str, verdict: str, transcript: str, allowed=("M00",)) -> None:
    p = Path(tmp) / "desktop/tests/fixtures/execution/rounds" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": "nf-round-fixture/1", "verdict": verdict,
                             "transcript": transcript, "allowed": list(allowed)},
                            ensure_ascii=False), encoding="utf-8")


def _pending_round(tmp: str, name: str, transcript: str, allowed=("M00",)) -> None:
    """待裁定样本（verdict/label_status = pending）：只过 parse 门，不进保真度分子分母。"""
    p = Path(tmp) / "desktop/tests/fixtures/execution/rounds" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": "nf-round-transcript/1", "verdict": "pending",
                             "label_status": "pending", "transcript": transcript,
                             "allowed": list(allowed), "adjudication": []},
                            ensure_ascii=False), encoding="utf-8")


def _corpus(tmp: str, doc_lines, adjudications, real_ids=("M00", "M01")) -> None:
    """造一份「真实语料 + 裁定表」最小场景（真实语料路径 / 裁定表挂在待裁定样本里）。"""
    doc = Path(tmp) / "docs" / "完整版样本_西幻生存流P03.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")
    import hashlib
    sha = hashlib.sha256(doc.read_bytes()).hexdigest()
    p = Path(tmp) / "desktop/tests/fixtures/execution/rounds" / "selfrun.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "schema": "nf-round-transcript/1", "verdict": "pending", "label_status": "pending",
        "transcript": "回合 1：依 06 §3 推进，M00 写回状态。\n", "allowed": list(real_ids),
        "real_corpus": {"source": "docs/完整版样本_西幻生存流P03.md", "sha256": sha,
                        "nonblank_lines": len([x for x in doc_lines if x.strip()]),
                        "real_ids": list(real_ids),
                        "adjudications": adjudications},
    }, ensure_ascii=False), encoding="utf-8")


#: 回合级 drill 的引用判据（_CITE）认 §N / 第N节|步|章 / L行 / 类别:Mxx——不认 [Mxx]
GOOD_TRANSCRIPT = ("回合 1：依 06 §3 推进，写回状态。\n"
                   "回合 2：依 06 §4 快照存档。\n")
BAD_TRANSCRIPT = "回合 1：既无引用也无推进。\n"


class MeasureTest(unittest.TestCase):
    def test_fidelity_is_ratio_of_passed_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            _exec_set(tmp, "p01_drill_cases.json", [
                {"id": "ok", "expect_captured": []},
                {"id": "bad", "expect_captured": ["不存在的捕获"]},
            ])
            _round(tmp, "good.json", "good", GOOD_TRANSCRIPT)
            m = df.measure(tmp)
        self.assertEqual(2, m["execution"]["cases"])
        self.assertEqual(1, m["execution"]["passed"])
        self.assertEqual(0.5, m["execution"]["fidelity"])
        self.assertEqual(1, m["rounds"]["total"])
        self.assertEqual(1, m["rounds"]["matched"])
        self.assertAlmostEqual(2 / 3, m["overall"]["fidelity"], places=4)

    def test_round_verdict_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            _round(tmp, "good.json", "good", GOOD_TRANSCRIPT)
            _round(tmp, "bad.json", "bad", BAD_TRANSCRIPT)
            m = df.measure(tmp)
        self.assertEqual(2, m["rounds"]["matched"], "good→conformant / bad→non-conformant 须复现")
        self.assertEqual(1.0, m["rounds"]["fidelity"])

    def test_round_mismatch_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _round(tmp, "wrong.json", "good", BAD_TRANSCRIPT)   # 声明 good 实则不合规
            m = df.measure(tmp)
        self.assertEqual(0, m["rounds"]["matched"])


class ScanTest(unittest.TestCase):
    def test_no_fixtures_fails_with_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues, _w, _s = df.scan(tmp)
        self.assertTrue(any("执行演练用例" in i and "修复指引" in i for i in issues), issues)
        self.assertTrue(any("回合级回放样本" in i for i in issues), issues)

    def test_imperfect_fidelity_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _exec_set(tmp, "p01_drill_cases.json", [{"id": "bad", "expect_captured": ["x"]}])
            _round(tmp, "good.json", "good", GOOD_TRANSCRIPT)
            issues, _w, _s = df.scan(tmp)
        self.assertTrue(any("保真度不足" in i for i in issues), issues)

    def test_perfect_fidelity_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _exec_set(tmp, "p01_drill_cases.json", [{"id": "ok", "expect_captured": []}])
            _round(tmp, "good.json", "good", GOOD_TRANSCRIPT)
            issues, _w, stats = df.scan(tmp)
        self.assertEqual([], issues)
        self.assertEqual(1.0, stats["fidelity"])

    def test_broken_json_set_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "desktop/tests/fixtures/execution/p01_drill_cases.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{oops", encoding="utf-8")
            issues, _w, _s = df.scan(tmp)
        self.assertTrue(any("不可解析" in i for i in issues), issues)


class PendingSampleTest(unittest.TestCase):
    """待裁定样本（verdict/label_status = pending）：不进保真度，但 parse 失败即 FAIL。"""

    def test_pending_sample_parsed_is_out_of_fidelity_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            _exec_set(tmp, "p01_drill_cases.json", [{"id": "ok", "expect_captured": []}])
            _round(tmp, "good.json", "good", GOOD_TRANSCRIPT)
            _pending_round(tmp, "selfrun.json", GOOD_TRANSCRIPT)
            issues, _w, stats = df.scan(tmp)
            m = df.measure(tmp)
        self.assertEqual([], issues)
        self.assertEqual(1.0, stats["fidelity"], "pending 样本不得拉低保真度")
        self.assertEqual(1, m["rounds"]["pending"])
        self.assertEqual(1, m["rounds"]["total"], "已裁定样本仍是 1")
        self.assertEqual(2, m["rounds"]["parse_total"])
        self.assertEqual(1.0, m["metrics"]["parse_rate"])

    def test_pending_sample_without_round_markers_fails_parse_gate(self):
        """真实语料跑 --rounds 已实测 FAIL（未检测到回合标记）：pending 样本同样不得放过。"""
        with tempfile.TemporaryDirectory() as tmp:
            _exec_set(tmp, "p01_drill_cases.json", [{"id": "ok", "expect_captured": []}])
            _pending_round(tmp, "selfrun.json", "整篇没有任何回合标记。\n")
            issues, _w, _s = df.scan(tmp)
        self.assertTrue(any("待裁定回合样本未解析出回合标记" in i for i in issues), issues)

    def test_pending_rule_hit_needs_adjudication(self):
        with tempfile.TemporaryDirectory() as tmp:
            _exec_set(tmp, "p01_drill_cases.json", [{"id": "ok", "expect_captured": []}])
            _pending_round(tmp, "selfrun.json", "回合 1：无引用也无推进。\n")
            issues, _w, _s = df.scan(tmp)
        self.assertTrue(any("规则命中未裁定" in i for i in issues), issues)


class RealCorpusAdjudicationTest(unittest.TestCase):
    """真实语料命中裁定门（唯一真实战例 P03）：命中必须逐条 TP/FP，TP 不得消失。"""

    def _issues(self, lines, adjudications, real_ids=("M00", "M01")):
        with tempfile.TemporaryDirectory() as tmp:
            _exec_set(tmp, "p01_drill_cases.json", [{"id": "ok", "expect_captured": []}])
            _corpus(tmp, lines, adjudications, real_ids)
            issues, _w, _s = df.scan(tmp)
        return issues

    def test_unadjudicated_hit_fails(self):
        issues = self._issues(["由 M99 推进。"], [])
        self.assertTrue(any("真实语料命中未裁定" in i for i in issues), issues)

    def test_adjudicated_hit_passes_and_counts(self):
        issues = self._issues(["由 M99 推进。"], [
            {"line": 1, "rule": "fabricated_id", "verdict": "FP", "live": True,
             "basis": "自造语料：句子无实际装配上下文"}])
        self.assertEqual([], issues)

    def test_tp_disappearance_fails_like_a_missed_capture(self):
        """TP 命中消失 = 漏报回归（「修缺陷」不得顺手把真捕获删掉）。"""
        issues = self._issues(["干干净净一句话。"], [
            {"line": 1, "rule": "fabricated_id", "verdict": "TP", "live": False,
             "basis": "自造语料：应为真捕获"}])
        self.assertTrue(any("TP 命中消失" in i for i in issues), issues)

    def test_claimed_live_hit_that_vanished_fails(self):
        issues = self._issues(["干干净净一句话。"], [
            {"line": 1, "rule": "fabricated_id", "verdict": "FP", "live": True,
             "basis": "自造语料"}])
        self.assertTrue(any("声称仍命中但实测已消失" in i for i in issues), issues)

    def test_trimmed_allowlist_is_rejected(self):
        """裁剪允许集能让命中变少 ⇒ 必须与语料注册表投影对账（防自指绿）。"""
        issues = self._issues(["| M00 | 甲 |\n| M01 | 乙 |", "由 M99 推进。"], [],
                              real_ids=("M00",))
        self.assertTrue(any("注册表投影不一致" in i for i in issues), issues)


class RealRepoTest(unittest.TestCase):
    def test_real_repo_fidelity_is_full(self):
        issues, _w, stats = df.scan(str(ROOT))
        self.assertEqual([], issues, f"真仓演练保真度须为满分，实得问题：{issues[:3]}")
        self.assertEqual(1.0, stats["fidelity"])
        self.assertGreaterEqual(stats["exec_sets"], 5)
        self.assertGreaterEqual(stats["round_samples"], 2)

    def test_real_repo_metrics_carry_parse_rate_hits_tp_fp(self):
        """`protocol/drill_fidelity.json` 的四个数必须有真载体：parse_rate / hits / TP / FP。"""
        m = df.measure(str(ROOT))
        met = m["metrics"]
        for key in ("parse_rate", "hits", "tp", "fp"):
            self.assertIn(key, met)
        # 真实语料整篇无回合标记 ⇒ raw parse 率 0；派生 3 回合自测转录可 parse ⇒ 样本 parse 率 1.0
        self.assertEqual(0.0, met["raw_parse_rate"], "原始 P03 不含「回合 N：」标记")
        self.assertEqual(1.0, met["parse_rate"], "回合样本应全部 parse 成功（含 pending 自测转录）")
        self.assertEqual(met["hits"], met["tp"] + met["fp"], "每条现存命中都必须有 TP/FP 裁定")
        # 2026-10-20 修完 5 条误报 ⇒ 真实语料现存命中 0（此前 5）
        self.assertEqual(5, met["hits_before"], "修复前命中数（裁定表条目）应仍为 5")
        self.assertEqual(0, met["hits"], "5 条已裁定误报修完后现存命中应为 0")
        self.assertEqual(0, met["tp"], "真实语料上从无真阳性")
        self.assertEqual(0, met["fp"], "现存误报应为 0")
        self.assertEqual(5, met["fp_resolved"], "5 条误报应全记入已修")

    def test_real_repo_adjudications_are_all_resolved(self):
        """逐条裁定必须与现测命中一致，且每条都带依据（不许「疑似」）。"""
        rc = df.real_corpus(str(ROOT))
        self.assertTrue(rc, "真实语料裁定块缺失（rounds/selfrun-*.json 的 real_corpus）")
        self.assertEqual([], rc["problems"], rc["problems"])
        live = {(a["line"], a["rule"]) for a in rc["adjudications"] if a["live"]}
        self.assertEqual(0, rc["hits"], f"真实语料现存命中应为 0：{sorted(live)}")
        self.assertEqual(set(), live)
        self.assertEqual(5, rc["fp_resolved"], "5 条误报应全部转为 live=false")
        for a in rc["adjudications"]:
            self.assertTrue(a["basis"].strip(), f"裁定缺依据：{a}")
            self.assertIn(a["verdict"], ("TP", "FP"))
        # 已确证缺陷：P03:109 的 `M10_死亡重生.md` 文件名误报必须消失（且不是靠放宽判据）
        self.assertNotIn((109, "fabricated_id"), live,
                         "M10 文件名误报仍在：路径 token 排除或后缀归一生效）")


if __name__ == "__main__":
    unittest.main()
