#!/usr/bin/env python3
"""docs/release.md 契约：发布策略声明件必须「11 步计划/3 步冻结链/3 版本面/4 工件」与策略件一致。

为什么必须有：这是发布策略的**人读投影**，机读真源是 protocol/release_policy.json，
release_gate 只机检「三段锚齐」——锚齐不等于数字对。本轮补「§现状对照」「§复现与引用口径」，
把计划步数、冻结链、版本面、必备工件与策略件/CLI 实读双向绑定；并同步 en/ja 译件后重签。

范围：只判本文与 release_policy/release_gate/CLI 事实自洽（不改策略）。
同族判据：test_release_gate.py（若在）/ test_locales.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、11 步 id 全列、冻结链 3 步顺序、版本面 3、工件 4、策略锚 3 段、
tag 人执行、现状对照 + 复现三命令、en/ja 译件含现状小节。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "release.md"
EN = ROOT / "docs" / "en" / "release.md"
JA = ROOT / "docs" / "ja" / "release.md"
POLICY = ROOT / "protocol" / "release_policy.json"
SECTIONS = ("## 这份文件解决什么", "## 冻结链", "## 版本面", "## Golden Master（已退役）",
            "## 变更条目", "## 现状对照", "## 复现与引用口径", "## 边界（不宣称）")
STEPS = ("pre-1", "pre-2", "gate-1", "gate-2", "changes-1", "freeze-1", "freeze-2",
         "freeze-3", "ver-1", "audit-1", "tag-1")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"发布策略文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("发布策略文档为空")
    return text


def policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def plan_steps() -> list:
    out = subprocess.run([sys.executable, "scripts/nf.py", "release", "--plan", "--json"],
                         cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=240, check=False)
    data = json.loads(out.stdout[out.stdout.index("{"):])
    return [s["id"] for s in data["steps"]]


def release_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 发布编排"):
        issues.append("缺标题「# 发布编排（release）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    p = policy()
    if len(p["freeze_chain"]) != 3:
        issues.append(f"冻结链步数已变（{len(p['freeze_chain'])}）")
    if len(p["version_faces"]) != 3:
        issues.append(f"版本面数已变（{len(p['version_faces'])}）")
    if len(p["required_artifacts"]) != 4:
        issues.append(f"必备工件数已变（{len(p['required_artifacts'])}）")
    ids = plan_steps()
    if ids != list(STEPS):
        issues.append(f"计划步序已变：{ids}")
    for sid in STEPS:
        if sid not in text:
            issues.append(f"正文缺步骤 id：{sid}")
    for label in ("**11**", "**3 步**", "**3 处**", "**4 件**", "**3 段**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    for marker in ("conformance", "approve", "receipts"):
        if marker not in text:
            issues.append(f"冻结链缺：{marker}")
    if "由人执行" not in text:
        issues.append("缺「git tag 由人执行」口径")
    if "已在" in text and "退役" not in text:
        issues.append("Golden Master 退役口径缺失")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p2 >= 0 for p2 in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py release --plan --json",
                "python scripts/nf.py release --plan",
                "python scripts/nf.py release"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    en = EN.read_text(encoding="utf-8") if EN.is_file() else ""
    ja = JA.read_text(encoding="utf-8") if JA.is_file() else ""
    if "Status check" not in en:
        issues.append("en 译件缺现状小节")
    if "現状対照" not in ja:
        issues.append("ja 译件缺现状小节")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ReleaseDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_release_matches_contract(self):
        self.assertEqual([], release_issues(self.text), "发布策略文档不满足契约")

    def test_policy_live(self):
        p = policy()
        self.assertEqual(3, len(p["freeze_chain"]))
        self.assertEqual(3, len(p["version_faces"]))
        self.assertEqual(4, len(p["required_artifacts"]))
        self.assertEqual(list(STEPS), plan_steps())

    def test_contract_catches_mutations(self):
        """变异自证：缺步骤 id / 冻结链回退 / 版本面回退 / 缺 tag 口径 / 缺命令。"""
        no_step = self.text.replace("tag-1", "tag")
        self.assertTrue(any("tag-1" in i for i in release_issues(no_step)))
        old_f = self.text.replace("**3 步**", "**2 步**")
        self.assertTrue(any("3 步" in i for i in release_issues(old_f)))
        old_v = self.text.replace("**3 处**", "**2 处**")
        self.assertTrue(any("3 处" in i for i in release_issues(old_v)))
        no_tag = self.text.replace("由人执行", "自动执行")
        self.assertTrue(any("由人执行" in i for i in release_issues(no_tag)))
        no_cmd = self.text.replace("python scripts/nf.py release --plan --json", "计划")
        self.assertTrue(any("--plan --json" in i for i in release_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_release.md")


if __name__ == "__main__":
    unittest.main()
