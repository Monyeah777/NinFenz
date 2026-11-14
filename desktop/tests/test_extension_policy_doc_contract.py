#!/usr/bin/env python3
"""protocol/EXTENSION.md 契约：影响度三档 / 派生三问 / check30+check13 接线必须与实现一致。

为什么必须有：这是「协议变更怎么定影响度」的唯一策略页——三档判定、派生三问、域包装卸不变量都在这里。
此前它只有 `test_extension_impact.py`（测 `nf diff` 的实现逻辑），**文档本身零判据**：档位名改了、
check30/check13 掉线、或正文钉了会漂的版本号，都不会被发现。本轮补「§现状对照」「§复现与引用口径」
并加判据把三档、三问、两条 check 接线与回放样本钉住。

范围：只判本文与 contract_history/verify.sh 事实自洽（不改策略）。
同族判据：test_extension_impact.py（实现逻辑）/ test_conformance_doc_contract.py。
契约：复核位、三档逐名、派生三问三条、check30/check13 在 verify.sh、回放样本 4 行、
现状对照 + 复现三命令、不钉运行时版本号、`nf diff` 的 verdict/impact 两套判定口径在文。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / 'desktop' / 'src'))

DOC = ROOT / "protocol" / "EXTENSION.md"
VERIFY = ROOT / "verify.sh"
TIERS = ("editorial", "additive", "bump")
QUESTIONS = ("基类是什么", "新增面是什么", "旧消费方可读性")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"扩展策略文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("扩展策略文档为空")
    return text


def ext_issues(text: str) -> list:
    issues = []
    if not text.startswith("# protocol/EXTENSION.md"):
        issues.append("缺标题「# protocol/EXTENSION.md · 协议扩展策略与变更影响分层」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for tier in TIERS:
        if tier not in text:
            issues.append(f"缺影响度档位：{tier}")
    for q in QUESTIONS:
        if q not in text:
            issues.append(f"缺派生问：{q}")
    verify_text = VERIFY.read_text(encoding="utf-8")
    for n in ("13", "30"):
        if f"check{n}()" not in verify_text:
            issues.append(f"verify.sh 缺 check{n}（策略页点名的门禁）")
        if f"check{n}" not in text:
            issues.append(f"正文未点名 check{n}")
    if "§现状对照"[1:] not in text and "## 现状对照" not in text:
        issues.append("缺「§现状对照」段")
    if "## 复现与引用口径" not in text:
        issues.append("缺「§复现与引用口径」段")
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and " | " in ln]
    replay = [ln for ln in rows if "bump" in ln or "additive" in ln]
    if len(replay) < 4:
        issues.append(f"回放样本行不足 4（{len(replay)}）")
    if "不钉运行时数字" not in text:
        issues.append("缺「不钉运行时版本号/件数」口径")
    if "verdict" not in text or "impact" not in text:
        issues.append("缺 verdict 与 impact 两套判定的区分口径")
    for cmd in ("python scripts/nf.py diff", "python scripts/nf.py verify --only 30"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ExtensionPolicyDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_policy_matches_contract(self):
        self.assertEqual([], ext_issues(self.text), "扩展策略文档不满足契约")

    def test_impact_tiers_live(self):
        src = (ROOT / "desktop" / "src" / "core" / "contract_history.py").read_text(
            encoding="utf-8")
        for tier in TIERS:
            self.assertIn(f'impact = "{tier}"', src)

    def test_check30_runs(self):
        proc = subprocess.run([sys.executable, "scripts/nf.py", "verify", "--only", "30"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, proc.stdout[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：缺档位 / 缺派生问 / 缺 check 点名 / 缺两套判定口径。"""
        no_tier = self.text.replace("additive", "外加")
        self.assertTrue(any("additive" in i for i in ext_issues(no_tier)))
        no_q = self.text.replace("旧消费方可读性", "兼容")
        self.assertTrue(any("旧消费方" in i for i in ext_issues(no_q)))
        no_check = self.text.replace("check30", "某个检查")
        self.assertTrue(any("check30" in i for i in ext_issues(no_check)))
        no_pair = self.text.replace("verdict", "判定")
        self.assertTrue(any("verdict" in i for i in ext_issues(no_pair)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_extension.md")


if __name__ == "__main__":
    unittest.main()
