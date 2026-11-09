"""自省层判据：发布结论必须绑定「产出它的验证器摘要」。

依据（第 96 轮）：发布结论只绑定 HEAD，不绑定「谁判的」。本判据断言结果件里的验证器摘要
等于当前重算值——**判定面脚本改了而没重跑，就是红**。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import self_audit_probe as sap  # noqa: E402
from core import verifier_version as vv  # noqa: E402


class VerifierVersionTest(unittest.TestCase):
    def test_digest_is_deterministic_and_covers_judge_files(self):
        first = vv.digest(ROOT)
        second = vv.digest(ROOT)
        self.assertEqual(first, second, "同一棵树两次摘要必须相同")
        self.assertEqual("nf-verifier-version/1", first["schema"])
        self.assertEqual(len(vv.JUDGE_FILES), first["files"])
        self.assertEqual(64, len(first["verifier_digest"]))

    def test_every_judge_file_exists(self):
        for rel in vv.JUDGE_FILES:
            self.assertTrue((ROOT / rel).is_file(), "判定面脚本不存在：" + rel)

    def test_committed_self_audit_is_fresh(self):
        """结果件里的验证器摘要必须等于当前重算（工具变了没重跑即红）。"""
        path = ROOT / sap.OUT_REL
        self.assertTrue(path.is_file(), "缺结果件：先跑 scripts/self_audit_probe.py --write")
        committed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(sap.build(), committed, "验证器摘要已陈旧，重跑 --write")

    def test_digest_changes_when_a_judge_file_changes(self):
        """变异测试：临时改一个判定面脚本的字节，摘要必须变。"""
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for rel in vv.JUDGE_FILES:
                dst = Path(tmp) / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / rel, dst)
            before = vv.digest(tmp)["verifier_digest"]
            victim = Path(tmp) / vv.JUDGE_FILES[0]
            victim.write_text(victim.read_text(encoding="utf-8") + "# x" + chr(10),
                              encoding="utf-8")
            after = vv.digest(tmp)["verifier_digest"]
        self.assertNotEqual(before, after, "改了判定面脚本而摘要不变——自省判据失效")


if __name__ == "__main__":
    unittest.main()
