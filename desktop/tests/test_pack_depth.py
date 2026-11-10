"""方法包深度判据：每个证据类目都必须有真实判据面（第 2026-11-10 批）。

为什么必须有：「11 个域 / 65 动作 / 31 证据类目」只证明清单够宽；
一个域到底做没做到深处，取决于它的每个证据类目是否有判据在看。
本件把「每域每类目 → 一个真实存在的判据模块」变成硬约束：缺一条就红。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
PACKS = ROOT / "protocol" / "method_packs"
DOC = ROOT / "docs" / "ccos" / "method-packs-v0.md"

MIN_MOVES = 5
MIN_STANDARDS = 2
MIN_FAILURES = 3


def pack_files() -> list:
    return sorted(p for p in PACKS.glob("*.json") if p.name != "index.json")


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def depth_issues(doc: dict, root: Path = ROOT) -> list:
    """单包深度问题（纯函数，便于变异自证）。"""
    issues = []
    pid = str(doc.get("id") or "?")
    moves = doc.get("expert_moves") or []
    standards = doc.get("evidence_standards") or []
    failures = doc.get("common_failures") or []
    judges = doc.get("judges") or {}
    if len(moves) < MIN_MOVES:
        issues.append(f"{pid} 动作数 {len(moves)} < {MIN_MOVES}")
    if len(standards) < MIN_STANDARDS:
        issues.append(f"{pid} 证据类目 {len(standards)} < {MIN_STANDARDS}")
    if len(failures) < MIN_FAILURES:
        issues.append(f"{pid} 常见失败 {len(failures)} < {MIN_FAILURES}")
    if not (doc.get("runnable") or []):
        issues.append(f"{pid} 无 runnable 入口")
    kinds = [str(s.get("claim_kind") or "") for s in standards]
    for kind in kinds:
        rel = judges.get(kind)
        if not rel:
            issues.append(f"{pid} 的 {kind} 类目没有判据（judges 缺条）")
            continue
        if not (root / str(rel)).is_file():
            issues.append(f"{pid} 的 {kind} 判据不存在：{rel}")
    extra = [k for k in judges if k not in kinds]
    if extra:
        issues.append(f"{pid} 的 judges 有多余类目：{extra}")
    return issues


class PackDepthTest(unittest.TestCase):
    def test_every_pack_covers_all_claim_kinds_with_real_judges(self):
        bad = []
        for p in pack_files():
            bad.extend(depth_issues(load(p)))
        self.assertEqual([], bad, "方法包深度不足：" + "；".join(bad[:5]))

    def test_depth_scale_is_not_trivial(self):
        """规模下限：防止有人用 1 动作 1 类目的空壳包凑数。"""
        packs = [load(p) for p in pack_files()]
        self.assertGreaterEqual(len(packs), 11, "域数少于 11")
        kinds = sum(len(p.get("evidence_standards") or []) for p in packs)
        self.assertGreaterEqual(kinds, 31, "证据类目总数少于 31")

    def test_doc_lists_every_pack(self):
        text = DOC.read_text(encoding="utf-8")
        missing = [load(p)["id"] for p in pack_files() if load(p)["id"] not in text]
        self.assertEqual([], missing, "文档缺这些域：" + ",".join(missing))

    def test_depth_issues_catch_broken_pack(self):
        """变异自证：缺判据 / 悬空判据 / 类目与判据错配 三种都必须报。"""
        good = load(pack_files()[0])
        kind = str(good["evidence_standards"][0]["claim_kind"])
        bad = json.loads(json.dumps(good))
        bad["judges"].pop(kind)
        self.assertTrue(depth_issues(bad), "缺判据必须报")
        bad2 = json.loads(json.dumps(good))
        bad2["judges"][kind] = "desktop/tests/definitely_missing_judge.py"
        self.assertTrue(depth_issues(bad2), "悬空判据必须报")
        bad3 = json.loads(json.dumps(good))
        bad3["judges"]["no-such-claim-kind"] = "desktop/tests/test_audit.py"
        self.assertTrue(depth_issues(bad3), "多余类目必须报")


if __name__ == "__main__":
    unittest.main()
