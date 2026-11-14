#!/usr/bin/env python3
"""docs/ccos/method-packs-v0.md 契约：11 域/65 动作/31 类目 + judges 全覆盖 + CLI 用法活绑定。

为什么必须有：这份规范是「某个领域专家实际会做哪几件事」的可核结构——它的全部价值在数字与判据映射：
11 域、65 动作、31 类目、每类目一条 judges。任何一项漂移，读者都会按错的清单去主张/去要证据。
本轮补最后更新位、现状对照与复现口径，并把 index 规模、各包 moves/standards、judges 合计、
两份判据例数、三种 CLI 用法全部活绑定。

范围：只判本文与 method_packs 数据/CLI/判据事实自洽（不改包）。同族判据：
test_pack_depth.py（4 例）/ test_method_pack.py（37 例）/ 词表登记测试 /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、11 域表逐行、index 11 条、moves 合计 65、类目 31、judges 合计 31、
每域规模下限、4+37 例判据、三 CLI 用法在册、现状对照 + 复现三命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "method-packs-v0.md"
INDEX = ROOT / "protocol" / "method_packs" / "index.json"
DEPTH_TEST = ROOT / "desktop" / "tests" / "test_pack_depth.py"
PACK_TEST = ROOT / "desktop" / "tests" / "test_method_pack.py"
NF = ROOT / "scripts" / "nf.py"
DOMAINS = ("watermarking", "evidence-audit", "metacognition", "evaluation-design",
           "prompt-injection-defense", "data-provenance", "resilience", "handoff",
           "privacy", "supply-chain", "operations")
SECTIONS = ("## 它是什么", "## 十一个域", "## 深度", "## 四种用法", "## 纪律",
            "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"方法包文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("方法包文档为空")
    return text


def packs() -> list:
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    return [json.loads((ROOT / row["path"]).read_text(encoding="utf-8"))
            for row in idx["packs"]]


def stats() -> dict:
    docs = packs()
    moves = sum(len(d.get("expert_moves") or []) for d in docs)
    kinds = {e.get("claim_kind") for d in docs
             for e in (d.get("evidence_standards") or [])}
    judges = sum(len(d.get("judges") or {}) for d in docs)
    return {"domains": len(docs), "moves": moves, "kinds": len(kinds),
            "judges": judges}


def count_cases(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("def test")


def pack_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 领域方法包 v0"):
        issues.append("缺标题「# 领域方法包 v0（十一个域）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for dom in DOMAINS:
        if dom not in text:
            issues.append(f"正文缺域：{dom}")
    st = stats()
    if st["domains"] != 11:
        issues.append(f"域数已变（{st['domains']}）")
    if st["moves"] != 65:
        issues.append(f"动作数已变（{st['moves']}）")
    if st["kinds"] != 31:
        issues.append(f"证据类目已变（{st['kinds']}）")
    if st["judges"] != 31:
        issues.append(f"judges 映射数已变（{st['judges']}）")
    for label in ("11 个域", "65", "31 个证据类目"):
        if label not in text:
            issues.append(f"规模口径缺要素：{label}")
    for d in packs():
        if len(d.get("expert_moves") or []) < 5:
            issues.append(f"{d.get('id')} 动作数低于下限 5")
        if len(d.get("evidence_standards") or []) < 2:
            issues.append(f"{d.get('id')} 证据类目低于下限 2")
        if not (d.get("common_failures") or []):
            issues.append(f"{d.get('id')} 缺常见失败")
        if not (d.get("runnable") or []):
            issues.append(f"{d.get('id')} 缺可跑入口")
        for e in d.get("evidence_standards") or []:
            kind = e.get("claim_kind")
            if kind not in (d.get("judges") or {}):
                issues.append(f"{d.get('id')} 类目缺 judges：{kind}")
    n_depth = count_cases(DEPTH_TEST)
    n_pack = count_cases(PACK_TEST)
    if n_depth != 4:
        issues.append(f"test_pack_depth 例数已变（{n_depth}）")
    if n_pack != 37:
        issues.append(f"test_method_pack 例数已变（{n_pack}）")
    for label in ("4 项", "37 项"):
        if label not in text:
            issues.append(f"未写判据数：{label}")
    nf = NF.read_text(encoding="utf-8")
    for flag in ("--packs-list", "--pack-checklist"):
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺旗标：{flag}")
    if "claim" not in nf:
        issues.append("CLI 缺 cog claim")
    for cmd in ("nf cognition --packs-list",
                "nf cognition --pack-checklist handoff",
                "python -m pytest desktop/tests/test_pack_depth.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class MethodPacksDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_packs_match_contract(self):
        self.assertEqual([], pack_issues(self.text), "方法包文档不满足契约")

    def test_pack_data_live(self):
        st = stats()
        self.assertEqual(11, st["domains"])
        self.assertEqual(65, st["moves"])
        self.assertEqual(31, st["kinds"])
        self.assertEqual(31, st["judges"])
        self.assertEqual(4, count_cases(DEPTH_TEST))
        self.assertEqual(37, count_cases(PACK_TEST))

    def test_contract_catches_mutations(self):
        """变异自证：去一域 / 规模回退 / judges 口径 / 例数漂移 / 缺 CLI 用法。"""
        no_dom = self.text.replace("operations", "ops")
        self.assertTrue(any("operations" in i for i in pack_issues(no_dom)))
        old_n = self.text.replace("65", "60")
        self.assertTrue(any("动作数" in i or "65" in i for i in pack_issues(old_n)))
        old_d = self.text.replace("4 项", "2 项")
        self.assertTrue(any("4 项" in i or "例数" in i for i in pack_issues(old_d)))
        no_cli = self.text.replace("nf cognition --pack-checklist handoff", "列清单")
        self.assertTrue(any("checklist" in i for i in pack_issues(no_cli)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_packs.md")


if __name__ == "__main__":
    unittest.main()
