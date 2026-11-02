"""xmind / posm / posf / UOF 写入 → 体检 端到端测试（CLI）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core.labeling import metadata, sm


class TestZipFormats(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.keys = sm.sm2_keygen()
        self.meta = os.path.join(self.td, "m.json")
        with open(self.meta, "w", encoding="utf-8") as f:
            json.dump({"Label": 1, "ContentProducer": "1" * 27,
                       "ProduceID": "NF-ZIP-1"}, f)

    def _run(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nf_labeling.py"), *args],
                              cwd=ROOT, capture_output=True, text=True)

    def _sign_check(self, kind, maker):
        p = os.path.join(self.td, "a." + kind)
        maker(p)
        r = self._run("sign", p, "--meta", self.meta,
                      "--priv", self.keys["private"])
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["verdict"], "PASS", rep)
        return rep

    def test_xmind(self):
        rep = self._sign_check("xmind", metadata.make_xmind)
        self.assertEqual(rep["meta_found_at"], "xmind.AIGC")

    def test_posm(self):
        rep = self._sign_check("posm", metadata.make_posm)
        self.assertEqual(rep["meta_found_at"], "posm.AIGC")

    def test_posf(self):
        rep = self._sign_check("posf", metadata.make_posf)
        self.assertEqual(rep["meta_found_at"], "posf.AIGC")

    def test_uof(self):
        rep = self._sign_check("uof", metadata.make_uof)
        self.assertEqual(rep["meta_found_at"], "uof.AIGC")

    def test_xmind_body_change_fails_binding(self):
        import zipfile
        p = os.path.join(self.td, "b.xmind")
        metadata.make_xmind(p)
        self._run("sign", p, "--meta", self.meta, "--priv", self.keys["private"])
        entries = []
        with zipfile.ZipFile(p) as zf:
            for n in zf.namelist():
                b = zf.read(n)
                if n == "content.json":
                    b = b.replace(b'"sheets": []', b'"sheets": [1]')
                entries.append((n, b))
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
            for n, b in entries:
                zf.writestr(n, b)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["sections"]["C"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
