#!/usr/bin/env python3
""".NET (C#) parity 判据（claim #21 的 .NET 半边）：独立 C# 实现对冻结向量复算六族。

边界：entity 族需完整 JSON Schema 引擎，显式 skipped；本件证明 Python↔.NET 逐字节一致。
需要 .NET SDK；缺 SDK 时整体跳过（不冒充已验）。
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"
PROJECT = ROOT / "scripts" / "trust_parity" / "csharp" / "TrustParity.csproj"
EXE = (ROOT / "scripts" / "trust_parity" / "csharp" / "bin" / "Release"
       / "net8.0" / "TrustParity.exe")


def _dotnet() -> str:
    candidates = [
        os.path.join(os.environ.get("USERPROFILE", ""), ".dotnet", "dotnet.exe"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".dotnet", "dotnet"),
        shutil.which("dotnet") or "",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            proc = subprocess.run([candidate, "--list-sdks"], capture_output=True,
                                  text=True, encoding="utf-8", timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return candidate
    return ""


DOTNET = _dotnet()
NEED = unittest.skipUnless(DOTNET, "环境无 .NET SDK：.NET parity 跳过（不冒充已验）")


@NEED
class DotnetParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([DOTNET, "build", str(PROJECT), "-c", "Release", "--nologo"],
                              capture_output=True, text=True, encoding="utf-8", timeout=600)
        if proc.returncode != 0:
            raise AssertionError(f".NET 构建失败：{proc.stdout[-1500:]}{proc.stderr[-800:]}")
        cls.vectors = json.loads(VECTORS.read_text(encoding="utf-8"))

    def _run(self, vectors_path):
        proc = subprocess.run([str(EXE), "--vectors", str(vectors_path)],
                              capture_output=True, text=True, encoding="utf-8", timeout=300)
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"C# 输出不是 JSON：{exc}；stdout={proc.stdout[:400]}") from exc
        return proc.returncode, report

    def test_parity_with_python_vectors(self):
        code, report = self._run(VECTORS)
        self.assertEqual(0, code, report.get("mismatches")[:3])
        self.assertTrue(report["ok"])
        self.assertEqual([], report["mismatches"])
        expected = {}
        for vec in self.vectors["vectors"]:
            if vec["family"] == "entity":
                continue
            expected[vec["family"]] = expected.get(vec["family"], 0) + 1
        self.assertEqual(expected, report["checked"])
        self.assertEqual(["entity"], report["skipped"])
        self.assertEqual(len(self.vectors["vectors"]), report["total"])

    def test_tampered_expectation_breaks_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vectors.json"
            doc = json.loads(VECTORS.read_text(encoding="utf-8"))
            for vec in doc["vectors"]:
                if vec["id"] == "LV-01":
                    vec["expected"]["exit_code"] = 99
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            code, report = self._run(path)
        self.assertEqual(1, code, report)
        self.assertIn("LV-01", [m["id"] for m in report["mismatches"]])

    def test_csharp_implementation_is_independent(self):
        source = (ROOT / "scripts/trust_parity/csharp/Program.cs").read_text(encoding="utf-8")
        for token in ("desktop/src", "core.trust", "python", "pytest"):
            self.assertNotIn(token, source, f"独立实现里出现了 {token!r}（不是独立复算）")


if __name__ == "__main__":
    unittest.main()
