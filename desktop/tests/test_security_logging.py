#!/usr/bin/env python3
"""ASVS V16 security-event logging and redaction regression tests."""
import io
import json
import logging
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import plog  # noqa: E402


class SecurityLoggingTest(unittest.TestCase):
    def _logger(self, stream):
        logger = logging.getLogger("nf.security.test")
        logger.handlers[:] = []
        logger.propagate = False
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(
            "%(asctime)sZ %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        logger.addHandler(handler)
        return logger

    def test_security_event_redacts_credentials_and_escapes_controls(self):
        stream = io.StringIO()
        logger = self._logger(stream)
        fake_token = "ghp_" + "abcdefghijklmnopqrstuvwxyz123456"
        plog.security_event(
            logger,
            "daemon.authorization_denied",
            outcome="denied",
            detail="line1\nline2",
            token=fake_token,
        )
        out = stream.getvalue()
        self.assertIn("[REDACTED]", out)
        self.assertNotIn(fake_token, out)
        self.assertEqual(1, len(out.strip().splitlines()))
        payload = json.loads(out.split(": ", 1)[1])
        self.assertEqual("daemon.authorization_denied", payload["event"])
        self.assertEqual("denied", payload["outcome"])
        self.assertEqual("line1\\nline2", payload["detail"])

    def test_sanitize_handles_unicode_line_boundaries(self):
        got = plog.sanitize("a\u2028b\u2029c\u0085d\x00e")
        self.assertNotIn("\u2028", got)
        self.assertNotIn("\u2029", got)
        self.assertNotIn("\u0085", got)
        self.assertNotIn("\x00", got)


if __name__ == "__main__":
    unittest.main()
