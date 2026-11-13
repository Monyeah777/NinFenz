#!/usr/bin/env python3
"""COCKPIT_RELEASE_NOTES.md 契约：发布说明的可核数字与「存疑项」必须与资产一致。

为什么必须有：这是驾驶舱唯一面向使用者的发布说明，「33 原子 / 14 方法节点 / 8 回合记忆」
这类数字一旦漂移，外部读者就会按错规模评估；更隐蔽的风险是**无代码载体的表述**
（实测：原文「12 层 Agent 反模式审计」在仓内只有本文与 DIFFERENTIATION.md 提及，
没有任何实现或判据）——不标注就会一直被当成已验证能力。本轮补「§现状对照」并加本判据。

范围：只判本文与资产/常量/grep 事实自洽（不改能力清单）。
同族判据：test_meta_cockpit.py（manifest 新鲜度）/ test_meta_cockpit_doc_contract.py。
契约：复核位、33 原子 / 14 方法节点 / 10 节点 / 5 节点 / 8 回合逐值、PENDING 状态、
machine digest 只指路不钉值、「12 层」存疑标注、A/B 7 子命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import method_memory, runtime_executor  # noqa: E402

BASE = ROOT / "desktop" / "src" / "core" / "meta_cockpit"
DOC = BASE / "COCKPIT_RELEASE_NOTES.md"
SUBS = ("preregister", "packets", "analyze", "save", "verify", "index", "audit")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"驾驶舱发布说明不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("驾驶舱发布说明为空")
    return text


def counts() -> dict:
    atoms = json.loads((BASE / "meta_atoms.json").read_text(encoding="utf-8"))["atoms"]
    content = json.loads((BASE / "cognition_pipeline.json").read_text(encoding="utf-8"))["nodes"]
    meta = json.loads((BASE / "cognition_meta_pipeline.json").read_text(encoding="utf-8"))["nodes"]
    return {"atoms": len(atoms), "methods": len(sorted(BASE.glob("method_*.json"))),
            "content": len(content), "meta": len(meta)}


def release_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 认知方法驾驶舱 · 发布说明"):
        issues.append("缺标题「# NF 认知方法驾驶舱 · 发布说明」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺「复核（2026-11-14）」说明")
    c = counts()
    if c["atoms"] != 33:
        issues.append(f"原子数已变（{c['atoms']}）")
    if c["methods"] != 14:
        issues.append(f"方法节点数已变（{c['methods']}）")
    if c["content"] != 10 or c["meta"] != 5:
        issues.append(f"管线节点数已变（{c['content']}/{c['meta']}）")
    for label in ("**33**", "**14**", "**10 节点**", "**5 节点**", "**8**"):
        if label not in text:
            issues.append(f"现状缺数字：{label}")
    if "PENDING" not in text:
        issues.append("缺人工复核 PENDING 状态")
    if runtime_executor.review_status()[0] != "PENDING":
        issues.append("运行器复核状态已非 PENDING（文档需更新）")
    if method_memory.MAX_HISTORY != 8:
        issues.append("方法记忆回合数已变")
    if "machine_digest()" not in text:
        issues.append("缺 machine digest 指路（应只指路、不钉值）")
    if "12 层" not in text or "存疑" not in text:
        issues.append("「12 层反模式审计」未标注存疑")
    for sub in SUBS:
        if sub not in text:
            issues.append(f"A/B 子命令缺：{sub}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class CockpitReleaseNotesTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_release_notes_match_contract(self):
        self.assertEqual([], release_issues(self.text), "驾驶舱发布说明不满足契约")

    def test_assets_live(self):
        c = counts()
        self.assertEqual(33, c["atoms"])
        self.assertEqual(14, c["methods"])
        self.assertEqual(10, c["content"])
        self.assertEqual(5, c["meta"])

    def test_contract_catches_mutations(self):
        """变异自证：数字回退 / 缺存疑标注 / 状态漂移 / 缺指路。"""
        bad = self.text.replace("**33**", "**30**")
        self.assertTrue(any("33" in i for i in release_issues(bad)))
        no_flag = self.text.replace("存疑", "已确认")
        self.assertTrue(any("12 层" in i for i in release_issues(no_flag)))
        no_ptr = self.text.replace("machine_digest()", "摘要")
        self.assertTrue(any("machine digest" in i for i in release_issues(no_ptr)))
        no_pending = self.text.replace("PENDING", "DONE")
        self.assertTrue(any("PENDING" in i for i in release_issues(no_pending)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_release_notes.md")


if __name__ == "__main__":
    unittest.main()
