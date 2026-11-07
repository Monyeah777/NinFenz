"""证据判定向量集（results/ccos/evidence_verdict_vectors.json）判据。

向量集是**跨语言一致性的锚点**：第三方（Go/Rust/任何语言）只读这一份 JSON 就能自证实现对不对，
不需要读本仓代码。所以判据必须钉住四件事：

1. 每条向量的**期望判定**在本仓实现上真的成立；
2. **零依赖单文件验证器**给出同样的判定与退出码（双实现一致，第三方才有可比基线）；
3. 向量集**确定可复现**（--write 两次逐字节一致；--check 比对提交件）；
4. 载体不夹带机器相关信息（绝对路径/用户名），否则「可移植」是假的。
"""
import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import evidence  # noqa: E402

VECTORS_REL = "results/ccos/evidence_verdict_vectors.json"
STANDALONE = ROOT / "scripts" / "nf_verify.py"


def _doc():
    return json.loads((ROOT / VECTORS_REL).read_text(encoding="utf-8"))


class TestVectorIntegrity(unittest.TestCase):
    def test_schema_and_count(self):
        doc = _doc()
        self.assertEqual("nf-evidence-vectors/1", doc["schema"])
        self.assertEqual(doc["count"], len(doc["vectors"]))

    def test_ids_unique(self):
        ids = [v["id"] for v in _doc()["vectors"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_sha_matches_bytes(self):
        for v in _doc()["vectors"]:
            raw = base64.b64decode(v["bundle_b64"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), v["bundle_sha256"], v["id"])

    def test_no_machine_specific_paths(self):
        text = (ROOT / VECTORS_REL).read_text(encoding="utf-8")
        for needle in ("C:\\", "\\\\Users", "/home/", "AppData"):
            self.assertNotIn(needle, text, f"向量集夹带机器路径：{needle}")


class TestExpectedVerdicts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nf_vectors_t_")
        self.addCleanup(self.tmp.cleanup)

    def _materialize(self, vec):
        path = Path(self.tmp.name) / (vec["id"] + ".zip")
        path.write_bytes(base64.b64decode(vec["bundle_b64"]))
        return path

    def _core(self, vec):
        key = base64.b64decode(vec["key_b64"]) if vec.get("key_b64") else None
        try:
            return evidence.verify_any(str(self._materialize(vec)), key=key,
                                   revocations=vec.get("revocations"),
                                   at=vec.get("at", ""),
                                   anchor=vec.get("anchor"))
        except ValueError:
            return {"verdict": "usage_error", "issues": ["不是证据包"]}

    def _standalone(self, vec):
        path = self._materialize(vec)
        argv = [sys.executable, str(STANDALONE), "--evidence", str(path), "--json"]
        if vec.get("key_b64"):
            kf = Path(self.tmp.name) / (vec["id"] + ".key")
            kf.write_bytes(base64.b64decode(vec["key_b64"]))
            argv += ["--key-file", str(kf)]
        if vec.get("revocations") is not None:
            rf = Path(self.tmp.name) / (vec["id"] + ".rev.json")
            rf.write_text(json.dumps(vec["revocations"]), encoding="utf-8")
            argv += ["--revocations", str(rf)]
        if vec.get("at"):
            argv += ["--at", vec["at"]]
        if vec.get("anchor"):
            af = Path(self.tmp.name) / (vec["id"] + ".anchor.json")
            af.write_text(json.dumps(vec["anchor"]), encoding="utf-8")
            argv += ["--anchor", str(af)]
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        try:
            return json.loads(proc.stdout), proc.returncode
        except ValueError:
            return None, proc.returncode

    def test_core_matches_every_vector(self):
        for vec in _doc()["vectors"]:
            got = self._core(vec)
            want = vec["expected"]["verdict"]
            if vec.get("special") == "not_a_bundle":
                self.assertEqual("usage_error", got["verdict"], vec["id"])
            else:
                self.assertEqual(want, got["verdict"], f"{vec['id']}: {got['issues']}")

    def test_standalone_matches_every_vector(self):
        """零依赖验证器必须同判且退出码一致——它是第三方复验的现实基线。"""
        for vec in _doc()["vectors"]:
            doc, rc = self._standalone(vec)
            if vec.get("special") == "not_a_bundle":
                # 用法错（rc=4）本来就不产出判定 JSON：要求它给 verdict 才是错的口径
                self.assertEqual(vec["expected"]["exit_code"], rc, f"{vec['id']} exit code")
                self.assertIsNone(doc, "用法错不该伪造 verdict")
                continue
            self.assertIsNotNone(doc, f"{vec['id']}: 独立验证器没给可解析 JSON")
            self.assertEqual(vec["expected"]["verdict"], doc.get("verdict"),
                             f"{vec['id']} verdict")
            self.assertEqual(vec["expected"]["exit_code"], rc, f"{vec['id']} exit code")


class TestReproducible(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "nf_evidence_vectors", ROOT / "scripts" / "evidence_vectors.py")
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT / "scripts"))
        spec.loader.exec_module(mod)
        self.mod = mod

    def test_generation_is_deterministic(self):
        a = self.mod.render_vectors(self.mod.build_vectors())
        b = self.mod.render_vectors(self.mod.build_vectors())
        self.assertEqual(a, b)

    def test_committed_equals_live(self):
        issues, live = self.mod.check_vectors()
        self.assertEqual([], issues)
        self.assertEqual(live["count"], self.mod.build_vectors()["count"])


if __name__ == "__main__":
    unittest.main()
