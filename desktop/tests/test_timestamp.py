#!/usr/bin/env python3
"""RFC 3161 timestamp query, token verification, and distributable record tests."""
from __future__ import annotations

import contextlib
import http.server
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import time_stamp  # noqa: E402
from core import timestamp  # noqa: E402

OPENSSL = shutil.which("openssl")
NEED = unittest.skipUnless(OPENSSL, "openssl unavailable; RFC 3161 live path skipped")


def _win(path: Path) -> str:
    return str(path).replace("\\", "/")


def _openssl(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [OPENSSL, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        stdin=subprocess.DEVNULL,
    )


def _make_tsa(tmp: Path) -> tuple[Path, Path]:
    (tmp / "tsa.cnf").write_text(
        "[ req ]\n"
        "distinguished_name = dn\n"
        "prompt = no\n"
        "[ dn ]\n"
        "CN = NF Test TSA CA\n"
        "O = NF Test\n"
        "[ tsa ]\n"
        "default_tsa = tsa_config\n"
        "[ tsa_config ]\n"
        f"serial = {_win(tmp)}/tsaserial\n"
        "crypto_device = builtin\n"
        f"signer_cert = {_win(tmp)}/tsa.crt\n"
        f"certs = {_win(tmp)}/ca.crt\n"
        f"signer_key = {_win(tmp)}/tsa.key\n"
        "signer_digest = sha256\n"
        "default_policy = 1.2.3.4.1\n"
        "other_policies = 1.2.3.4.2\n"
        "digests = sha256, sha384, sha512\n"
        "accuracy = secs:1\n"
        "ordering = yes\n"
        "tsa_name = yes\n"
        "ess_cert_id_chain = no\n"
        "ess_cert_id_alg = sha256\n",
        encoding="utf-8",
    )
    (tmp / "tsa.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,nonRepudiation\n"
        "extendedKeyUsage=critical,timeStamping\n",
        encoding="utf-8",
    )
    _openssl(
        "req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(tmp / "ca.key"), "-out", str(tmp / "ca.crt"),
        "-days", "3650", "-config", str(tmp / "tsa.cnf"),
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign",
    )
    _openssl(
        "req", "-new", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(tmp / "tsa.key"), "-out", str(tmp / "tsa.csr"),
        "-config", str(tmp / "tsa.cnf"),
    )
    _openssl(
        "x509", "-req", "-in", str(tmp / "tsa.csr"),
        "-CA", str(tmp / "ca.crt"), "-CAkey", str(tmp / "ca.key"),
        "-CAcreateserial", "-out", str(tmp / "tsa.crt"),
        "-days", "3650", "-extfile", str(tmp / "tsa.ext"),
    )
    (tmp / "tsaserial").write_text("01", encoding="utf-8")
    return tmp / "ca.crt", tmp / "tsa.cnf"


def _issue(tmp: Path, data: Path) -> tuple[Path, Path, Path]:
    ca, config = _make_tsa(tmp)
    query = tmp / "query.tsq"
    result = timestamp.make_query(str(data), out=str(query))
    if not result.ok:
        raise AssertionError(result.issues)
    token = tmp / "reply.tsr"
    proc = _openssl("ts", "-reply", "-config", str(config), "-queryfile", str(query),
                    "-out", str(token))
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + proc.stderr)
    return query, token, ca


