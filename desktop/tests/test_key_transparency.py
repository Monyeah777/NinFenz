"""密钥透明目录判据：能证「这一版自洽」，也能证「两份目录分叉」。

后者是钉根方案（nf-revocation-trust/1）的盲点：两个验证方看到不同密钥集时，
被骗的一方无法自证被喂了假目录。判据必须证明：
① 链与根可复算（改任何一处都红）；② 单键包含证明可离线验；
③ 分叉检测（同版本不同根 / 新链缺旧根）给出 witness；④ 合法追加不误报。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import key_transparency as kt  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))
K1 = {"org-a/key-1": "a" * 64, "org-b/key-1": "b" * 64}
K2 = dict(K1, **{"org-c/key-1": "c" * 64})


def _doc(keys=None, prev=None):
    return kt.build(keys or K1, prev=prev)


class BuildVerifyTest(unittest.TestCase):
    def test_build_is_deterministic(self):
        self.assertEqual(json.dumps(_doc(), sort_keys=True),
                         json.dumps(_doc(), sort_keys=True))

    def test_verify_ok(self):
        res = kt.verify(_doc())
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(1, res["version"])

    def test_empty_keys_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            kt.build({})
        self.assertIn("修复指引", str(ctx.exception))

    def test_bad_pubkey_length_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            kt.build({"k": "abc"})
        self.assertIn("64", str(ctx.exception))

    def test_tampered_keys_break_root(self):
        doc = _doc()
        doc["keys"]["org-b/key-1"] = "d" * 64
        res = kt.verify(doc)
        self.assertFalse(res["ok"])
        self.assertTrue(any("重算根" in i for i in res["issues"]), res["issues"])

    def test_tampered_log_breaks_chain(self):
        doc = _doc(_doc() and K2, prev=_doc())
        doc["log"][1]["prev"] = "0" * 64
        res = kt.verify(doc)
        self.assertFalse(res["ok"])
        self.assertTrue(any("链断" in i for i in res["issues"]), res["issues"])

    def test_version_must_match_log_length(self):
        doc = _doc()
        doc["version"] = 5
        self.assertFalse(kt.verify(doc)["ok"])


class InclusionTest(unittest.TestCase):
    def test_lookup_returns_verifiable_proof(self):
        doc = _doc(K2)
        bundle = kt.lookup(doc, "org-b/key-1")
        self.assertTrue(bundle["ok"], bundle["issues"])
        self.assertTrue(kt.verify_inclusion(bundle))

    def test_proof_fails_on_wrong_pubkey(self):
        bundle = kt.lookup(_doc(K2), "org-b/key-1")
        bundle["pub"] = "e" * 64
        self.assertFalse(kt.verify_inclusion(bundle))

    def test_unknown_key_is_rejected_with_guide(self):
        res = kt.lookup(_doc(), "no/such-key")
        self.assertFalse(res["ok"])
        self.assertIn("修复指引", res["issues"][0])


class ConsistencyAndSplitTest(unittest.TestCase):
    def test_append_is_consistent(self):
        d1 = _doc()
        d2 = _doc(K2, prev=d1)
        res = kt.consistency(d1, d2)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual("append", res["kind"])

    def test_same_doc_is_not_split(self):
        d1 = _doc()
        self.assertFalse(kt.split_witness(d1, d1)["split"])

    def test_same_version_different_root_is_split(self):
        d2 = _doc(K2, prev=_doc())
        fake = json.loads(json.dumps(d2))
        fake["keys"]["org-a/key-1"] = "f" * 64
        fake["root"] = kt._root(fake["keys"])
        fake["log"][-1] = {"seq": fake["version"], "root": fake["root"],
                           "prev": fake["log"][-2]["root"]}
        self.assertTrue(kt.verify(fake)["ok"], "伪造目录本身必须自洽（否则不算分叉攻击）")
        res = kt.split_witness(d2, fake)
        self.assertTrue(res["split"])
        self.assertEqual("split", res["detail"]["ab"]["kind"])
        self.assertIn("root_b", res["detail"]["ab"]["witness"])

    def test_fork_detected_when_history_rewritten(self):
        """分叉的严格定义：新版本更高，但第 old_version 条的根不是旧根（来自另一条链）。"""
        d1 = _doc()
        alt_v1 = _doc(K2)                          # 另一条独立链的第 1 版
        alt_v2 = kt.build(K2, prev=alt_v1)         # 该链的第 2 版
        self.assertNotEqual(d1["root"], alt_v1["root"])
        res = kt.consistency(d1, alt_v2)
        self.assertFalse(res["ok"])
        self.assertEqual("fork", res["kind"])
        self.assertIn("old_root", res["witness"])
        self.assertEqual(2, res["witness"]["new_version"])


class CliTest(unittest.TestCase):
    def test_build_verify_lookup_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            keys = tmp / "keys.json"
            keys.write_text(json.dumps(K1), encoding="utf-8")
            d1 = tmp / "d1.json"
            proc = subprocess.run([*NF, "evidence", "revocations", "trust", "kt-build",
                                   str(keys), "--out", str(d1), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            doc = json.loads(proc.stdout)
            self.assertEqual(1, doc["version"])
            verify = subprocess.run([*NF, "evidence", "revocations", "trust", "kt-verify",
                                    str(d1), "--json"],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=180)
            self.assertEqual(0, verify.returncode, verify.stderr[-300:])
            self.assertTrue(json.loads(verify.stdout)["ok"])
            lookup = subprocess.run([*NF, "evidence", "revocations", "trust", "kt-lookup",
                                    str(d1), "--id", "org-a/key-1", "--json"],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=180)
            self.assertEqual(0, lookup.returncode, lookup.stderr[-300:])
            self.assertTrue(json.loads(lookup.stdout)["inclusion_ok"])
            split = subprocess.run([*NF, "evidence", "revocations", "trust", "kt-split",
                                   "--a", str(d1), "--b", str(d1)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, split.returncode, split.stderr[-300:])


if __name__ == "__main__":
    unittest.main()
