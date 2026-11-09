"""包的可跑入口必须真能跑（第 160 轮）：把「声明」推进到「可执行验证」。

依据：第 144 轮给每个包加了 `runnable`，第 145 轮绑定了文档列——但**没有一条判据真的去跑它**。
本件逐条执行，断言：命令能起来、退出码属于「成功或用法提示」（0 / 2）、不超时、有输出。

口径说明：部分入口需要参数（如 `nf cog calibrate --pairs`），裸跑会返回 2（用法提示）；
这在 CLI 语义里是**正常的自我说明**，不是失败。判据因此允许 0/2，拒绝 1 与超时。
"""
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "protocol" / "method_packs"
NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))


def _runnable_commands() -> list:
    commands = []
    index = json.loads((PACKS / "index.json").read_text(encoding="utf-8"))
    for item in index["packs"]:
        doc = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
        for cmd in doc.get("runnable") or []:
            commands.append(str(cmd))
    return sorted(set(commands))


def _argv(command: str) -> list:
    parts = command.split()
    if parts[0] == "nf":
        return list(NF) + parts[1:]
    if parts[0] == "python":
        return [sys.executable] + parts[1:]
    return parts


class PackRunnableRunsTest(unittest.TestCase):
    def test_commands_are_discoverable(self):
        commands = _runnable_commands()
        self.assertGreaterEqual(len(commands), 10, "可跑入口太少（判据可能已失效）")

    def test_every_entry_runs(self):
        bad = []
        for command in _runnable_commands():
            started = time.perf_counter()
            try:
                proc = subprocess.run(_argv(command), cwd=str(ROOT), capture_output=True,
                                      text=True, encoding="utf-8", errors="replace",
                                      timeout=120)
            except subprocess.TimeoutExpired:
                bad.append(command + " → 超时")
                continue
            elapsed = time.perf_counter() - started
            if proc.returncode not in (0, 2):
                bad.append(command + " → 退出码 " + str(proc.returncode))
            if not (proc.stdout or proc.stderr):
                bad.append(command + " → 没有任何输出")
            if elapsed > 60:
                bad.append(command + f" → 太慢（{elapsed:.1f}s）")
        self.assertEqual([], bad, "这些可跑入口跑不起来：" + "; ".join(bad))


if __name__ == "__main__":
    unittest.main()
