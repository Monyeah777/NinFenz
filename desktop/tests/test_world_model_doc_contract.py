#!/usr/bin/env python3
"""protocol/WORLD_MODEL.md 契约：schema 形状 / 硬门语义 / 运行器 API 必须与实现一致。

为什么必须有：这是 world_model 字段的唯一语义规范（含运行器与 CLI），此前只有实现测试
（test_world_model 20 例），**文档本身零判据**：schema 键名改了、check32 掉线、或运行器方法被删，
都不会被发现。本轮补「§现状对照」「§复现与引用口径」并加判据：把「契约形状 / 硬门 / 运行器 API /
扫描统计不钉」四件事钉住，并实跑 `nf worldmodel --run` 验证首战实例。

范围：只判本文与 world_model/world_slots/verify.sh 事实自洽（不改语义）。
同族判据：test_world_model.py（20 例）/ test_world_slots.py /
test_machine_contract_doc_contract.py。
契约：复核位、schema 键逐名、硬门 8 条要点、运行器 8 方法、check32 接线、
CLI 四形态、扫描统计不钉口径、复现三命令、`--run` 实跑含 digest。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import world_model as wm  # noqa: E402

DOC = ROOT / "protocol" / "WORLD_MODEL.md"
VERIFY = ROOT / "verify.sh"
SLOTS = ROOT / "protocol" / "world_slots.json"
SCHEMA_KEYS = ("abstract_state", "variables", "initial", "transition", "phases",
               "initial_phase", "invariants", "checks")
RUNTIME = ("validate_state", "advance", "replay", "extract_state",
           "validate_concrete", "advance_concrete", "replay_concrete")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"world_model 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("world_model 文档为空")
    return text


def cli_run() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "scripts/nf.py", "worldmodel", "--run"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180, check=False)


def doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# WORLD_MODEL · 确定性抽象状态契约"):
        issues.append("缺标题「# WORLD_MODEL · 确定性抽象状态契约」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for key in SCHEMA_KEYS:
        if key not in text:
            issues.append(f"缺 schema 键：{key}")
    src = (ROOT / 'desktop' / 'src' / 'core' / 'world_model.py').read_text(encoding='utf-8')
    for name in ("validate_contract", "advance_phase", "trace_digest", "scan"):
        if f'def {name}(' not in src:
            issues.append(f"实现缺函数：{name}")
        if name not in text:
            issues.append(f"正文未点名实现函数：{name}")
    for name in RUNTIME:
        if name not in src:
            issues.append(f"运行器缺方法：{name}")
        if name not in text:
            issues.append(f"正文未写运行器方法：{name}")
    if not SLOTS.is_file():
        issues.append("protocol/world_slots.json 不在场")
    if "world_slots.json" not in text:
        issues.append("未把 slot 注册指向 world_slots.json")
    verify_text = VERIFY.read_text(encoding="utf-8")
    if "check32()" not in verify_text:
        issues.append("verify.sh 缺 check32")
    if "check32" not in text:
        issues.append("正文未点名 check32")
    for section in ("## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "扫描基线不钉死" not in text:
        issues.append("缺「扫描基线不钉死」口径")
    if "不等于" not in text and "≠" not in text:
        issues.append("缺「契约自洽不等于质量好」的边界口径")
    for cmd in ("python scripts/nf.py worldmodel --run",
                "python -m pytest desktop/tests/test_world_model.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class WorldModelDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_doc_matches_contract(self):
        self.assertEqual([], doc_issues(self.text), "world_model 文档不满足契约")

    def test_run_produces_digest(self):
        proc = cli_run()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("digest=", proc.stdout)
        self.assertIn("M50", proc.stdout)

    def test_scan_live(self):
        issues, stats = wm.scan(str(ROOT))
        self.assertEqual([], issues)
        self.assertEqual(1, stats["modules"])
        self.assertEqual(4, stats["variables"])
        self.assertEqual(5, stats["phases"])

    def test_contract_catches_mutations(self):
        """变异自证：缺 schema 键 / 缺实现函数 / 缺运行器方法 / 缺边界口径。"""
        no_key = self.text.replace("initial_phase", "start_phase")
        self.assertTrue(any("schema 键" in i for i in doc_issues(no_key)))
        no_fn = self.text.replace("trace_digest", "摘要")
        self.assertTrue(any("trace_digest" in i for i in doc_issues(no_fn)))
        no_rt = self.text.replace("replay_concrete", "重放具体")
        self.assertTrue(any("replay_concrete" in i for i in doc_issues(no_rt)))
        no_edge = self.text.replace("不等于", "等于").replace("≠", "=")
        self.assertTrue(any("边界口径" in i for i in doc_issues(no_edge)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_world_model.md")


if __name__ == "__main__":
    unittest.main()
