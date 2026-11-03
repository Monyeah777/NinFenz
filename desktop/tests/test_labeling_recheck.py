"""labeling.recheck 回归：指纹 / 复测记录 / 历史 / 摘要。

作者：impl（DSH agent）· 2026-11-02
运行：cd desktop && PYTHONPATH=src python3 -m unittest \
      tests.test_labeling_recheck -v

夹具：两个临时 PNG（无标识 → FAIL；metadata.make_png 写 AIGC 文本块 →
WARN），用 checker.check_file 生成 before/after，再交给 build_record。
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import checker, metadata, recheck  # noqa: E402

RAW = {
    "Label": "1",
    "ContentProducer": "001091350100M000100Y4300000",
    "ProduceID": "pid20250101v123456",
}

STATES = {"fixed", "regressed", "unchanged", "new", "removed"}


def _snapshot(path):
    """checker.check_file + fingerprint → build_record 可用的 before/after。"""
    report = checker.check_file(path)
    fp = recheck.fingerprint(path)
    return {
        "report_id": fp["sha256"][:16],
        "file_sha256": fp["sha256"],
        "verdict": report["verdict"],
        "sections": report["sections"],
    }


def _by_id(record):
    return {t["id"]: t for t in record["transitions"]}


class RecheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.fail_png = str(cls.tmp / "before.png")
        cls.ok_png = str(cls.tmp / "after.png")
        metadata.make_png(cls.fail_png)
        payload = json.dumps({"AIGC": RAW}, ensure_ascii=False)
        metadata.make_png(cls.ok_png, {"AIGC": payload})
        cls.before_report = checker.check_file(cls.fail_png)
        cls.after_report = checker.check_file(cls.ok_png)
        cls.before = _snapshot(cls.fail_png)
        cls.after = _snapshot(cls.ok_png)
        cls.record = recheck.build_record(cls.before, cls.after)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # ------------------------------------------------------------ 指纹
    def test_fingerprint_png_fields(self):
        fp = recheck.fingerprint(self.fail_png)
        raw = Path(self.fail_png).read_bytes()
        self.assertEqual(
            set(fp), {"sha256", "size", "container", "cntsel"})
        self.assertEqual(fp["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(fp["size"], len(raw))
        self.assertEqual(fp["container"], "png")
        self.assertEqual(fp["cntsel"], "PNG")

    def test_fingerprint_missing_file_raises_with_guidance(self):
        missing = str(self.tmp / "nope.png")
        with self.assertRaises(ValueError) as ctx:
            recheck.fingerprint(missing)
        self.assertIn("修复指引", str(ctx.exception))

    def test_fingerprint_without_idat_cntsel_is_none(self):
        broken = self.tmp / "broken.png"
        broken.write_bytes(b"\x89PNG\r\n\x1a\n")
        fp = recheck.fingerprint(str(broken))
        self.assertEqual(fp["container"], "png")
        self.assertIsNone(fp["cntsel"])
        self.assertEqual(fp["size"], 8)

    # ------------------------------------------------------------ 记录
    def test_record_schema_id_and_snapshots(self):
        rec = self.record
        self.assertEqual(rec["schema"], "nf-label-recheck/1")
        joined = self.before["report_id"] + self.after["report_id"]
        want = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
        self.assertEqual(rec["recheck_id"], want)
        self.assertEqual(len(rec["recheck_id"]), 16)
        self.assertEqual(rec["before"], {
            "report_id": self.before["report_id"],
            "file_sha256": self.before["file_sha256"],
            "verdict": "FAIL",
        })
        self.assertEqual(rec["after"]["file_sha256"],
                         self.after["file_sha256"])
        self.assertEqual(rec["after"]["verdict"], "WARN")

    def test_transitions_section_and_item_states(self):
        rows = _by_id(self.record)
        statuses = {t["state"] for t in self.record["transitions"]}
        self.assertTrue(statuses <= STATES, statuses)
        self.assertEqual(
            {key for key in rows if len(key) == 1},
            {"A", "B", "C", "D", "E"})
        self.assertEqual(rows["B0"]["state"], "removed")
        self.assertEqual(rows["B1"]["state"], "new")
        self.assertEqual(rows["B1"]["after"], "PASS")
        self.assertEqual(rows["B"]["before"], "FAIL")
        self.assertEqual(rows["B"]["after"], "WARN")
        self.assertEqual(rows["B"]["state"], "fixed")
        self.assertEqual(rows["E1"]["state"], "fixed")
        # NA→WARN 表示判据刚适用，不算回退
        self.assertEqual(rows["C"]["state"], "unchanged")
        self.assertEqual(rows["C0"]["state"], "unchanged")

    def test_fixed_remaining_regressed_lists(self):
        rec = self.record
        self.assertEqual(set(rec["fixed"]), {"E1", "E6"})
        self.assertNotIn("B1", rec["fixed"])
        self.assertIn("B3", rec["remaining"])
        self.assertNotIn("E1", rec["remaining"])
        self.assertEqual(rec["regressed"], [])

    def test_verdict_delta_and_summary(self):
        delta = self.record["verdict_delta"]
        self.assertEqual((delta["before"], delta["after"]), ("FAIL", "WARN"))
        self.assertEqual(delta["direction"], "improved")
        self.assertTrue(delta["changed"])
        text = recheck.summary(self.record)
        self.assertIn("FAIL→WARN", text)
        self.assertIn("改善", text)
        self.assertNotIn("\n", text)

    def test_reversed_order_reports_regression(self):
        rev = recheck.build_record(self.after, self.before)
        self.assertEqual(rev["verdict_delta"]["direction"], "worsened")
        self.assertEqual(set(rev["regressed"]), {"E1", "E6"})
        self.assertIn("B0", rev["remaining"])
        self.assertNotEqual(rev["recheck_id"], self.record["recheck_id"])

    def test_raw_check_file_reports_are_accepted(self):
        raw = recheck.build_record(self.before_report, self.after_report)
        self.assertEqual(raw["schema"], "nf-label-recheck/1")
        self.assertIsNone(raw["before"]["file_sha256"])
        self.assertEqual(len(raw["before"]["report_id"]), 16)
        self.assertEqual(_by_id(raw)["B1"]["state"], "new")
        again = recheck.build_record(self.before_report, self.after_report)
        self.assertEqual(again, raw)

    # ------------------------------------------------------------ 历史
    def test_history_append_dedupes_same_recheck_id(self):
        history = [dict(self.record)]
        twice = recheck.history_append(history, self.record)
        self.assertEqual(twice, [self.record])
        self.assertEqual(history, [self.record])  # 不改入参
        updated = dict(self.record, note="人工复核")
        merged = recheck.history_append(twice, updated)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["note"], "人工复核")

    def test_history_append_orders_by_time(self):
        early = {"recheck_id": "a" * 16,
                 "created_at": "2026-01-01T00:00:00+08:00"}
        late = {"recheck_id": "b" * 16,
                "created_at": "2026-02-01T00:00:00+08:00"}
        got = recheck.history_append([late], early)
        self.assertEqual([r["recheck_id"] for r in got],
                         [early["recheck_id"], late["recheck_id"]])

    def test_history_save_load_roundtrip(self):
        path = self.tmp / "history.json"
        recheck.save_history(str(path), [self.record])
        self.assertEqual(recheck.load_history(str(path)), [self.record])
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))

    def test_load_history_missing_file_is_empty(self):
        self.assertEqual(recheck.load_history(str(self.tmp / "none.json")), [])

    def test_load_history_bad_json_raises_with_guidance(self):
        broken = self.tmp / "broken.json"
        broken.write_text("{oops", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            recheck.load_history(str(broken))
        self.assertIn("修复指引", str(ctx.exception))
        with self.subTest("根节点不是数组"):
            obj = self.tmp / "object.json"
            obj.write_text('{"a": 1}', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx2:
                recheck.load_history(str(obj))
            self.assertIn("修复指引", str(ctx2.exception))


if __name__ == "__main__":
    unittest.main()
