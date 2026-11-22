"""M1: flash_fill 参考原型必须持续可运行。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / "app" / "prototypes" / "flash_fill"


def test_flash_fill_prototype_suite() -> None:
    assert PROTO.is_dir(), PROTO
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "test_flash_fill.py"],
        cwd=PROTO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Ran 9 tests" in completed.stderr
