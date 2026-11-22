"""M15: property/differential 参考原型必须持续可运行。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / "app" / "prototypes" / "property_test"


def test_property_prototype_suite() -> None:
    assert PROTO.is_dir(), PROTO
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "test_property_test.py"],
        cwd=PROTO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Ran 4 tests" in completed.stderr
