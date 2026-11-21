"""WP-0.9: zero_slice 参考原型必须持续可运行。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / "app" / "prototypes" / "zero_slice"


def test_zero_slice_prototype_suite() -> None:
    assert PROTO.is_dir(), PROTO
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "test_zero_slice.py"],
        cwd=PROTO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Ran 14 tests" in completed.stderr
