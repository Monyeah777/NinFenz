"""CLI 侧 golden 向量：与 Desktop/Android 共享同一请求/响应。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "fixtures/golden/core-vectors.json"
BIN = ROOT / "core/target/release/nf-app-core.exe"


def test_cli_matches_shared_core_vectors(tmp_path):
    if not BIN.is_file():
        import pytest
        pytest.skip("core CLI 未构建")
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    for vector in data["vectors"]:
        req = tmp_path / (vector["id"] + ".json")
        req.write_text(json.dumps(vector["in"], ensure_ascii=False), encoding="utf-8")
        out = subprocess.run([str(BIN), vector["op"], "--in", str(req)], capture_output=True, text=True, check=False)
        assert out.returncode == 0, out.stderr
        env = json.loads(out.stdout)
        assert env["ok"] is True
        for key, want in vector["want"].items():
            assert env["result"][key] == want