@NEED
class LocalTsaTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="nf_rfc3161_")
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.subject = self.tmp / "subject.bin"
        self.subject.write_bytes(b"ninfenz-rfc3161-subject")

    def test_full_chain_verifies_offline_and_records_trusted_time(self):
        query, token, ca = _issue(self.tmp, self.subject)
        result = timestamp.verify(str(self.subject), str(query), str(token), str(ca))
        self.assertTrue(result.ok, result.issues)
        self.assertEqual("tsa", result.verdict)
        self.assertRegex(result.gen_time, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

        record_path = self.tmp / "record.json"
        record = timestamp.write_record(
            str(self.subject), str(query), str(token), str(ca), out=str(record_path)
        )
        self.assertEqual(timestamp.SCHEMA, record["schema"])
        self.assertEqual(result.gen_time, record["tsa_result"]["gen_time"])
        self.assertEqual("sha256", record["tsa_result"]["hash_algorithm"])
        self.assertTrue(record["tsa_result"]["policy_oid"])
        self.assertTrue(record["tsa_result"]["nonce"])
        self.assertEqual(64, len(record["token"]["sha256"]))
        self.assertTrue(record["token"]["der_base64"])
        self.assertEqual([], timestamp.verify_record(
            str(self.subject), record, str(ca)
        ).issues)

    def test_wrong_anchor_and_missing_anchor_fail_closed(self):
        query, token, ca = _issue(self.tmp, self.subject)
        other = self.tmp / "other-ca.pem"
        other.write_text("not a certificate\n", encoding="utf-8")
        wrong = timestamp.verify(str(self.subject), str(query), str(token), str(other))
        self.assertFalse(wrong.ok)
        self.assertTrue(any("修复指引" in item for item in wrong.issues))
        missing = timestamp.verify(str(self.subject), str(query), str(token), "")
        self.assertFalse(missing.ok)
        self.assertTrue(any("信任锚" in item for item in missing.issues))

    def test_token_for_other_subject_is_rejected(self):
        query, token, ca = _issue(self.tmp, self.subject)
        other = self.tmp / "other.bin"
        other.write_bytes(b"different subject")
        result = timestamp.verify(str(other), str(query), str(token), str(ca))
        self.assertFalse(result.ok)
        self.assertTrue(any("绑定" in item or "校验不过" in item for item in result.issues))

    def test_tampered_token_and_record_are_rejected(self):
        query, token, ca = _issue(self.tmp, self.subject)
        tampered = self.tmp / "tampered.tsr"
        raw = bytearray(token.read_bytes())
        raw[-1] ^= 0x01
        tampered.write_bytes(raw)
        result = timestamp.verify(str(self.subject), str(query), str(tampered), str(ca))
        self.assertFalse(result.ok)

        record = timestamp.record_doc(
            str(self.subject), str(query), str(token), str(ca)
        )
        record["subject"]["sha256"] = "0" * 64
        checked = timestamp.verify_record(str(self.subject), record, str(ca))
        self.assertTrue(any("subject" in item for item in checked.issues), checked.issues)

        malformed = dict(record)
        malformed.pop("trust_anchor")
        checked = timestamp.verify_record(str(self.subject), malformed, str(ca))
        self.assertTrue(any("trust_anchor" in item for item in checked.issues), checked.issues)

        replay = timestamp.record_doc(
            str(self.subject), str(query), str(token), str(ca)
        )
        replay["tsa_result"]["nonce"] = "0x00"
        checked = timestamp.verify_record(str(self.subject), replay, str(ca))
        self.assertTrue(any("nonce" in item for item in checked.issues), checked.issues)

    def test_submit_rejects_non_http_and_missing_query(self):
        result = timestamp.submit(str(self.tmp / "missing.tsq"), "file:///tmp/tsa")
        self.assertFalse(result.ok)
        self.assertTrue(any("http" in item for item in result.issues))
        result = timestamp.submit(
            str(self.tmp / "missing.tsq"), "http://tsa.example.invalid"
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("HTTPS" in item for item in result.issues))

    def test_cli_verify_emits_structured_result(self):
        query, token, ca = _issue(self.tmp, self.subject)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = time_stamp.main([
                "verify", "--subject", str(self.subject), "--query", str(query),
                "--token", str(token), "--ca-file", str(ca), "--json",
            ])
        self.assertEqual(0, code, out.getvalue())
        result = json.loads(out.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual("tsa", result["verdict"])

    def test_cli_create_uses_loopback_tsa_and_writes_record(self):
        ca, config = _make_tsa(self.tmp)
        tmp = self.tmp
        request_path = tmp / "http-query.tsq"

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # stdlib callback name is fixed by BaseHTTPRequestHandler
                size = int(self.headers.get("Content-Length", "0"))
                request_path.write_bytes(self.rfile.read(size))
                token_path = tmp / "http-reply.tsr"
                proc = _openssl(
                    "ts", "-reply", "-config", str(config),
                    "-queryfile", str(request_path), "-out", str(token_path),
                )
                if proc.returncode != 0:
                    self.send_error(500)
                    return
                payload = token_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/timestamp-reply")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format, *args):
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        record = self.tmp / "created.time.json"
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = time_stamp.main([
                    "create", "--subject", str(self.subject),
                    "--tsa-url", f"http://127.0.0.1:{server.server_port}/",
                    "--ca-file", str(ca), "--record-out", str(record), "--json",
                ])
        finally:
            server.shutdown()
            thread.join(timeout=5)
        self.assertEqual(0, code, out.getvalue())
        self.assertTrue(record.is_file())
        result = json.loads(out.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual("tsa", result["verdict"])


if __name__ == "__main__":
    unittest.main()
