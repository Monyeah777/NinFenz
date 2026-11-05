"""标注 sidecar v0（core/label_sidecar.py + nf label write/read/list）判据。

判据重点：**永远不会假装已嵌入**（embedded 恒 false）、**对象变了就判过期**（绑定摘要）、
以及写盘原子（半截旁车会让读者读到假声明）。这三条是 sidecar 回退能成立的底线。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import label_ir  # noqa: E402
from core import label_sidecar as ls  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"


def _fixture(tmp: str, body: bytes = b"\x89PNG demo") -> str:
    obj = str(Path(tmp) / "poster.png")
    Path(obj).write_bytes(body)
    return obj


def _ir(obj: str) -> dict:
    return label_ir.build(obj, ls.object_digest(obj), items=[
        {"face": "explicit", "kind": "text", "where": "start", "value": "AI 生成"},
        {"face": "implicit", "kind": "metadata", "key": "AIGC", "value": "1"},
    ])


class TestWriteRead(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nf_side_t_")
        self.addCleanup(self.tmp.cleanup)
        self.obj = _fixture(self.tmp.name)

    def test_round_trip_ok_and_never_embedded(self):
        dest, info = ls.write(self.obj, _ir(self.obj))
        self.assertFalse(info["embedded"], "sidecar 不是嵌入：embedded 必须恒 false")
        self.assertTrue(dest.endswith(ls.SUFFIX))
        res = ls.read(self.obj)
        self.assertEqual("ok", res["verdict"], res["issues"])
        self.assertFalse(res["embedded"])
        self.assertEqual("GB 45438-2025", res["label"]["standard"])

    def test_sidecar_binds_object_digest(self):
        ls.write(self.obj, _ir(self.obj))
        doc = json.loads(Path(ls.sidecar_path(self.obj)).read_text(encoding="utf-8"))
        self.assertEqual(ls.object_digest(self.obj), doc["object"]["digest"])
        self.assertFalse(doc["embedded"])

    def test_changed_object_is_stale(self):
        ls.write(self.obj, _ir(self.obj))
        Path(self.obj).write_bytes(b"\x89PNG demo-changed")
        res = ls.read(self.obj)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("对象已被改动", " ".join(res["issues"]))

    def test_missing_sidecar_is_invalid_with_guidance(self):
        res = ls.read(self.obj)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("nf label write", " ".join(res["issues"]))

    def test_missing_object_is_invalid(self):
        Path(self.obj).unlink()
        res = ls.read(self.obj)
        self.assertEqual("invalid", res["verdict"])

    def test_ir_digest_mismatch_is_rejected(self):
        other = str(Path(self.tmp.name) / "other.png")
        Path(other).write_bytes(b"other")
        with self.assertRaises(ValueError) as ctx:
            ls.write(self.obj, _ir(other))
        self.assertIn("摘要", str(ctx.exception))

    def test_invalid_ir_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            ls.write(self.obj, {"schema": "nope"})
        self.assertIn("IR 不合法", str(ctx.exception))

    def test_bad_sidecar_schema_is_invalid(self):
        ls.write(self.obj, _ir(self.obj))
        p = Path(ls.sidecar_path(self.obj))
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["schema"] = "nf-label-sidecar/9"
        p.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual("invalid", ls.read(self.obj)["verdict"])

    def test_custom_out_path(self):
        out = str(Path(self.tmp.name) / "custom.json")
        dest, _info = ls.write(self.obj, _ir(self.obj), out=out)
        self.assertEqual(out, dest)
        self.assertEqual("ok", ls.read(self.obj, path=out)["verdict"])


class TestDiscover(unittest.TestCase):
    def test_discover_finds_sidecars_only(self):
        with tempfile.TemporaryDirectory(prefix="nf_side_d_") as tmp:
            obj = _fixture(tmp)
            ls.write(obj, _ir(obj))
            rows = ls.discover(tmp)
            self.assertEqual(1, len(rows))
            sidecar, target, embedded = rows[0]
            self.assertTrue(sidecar.endswith(ls.SUFFIX))
            self.assertEqual("poster.png", target)
            self.assertFalse(embedded)


class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "label", *args], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")

    def test_write_then_read_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="nf_side_c_") as tmp:
            obj = _fixture(tmp)
            ir = _ir(obj)
            ir_path = Path(tmp, "ir.json")
            ir_path.write_text(json.dumps(ir, ensure_ascii=False), encoding="utf-8")
            proc = self._run("write", "--object", obj, "--ir", str(ir_path), "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-400:])
            doc = json.loads(proc.stdout)
            self.assertFalse(doc["embedded"])
            proc = self._run("read", obj, "--json")
            self.assertEqual(0, proc.returncode)
            self.assertEqual("ok", json.loads(proc.stdout)["verdict"])

    def test_read_stale_exits_1(self):
        with tempfile.TemporaryDirectory(prefix="nf_side_c2_") as tmp:
            obj = _fixture(tmp)
            ir_path = Path(tmp, "ir.json")
            ir_path.write_text(json.dumps(_ir(obj), ensure_ascii=False), encoding="utf-8")
            self._run("write", "--object", obj, "--ir", str(ir_path))
            Path(obj).write_bytes(b"tampered")
            proc = self._run("read", obj, "--json")
            self.assertEqual(1, proc.returncode)
            self.assertEqual("invalid", json.loads(proc.stdout)["verdict"])

    def test_list_is_read_only_and_parseable(self):
        proc = self._run("list", "--json")
        self.assertEqual(0, proc.returncode)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["count"], len(doc["rows"]))


if __name__ == "__main__":
    unittest.main()
