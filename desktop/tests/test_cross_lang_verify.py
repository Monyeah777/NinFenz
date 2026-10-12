"""P-C2 仲裁判据：规范为权威、多数票只作定位线索（含 SPEC-GAP 分支）。

另含两条**环境无关**的常驻判据（不依赖 cargo/dotnet 在场）：
  - 向量清单的形状（schema / id 唯一 / 输入在场 / 正例期望非空）；
  - 覆盖棘轮（§16.3）：当前覆盖的 spec_clause 不得少于 'ratchet.json' 冻结基线，
    且 probe 条目**不计入**覆盖（否则加一条探针就能刷数字）。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "clv", str(ROOT / "scripts" / "cross_lang_verify.py"))
clv = importlib.util.module_from_spec(_SPEC)
sys.modules["clv"] = clv
_SPEC.loader.exec_module(clv)

VECTOR_DIR = ROOT / "protocol" / "generated" / "test_vectors"
MANIFESTS = ("jcs_conformance.json", "jcs_reject.json", "jcs_basic.json", "harness.json")


def _load(name):
    return clv.json_doc.loads((VECTOR_DIR / name).read_text(encoding="utf-8"), dict,
                              what=name)


def _vectors(pairs):
    """pairs: {(id, lang): status} → verify 形状的 rows。"""
    rows = {}
    for (vid, lang), st in pairs.items():
        rows.setdefault(vid, {"id": vid, "langs": {}})
        rows[vid]["langs"][lang] = {"status": st}
    return [rows[k] for k in sorted(rows)]


class ArbitrateTest(unittest.TestCase):
    def test_all_agree(self):
        got = clv.arbitrate(_vectors({("v", "python"): "PASS", ("v", "rust"): "PASS"}))
        self.assertEqual("PASS", got["outcome"])

    def test_single_deviation_is_suspect(self):
        got = clv.arbitrate(_vectors({("v", "python"): "PASS", ("v", "rust"): "FAIL",
                                      ("v", "csharp"): "PASS"}))
        self.assertEqual("FAIL", got["outcome"])
        self.assertEqual(["v/rust"], got["suspects"])
        self.assertIn("线索", got["clue"])

    def test_majority_deviation_is_spec_gap_not_verdict(self):
        got = clv.arbitrate(_vectors({("v", "python"): "FAIL", ("v", "rust"): "FAIL",
                                      ("v", "csharp"): "PASS"}))
        self.assertEqual("SPEC-GAP", got["outcome"])
        self.assertIn("不得", got["clue"])

    def test_two_comparable_single_deviation_is_fail_not_spec_gap(self):
        """N=2 没有「多数」可言：单一偏离必须判 FAIL 并点名偏离方。

        实测来源（2026-10-12）：512 MiB 插件对拍里 wasm 一侧偏离，旧规则 `len(deviants)*2 >=
        len(available)` 在 N=2 下把 1/2 当成多数 ⇒ 误报 SPEC-GAP（把「无从分辨」说成
        「规范有缺口」）。修法：SPEC-GAP 需要**至少 2 个偏离方**。
        """
        got = clv.arbitrate(_vectors({("v", "python"): "PASS", ("v", "wasm"): "FAIL"}))
        self.assertEqual("FAIL", got["outcome"])
        self.assertEqual(["v/wasm"], got["suspects"])

    def test_all_unknown_makes_no_claim(self):
        got = clv.arbitrate(_vectors({("v", "rust"): "UNKNOWN", ("v", "csharp"): "UNKNOWN"}))
        self.assertEqual("UNKNOWN", got["outcome"])
        self.assertIn("不下结论", got["clue"])

    def test_single_available_pass_is_pass_not_unknown(self):
        got = clv.arbitrate(_vectors({("v", "python"): "PASS", ("v", "rust"): "UNKNOWN"}))
        self.assertEqual("PASS", got["outcome"])


class RealVectorTest(unittest.TestCase):
    def test_repo_vector_arbitrates(self):
        doc = _load("jcs_basic.json")
        rep = clv.verify(doc, root=str(ROOT))
        self.assertEqual("PASS", rep["arbitration"]["outcome"], rep["arbitration"])
        # 整体 verdict 是**三态**且与环境绑定：工具链齐 ⇒ 必须 PASS（不得停在 UNKNOWN）；
        # 有缺席 ⇒ 必须如实 UNKNOWN（不许把没跑过的说成通过）。两侧都断言，才不会
        # 因「本机恰好有工具链」而把缺席路径悄悄放进盲区。
        declared = sorted({lang for v in doc["vectors"] for lang in (v.get("langs") or {})})
        tools = rep["toolchains"]
        missing = [lang for lang in declared if not tools.get(lang)]
        if missing:
            self.assertEqual("UNKNOWN", rep["verdict"],
                             f"工具链缺席（{missing}）时整体仍须 UNKNOWN")
        else:
            self.assertEqual("PASS", rep["verdict"],
                             f"三实现齐备时整体必须 PASS：{rep['vectors']}")


class ManifestShapeTest(unittest.TestCase):
    def test_every_manifest_is_wellformed(self):
        # jcs_basic.json 是 jcs_conformance.json 的**单条子集**（P-C1 走通件），
        # 故 id 唯一性只在「并集真正的三条清单」上要求，basic 单独存在是刻意的。
        ids = set()
        for name in MANIFESTS:
            doc = _load(name)
            self.assertEqual("nf-test-vectors/1", doc.get("schema"), name)
            seen_here = set()
            for v in doc["vectors"]:
                vid = v["id"]
                self.assertNotIn(vid, seen_here, f"同一清单内 id 重复：{vid}")
                seen_here.add(vid)
                if name != "jcs_basic.json":
                    self.assertNotIn(vid, ids, f"向量 id 跨清单重复：{vid}")
                    ids.add(vid)
                self.assertIn(v.get("expect") or "ok", ("ok", "fail"), vid)
                rel = str(v.get("input") or "")
                if rel:
                    self.assertTrue((ROOT / rel).is_file(), f"{vid} 的输入夹具缺席：{rel}")
                real = [s for s in (v.get("langs") or {}).values() if not s.get("probe")]
                if (v.get("expect") or "ok") == "ok" and real:
                    # 全 probe 的向量只探工具链在场，本就没有可比期望值。
                    self.assertTrue(str(v.get("expected") or ""),
                                    f"{vid} 有真实现却无可比期望值")
                for lang, spec in (v.get("langs") or {}).items():
                    self.assertIn(lang, clv.LANGS, vid)
                    if not spec.get("probe"):
                        self.assertTrue(spec.get("cmd"), f"{vid}/{lang} 缺 cmd")

    def test_covered_vector_ids_are_stable(self):
        # 覆盖棘轮的另一半：正例集合不许「改 id」式替换——实测的 id 集合冻结在测例里。
        conf = _load("jcs_conformance.json")
        self.assertEqual(
            ["jcs/astral-key-order", "jcs/basic-ascii", "jcs/escape-minimal",
             "jcs/escape-slash", "jcs/nested-sort", "jcs/number-fixed-vs-exp",
             "jcs/number-forms", "jcs/unicode-escape-decoded"],
            sorted(v["id"] for v in conf["vectors"]))


class CoverageRatchetTest(unittest.TestCase):
    def test_current_coverage_does_not_regress(self):
        cur = clv.coverage(clv.load_manifests(str(ROOT)))
        frozen = _load("ratchet.json")
        self.assertEqual([], clv.ratchet_regressions(cur, frozen),
                         "覆盖棘轮退化：某实现少覆盖了冻结基线里的 spec_clause")
        # 三实现都必须在棘轮里有登记（否则「只增不减」对它是空转）
        self.assertEqual({"python", "rust", "csharp"}, set(frozen["clauses"]))

    def test_probe_entries_do_not_count_as_coverage(self):
        docs = [{"vectors": [{"id": "a", "spec_clause": "S/1",
                              "langs": {"rust": {"cmd": ["cargo"], "probe": True}}}]}]
        self.assertEqual({}, clv.coverage(docs),
                         "probe 只探工具链在场，不得计入实现覆盖")

    def test_regression_detector_flags_missing_clause(self):
        got = clv.ratchet_regressions({"rust": ["S/1"]},
                                      {"clauses": {"rust": ["S/1", "S/9"]}})
        self.assertEqual(["rust 少覆盖 S/9"], got)
        self.assertEqual([], clv.ratchet_regressions({"rust": ["S/1", "S/9"]},
                                                     {"clauses": {"rust": ["S/1"]}}))


if __name__ == "__main__":
    unittest.main()
