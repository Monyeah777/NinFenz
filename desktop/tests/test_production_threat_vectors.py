#!/usr/bin/env python3
"""生产平面威胁模型三面一致判据（NF-Final WP-03）。

三面 = `docs/production/THREAT_MODEL.md`（人读）· `protocol/boundaries.json`（边界登记）·
`results/production/threat_vectors.json`（机器向量）。判据：
1. 文档结构：§8.1/§8.2/§8.3 三张表在场，行数恰为 6/8/8，表头固定；
2. 边界：六条 B-01…B-06，id 唯一，`core.boundaries.validate` 零问题（代码件与文档件都在场）；
3. 向量：schema/编号集合/状态词表合法；每条 boundary 属六条之一；evidence 非空且路径在场；
   `enforced` 必须至少一条测试/门禁证据，`partial`/`planned` 必须写 `planned_gate`，
   `UNOBSERVABLE` 必须写 reason；
4. 交叉：文档行 ↔ 向量行一一对应（id 与状态一致），每条边界至少被一个威胁行引用；
5. 不越级声称：文档含「不承诺」段，禁用词只允许出现在否定语境；
6. 变异自证：删行/断证据/降状态证据/去 planned_gate/删边界/重复 id 六类注入必须红。
"""
import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import boundaries as B  # noqa: E402

DOC = ROOT / "docs" / "production" / "THREAT_MODEL.md"
BOUND = ROOT / "protocol" / "boundaries.json"
VEC = ROOT / "results" / "production" / "threat_vectors.json"

EXPECTED_BOUNDARIES = ("B-01", "B-02", "B-03", "B-04", "B-05", "B-06")
EXPECTED_STRIDE = tuple("NF-TH-%02d" % i for i in range(1, 9))
EXPECTED_FAILURE = tuple("NF-FM-%02d" % i for i in range(1, 9))
STATUS = {"enforced", "partial", "planned", "UNOBSERVABLE"}
GATES = {"G0", "G1", "G2", "G3", "G4", "G5"}
TEST_EVIDENCE = re.compile(r"^(desktop/tests/|scripts/|verify\.sh$)")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _json(path):
    return json.loads(_read(path))


def parse_tables(text):
    """→ [(header_cells, [row_cells...])]；只收标准 pipe 表。"""
    blocks, cur = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cur.append([c.strip() for c in s[1:-1].split("|")])
        else:
            if cur:
                blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    out = []
    for block in blocks:
        if len(block) >= 2 and all(re.fullmatch(r":?-{2,}:?", c) for c in block[1]):
            out.append((block[0], block[2:]))
    return out


def table_for(text, *musts):
    """取表头同时含全部 musts 的表 → (header, rows)；找不到返回 (None, None)。"""
    for header, rows in parse_tables(text):
        if all(m in header for m in musts):
            return header, rows
    return None, None


def boundary_ids(doc):
    return [str(e.get("id")) for e in doc.get("boundaries") or []]


def vector_issues(vec):
    """向量表判据（供正例与变异共用）。"""
    issues = []
    if vec.get("schema") != "nf-threat-vectors/1":
        return ["schema 不匹配（期望 nf-threat-vectors/1）"]
    if sorted(vec.get("boundaries") or []) != sorted(EXPECTED_BOUNDARIES):
        issues.append("boundaries 集合必须恰为 %s" % (EXPECTED_BOUNDARIES,))
    for group, expected in (("stride", EXPECTED_STRIDE), ("failure_matrix", EXPECTED_FAILURE)):
        rows = vec.get(group) or []
        ids = [str(r.get("id")) for r in rows if isinstance(r, dict)]
        if ids != list(expected):
            issues.append("%s 的 id 必须恰为 %s（实际 %s）" % (group, list(expected), ids))
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                issues.append("%s 含非对象行" % group)
                continue
            rid = str(row.get("id"))
            if rid in seen:
                issues.append("重复 id：%s" % rid)
            seen.add(rid)
            status = str(row.get("status"))
            if status not in STATUS:
                issues.append("%s 的 status 非法：%s" % (rid, status))
            if str(row.get("boundary")) not in EXPECTED_BOUNDARIES:
                issues.append("%s 的 boundary 不在六条边界内：%s" % (rid, row.get("boundary")))
            ev = row.get("evidence") or []
            if not ev:
                issues.append("%s 缺 evidence（威胁/失败行必须绑定证据）" % rid)
            for rel in ev:
                if not (ROOT / str(rel)).exists():
                    issues.append("%s 的 evidence 不在场：%s" % (rid, rel))
            if status == "enforced" and not any(TEST_EVIDENCE.match(str(x)) for x in ev):
                issues.append("%s 标 enforced 但缺测试/门禁证据：%s" % (rid, ev))
            if status in ("partial", "planned"):
                if str(row.get("planned_gate")) not in GATES:
                    issues.append("%s 标 %s 但缺合法 planned_gate" % (rid, status))
            if status == "UNOBSERVABLE" and not str(row.get("reason") or "").strip():
                issues.append("%s 标 UNOBSERVABLE 但缺 reason" % rid)
    return issues


class ProductionThreatModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc_text = _read(DOC)
        cls.bound = _json(BOUND)
        cls.vec = _json(VEC)
        cls.stride_header, cls.stride_rows = table_for(cls.doc_text, "类别", "威胁")
        cls.fail_header, cls.fail_rows = table_for(cls.doc_text, "攻击", "期望")
        cls.bound_header, cls.bound_rows = table_for(cls.doc_text, "边界", "内容")

    def test_doc_structure(self):
        for sec in ("## 信任边界", "## STRIDE 矩阵", "## 关键失败矩阵",
                    "## 状态词表与证据规则", "## 复核命令", "## 不承诺"):
            self.assertIn(sec, self.doc_text, "缺章节：" + sec)
        self.assertIsNotNone(self.stride_header, "缺 STRIDE 表")
        self.assertIsNotNone(self.fail_header, "缺失败矩阵表")
        self.assertIsNotNone(self.bound_header, "缺信任边界表")
        self.assertEqual(list(EXPECTED_STRIDE),
                         [r[0] for r in self.stride_rows], "STRIDE 必须恰为 8 行")
        self.assertEqual(list(EXPECTED_FAILURE),
                         [r[0] for r in self.fail_rows], "失败矩阵必须恰为 8 行")
        self.assertEqual(list(EXPECTED_BOUNDARIES),
                         [r[0] for r in self.bound_rows], "信任边界必须恰为 6 行")

    def test_boundaries_registry(self):
        self.assertEqual("nf-boundaries/1", self.bound.get("schema"))
        self.assertEqual(list(EXPECTED_BOUNDARIES), boundary_ids(self.bound),
                         "protocol/boundaries.json 必须恰为六条且顺序稳定")
        self.assertEqual([], B.validate(self.bound.get("boundaries") or [], str(ROOT)),
                         "边界登记的代码件/文档件必须都在场")

    def test_vectors(self):
        self.assertEqual([], vector_issues(self.vec))

    def test_doc_and_vectors_cross_consistent(self):
        for group, rows in (("stride", self.stride_rows), ("failure_matrix", self.fail_rows)):
            vec_rows = {str(r.get("id")): str(r.get("status"))
                        for r in self.vec.get(group) or []}
            for cells in rows:
                rid = cells[0]
                self.assertIn(rid, vec_rows, "文档行未进向量表：" + rid)
                doc_status = cells[-1].split("（")[0].strip()
                self.assertEqual(vec_rows[rid], doc_status,
                                 "%s 文档状态 %r ≠ 向量 %r" % (rid, doc_status, vec_rows[rid]))

    def test_boundary_coverage(self):
        used = {str(r.get("boundary")) for group in ("stride", "failure_matrix")
                for r in self.vec.get(group) or []}
        self.assertEqual(set(EXPECTED_BOUNDARIES), used, "每条信任边界必须至少被一行威胁引用")

    def test_no_overclaim(self):
        self.assertIn("## 不承诺", self.doc_text)
        for word in ("不可抵赖", "合规", "认证"):
            for line in self.doc_text.splitlines():
                if word in line:
                    self.assertTrue(any(m in line
                                        for m in ("不承诺", "不声称", "不写", "非", "不作为")),
                                    "禁用词 %r 未在否定语境：%s" % (word, line.strip()))

    def test_mutation_self_proof(self):
        dropped = copy.deepcopy(self.vec)
        dropped["stride"] = [r for r in dropped["stride"] if r["id"] != "NF-TH-04"]
        self.assertTrue(vector_issues(dropped), "删威胁行必须红")

        bad_evidence = copy.deepcopy(self.vec)
        bad_evidence["stride"][0]["evidence"] = ["desktop/tests/nonexistent_zzz.py"]
        self.assertTrue(vector_issues(bad_evidence), "证据不在场必须红")

        weak_status = copy.deepcopy(self.vec)
        weak_status["stride"][2]["evidence"] = ["docs/verification-cards.md"]
        self.assertTrue(vector_issues(weak_status), "enforced 缺测试证据必须红")

        no_gate = copy.deepcopy(self.vec)
        no_gate["stride"][1].pop("planned_gate", None)
        self.assertTrue(vector_issues(no_gate), "partial 缺 planned_gate 必须红")

        no_boundary = copy.deepcopy(self.vec)
        no_boundary["boundaries"] = ["B-01"]
        self.assertTrue(vector_issues(no_boundary), "边界集合缺失必须红")

        dup = copy.deepcopy(self.vec)
        dup["failure_matrix"].append(copy.deepcopy(dup["failure_matrix"][0]))
        self.assertTrue(vector_issues(dup), "重复 id 必须红")


if __name__ == "__main__":
    unittest.main()
