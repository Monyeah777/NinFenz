"""桥接真实证据包判据（对应闭包台账 D-03）：闭环输入必须是真 nf evidence verify 输出。

之前闭环测试用的是**合成** cc 结果——那只能证明桥自己自洽，证明不了「跟真证据接得上」。
本测试真跑：pack（生成 .zip）→ verify --json（四词判定）→ commit_from_verify → obligation → apply。
另含篡改用例：把证据包改坏 → verify 判 invalid → 回灌 → 控制面 detect。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.cognition_workspace import bridge as br  # noqa: E402
from core.cognition_workspace import session as se  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))
CLAIM = {"schema": "nf-cog-claim/1", "claim": "abi-v0 文档可被证据包复验",
         "digest": "c" * 64}


def _pack_and_verify(tmp: Path) -> tuple[dict, Path]:
    """真跑：把仓内文档打成证据包并复验，返回 verify JSON。"""
    bundle = Path(tmp) / "ev.zip"
    pack = subprocess.run([*NF, "evidence", "pack", "docs/ccos/abi-v0.md",
                           "--out", str(bundle)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300, cwd=str(ROOT))
    if pack.returncode != 0:
        raise unittest.SkipTest("环境无法生成证据包：" + pack.stderr[-200:])
    verify = subprocess.run([*NF, "evidence", "verify", str(bundle), "--json"],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=300, cwd=str(ROOT))
    return json.loads(verify.stdout), bundle


class RealVerifyTest(unittest.TestCase):
    def test_pack_verify_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc, _bundle = _pack_and_verify(Path(tmp))
            self.assertEqual("ok", doc["verdict"], doc.get("issues"))

    def test_commit_from_real_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc, _bundle = _pack_and_verify(Path(tmp))
            bundle = se.begin("证据可过桥")
            commitment = br.commit_from_verify(bundle, CLAIM, doc)
            self.assertEqual("ok", commitment["cc_verdict"])
            self.assertEqual(doc["head"], br.cc_result_from_verify(doc)["subject"])
            res = br.verify_commitment(commitment, bundle, CLAIM,
                                       br.cc_result_from_verify(doc))
            self.assertTrue(res["ok"], res["issues"])

    def test_tampered_bundle_produces_obligation(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc, bundle_path = _pack_and_verify(Path(tmp))
            raw = bytearray(bundle_path.read_bytes())
            raw[-8:] = b"XXXXXXXX"          # 改包尾 → 复验必红
            bundle_path.write_bytes(bytes(raw))
            verify = subprocess.run([*NF, "evidence", "verify", str(bundle_path),
                                     "--json"],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=300, cwd=str(ROOT))
            bad = json.loads(verify.stdout)
            # 真 CLI 对「包读不开」给的是 error 对象；桥必须把它当 invalid 而不是崩
            if "verdict" not in bad:
                bad = {"verdict": "invalid", "issues": [bad.get("error", "")]}
            self.assertNotEqual("ok", bad["verdict"], "篡改后的证据包不该判 ok")
            commit_bundle = se.begin("证据被改过怎么办")
            commitment = br.commit_from_verify(commit_bundle, CLAIM, bad)
            ob = br.obligation_from_verify(commitment, bad)
            self.assertTrue(ob["failed"], "篡改必须有回灌项")
            after = br.apply_obligation(commit_bundle, ob)
            self.assertEqual(1, len(after["control"]["records"]))
            self.assertEqual("detect", after["control"]["records"][0]["op"])
            self.assertEqual(commit_bundle["state"]["digest"], after["state"]["digest"])

    def test_unknown_verdict_word_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            br.cc_result_from_verify({"verdict": "maybe-ok"})
        self.assertIn("四词判定", str(ctx.exception))

    def test_missing_head_uses_root_as_subject(self):
        doc = {"verdict": "ok", "root": "d" * 64, "level": "digest_only"}
        self.assertEqual("d" * 64, br.cc_result_from_verify(doc)["subject"])


if __name__ == "__main__":
    unittest.main()
