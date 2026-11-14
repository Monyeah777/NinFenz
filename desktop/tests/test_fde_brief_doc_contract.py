#!/usr/bin/env python3
"""docs/fde-sample/brief.md 契约：brief 的「诉求 → 可判定项」映射必须每条落点真实可复核。

为什么必须有：brief 是样例的输入侧——它把客户四条诉求翻译成五项可判定项，每一项都指向仓内落点。
若落点文件不存在、字段名写错、或把 brief 本身说成门禁输入，读者就会拿错东西去复核（尤其
「模型无关」这条：字段其实在 SYSTEM_CARD 的 system 子对象里）。本轮补「§现状对照」逐条复核口径 +
「§复现与引用口径」，并活绑定两个边界事实：manifest.inputs 不含 brief；交付物「四道门 + 中游层核验」
= G1–G4 + G5。

范围：只判本文与落点文件/证据件事实自洽（不改生成物）。同族判据：test_fde_sample_doc_contract.py
（README 五门数字）/ test_json_shape_contracts.py（manifest 形状）/ test_doc_hygiene.py。
契约：最后更新位 + 复核、四诉求与五判定行在文、七个落点存在、系统卡 model_agnostic=true 且交付物写
「模型无关：True」、manifest.inputs 不含 brief、现状对照 + 复现两命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "fde-sample" / "brief.md"
SAMPLE = ROOT / "docs" / "fde-sample"
MANIFEST = SAMPLE / "evidence" / "manifest.json"
DELIVERABLE = SAMPLE / "evidence" / "deliverable.md"
GATES = SAMPLE / "evidence" / "gates.txt"
CARD = ROOT / "community" / "AI系统域包" / "outputs" / "SYSTEM_CARD.json"
SECTIONS = ("## 一、客户诉求", "## 二、FDE 侧的交付判定", "## 现状对照",
            "## 复现与引用口径", "## 三、边界")
CLAIMS = ("概念先后写清", "依据什么", "怎么验收", "谁验过", "换供应商不推翻")
TARGETS = (
    "docs/fde-sample/evidence/deliverable.md",
    "protocol/standards_binding.json",
    "docs/standards/index.md",
    "docs/fde-sample/evidence/gates.txt",
    "docs/fde-sample/evidence/manifest.json",
    "docs/interop-thirdparty.md",
)


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"FDE brief 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("FDE brief 为空")
    return text


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def card() -> dict:
    return json.loads(CARD.read_text(encoding="utf-8"))


def brief_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 客户 brief"):
        issues.append("缺标题「# 客户 brief（样例输入）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for i in range(1, 5):
        if str(i) + "." not in text:
            issues.append(f"缺客户诉求 {i}")
    for c in CLAIMS:
        if c not in text:
            issues.append(f"缺判定行：{c}")
    for rel in TARGETS:
        if not (ROOT / rel).exists():
            issues.append(f"落点不存在：{rel}")
        if rel not in text and Path(rel).name not in text:
            issues.append(f"正文未点名落点：{rel}")
    c = card()
    sysinfo = c.get("system") if isinstance(c.get("system"), dict) else {}
    if sysinfo.get("model_agnostic") is not True:
        issues.append("系统卡 system.model_agnostic 不是 true")
    if "模型无关：True" not in DELIVERABLE.read_text(encoding="utf-8"):
        issues.append("交付物缺「模型无关：True」")
    inputs = list(manifest().get("inputs") or {})
    if any("brief" in str(k) for k in inputs):
        issues.append("brief 被误当门禁输入（不应在 manifest.inputs）")
    if "不参与门禁" not in text:
        issues.append("缺「brief 不参与门禁」口径")
    if "manifest" not in text or "inputs" not in text:
        issues.append("缺 manifest.inputs 边界口径")
    if "四道门 + 中游层核验" not in text or "G1–G4 + G5" not in text:
        issues.append("缺「四道门 + 中游层核验 = G1–G4 + G5」澄清")
    gates = GATES.read_text(encoding="utf-8")
    for g in ("G1", "G2", "G3", "G4", "G5"):
        if ("[PASS] " + g) not in gates:
            issues.append(f"gates.txt 缺 PASS：{g}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/fde_sample_run.py --check",
                "python scripts/nf.py standards --stats"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class FdeBriefTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_brief_matches_contract(self):
        self.assertEqual([], brief_issues(self.text), "FDE brief 不满足契约")

    def test_targets_live(self):
        for rel in TARGETS:
            self.assertTrue((ROOT / rel).exists(), rel)
        self.assertIs(True, card()["system"]["model_agnostic"])
        inputs = list(manifest()["inputs"])
        self.assertFalse(any("brief" in str(k) for k in inputs))
        self.assertFalse(any("brief" in str(k) for k in inputs))
        for g in ("G1", "G2", "G3", "G4", "G5"):
            self.assertIn("[PASS] " + g, GATES.read_text(encoding="utf-8"))

    def test_contract_catches_mutations(self):
        """变异自证：缺诉求 / 缺判定行 / 落点错名 / 缺输入边界 / 缺命令。"""
        no_claim = self.text.replace("谁验过", "谁验了")
        self.assertTrue(any("谁验过" in i for i in brief_issues(no_claim)))
        no_row = self.text.replace("怎么验收", "如何验收")
        self.assertTrue(any("怎么验收" in i for i in brief_issues(no_row)))
        bad = self.text.replace("docs/interop-thirdparty.md", "docs/interop-nowhere.md")
        self.assertTrue(any("落点" in i for i in brief_issues(bad)))
        no_in = self.text.replace("不参与门禁", "参与门禁")
        self.assertTrue(any("不参与门禁" in i for i in brief_issues(no_in)))
        no_cmd = self.text.replace("python scripts/fde_sample_run.py --check", "自检")
        self.assertTrue(any("--check" in i for i in brief_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_brief.md")


if __name__ == "__main__":
    unittest.main()
