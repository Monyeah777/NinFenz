#!/usr/bin/env python3
"""docs/modeling.md 契约：建模三件文档必须「12 scheme/37 规范/54 契约与 nf model 实读一致」。

为什么必须有：这页把「词表 / 规范件 / 数据契约」三件建模问题变成机检件，读者据此判断
「谁说了算 / 哪些件有约束力 / 每个机读件谁管」。三件的规模与解析面（42 checks + 24 assertions）
一旦漂移，口径就会失真。本轮补「§现状对照」「§复现与引用口径」并把数字与 nf model 输出活绑定。

范围：只判本文与 vocabularies/normative/data_contracts/CLI/判据事实自洽（不改册子）。
同族判据：test_modeling.py（12 例）/ test_version_map.py / test_doc_hygiene.py /
test_doc_examples.py。
契约：最后更新位 + 复核、12 scheme、37 规范件、2445 说明件、66 回执、54 契约、
42 checks/24 assertions、12 例、现状对照 + 复现三命令、literal 0 口径。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "modeling.md"
VOCAB = ROOT / "protocol" / "vocabularies.json"
NORM = ROOT / "protocol" / "normative.json"
CONTRACTS = ROOT / "protocol" / "data_contracts.json"
SECTIONS = ("## 是什么", "## 怎么用", "## 判据（可证）", "## 现状对照",
            "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"建模文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("建模文档为空")
    return text


def data() -> dict:
    v = json.loads(VOCAB.read_text(encoding="utf-8"))
    n = json.loads(NORM.read_text(encoding="utf-8"))
    c = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    schemes = v.get("schemes") or []
    literal = [s for s in schemes
               if str((s.get("probe") or {}).get("kind")) == "literal"]
    return {"schemes": len(schemes), "literal": len(literal),
            "normative": len(n.get("normative") or []),
            "contracts": len(c.get("contracts") or [])}


def modeling_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 内容建模三件"):
        issues.append("缺标题「# 内容建模三件（modeling）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    d = data()
    if d["schemes"] != 12:
        issues.append(f"词表 scheme 数已变（{d['schemes']}）")
    if d["literal"] != 0:
        issues.append(f"literal 档非 0（{d['literal']}）")
    if d["normative"] != 37:
        issues.append(f"规范件数已变（{d['normative']}）")
    if d["contracts"] != 54:
        issues.append(f"数据契约数已变（{d['contracts']}）")
    for label in ("**12**", "**37**", "**54**", "**2445**", "**66**",
                  "**42 checks + 24 assertions**", "**12 例**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    if "literal 0" not in text:
        issues.append("缺 literal 0 口径")
    for marker in ("probe", "quality_rule", "说明件不得被回执锚定"):
        if marker not in text:
            issues.append(f"判据/边界缺：{marker}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py model",
                "python scripts/nf.py model --json",
                "python -m pytest desktop/tests/test_modeling.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不复制" not in text:
        issues.append("缺「册子不复制真源」边界")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ModelingDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_modeling_matches_contract(self):
        self.assertEqual([], modeling_issues(self.text), "建模文档不满足契约")

    def test_data_live(self):
        d = data()
        self.assertEqual(12, d["schemes"])
        self.assertEqual(0, d["literal"])
        self.assertEqual(37, d["normative"])
        self.assertEqual(54, d["contracts"])

    def test_contract_catches_mutations(self):
        """变异自证：scheme 回退 / 规范件回退 / 契约回退 / 缺解析面 / 缺命令。"""
        old_s = self.text.replace("**12**", "**9**")
        self.assertTrue(any("12" in i for i in modeling_issues(old_s)))
        old_n = self.text.replace("**37**", "**30**")
        self.assertTrue(any("37" in i for i in modeling_issues(old_n)))
        old_c = self.text.replace("**54**", "**50**")
        self.assertTrue(any("54" in i for i in modeling_issues(old_c)))
        old_q = self.text.replace("**42 checks + 24 assertions**", "**checks**")
        self.assertTrue(any("42 checks" in i for i in modeling_issues(old_q)))
        no_cmd = self.text.replace("python scripts/nf.py model --json", "看结果")
        self.assertTrue(any("--json" in i for i in modeling_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_modeling.md")


if __name__ == "__main__":
    unittest.main()
