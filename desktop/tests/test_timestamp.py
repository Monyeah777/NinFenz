"""RFC 3161 可信时间戳（G3 的可落地半边）判据：本地 TSA 全链路 + 篡改/错锚必拒。

判据不依赖外网：测试自己用 openssl 起一个**本地 TSA**（自签 CA + TSA 证书），签发 token 后
离线校验。缺 openssl 时整类跳过（不冒充已验）；外网 TSA 的连通性由人工/CI 另测。
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import evidence, timestamp  # noqa: E402

OPENSSL = shutil.which("openssl")
NEED = unittest.skipUnless(OPENSSL, "环境无 openssl：时间戳面跳过（不冒充已验）")


def _win(p: Path) -> str:
    """给 openssl 的路径：Windows 反斜杠转正斜杠（MSYS 下避免反斜杠被当转义）。"""
    return str(p).replace("\\", "/")


def _openssl(*args, cwd=None):
    return subprocess.run([OPENSSL, *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120,
                          stdin=subprocess.DEVNULL)


def _make_tsa(tmp: Path) -> tuple[Path, Path, Path]:
    """起一个本地 TSA → (ca.pem, tsa.cnf, serial)；返回后可直接 openssl ts -reply。"""
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
        encoding="utf-8")
    (tmp / "tsa.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,nonRepudiation\n"
        "extendedKeyUsage=critical,timeStamping\n", encoding="utf-8")
    _openssl("req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(tmp / "ca.key"), "-out", str(tmp / "ca.crt"), "-days", "3650",
             "-config", str(tmp / "tsa.cnf"),
             "-addext", "basicConstraints=critical,CA:TRUE",
             "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    _openssl("req", "-new", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(tmp / "tsa.key"), "-out", str(tmp / "tsa.csr"),
             "-config", str(tmp / "tsa.cnf"))
    _openssl("x509", "-req", "-in", str(tmp / "tsa.csr"), "-CA", str(tmp / "ca.crt"),
             "-CAkey", str(tmp / "ca.key"), "-CAcreateserial", "-out", str(tmp / "tsa.crt"),
             "-days", "3650", "-extfile", str(tmp / "tsa.ext"))
    (tmp / "tsaserial").write_text("01", encoding="utf-8")
    return tmp / "ca.crt", tmp / "tsa.cnf", tmp / "tsaserial"


def _issue(tmp: Path, data: Path) -> tuple[Path, Path, Path]:
    """数据 → (tsq, tsr, ca)；用本地 TSA 签。"""
    ca, cnf, _serial = _make_tsa(tmp)
    q = tmp / "q.tsq"
    _openssl("ts", "-query", "-data", str(data), "-sha256", "-cert", "-out", str(q))
    r = tmp / "r.tsr"
    _openssl("ts", "-reply", "-config", str(cnf), "-queryfile", str(q), "-out", str(r))
    return q, r, ca


@NEED
class LocalTsaTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="nf_ts_")
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.data = self.tmp / "data.bin"
        self.data.write_bytes(b"nf-timestamp-payload")

    def test_full_chain_verifies_offline(self):
        q, r, ca = _issue(self.tmp, self.data)
        self.assertGreater(q.stat().st_size, 0)
        self.assertGreater(r.stat().st_size, 0)
        res = timestamp.verify(str(r), str(q), ca_file=str(ca))
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual("ok", res["verdict"])
        self.assertRegex(res["gen_time"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_wrong_anchor_is_rejected(self):
        q, r, ca = _issue(self.tmp, self.data)
        other = self.tmp / "not-a-ca.pem"
        other.write_text("not a cert\n", encoding="utf-8")
        res = timestamp.verify(str(r), str(q), ca_file=str(other))
        self.assertFalse(res["ok"])
        self.assertTrue(any("修复指引" in i for i in res["issues"]), res["issues"])

    def test_missing_anchor_is_fail_closed(self):
        q, r, _ca = _issue(self.tmp, self.data)
        res = timestamp.verify(str(r), str(q), ca_file="")
        self.assertFalse(res["ok"])
        self.assertTrue(any("信任锚" in i for i in res["issues"]))

    def test_token_for_other_data_is_rejected(self):
        """token 绑定的是摘要：换一份数据（请求也要重做）就会对不上。"""
        q, r, ca = _issue(self.tmp, self.data)
        other = self.tmp / "other.bin"
        other.write_bytes(b"different payload")
        q2 = self.tmp / "q2.tsq"
        _openssl("ts", "-query", "-data", str(other), "-sha256", "-cert", "-out", str(q2))
        res = timestamp.verify(str(r), str(q2), ca_file=str(ca))
        self.assertFalse(res["ok"])


@NEED
class EvidenceTimeAnchorTest(unittest.TestCase):
    """证据复验用 TSA token 锚定「该字节在何时已存在」；摘要不符必须 invalid。"""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(prefix="nf_ts_ev_")
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        root = self.tmp / "repo"
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
        data, _info = evidence.build(str(root), ["docs/a.md"],
                                     created_at="2026-01-01T00:00:00Z")
        self.bundle = self.tmp / "b.zip"
        self.bundle.write_bytes(data)
        self.q, self.r, ca = _issue(self.tmp, self.bundle)
        self.ca = ca
        self.record, _ = timestamp.record(str(self.bundle), str(self.r), str(self.q),
                                         timestamp.subject_digest(data), str(ca),
                                         out=str(self.tmp / "record.json"))

    def test_verify_with_token_sets_time_proof_tsa(self):
        rec = dict(self.record)
        res = evidence.verify(str(self.bundle), time_record=rec, time_ca=str(self.ca))
        self.assertEqual("ok", res["verdict"], res["issues"])
        self.assertEqual("tsa", res["time_proof"])
        self.assertRegex(res["time_basis"], r"^\d{4}-\d{2}-\d{2}T")

    def test_token_on_other_bundle_is_invalid(self):
        other = self.tmp / "other.zip"
        other.write_bytes(self.bundle.read_bytes() + b"x")
        rec = dict(self.record)
        res = evidence.verify(str(other), time_record=rec, time_ca=str(self.ca))
        self.assertEqual("invalid", res["verdict"])
        self.assertTrue(any("时间锚与被证对象不符" in i for i in res["issues"]))

    def test_record_contains_expected_fields(self):
        doc = self.record
        self.assertEqual("nf-time-token/1", doc["schema"])
        self.assertEqual(timestamp.subject_digest(self.bundle.read_bytes()),
                         doc["subject"]["sha256"])
        self.assertEqual(64, len(doc["token"]["sha256"]))
        self.assertEqual(64, len(doc["ca"]["sha256"]))

    def test_no_token_means_clock_based_marking(self):
        res = evidence.verify(str(self.bundle))
        self.assertEqual("none", res["time_proof"])


if __name__ == "__main__":
    unittest.main()
