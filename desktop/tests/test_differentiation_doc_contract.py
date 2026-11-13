#!/usr/bin/env python3
"""DIFFERENTIATION.md 契约：46 条核心的「声明 → 载体」对照必须与实现一致。

为什么必须有：这份文件用 46 条「不可让渡的核心」界定驾驶舱边界，但此前没有任何判据——
实测发现 4 条（#34 12 层反模式 / #43 Ruff+Mypy 全覆盖 / #44 Ruff C901≤25 / #45 Radon 交叉 /
#46 豁免白名单）**在仓内没有载体**：ruff.toml 只 select E9/F63/F7/F82，无 mypy 配置、无 radon 依赖。
本轮补「§载体对照」把有载体的条目钉住、把无载体的如实登记为缺口，并加本判据防止
「文档很硬、实现没有」再次被当成已验证能力。

范围：只判本文与资产/配置事实自洽（不改 46 条正文）。
同族判据：test_meta_cockpit.py / test_cockpit_release_notes_doc_contract.py。
契约：21 行先例表 + 46 条编号齐全、复核位、载体对照段、7 项有载体条目逐条、
4 项缺口标注「无载体」、ruff 配置与声明不符必须显性写出。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "desktop" / "src" / "core" / "meta_cockpit"
DOC = BASE / "DIFFERENTIATION.md"
RUFF = ROOT / "ruff.toml"
LINKED = ("meta_gradient.json", "meta_atoms.json", "meta_guard.json",
          "context_pack", "meta_runtime_manifest", "session_journal")
GAPS = ("12 层架构反模式", "Ruff/Mypy", "C901", "Radon", "白名单")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"差异化论证不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("差异化论证为空")
    return text


def diff_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 核心与差异化"):
        issues.append("缺标题「# 核心与差异化（可借鉴，但不可丢）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺「复核（2026-11-14）」说明")
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "|" in ln[2:]]
    data_rows = [ln for ln in rows
                 if not ln.startswith("| 先例") and not ln.startswith("|---")
                 and not ln.startswith("| 条目")]
    if len(data_rows) < 22:
        issues.append(f"先例/载体对照行数异常（{len(data_rows)}）")
    nums = re.findall(r"(?m)^([0-9]{1,2})\. ", text)
    if len(nums) != 46:
        issues.append(f"46 条编号不全（{len(nums)}）")
    if "## 载体对照" not in text:
        issues.append("缺「§载体对照」段")
    for token in LINKED:
        if token not in text:
            issues.append(f"有载体条目未点名载体：{token}")
    if "**无载体（缺口）**" not in text:
        issues.append("缺「无载体（缺口）」标注")
    for gap in GAPS:
        if gap not in text:
            issues.append(f"缺口条目未登记：{gap}")
    if text.count("有载体") < 6:
        issues.append("有载体条目过少（应 ≥6）")
    ruff = RUFF.read_text(encoding="utf-8")
    if "C901" in ruff:
        issues.append("ruff 已开 C901，本文「未开」口径需更新")
    if "E9" not in ruff:
        issues.append("ruff select 已变，本文口径需更新")
    if "不是删条目的理由" not in text:
        issues.append("缺「缺口不是删条目理由」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class DifferentiationDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_differentiation_matches_contract(self):
        self.assertEqual([], diff_issues(self.text), "差异化论证不满足契约")

    def test_carriers_live(self):
        for name in ("meta_gradient.json", "meta_atoms.json", "meta_guard.json"):
            self.assertTrue((BASE / name).is_file(), f"载体不在场：{name}")
        guard = json.loads((BASE / "meta_guard.json").read_text(encoding="utf-8"))
        self.assertIn("holdout_pack_digest", json.dumps(guard))
        atoms = json.loads((BASE / "meta_atoms.json").read_text(encoding="utf-8"))["atoms"]
        self.assertEqual(33, len(atoms))

    def test_contract_catches_mutations(self):
        """变异自证：缺缺口标注 / 编号缺失 / ruff 口径过期 / 缺对照段。"""
        no_gap = self.text.replace("**无载体（缺口）**", "**已具备**")
        self.assertTrue(any("无载体" in i for i in diff_issues(no_gap)))
        drop = self.text.replace("46. 复杂度豁免必须显式可审计", "46 复杂度豁免")
        self.assertTrue(any("46 条" in i for i in diff_issues(drop)))
        no_sec = self.text.replace("## 载体对照", "## 附注")
        self.assertTrue(any("载体对照" in i for i in diff_issues(no_sec)))
        no_reason = self.text.replace("不是删条目的理由", "可删")
        self.assertTrue(any("删条目理由" in i for i in diff_issues(no_reason)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_diff.md")


if __name__ == "__main__":
    unittest.main()
