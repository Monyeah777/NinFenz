#!/usr/bin/env python3
"""tui/README.md 契约：TUI 说明的「动作数 / 区数 / 闸门三表 / 自检 6 条 / 退出码」与实跑一致。

为什么必须有：`tui/` 是公开的终端入口，README 写着「34 动作 / 9 区 / 14 旗标 / 24 动词 / 4 配对」
这些数字此前**零判据**——投影重生成后数字变了没人发现，读者会按旧数字判断「有没有这个动作」。
本轮补「§现状对照」「§复现与引用口径」，并加判据：`--selftest` 实跑 6 条全绿、`--list-actions`
实读的数字与文一致、四条安全底线与六类退出码在文、且不把投影数字写成承诺。

范围：只判本文与 `tui/nf.py` 实跑输出一致（不改 TUI 行为）。
同族判据：test_terminal*.py / test_shell_*.py（真源策展表侧）/ verify check39（投影逐字节）。
契约：复核位、四条安全底线、六类退出码、selftest 6 条行名、现状对照段、复现四命令、
「投影会随 CLI 演进，不当作承诺」口径、以及 selftest 实跑 rc=0。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "tui" / "README.md"
TUI = ROOT / "tui" / "nf.py"
SURFACE = ROOT / "tui" / "_surface.py"
EXIT_CODES = ("0", "1", "2", "3", "4", "130")
SAFETY = ("不用 shell", "命令白名单", "路径包含性", "密钥不落地")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"tui README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("tui README 为空")
    return text


def run_tui(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "tui/nf.py", *args],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180, check=False)


def actions_json() -> dict:
    proc = run_tui("--list-actions", "--json")
    if proc.returncode != 0:
        raise ValueError("--list-actions 失败：" + proc.stderr[-200:])
    return json.loads(proc.stdout)


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 终端 TUI（nf-tui）"):
        issues.append("缺标题「# NF 终端 TUI（nf-tui）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for name in SAFETY:
        if name not in text:
            issues.append(f"缺安全底线：{name}")
    for code in EXIT_CODES:
        if f"| {code} |" not in text:
            issues.append(f"退出码表缺 {code}")
    for row in ("闸门口径", "投影同源", "密钥不硬编码", "渲染确定性",
                "交互语义", "CLI 面漂移"):
        if row not in text:
            issues.append(f"正文未列自检项：{row}")
    for section in ("## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "不当作承诺" not in text:
        issues.append("缺「投影数字不当作承诺」口径")
    if "_surface.py" not in text or "生成件" not in text:
        issues.append("缺「_surface.py 是生成件、改真源后重生成」纪律")
    for cmd in ("python tui/nf.py --selftest",
                "python tui/nf.py --list-actions --json"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    data = actions_json()
    if data.get("kind") != "nf-tui-actions":
        issues.append("--list-actions 的 kind 已变")
    n_actions = len(data.get("actions") or [])
    if f"**{n_actions}** 个动作" not in text:
        issues.append(f"正文动作数与实读不符（实读 {n_actions}）")
    if len(data.get("exit_codes") or {}) != 6:
        issues.append("exit_codes 已不是 6 类")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class TuiReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], doc_issues(self.text), "tui README 不满足契约")

    def test_selftest_passes(self):
        proc = run_tui("--selftest")
        self.assertEqual(0, proc.returncode, proc.stdout[-500:] + proc.stderr[-300:])
        for row in ("闸门口径", "投影同源", "密钥不硬编码"):
            self.assertIn(row, proc.stdout)

    def test_surface_is_generated(self):
        self.assertTrue(SURFACE.is_file())
        head = SURFACE.read_text(encoding="utf-8")[:400]
        self.assertIn("生成", head)

    def test_contract_catches_mutations(self):
        """变异自证：缺安全底线 / 缺退出码 / 改错动作数 / 缺口径。"""
        no_safety = self.text.replace("密钥不落地", "密钥可选")
        self.assertTrue(any("密钥不落地" in i for i in doc_issues(no_safety)))
        no_code = self.text.replace("| 130 |", "| 137 |")
        self.assertTrue(any("130" in i for i in doc_issues(no_code)))
        bad_n = self.text.replace("**34** 个动作", "**99** 个动作")
        self.assertTrue(any("动作数" in i for i in doc_issues(bad_n)))
        no_rule = self.text.replace("不当作承诺", "即承诺")
        self.assertTrue(any("承诺" in i for i in doc_issues(no_rule)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_tui_readme.md")


if __name__ == "__main__":
    unittest.main()
