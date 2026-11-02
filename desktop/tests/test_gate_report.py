#!/usr/bin/env python3
"""JUnit gate-report tests: stable mapping, fail-closed parsing, valid XML."""
from __future__ import annotations

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import gate_report  # noqa: E402


def _complete_records():
    lines = []
    for check_id in range(1, gate_report.EXPECTED_CHECKS + 1):
        status = "PASS"
        if check_id == 12:
            status = "FAIL"
        elif check_id == 13:
            status = "WARN"
        lines.append(f"{check_id}\t{status}\tcheck {check_id} <detail & evidence>")
    return lines


class GateReportTest(unittest.TestCase):
    def test_complete_mapping_is_valid_junit(self):
        xml = gate_report.render_junit(
            gate_report.parse_records(_complete_records()), elapsed=12.5
        )
        root = ET.fromstring(xml)

        self.assertEqual("testsuites", root.tag)
        self.assertEqual("42", root.get("tests"))
        self.assertEqual("1", root.get("failures"))
        self.assertEqual("0", root.get("errors"))
        self.assertEqual("1", root.get("skipped"))
        self.assertEqual("42", str(len(root.findall("./testsuite/testcase"))))

        cases = {
            int(case.find("./properties/property[@name='check_id']").get("value")): case
            for case in root.findall("./testsuite/testcase")
        }
        self.assertIsNotNone(cases[12].find("failure"))
        self.assertIsNotNone(cases[13].find("skipped"))
        self.assertEqual(
            "WARN",
            cases[13].find("./properties/property[@name='nf.status']").get("value"),
        )
        self.assertIn("check 13 <detail & evidence>", cases[13].findtext("system-out"))

    def test_missing_check_becomes_error_not_silent_pass(self):
        lines = [line for line in _complete_records() if not line.startswith("42\t")]
        root = ET.fromstring(gate_report.render_junit(gate_report.parse_records(lines)))
        case = next(
            item
            for item in root.findall("./testsuite/testcase")
            if item.find("./properties/property[@name='check_id']").get("value") == "42"
        )

        self.assertEqual("1", root.get("errors"))
        self.assertIsNotNone(case.find("error"))

    def test_unknown_check_and_status_fail_closed(self):
        for bad in ("43\tPASS\tunknown", "1\tMAYBE\tbad status"):
            with self.subTest(bad=bad), self.assertRaises(gate_report.GateReportError):
                gate_report.parse_records([bad])

    def test_malformed_record_fails_closed(self):
        with self.assertRaises(gate_report.GateReportError):
            gate_report.parse_records(["1\tPASS"])

    def test_rendering_is_deterministic(self):
        parsed = gate_report.parse_records(_complete_records())
        self.assertEqual(
            gate_report.render_junit(parsed, elapsed=1.0),
            gate_report.render_junit(parsed, elapsed=1.0),
        )

    def test_cli_writes_report_and_returns_failure_for_failed_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = Path(tmp) / "records.tsv"
            output = Path(tmp) / "junit.xml"
            records.write_text("\n".join(_complete_records()) + "\n", encoding="utf-8")

            code = gate_report.main(
                ["--records", str(records), "--out", str(output), "--elapsed", "3.25"]
            )

            self.assertEqual(1, code)
            self.assertEqual("42", ET.parse(output).getroot().get("tests"))


if __name__ == "__main__":
    unittest.main()
