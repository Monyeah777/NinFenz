"""DOCX / OFD / Markdown 写入 → 体检 的端到端测试（CLI 路径）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core.labeling import metadata, sm


class TestDocFormats(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.keys = sm.sm2_keygen()
        self.meta = os.path.join(self.td, "m.json")
        with open(self.meta, "w", encoding="utf-8") as f:
            json.dump({"Label": 1, "ContentProducer": "1" * 27,
                       "ProduceID": "NF-DOC-1"}, f)

    def _run(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nf_labeling.py"), *args],
                              cwd=ROOT, capture_output=True, text=True)

    def _sign_check(self, name, maker):
        p = os.path.join(self.td, name)
        maker(p)
        r = self._run("sign", p, "--meta", self.meta,
                      "--priv", self.keys["private"])
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["verdict"], "PASS", rep)
        return rep

    def test_docx(self):
        rep = self._sign_check("a.docx", metadata.make_docx)
        self.assertEqual(rep["meta_found_at"], "docx.custom")

    def test_ofd(self):
        rep = self._sign_check("a.ofd", metadata.make_ofd)
        self.assertEqual(rep["meta_found_at"], "ofd.CustomData")

    def test_markdown(self):
        rep = self._sign_check(
            "a.md", lambda p: open(p, "w", encoding="utf-8").write("# 标题\n\n正文\n"))
        self.assertEqual(rep["meta_found_at"], "markdown.AIGC")
        self.assertEqual(rep["sections"]["A"]["status"], "PASS")

    def test_docx_body_change_fails_binding(self):
        p = os.path.join(self.td, "b.docx")
        metadata.make_docx(p)
        self._run("sign", p, "--meta", self.meta, "--priv", self.keys["private"])
        data = open(p, "rb").read()
        # 直接改 zip 里的 word/document.xml（用 zipfile 重写）
        import zipfile
        entries = []
        with zipfile.ZipFile(p) as zf:
            for n in zf.namelist():
                b = zf.read(n)
                if n == "word/document.xml":
                    b = b.replace(b"demo", b"DEMO")
                entries.append((n, b))
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
            for n, b in entries:
                zf.writestr(n, b)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["sections"]["C"]["status"], "FAIL")

    def test_markdown_plain_text_still_scanned(self):
        p = os.path.join(self.td, "c.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write("本内容由 AI 生成。\n")
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["sections"]["A"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
