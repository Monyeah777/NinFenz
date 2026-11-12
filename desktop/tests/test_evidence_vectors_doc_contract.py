#!/usr/bin/env python3
"""docs/ccos/evidence-vectors-v0.md 契约：28 条结构/分布/覆盖表与数据一致 + 围栏合法。

为什么必须有：这是跨语言复验的「锚点文档」——第三方只看这份 JSON 与本文。本轮修的三处都是实际缺陷：
① 两个代码块围栏写成单反引号（围栏不成立，写「样例」却渲染成行内）；② 样例 count 写 15（实 28）；
③ 覆盖表漏 3 条 decision 向量（表只列 25，实 28）。
这类「样例与数据不同步」会让第三方照着错样例实现。

范围：只判本文与向量集数据/生成器/测试事实自洽（不改向量）。同族判据：
test_evidence_vectors.py（8 例）/ test_ccos_abi_docs.py（文档数字守卫）/
test_doc_hygiene.py / test_doc_examples.py。
契约：⛔ 标识 + last-updated + 复核位、json/bash 三反引号围栏成立（不得有单反引号围栏）、
样例 count 28、覆盖表含全部 28 个 id、分布 18/4/6、8 项判据、现状对照与复现三命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BT = chr(96).encode("ascii").decode()
FENCE = BT * 3

DOC = ROOT / "docs" / "ccos" / "evidence-vectors-v0.md"
VECTORS = ROOT / "results" / "ccos" / "evidence_verdict_vectors.json"
GEN = ROOT / "scripts" / "evidence_vectors.py"
TEST = ROOT / "desktop" / "tests" / "test_evidence_vectors.py"
SECTIONS = ("## 是什么", "## 产物形状", "## 28 条向量覆盖什么", "## 第三方怎么用",
            "## 本仓怎么生成与复核", "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"向量集文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("向量集文档为空")
    return text


def vectors() -> dict:
    return json.loads(VECTORS.read_text(encoding="utf-8"))


def distribute(ids: list) -> dict:
    out = {"receipts": 0, "attest": 0, "bundle": 0}
    for vid in ids:
        if vid.startswith("receipts_"):
            out["receipts"] += 1
        elif vid.startswith("attest_"):
            out["attest"] += 1
        else:
            out["bundle"] += 1
    return out


def case_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def vector_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 证据判定向量集 v0"):
        issues.append("缺标题「# 证据判定向量集 v0」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核（2026-11-13）" not in text:
        issues.append("缺「复核（2026-11-13）」位")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    data = vectors()
    ids = [v["id"] for v in data["vectors"]]
    if int(data["count"]) != 28 or len(ids) != 28:
        issues.append(f"向量集条数已变（count={data['count']}, len={len(ids)}）")
    if data.get("schema") != "nf-evidence-vectors/1":
        issues.append("向量集 schema 已变")
    if '"count": 28' not in text:
        issues.append("样例 count 未写 28")
    for vid in ids:
        if vid not in text:
            issues.append(f"覆盖表缺向量：{vid}")
    dist = distribute(ids)
    if dist != {"bundle": 18, "receipts": 4, "attest": 6}:
        issues.append(f"形态分布已变：{dist}")
    for label in ("18", "4", "6"):
        if label not in text:
            issues.append(f"分布缺数字：{label}")
    for line in text.splitlines():
        s = line.strip()
        if s in (BT + "json", BT + "bash", BT):
            issues.append(f"存在单反引号围栏行：{s}")
    if FENCE + "json" not in text:
        issues.append("缺 json 三反引号围栏")
    if FENCE + "bash" not in text:
        issues.append("缺 bash 三反引号围栏")
    for vid in ("decision_ok", "decision_policy_swap", "decision_strip"):
        if vid not in text:
            issues.append(f"覆盖表缺 decision 向量：{vid}")
    n_cases = case_count()
    if n_cases != 8:
        issues.append(f"test_evidence_vectors 例数已变（{n_cases}）")
    if str(n_cases) + " 项" not in text:
        issues.append(f"未写判据数（{n_cases} 项）")
    if not GEN.is_file():
        issues.append("缺生成器 scripts/evidence_vectors.py")
    for cmd in ("python scripts/evidence_vectors.py --check",
                "python scripts/nf.py evidence bench",
                "python -m pytest desktop/tests/test_evidence_vectors.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class EvidenceVectorsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_vectors_doc_matches_contract(self):
        self.assertEqual([], vector_issues(self.text), "向量集文档不满足契约")

    def test_vectors_live(self):
        data = vectors()
        ids = [v["id"] for v in data["vectors"]]
        self.assertEqual(28, int(data["count"]))
        self.assertEqual(28, len(ids))
        self.assertEqual(28, len(set(ids)))
        self.assertEqual({"bundle": 18, "receipts": 4, "attest": 6}, distribute(ids))
        self.assertEqual(8, case_count())

    def test_contract_catches_mutations(self):
        """变异自证：样例 count 回退 15 / 单反引号围栏 / 覆盖表缺 decision / 缺复核位。"""
        old_count = self.text.replace('"count": 28', '"count": 15')
        self.assertTrue(any("count" in i for i in vector_issues(old_count)))
        bad_fence = self.text.replace(FENCE + "json", BT + "json", 1)
        self.assertTrue(any("围栏" in i for i in vector_issues(bad_fence)))
        no_decision = self.text.replace("decision_policy_swap", "某向量")
        self.assertTrue(any("decision_policy_swap" in i
                            for i in vector_issues(no_decision)))
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in vector_issues(no_date)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_vectors.md")


if __name__ == "__main__":
    unittest.main()
