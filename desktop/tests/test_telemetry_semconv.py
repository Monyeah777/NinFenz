"""遥测 semconv 映射单测（不改 trace 格式；只对齐属性命名与 OTLP 形状）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import telemetry_semconv as ts  # noqa: E402

RECORD = {
    "tool": "nf assemble",
    "phase": "plan",
    "requirement": "校园情感，毕业遗憾线",
    "status": "preset",
    "matched": True,
    "package": "西幻生存领域包",
    "pipeline": "P03",
    "allowed_modules": 44,
    "ok": True,
    "issues": [],
    "stats": {"segments": 8},
}


class TestTelemetrySemconv(unittest.TestCase):
    def test_tool_name_and_call_id_deterministic(self):
        self.assertEqual(ts.tool_name_of(RECORD), "nf.assemble")
        self.assertEqual(ts.tool_name_of({"tool": "nf"}), "nf")
        self.assertEqual(ts.call_id_of(RECORD), ts.call_id_of(dict(RECORD)))

    def test_attributes_carry_semconv_names(self):
        attrs = ts.attributes_for(RECORD)
        self.assertEqual(attrs["gen_ai.operation.name"], "execute_tool")
        self.assertEqual(attrs["gen_ai.tool.name"], "nf.assemble")
        self.assertEqual(attrs["gen_ai.agent.name"], "ninfenz")
        self.assertEqual(attrs["gen_ai.tool.call.arguments"]["phase"], "plan")
        self.assertEqual(attrs["gen_ai.tool.call.result"]["pipeline"], "P03")
        self.assertIn("gen_ai.tool.call.id", attrs)

    def test_span_name_and_status(self):
        span = ts.to_span(RECORD)
        self.assertEqual(span["name"], "execute_tool nf.assemble")
        self.assertEqual(span["status"]["code"], 1)
        bad = ts.to_span(dict(RECORD, ok=False))
        self.assertEqual(bad["status"]["code"], 2)
        keys = {a["key"] for a in span["attributes"]}
        self.assertIn("gen_ai.tool.name", keys)

    def test_export_shape(self):
        out = ts.to_export([RECORD, dict(RECORD, phase="check")])
        rs = out["resourceSpans"][0]
        self.assertEqual(rs["resource"]["attributes"][0]["key"], "service.name")
        spans = rs["scopeSpans"][0]["spans"]
        self.assertEqual(len(spans), 2)
        self.assertEqual(rs["scopeSpans"][0]["scope"]["name"], ts.SCOPE_NAME)

    def test_minimal_record_does_not_crash(self):
        attrs = ts.attributes_for({})
        self.assertEqual(attrs["gen_ai.tool.name"], "nf")
        self.assertNotIn("gen_ai.tool.call.arguments", attrs)

    def test_load_trace_accepts_single_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp, "one.json")
            p1.write_text(json.dumps(RECORD, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(len(ts.load_trace(str(p1))), 1)
            p2 = Path(tmp, "many.json")
            p2.write_text(json.dumps({"records": [RECORD, RECORD]}),
                          encoding="utf-8")
            self.assertEqual(len(ts.load_trace(str(p2))), 2)

    def test_golden_semconv_attributes_and_otlp_ids(self):
        span = ts.to_span(RECORD)
        self.assertEqual("nf-5e22b03a2ef472c6", ts.call_id_of(RECORD))
        self.assertEqual("0d19d6f19529a5084490fd40c071b15b", span["traceId"])
        self.assertEqual("8010a58cf08cc46c", span["spanId"])
        self.assertEqual("execute_tool nf.assemble", span["name"])
        self.assertEqual(1, span["kind"])
        self.assertEqual(1, span["status"]["code"])
        self.assertEqual(
            [
                "gen_ai.agent.name",
                "gen_ai.conversation.id",
                "gen_ai.operation.name",
                "gen_ai.tool.call.arguments",
                "gen_ai.tool.call.id",
                "gen_ai.tool.call.result",
                "gen_ai.tool.name",
            ],
            [attr["key"] for attr in span["attributes"]],
        )

    def test_otlp_json_shape_does_not_claim_transport_or_wall_clock(self):
        export = ts.to_export([RECORD])
        self.assertEqual({"resourceSpans"}, set(export))
        resource_spans = export["resourceSpans"][0]
        self.assertEqual({"resource", "scopeSpans"}, set(resource_spans))
        scope_spans = resource_spans["scopeSpans"][0]
        self.assertEqual({"scope", "spans"}, set(scope_spans))
        self.assertNotIn("schemaUrl", scope_spans["scope"])
        span = scope_spans["spans"][0]
        self.assertNotIn("startTimeUnixNano", span)
        self.assertNotIn("endTimeUnixNano", span)
        self.assertNotIn("endpoint", json.dumps(export))


class StrictOtlpIdsTest(unittest.TestCase):
    def test_ids_are_fixed_length_hex(self):
        span = ts.to_span(RECORD)
        self.assertEqual(32, len(span["traceId"]))
        self.assertEqual(16, len(span["spanId"]))
        self.assertTrue(all(ch in "0123456789abcdef" for ch in span["traceId"]))
        self.assertTrue(all(ch in "0123456789abcdef" for ch in span["spanId"]))
        padded = ts.to_span(RECORD, span_id="abc")
        self.assertEqual("abc" + "0" * 13, padded["spanId"])

    def test_status_is_tristate(self):
        without = {k: v for k, v in RECORD.items() if k != "ok"}
        self.assertEqual(0, ts.to_span(without)["status"]["code"])
        self.assertEqual(1, ts.to_span(dict(RECORD, ok=True))["status"]["code"])
        self.assertEqual(2, ts.to_span(dict(RECORD, ok=False))["status"]["code"])


class TraceRejectTest(unittest.TestCase):
    def _write(self, root: str, name: str, text: str) -> str:
        path = Path(root, name)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_rejects_non_object_empty_and_mixed_records(self):
        cases = {
            "scalar.json": "1",
            "empty.json": "{}",
            "mixed.json": json.dumps([RECORD, 1], ensure_ascii=False),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in cases.items():
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        ts.load_trace(self._write(tmp, name, text))

    def test_rejects_nonfinite_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in {
                "nan.json": '{"records":[{"stats":{"score":NaN}}]}',
                "bad.json": '{"records": [',
            }.items():
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        ts.load_trace(self._write(tmp, name, text))

    def test_rejects_oversized_trace_before_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "large.json", json.dumps(RECORD))
            with mock.patch.object(ts, "MAX_TRACE_BYTES", 8):
                with self.assertRaisesRegex(ValueError, "trace 过大"):
                    ts.load_trace(path)


if __name__ == "__main__":
    unittest.main()
