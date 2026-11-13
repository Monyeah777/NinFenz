#!/usr/bin/env python3
"""patterns/verifier-must-run/PATTERN.md 契约：接线表/下限/四源面清单必须与实现一致。

为什么必须有：这条 pattern 自己就是「元判据」——它断言「没跑过的判据不算判据」。如果它的载体
（`EXTERNAL_SUITES` 接线表、`MIN_DISCOVERED` 下限、四源面清单）被改掉而不自知，元判据会空转。
本轮补「§现状对照」「§复现与引用口径」并加判据：登记表每条**目标真实存在**、下限常量在、
四源函数在、三条判据实跑通过；同时写明「不钉套件总数」与「npm 面依赖本机 payload 前置」。

范围：只判本文与接线实现/判据事实自洽（不改判定）。
同族判据：test_single_source_truth_pattern_doc_contract.py（同骨架）/ test_suite_wiring.py。
契约：6 必填键、3 规则、applies_to 三目标（tests 目录通配 + verify.sh + workflows 通配）、
evidence 四件可解析、五段正文、`EXTERNAL_SUITES` 每条目标在场、`MIN_DISCOVERED` 在文且在实现、
四源函数在文、不钉总数口径、复现三命令、test_suite_wiring 实跑 rc=0。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "verifier-must-run" / "PATTERN.md"
WIRING = ROOT / "desktop" / "tests" / "test_suite_wiring.py"
FASTLANE = ROOT / "desktop" / "tests" / "test_rust_fastlane.py"
FACES = ("_documented_faces", "_self_declared_subfaces", "_probed_faces", "_source_faces")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"pattern 正文不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("pattern 正文为空")
    return text


def entry() -> dict:
    for e in pat.entries(str(ROOT)):
        if e["dir"] == "verifier-must-run":
            return e
    raise ValueError("patterns 里找不到 verifier-must-run")


def wired_suites() -> list:
    """从接线表里取已登记套件路径（文本解析，避免 import 测试模块）。"""
    text = WIRING.read_text(encoding="utf-8")
    start = text.index("EXTERNAL_SUITES = {")
    end = text.index("\n}", start)
    block = text[start:end]
    return re.findall(r'^\s+"([^"]+)":', block, re.M)


def vm_issues(text: str) -> list:
    issues = []
    e = entry()
    fm = e["fm"]
    for key in pat.REQUIRED:
        if key not in fm:
            issues.append(f"frontmatter 缺 {key}")
    rules = pat._as_list(fm.get("rules"))
    if len(rules) != 3:
        issues.append(f"规则数已变（{len(rules)}，应为 3）")
    verify_text = (ROOT / "verify.sh").read_text(encoding="utf-8")
    for ev in pat._as_list(fm.get("evidence")):
        rel = str(ev).replace("\\", "/")
        if not (ROOT / rel).exists():
            issues.append(f"evidence 不在场：{rel}")
    wiring = WIRING.read_text(encoding="utf-8")
    if "EXTERNAL_SUITES" not in wiring:
        issues.append("接线表 EXTERNAL_SUITES 消失（元判据空转）")
    suites = wired_suites()
    if not suites:
        issues.append("接线表为空（至少应登记 1 条）")
    for rel in suites:
        if not (ROOT / rel).exists():
            issues.append(f"接线表登记的套件不在场：{rel}")
    if "MIN_DISCOVERED" not in wiring:
        issues.append("缺 MIN_DISCOVERED 塌缩下限")
    if "MIN_DISCOVERED" not in text:
        issues.append("正文未写塌缩下限")
    fast = FASTLANE.read_text(encoding="utf-8")
    for fn in FACES:
        if fn not in fast:
            issues.append(f"面清单来源消失：{fn}")
        if fn not in text:
            issues.append(f"正文未写面清单来源：{fn}")
    for section in ("## 为什么", "## 怎么用", "## 反例", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "不钉" not in text:
        issues.append("缺「不钉套件总数」口径")
    if "执行前置" not in text:
        issues.append("缺「npm 面依赖本机 payload 前置」说明")
    for cmd in ("python -m pytest desktop/tests/test_suite_wiring.py",
                "python -m pytest desktop/tests/test_rust_fastlane.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if verify_text.count("check12()") != 1:
        issues.append("verify.sh 的 check12 定义异常")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class VerifierMustRunTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pattern_matches_contract(self):
        self.assertEqual([], vm_issues(self.text), "verifier-must-run 不满足契约")

    def test_wiring_and_faces_live(self):
        self.assertTrue(wired_suites())
        for fn in FACES:
            self.assertIn(fn, FASTLANE.read_text(encoding="utf-8"))

    def test_wiring_judge_passes(self):
        proc = subprocess.run([sys.executable, "-m", "pytest",
                               "desktop/tests/test_suite_wiring.py", "-q"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, proc.stdout[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：缺现状段 / 缺下限 / 缺四源 / 缺前置说明。"""
        no_sec = self.text.replace("## 现状对照", "## 附注")
        self.assertTrue(any("现状对照" in i for i in vm_issues(no_sec)))
        no_min = self.text.replace("MIN_DISCOVERED", "下限")
        self.assertTrue(any("塌缩下限" in i for i in vm_issues(no_min)))
        no_faces = self.text.replace("_source_faces", "源码面")
        self.assertTrue(any("_source_faces" in i for i in vm_issues(no_faces)))
        no_pre = self.text.replace("执行前置", "环境")
        self.assertTrue(any("前置" in i for i in vm_issues(no_pre)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_vmr.md")


if __name__ == "__main__":
    unittest.main()
