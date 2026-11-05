"""CCOS 一条链复现单测（cc_check → cc_attest → cc_verify → cc_replay）。

判据 = **摘要逐个流下去**：同一对象字节在四环里算出的摘要必须完全相同。只断言「四步都
返回 0」是不够的——四个命令各自成功而链条换了字节，仍然不是同一条链。
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "desktop" / "src"))


def _load_script():
    script = _REPO / "scripts" / "ccos_chain.py"
    spec = importlib.util.spec_from_file_location("nf_ccos_chain", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_chain_t_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "doc.md").write_text("# 文档\n\n正文一行。\n", encoding="utf-8")
        self.chain = _load_script()

    def test_chain_ok_and_digests_flow(self):
        res = self.chain.run(str(self.root), "doc.md")
        self.assertTrue(res["ok"], res)
        self.assertTrue(res["digests_agree"])
        self.assertEqual(len(set(res["digests"].values())), 1)
        self.assertEqual([link["link"] for link in res["links"]],
                         ["cc_check", "cc_attest", "cc_verify", "cc_replay"])

    def test_chain_marks_missing_link(self):
        """缺环必须如实标注：本仓无 labeling 子系统，链上不许假装有 cc_label。"""
        res = self.chain.run(str(self.root), "doc.md")
        self.assertIn("cc_label", res["missing"])

    def test_chain_breaks_on_empty_object(self):
        """空对象：体检环节就该判否，链条整体不成立（不抛异常，给的是判定）。"""
        (self.root / "empty.md").write_text("", encoding="utf-8")
        res = self.chain.run(str(self.root), "empty.md")
        self.assertFalse(res["ok"])
        self.assertEqual(res["links"][0]["verdict"], "invalid")

    def test_chain_missing_object_raises(self):
        with self.assertRaises(ValueError):
            self.chain.run(str(self.root), "nope.md")

    def test_chain_with_hmac(self):
        key = b"0123456789abcdef0123456789abcdef"
        res = self.chain.run(str(self.root), "doc.md", key=key)
        self.assertTrue(res["ok"], res)
        attest_link = [link for link in res["links"] if link["link"] == "cc_attest"][0]
        self.assertIn("hmac-sha256", attest_link["detail"])

    def test_missing_rings_closed_to_known_set(self):
        """缺环是挂账不是默认：链上 missing 只允许 cc_label 一项。

        新增缺环 = 新增未实装承诺，必须走裁决并同时改本用例与 docs/ccos/abi-v0.md；
        悄悄出现第二个缺环即红（防「链条短一截但没人发现」）。
        """
        res = self.chain.run(str(self.root), "doc.md")
        self.assertEqual(res["missing"], ["cc_label"])
        self.assertEqual(list(self.chain.MISSING), ["cc_label"])

    def test_chain_cli_json(self):
        import subprocess
        proc = subprocess.run([sys.executable, str(_REPO / "scripts" / "ccos_chain.py"),
                               "--root", str(self.root), "--target", "doc.md", "--json"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        doc = json.loads(proc.stdout)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["schema"], "nf-ccos-chain/1")


if __name__ == "__main__":
    unittest.main()
