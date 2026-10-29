#!/usr/bin/env python3
"""ASVS V16.4.2/V16.4.3: tamper-evident, independently retained audit events."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import security_audit  # noqa: E402


class _Sink:
    def __init__(self):
        self.records = []

    def emit(self, payload: str) -> None:
        self.records.append(payload)


class SecurityAuditTest(unittest.TestCase):
    def test_hash_chain_verifies_and_detects_modified_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "security-audit.jsonl"
            sink = _Sink()
            audit = security_audit.SecurityAuditLog(path, sink=sink)
            first = audit.append({"event": "daemon.started"})
            second = audit.append({"event": "daemon.authorization_denied"})
            self.assertEqual(2, len(sink.records))
            self.assertEqual(first["digest"], second["prev"])
            self.assertEqual([], audit.verify())

            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            rows[0]["payload"]["event"] = "daemon.stopped"
            path.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(any("digest mismatch" in issue for issue in audit.verify()))

    def test_each_record_is_forwarded_to_the_independent_os_sink(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = _Sink()
            audit = security_audit.SecurityAuditLog(
                Path(tmp) / "security-audit.jsonl", sink=sink
            )
            record = audit.append({"event": "daemon.request_rejected", "reason": "protocol"})
        self.assertEqual(1, len(sink.records))
        forwarded = json.loads(sink.records[0])
        self.assertEqual(record["digest"], forwarded["digest"])
        self.assertEqual("daemon.request_rejected", forwarded["payload"]["event"])
        self.assertEqual("v1", forwarded["alg"])

    def test_os_sink_selection_is_explicit_and_supported(self):
        sink = security_audit.default_sink()
        self.assertIn(sink.kind, {"windows-eventlog", "posix-syslog"})

    def test_records_fail_closed_on_unknown_crypto_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "security-audit.jsonl"
            path.write_text(
                json.dumps({
                    "alg": "made-up",
                    "digest": "0" * 64,
                    "payload": {"event": "forged"},
                    "prev": "",
                }) + "\n",
                encoding="utf-8",
            )
            audit = security_audit.SecurityAuditLog(path, sink=_Sink())
            self.assertTrue(any("unknown crypto suite" in issue for issue in audit.verify()))

    def test_append_reads_only_the_tail_not_the_whole_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = security_audit.SecurityAuditLog(
                Path(tmp) / "security-audit.jsonl", sink=_Sink()
            )
            audit.append({"event": "daemon.started"})
            with mock.patch.object(
                Path, "read_text", side_effect=AssertionError("append must not read full log")
            ):
                record = audit.append({"event": "daemon.stopped"})
        self.assertTrue(record["prev"])


if __name__ == "__main__":
    unittest.main()
