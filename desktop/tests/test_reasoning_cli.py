"""CLI 接线冒烟：nf cockpit 的 --reasoning 只加 reasoning 块，不改变既有输出面。"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
PROMPT = "设计一个游戏的失败回滚与死亡重生机制"
FORBIDDEN_KEYS = {"reward", "q", "value", "score", "weights"}


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def run_cockpit(*extra):
    return subprocess.run(
        [
            PYTHON,
            "scripts/nf.py",
            "cockpit",
            "--prompt",
            PROMPT,
            "--max-turns",
            "8",
            "--json",
            *extra,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )


class CockpitCliReasoningTests(unittest.TestCase):
    def test_reasoning_flag_adds_session_summary(self):
        completed = run_cockpit("--reasoning")
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        payload = json.loads(completed.stdout)
        self.assertIn("reasoning", payload)
        self.assertEqual(payload["reasoning"]["schema"], "nf-reasoning-session/1")
        self.assertIn("reasoning", payload["run"])
        self.assertEqual(
            payload["run"]["reasoning"]["schema"], "nf-reasoning-session/1"
        )
        self.assertEqual(set(walk_keys(payload)) & FORBIDDEN_KEYS, set())
        self.assertIn("no_scoring", payload["reasoning"])

    def test_without_reasoning_flag_output_is_unchanged(self):
        completed = run_cockpit()
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        payload = json.loads(completed.stdout)
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("reasoning", payload["run"])

    def test_reasoning_mode_search_accepted(self):
        completed = run_cockpit("--reasoning", "--reasoning-mode", "search")
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["reasoning"]["mode"], "search")


if __name__ == "__main__":
    unittest.main(verbosity=2)
