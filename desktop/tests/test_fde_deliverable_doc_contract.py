#!/usr/bin/env python3
"""交付物生成契约：五门口径一致 + 与 manifest sha 对得上。

为什么必须有：这是 --run 生成的交付物样本，也是客户侧唯一读到的「交付长什么样」。
它有两个必须机的面：
① 内部口径一致——本轮修掉的真实缺陷是标题写「四道门 + 中游层核验」
   而表格列了 G1–G5（同一文件里 4≠5）；
② 与证据自洽——manifest.artifacts 里记的 sha256 必须等于盘上交付物字节。
本判据把生成物标记、五门标题、五行门表、§1 模型无关、§2 数字、§3 六面、§4 五步、manifest sha
与生成器 docstring 全部活绑定（**只读**判生成物；要改内容必须改生成器再 --run）。

范围：只判生成物与生成器/manifest 事实自洽。同族判据：
test_fde_sample_doc_contract.py（README 五门）/ test_fde_brief_doc_contract.py（brief 落点）/
test_json_shape_contracts.py（manifest 形状）。
契约：生成物标记、五道门标题且无「四道门」残留、恰 5 行门表、§1「模型无关：True」、
§2 三个数字、§3 六面、§4 五步、manifest sha == 盘上 sha、生成器同口径。
"""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DELIV = ROOT / "docs" / "fde-sample" / "evidence" / "deliverable.md"
MANIFEST = ROOT / "docs" / "fde-sample" / "evidence" / "manifest.json"
GENERATOR = ROOT / "scripts" / "fde_sample_run.py"
SECTIONS = ("## 1. 交付对象", "## 2. 概念闭包", "## 3. 交付面清单", "## 4. 装配步骤",
            "## 5. 验收判据")


def load_text(path: Path = DELIV) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"交付物样本不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("交付物样本为空")
    return text


def artifact_sha() -> str:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rel = "docs/fde-sample/evidence/deliverable.md"
    return str((man.get("artifacts") or {}).get(rel) or "")


def deliv_issues(text: str) -> list:
    issues = []
    if not text.startswith("# FDE 交付样例"):
        issues.append("缺标题「# FDE 交付样例 · AI 系统域包 → 技术文档交付物」")
    if "禁止手改" not in text:
        issues.append("缺「生成物，禁止手改」标记")
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    if "五道门" not in text:
        issues.append("标题未写「五道门」")
    if "四道门" in text:
        issues.append("仍残留「四道门」（与五行门表 4≠5 矛盾）")
    if "G1–G4 结构面 + G5 中游出口" not in text:
        issues.append("缺五门口径说明（G1–G4 + G5）")
    rows = [ln for ln in text.splitlines() if ln.startswith("| G")]
    if len(rows) != 5:
        issues.append(f"门表行数应为 5（实测 {len(rows)}）")
    for i in range(1, 6):
        if ("| G" + str(i) + " |") not in text:
            issues.append(f"门表缺 G{i}")
    if "模型无关：True" not in text:
        issues.append("§1 缺「模型无关：True」")
    for num in ("48", "47", "23"):
        if num not in text:
            issues.append(f"§2 缺数字：{num}")
    lists = [ln for ln in text.splitlines()
             if ln.startswith("|") and "outputs/" in ln]
    if len(lists) != 6:
        issues.append(f"§3 产出面应为 6 行（实测 {len(lists)}）")
    steps = [ln for ln in text.splitlines() if ln[:3] in ("1. ", "2. ", "3. ", "4. ", "5. ")]
    if len(steps) != 5:
        issues.append(f"§4 步骤应为 5 步（实测 {len(steps)}）")
    sha = artifact_sha()
    actual = hashlib.sha256(DELIV.read_bytes()).hexdigest()
    if not sha:
        issues.append("manifest 未记录交付物 sha")
    elif sha != actual:
        issues.append(f"manifest sha 与盘上不符（{sha[:8]} vs {actual[:8]}）")
    gen = GENERATOR.read_text(encoding="utf-8")
    if "四道门" in gen:
        issues.append("生成器文本仍写「四道门」")
    if "五道门" not in gen:
        issues.append("生成器未写「五道门」口径")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class FdeDeliverableTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_deliverable_matches_contract(self):
        self.assertEqual([], deliv_issues(self.text), "交付物样本不满足契约")

    def test_manifest_sha_live(self):
        self.assertEqual(hashlib.sha256(DELIV.read_bytes()).hexdigest(), artifact_sha())
        self.assertIn("五道门", DELIV.read_text(encoding="utf-8"))
        self.assertIn("五道门", GENERATOR.read_text(encoding="utf-8"))

    def test_contract_catches_mutations(self):
        """变异自证：回退四道门 / 少了 G4 / 缺模型无关 / 产出面少一行 / 生成器回退。"""
        back = self.text.replace("五道门", "四道门")
        self.assertTrue(any("五道门" in i or "四道门" in i for i in deliv_issues(back)))
        no_g4 = self.text.replace("| G4 |", "| GX |")
        self.assertTrue(any("G4" in i for i in deliv_issues(no_g4)))
        no_m = self.text.replace("模型无关：True", "模型无关：—")
        self.assertTrue(any("模型无关" in i for i in deliv_issues(no_m)))
        old_row = self.text.replace("outputs/CONCEPT_DAG.graphml", "CONCEPT_DAG.graphml")
        self.assertTrue(any("§3" in i for i in deliv_issues(old_row)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_deliverable.md")


if __name__ == "__main__":
    unittest.main()
