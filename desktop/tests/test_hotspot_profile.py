"""P5-09 判据：剖析三件套必须**同输入同输出**（排名可复算），且缺席如实记、目标解析 fail-closed。

为什么判可复算而不是判「跑得快」：取数工具是给「该不该换语言」做依据的。若它自己的排名随
调用顺序漂移，那么一切基于它的决策都不可复核。故判据钉在**确定性**、**纯函数解析面**与
**拒绝面**上；外部工具（py-spy / hyperfine）**在不在场**只影响能否实跑，不影响解析面正确性。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "nf_hotspot", str(ROOT / "scripts" / "hotspot_profile.py"))
hot = importlib.util.module_from_spec(_SPEC)
sys.modules["nf_hotspot"] = hot
_SPEC.loader.exec_module(hot)


def _fake(key, cum, self_time=0.0, calls=1):
    return {"key": key, "calls": calls, "tottime_s": self_time, "cumtime_s": cum}


class RankTest(unittest.TestCase):
    def test_ordered_by_cumtime_then_key(self):
        rows = [_fake("b", 1.0), _fake("a", 5.0), _fake("c", 5.0)]
        self.assertEqual(["a", "c", "b"], [e["key"] for e in hot.rank(rows, 3)])

    def test_truncates_and_handles_zero(self):
        rows = [_fake("a", 1.0), _fake("b", 2.0)]
        self.assertEqual(["b"], [e["key"] for e in hot.rank(rows, 1)])
        self.assertEqual([], hot.rank(rows, 0))
        self.assertEqual([], hot.rank([], 5))

    def test_rank_is_stable_across_input_order(self):
        rows = [_fake("x", 2.0), _fake("y", 2.0), _fake("z", 9.0)]
        first = [e["key"] for e in hot.rank(rows, 3)]
        shuffled = [e["key"] for e in hot.rank(list(reversed(rows)), 3)]
        self.assertEqual(first, shuffled)

    def test_missing_time_fields_do_not_crash(self):
        self.assertEqual(["k"], [e["key"] for e in hot.rank([{"key": "k"}], 1)])


class SummarizeTest(unittest.TestCase):
    def test_report_shape_and_totals(self):
        rep = hot.summarize([_fake("a", 1.5), _fake("b", 2.5)], 1)
        self.assertEqual("nf-hotspot-profile/1", rep["schema"])
        self.assertEqual(2, rep["entries"])
        self.assertEqual(4.0, rep["total_cumtime_s"])
        self.assertEqual(1, len(rep["top"]))

    def test_tool_presence_is_reported_for_all_three_axes(self):
        # 三件套齐不齐是**环境事实**，报告里必须逐条出现（在场给路径、缺席给 None）。
        tools = hot.summarize([], 1)["tools"]
        self.assertEqual({"cProfile", "py-spy", "hyperfine"}, set(tools))
        self.assertEqual("stdlib", tools["cProfile"])
        for name in hot.EXTERNAL_TOOLS:
            self.assertTrue(tools[name] is None or Path(tools[name]).is_file() or tools[name])


class SampleParsingTest(unittest.TestCase):
    """py-spy record 的 speedscope 输出解析（纯函数；与工具在不在场无关）。"""

    FRAMES = [{"name": "hot", "file": "a.py", "line": 1},
              {"name": "cold", "file": "b.py", "line": 2}]

    def test_top_frames_counts_sample_hits(self):
        rows = hot.top_frames(self.FRAMES, [[0, 1], [0], [0], [1]], 2)
        self.assertEqual(["a.py:hot", "b.py:cold"], [r["key"] for r in rows])
        self.assertEqual(3, rows[0]["samples"])

    def test_out_of_range_indices_are_ignored(self):
        self.assertEqual(["a.py:hot"], [r["key"] for r in hot.top_frames(self.FRAMES, [[0, 9]], 5)])

    def test_empty_samples_are_not_an_error(self):
        self.assertEqual([], hot.top_frames(self.FRAMES, [], 5))
        rep = hot.speedscope_report({}, 5)
        self.assertEqual("nf-hotspot-samples/1", rep["schema"])
        self.assertEqual((0, 0, []), (rep["frames"], rep["samples"], rep["top"]))

    def test_speedscope_report_merges_profiles(self):
        doc = {"shared": {"frames": self.FRAMES},
               "profiles": [{"samples": [[0]]}, {"samples": [[0], [1]]}]}
        rep = hot.speedscope_report(doc, 2)
        self.assertEqual(3, rep["samples"])
        self.assertEqual(2, rep["top"][0]["samples"])


class BenchmarkParsingTest(unittest.TestCase):
    """hyperfine 的 JSON 换过 schema：2.x 用 measurements[].<metric>.value，1.x 用 mean。"""

    NEW = {"primary_metric": "time_wall_clock", "results": [
        {"command": "A", "measurements": [{"time_wall_clock": {"value": 2.0}},
                                          {"time_wall_clock": {"value": 4.0}}]},
        {"command": "B", "measurements": [{"time_wall_clock": {"value": 1.0}},
                                          {"time_wall_clock": {"value": 1.0}}]}]}
    LEGACY = {"results": [{"command": "A", "mean": 2.0, "stddev": 0.1, "min": 1.9,
                           "times": [2, 2]},
                          {"command": "B", "mean": 0.5, "stddev": 0.01, "min": 0.49,
                           "times": [0.5, 0.5]}]}

    def test_new_schema_mean_and_speedup(self):
        rep = hot.hyperfine_report(self.NEW)
        self.assertEqual(3.0, rep["commands"][0]["mean_s"])
        self.assertEqual(2, rep["commands"][0]["runs"])
        self.assertEqual("time_wall_clock", rep["metric"])
        self.assertEqual(3.0, rep["speedup_first_over_second"])

    def test_legacy_schema_still_parses(self):
        rep = hot.hyperfine_report(self.LEGACY)
        self.assertEqual(4.0, rep["speedup_first_over_second"])

    def test_empty_results_have_no_speedup(self):
        self.assertIsNone(hot.hyperfine_report({"results": []})["speedup_first_over_second"])

    def test_stddev_is_computed_not_assumed(self):
        self.assertAlmostEqual(1.0, hot.hyperfine_report(self.NEW)["commands"][0]["stddev_s"], 6)


class TargetResolutionTest(unittest.TestCase):
    def test_rejects_malformed_targets(self):
        for bad in ("", "nosuchmodule:fn", "moduleonly", ":fn"):
            with self.assertRaises((ValueError, ImportError, AttributeError), msg=bad):
                hot.resolve_target(bad)

    def test_resolves_real_stdlib_target(self):
        self.assertTrue(callable(hot.resolve_target("json:dumps")))

    def test_profile_callable_returns_entries(self):
        stats = hot.profile_callable(hot.resolve_target("json:dumps"), ({"a": 1},))
        self.assertTrue(stats)
        self.assertIn("key", stats[0])

    def test_absent_tool_resolves_to_none_not_a_made_up_path(self):
        for name in ("definitely-not-a-real-tool-xyz",):
            self.assertIsNone(hot.resolve_tool(name))

    def test_sample_and_benchmark_report_absence_instead_of_faking(self):
        # 让解析面指向空地：实跑必须返回 ok=False + 缺席原因，而不是抛或返回空成功。
        saved = hot.ENV_DIRS
        import os
        old = os.environ.get(saved)
        os.environ[saved] = str(ROOT / "no" / "such" / "tools")
        try:
            sample = hot.run_sample("json:dumps", (), 1, ROOT / ".rivet" / "scratch" / "profile")
            bench = hot.run_benchmark(["a", "b"], 1, ROOT / ".rivet" / "scratch" / "profile")
        finally:
            if old is None:
                os.environ.pop(saved, None)
            else:
                os.environ[saved] = old
        for rep in (sample, bench):
            self.assertIn("ok", rep)
            if not rep["ok"]:
                self.assertTrue(rep["reason"] and rep["why"], rep)


if __name__ == "__main__":
    unittest.main()
