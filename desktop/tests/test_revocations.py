"""吊销分发件 v0（core/revocations.py + nf evidence revocations CLI）判据。

判据重点：签名在就必须过（缺密钥不降级）、序号链防回滚/防分叉、合并「一份不过则整次失败」。
为什么这么严：吊销面一旦被回滚，已吊销的错签会重新「生效」——这是比缺表更危险的状态。
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "nf.py"
KEY = b"k" * 32


def _rv():
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    spec = importlib.util.spec_from_file_location(
        "nf_revocations", ROOT / "desktop" / "src" / "core" / "revocations.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(digest="a" * 64, reason="错签"):
    return {"digest": digest, "reason": reason}


class TestSignVerify(unittest.TestCase):
    def setUp(self):
        self.rv = _rv()
        self.t1 = self.rv.make_table([_row()])
        self.f1 = self.rv.sign(self.t1, KEY, issuer="acme", seq=1)

    def test_roundtrip_ok(self):
        res = self.rv.verify(self.f1, key=KEY)
        self.assertEqual("ok", res["verdict"])
        self.assertTrue(res["signed"])
        self.assertEqual(1, res["seq"])
        self.assertEqual(1, res["count"])

    def test_digest_is_deterministic(self):
        self.assertEqual(self.rv.digest(self.f1), self.rv.digest(self.f1))

    def test_tampered_table_fails(self):
        bad = dict(self.f1)
        bad["table"] = self.rv.make_table([_row("b" * 64)])
        res = self.rv.verify(bad, key=KEY)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("签名不匹配", " ".join(res["issues"]))

    def test_wrong_key_fails(self):
        self.assertEqual("invalid", self.rv.verify(self.f1, key=b"w" * 32)["verdict"])

    def test_missing_key_does_not_downgrade(self):
        res = self.rv.verify(self.f1)
        self.assertEqual("invalid", res["verdict"], "签名在就必须给密钥，缺密钥不降级")
        self.assertIn("缺密钥", " ".join(res["issues"]))

    def test_unsigned_table_warns(self):
        res = self.rv.verify(self.t1)
        self.assertEqual("ok", res["verdict"], "裸表形状可判")
        self.assertTrue(res["warnings"])
        self.assertFalse(res["signed"])

    def test_bad_seq_fails(self):
        bad = dict(self.f1)
        bad["seq"] = -1
        self.assertEqual("invalid", self.rv.verify(bad, key=KEY)["verdict"])

    def test_unknown_schema_fails(self):
        self.assertEqual("invalid", self.rv.verify({"schema": "x"})["verdict"])

    def test_table_missing_fails(self):
        doc = {"schema": "nf-revocation-feed/1"}
        self.assertEqual("invalid", self.rv.verify(doc)["verdict"])


class TestChain(unittest.TestCase):
    def setUp(self):
        self.rv = _rv()
        self.f1 = self.rv.sign(self.rv.make_table([_row()]), KEY, seq=1)
        t2 = self.rv.make_table([_row(), _row("b" * 64)])
        self.f2 = self.rv.sign(t2, KEY, seq=2, prev=self.f1)

    def test_chain_ok(self):
        self.assertEqual("ok", self.rv.verify(self.f2, key=KEY, prev=self.f1)["verdict"])

    def test_rollback_detected(self):
        res = self.rv.verify(self.f1, key=KEY, prev=self.f2)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("序号不连续", " ".join(res["issues"]))

    def test_fork_detected(self):
        other = self.rv.sign(self.rv.make_table([_row("c" * 64)]), KEY, seq=2)
        res = self.rv.verify(other, key=KEY, prev=self.f1)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("前序摘要", " ".join(res["issues"]))


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.rv = _rv()
        self.f1 = self.rv.sign(self.rv.make_table([_row()]), KEY, seq=1)
        t2 = self.rv.make_table([_row(), _row("b" * 64)])
        self.f2 = self.rv.sign(t2, KEY, seq=2, prev=self.f1)

    def test_merge_union_sorted(self):
        res = self.rv.merge([self.f2, self.f1], key=KEY)
        self.assertTrue(res["ok"])
        self.assertEqual(2, res["count"])
        self.assertEqual(2, res["feeds"])
        digests = [r["digest"] for r in res["table"]["revoked"]]
        self.assertEqual(sorted(digests), digests, "合并结果必须稳定排序")

    def test_merge_forged_fails_whole(self):
        bad = dict(self.f2)
        bad["table"] = self.rv.make_table([_row("z" * 64)])
        self.assertFalse(self.rv.merge([self.f1, bad], key=KEY)["ok"],
                         "一份不过则整次失败")

    def test_merge_without_key_fails(self):
        self.assertFalse(self.rv.merge([self.f1], key=None)["ok"])


class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "evidence", "revocations", *args],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def _fixtures(self, td):
        key = Path(td, "k.bin")
        key.write_bytes(KEY)
        t1 = Path(td, "t1.json")
        t1.write_text(json.dumps({"schema": "nf-revocation/1", "revoked": [_row()]}),
                      encoding="utf-8")
        return key, t1

    def test_sign_verify_merge_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            key, t1 = self._fixtures(td)
            f1 = Path(td, "f1.json")
            proc = self._run("sign", "--table", str(t1), "--key-file", str(key),
                             "--seq", "1", "--out", str(f1), "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            proc = self._run("verify", str(f1), "--key-file", str(key), "--json")
            self.assertEqual(0, proc.returncode)
            self.assertEqual("ok", json.loads(proc.stdout)["verdict"])
            merged = Path(td, "m.json")
            proc = self._run("merge", str(f1), "--key-file", str(key), "--out", str(merged),
                             "--json")
            self.assertEqual(0, proc.returncode)
            self.assertEqual(1, json.loads(merged.read_text(encoding="utf-8"))["count"])

    def test_verify_without_key_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            key, t1 = self._fixtures(td)
            f1 = Path(td, "f1.json")
            self._run("sign", "--table", str(t1), "--key-file", str(key), "--out", str(f1))
            proc = self._run("verify", str(f1), "--json")
            self.assertEqual(1, proc.returncode, "缺密钥必须 invalid，不降级")


if __name__ == "__main__":
    unittest.main()
