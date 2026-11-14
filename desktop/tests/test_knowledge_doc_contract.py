#!/usr/bin/env python3
"""docs/knowledge.md 契约：双源知识层文档必须「6 源分档/顺序全排列/巡检与台账实读一致」。

为什么必须有：这页给「外部检索来的东西算不算事实」一个可判定答案——源数、contract/reference 分档、
query_order 全排列、认知裁剪模块、频次台账 total，任何一项漂移都会让读者误判「哪些是合同级知识」。
本轮补可核现状（6 源 = 3+3、public 4 / internal 2、order 6、M23、lint 全绿、usage total 0）
与「§现状对照」「§复现与引用口径」。

范围：只判本文与 knowledge_sources/knowledge_usage/CLI/判据事实自洽（不改知识源）。
同族判据：test_knowledge.py（35 例）/ test_knowledge_sig.py（10 例）/ test_doc_hygiene.py。
契约：最后更新位 + 复核、6 源与 3+3 在文、query_order 6 且 contract 全在前、M23 在文、
lint 全绿口径、usage total 0、现状对照 + 复现三命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "knowledge.md"
SOURCES = ROOT / "protocol" / "knowledge_sources.json"
USAGE = ROOT / "protocol" / "knowledge_usage.json"
SECTIONS = ("## 是什么", "## 怎么用", "## 判据（可证）", "## 晋升（转正）规则",
            "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"知识层文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("知识层文档为空")
    return text


def data() -> dict:
    return json.loads(SOURCES.read_text(encoding="utf-8"))


def knowledge_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 双源知识层（knowledge）"):
        issues.append("缺标题「# 双源知识层（knowledge）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    d = data()
    src = d.get("sources") or []
    if len(src) != 6:
        issues.append(f"知识源数已变（{len(src)}）")
    auth = {}
    vis = {}
    for s in src:
        auth[s.get("authority")] = auth.get(s.get("authority"), 0) + 1
        vis[s.get("visibility")] = vis.get(s.get("visibility"), 0) + 1
    if auth != {"contract": 3, "reference": 3}:
        issues.append(f"权威分档已变：{auth}")
    if vis != {"public": 4, "internal": 2}:
        issues.append(f"可见性分档已变：{vis}")
    order = list(d.get("query_order") or [])
    ids = [s.get("id") for s in src]
    if sorted(order) != sorted(ids) or len(order) != 6:
        issues.append("query_order 不是 6 源的全排列")
    if "**6 条**" not in text or "contract 3 / reference 3" not in text:
        issues.append("未写 6 源与 3+3 分档")
    if "public 4 / internal 2" not in text:
        issues.append("未写可见性 4+2")
    if "**6**（全排列" not in text and "**6**" not in text:
        issues.append("未写 query_order 6")
    filt = str((d.get("cognition") or {}).get("filter_module") or "")
    if filt != "M23":
        issues.append(f"认知裁剪模块已变（{filt}）")
    if "**M23**" not in text:
        issues.append("未写 M23")
    usage = json.loads(USAGE.read_text(encoding="utf-8"))
    if int(usage.get("total") or 0) != 0:
        issues.append(f"频次台账 total 已变（{usage.get('total')}）")
    if "**total 0**" not in text:
        issues.append("未写 usage total 0")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py knowledge",
                "python scripts/nf.py knowledge lint",
                "python -m pytest desktop/tests/test_knowledge.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "先校验后写盘" not in text:
        issues.append("缺「先校验后写盘」纪律")
    if "不引入向量库" not in text:
        issues.append("缺「不引入向量库」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class KnowledgeDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_knowledge_matches_contract(self):
        self.assertEqual([], knowledge_issues(self.text), "知识层文档不满足契约")

    def test_sources_live(self):
        d = data()
        self.assertEqual(6, len(d["sources"]))
        self.assertEqual(6, len(d["query_order"]))
        self.assertEqual("M23", d["cognition"]["filter_module"])
        self.assertEqual(0, int(json.loads(USAGE.read_text(encoding="utf-8"))["total"]))

    def test_contract_catches_mutations(self):
        """变异自证：源数回退 / 分档回退 / 缺 M23 / total 回退 / 缺命令。"""
        old = self.text.replace("**6 条**", "**4 条**")
        self.assertTrue(any("6" in i or "未写" in i for i in knowledge_issues(old)))
        bad = self.text.replace("public 4 / internal 2", "public 5 / internal 1")
        self.assertTrue(any("可见性" in i for i in knowledge_issues(bad)))
        no_m = self.text.replace("**M23**", "M99")
        self.assertTrue(any("M23" in i for i in knowledge_issues(no_m)))
        no_u = self.text.replace("**total 0**", "**total 9**")
        self.assertTrue(any("total" in i for i in knowledge_issues(no_u)))
        no_cmd = self.text.replace("python scripts/nf.py knowledge lint", "巡检")
        self.assertTrue(any("lint" in i for i in knowledge_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_knowledge.md")


if __name__ == "__main__":
    unittest.main()
