"""Concurrent local verify runs must not share ignored build state."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import posix_shell as psh  # noqa: E402


BASH = psh.find_posix_shell()


def _guard_command(root: Path, body: str) -> list[str]:
    script = (
        "set -eu; "
        f"source {str(ROOT / 'scripts' / 'verify_guard.sh')!r}; "
        f"trap verify_guard_release EXIT INT TERM; "
        f"verify_guard_acquire {str(root)!r}; "
        + body
    )
    return [BASH, "-lc", script]


@unittest.skipUnless(BASH, "Git for Windows / POSIX bash unavailable")
class VerifyGuardTest(unittest.TestCase):
    def test_second_process_fails_clearly_after_bounded_wait(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nf-verify-guard-") as td:
            root = Path(td)
            first = subprocess.Popen(
                _guard_command(root, "sleep 4"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                lock_root = root / ".rivet" / "verify-locks"
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if lock_root.is_dir() and any(lock_root.iterdir()):
                        break
                    time.sleep(0.05)
                else:
                    self.fail("first process did not acquire the guard")

                env = dict(os.environ, NF_VERIFY_LOCK_WAIT="0")
                second = subprocess.run(
                    _guard_command(root, "printf 'unexpected\\n'"),
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20,
                )
                self.assertEqual(1, second.returncode, second.stdout + second.stderr)
                self.assertIn("另一个 verify.sh 正在此仓库运行", second.stderr)
                self.assertIn("NF_VERIFY_LOCK_WAIT", second.stderr)
                self.assertNotIn("unexpected", second.stdout)
            finally:
                first.terminate()
                first.communicate(timeout=10)

    def test_lock_is_released_for_next_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nf-verify-guard-") as td:
            root = Path(td)
            first = subprocess.run(
                _guard_command(root, "printf 'one\\n'"),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            second = subprocess.run(
                _guard_command(root, "printf 'two\\n'"),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            self.assertEqual("two\n", second.stdout)

    def test_verify_entrypoint_acquires_and_releases_guard(self) -> None:
        source = (ROOT / "verify.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/verify_guard.sh", source)
        self.assertIn("verify_guard_acquire", source)
        self.assertIn("verify_guard_release", source)
        acquire = source.index("verify_guard_acquire")
        early_trap = source.index("trap verify_guard_release", acquire)
        argument_parse = source.index("# ---- 命令行参数", acquire)
        self.assertLess(early_trap, argument_parse, "early exits must release the guard")


if __name__ == "__main__":
    unittest.main()

