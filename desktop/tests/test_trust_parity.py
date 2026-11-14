#!/usr/bin/env python3
"""跨语言 parity 判据（claim #21）：Node.js 独立实现对冻结向量逐字节复算。

范围与边界（如实）：
- 覆盖 canonical / domain / pae / merkle / process / level 六族（纯复算面）；
- entity 族需要完整 JSON Schema 引擎，**不在本独立实现范围**，显式列入 skipped；
- .NET 引擎线因本机无 SDK（BASELINE ENV-01）未实现；本件证明的是 Python ↔ Node.js parity，
  不冒充 Python ↔ .NET。
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"
SCRIPT = ROOT / "scripts" / "trust_parity" / "verify.mjs"
NODE = shutil.which("node")
NEED = unittest.skipUnless(NODE, "环境没有 node：跨语言 parity 跳过（不冒充已验）")


def _run(vectors_path):
    proc = subprocess.run([NODE, str(SCRIPT), "--vectors", str(vectors_path)],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"node 输出不是 JSON：{exc}；stdout={proc.stdout[:400]}") from exc
    return proc.returncode, report


@NEED
class NodeParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_all_pure_recompute_families_parity(self):
        code, report = _run(VECTORS)
        self.assertEqual(0, code, report.get("mismatches")[:3])
        self.assertTrue(report["ok"], report.get("mismatches")[:3])
        self.assertEqual([], report["mismatches"])
        expected_counts = {}
        for vec in self.vectors["vectors"]:
            if vec["family"] == "entity":
                continue
            expected_counts[vec["family"]] = expected_counts.get(vec["family"], 0) + 1
        self.assertEqual(expected_counts, report["checked"])
        self.assertEqual(["entity"], report["skipped"])
        self.assertEqual(len(self.vectors["vectors"]), report["total"])

    def test_tampered_expectation_breaks_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vectors.json"
            doc = json.loads(VECTORS.read_text(encoding="utf-8"))
            for vec in doc["vectors"]:
                if vec["id"] == "CV-01":
                    vec["expected"]["sha256"] = "0" * 64
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            code, report = _run(path)
            self.assertEqual(1, code, report)
            self.assertIn("CV-01", [m["id"] for m in report["mismatches"]])

    def test_node_implementation_is_independent(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for token in ("desktop/src", "core.trust", "python", "pytest"):
            self.assertNotIn(token, source, f"独立实现里出现了 {token!r}（不是独立复算）")


if __name__ == "__main__":
    unittest.main()
