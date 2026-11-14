#!/usr/bin/env python3
"""docs/ccos/isomorphism-matrix.md 契约：矩阵说明档必须与矩阵数据件逐行一致 + 层数措辞正确。

为什么必须有：这份档是「判定细节」——每层判什么、放哪个测试、怎么被打死。它的可信度依赖三条活绑定：
① covered 9 行与文档判据表 9 个层名一一对应；② 每行 6 字段齐（layer/module/test/how/kill_module/
kill_test）；③ 常驻判据 11 例。本轮修的真实缺陷是文末边界把「9 层 / 9 条判据」写成「5 条」，属于
最容易被忽略的**结论性措辞漂移**。

范围：只判本文与矩阵/测试事实自洽（不改矩阵）。同族判据：
test_isomorphism_matrix.py（11 例）/ test_dual_core_invariants_contract.py（总档）/
test_doc_hygiene.py / test_doc_examples.py。
契约：落款复核位、判据表 9 个层名、矩阵 covered 9/missing 0、kill_test 全在文、11 例判据、
「9 条判据」措辞（9 层/9 条）、现状对照 + 复现口径、与 dual-core 互链。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "isomorphism-matrix.md"
MATRIX = ROOT / "desktop" / "tests" / "fixtures" / "isomorphism_matrix.json"
ISO_TEST = ROOT / "desktop" / "tests" / "test_isomorphism_matrix.py"
CORE_DOC = ROOT / "docs" / "ccos" / "dual-core-invariants.md"
SECTIONS = ("## 为什么需要它", "## 判据表", "## 缺失层", "## 现状对照", "## 怎么跑",
            "## 复现与引用口径", "## 边界")
LAYERS = ("时相", "身份", "观测", "语义", "负空间", "授权", "资源", "对抗", "自省")
FIELDS = ("layer", "module", "test", "how", "kill_module", "kill_test")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"矩阵说明档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("矩阵说明档为空")
    return text


def matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def iso_cases() -> int:
    return ISO_TEST.read_text(encoding="utf-8").count("def test")


def matrix_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 同构判据矩阵 v0"):
        issues.append("缺标题「# 同构判据矩阵 v0（九双生层）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "最后更新：2026-11-13" not in text:
        issues.append("缺「最后更新：2026-11-13」位")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    data = matrix()
    rows = data.get("covered") or []
    if len(rows) != 9:
        issues.append(f"矩阵覆盖行数已变（{len(rows)}）")
    if data.get("missing"):
        issues.append(f"矩阵出现缺失行（{data.get('missing')}）")
    letters = {str(r.get("layer")) for r in rows}
    if letters != set(LAYERS):
        issues.append(f"矩阵层集合已变：{sorted(letters)}")
    for layer in LAYERS:
        if layer not in text:
            issues.append(f"判据表缺层：{layer}")
    for row in rows:
        for key in FIELDS:
            if not str(row.get(key) or "").strip():
                issues.append(f"矩阵行缺字段 {key}：{row.get('layer')}")
        kill = str(row.get("kill_test") or "")
        if kill and kill not in text:
            issues.append(f"判据表缺变异测试：{kill}")
    if "9 覆盖 / 0 缺失" not in text:
        issues.append("状态行未写「9 覆盖 / 0 缺失」")
    if "**9 条判据只说明这 9 个层**" not in text:
        issues.append("边界措辞未写「9 条判据 / 9 个层」（旧版误写 5）")
    if "5 条判据" in text:
        issues.append("仍残留「5 条判据」旧措辞")
    n_cases = iso_cases()
    if n_cases != 11:
        issues.append(f"test_isomorphism_matrix 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写常驻判据例数（{n_cases} 例）")
    for cmd in ("python -m pytest desktop/tests/test_isomorphism_matrix.py",
                "python -m pytest desktop/tests/test_dual_core_invariants_contract.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "dual-core-invariants.md" not in text:
        issues.append("缺与总档的互链")
    if not CORE_DOC.is_file():
        issues.append("缺 docs/ccos/dual-core-invariants.md")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class IsomorphismMatrixDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_matrix_doc_matches_contract(self):
        self.assertEqual([], matrix_issues(self.text), "矩阵说明档不满足契约")

    def test_matrix_live(self):
        data = matrix()
        self.assertEqual(9, len(data["covered"]))
        self.assertFalse(data.get("missing"))
        for row in data["covered"]:
            for key in FIELDS:
                self.assertTrue(str(row.get(key) or "").strip(), key)
        self.assertEqual(11, iso_cases())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 边界回退 5 / 缺层 / 缺变异测试名 / 缺例数 / 缺命令。"""
        no_date = self.text.replace("最后更新：2026-11-13", "最后更新：2026-01-01")
        self.assertTrue(any("最后更新：2026-11-13" in i
                            for i in matrix_issues(no_date)))
        old5 = self.text.replace("**9 条判据只说明这 9 个层**", "5 条判据只说明这 5 个层")
        self.assertTrue(any("9 条判据" in i or "5 条判据" in i
                            for i in matrix_issues(old5)))
        no_layer = self.text.replace("负空间", "空间")
        self.assertTrue(any("负空间" in i for i in matrix_issues(no_layer)))
        no_kill = self.text.replace("test_authority_check_can_be_killed", "某变异")
        self.assertTrue(any("test_authority_check_can_be_killed" in i
                            for i in matrix_issues(no_kill)))
        old_n = self.text.replace("11 例", "9 例")
        self.assertTrue(any("例数" in i or "11" in i for i in matrix_issues(old_n)))
        no_cmd = self.text.replace("python -m pytest desktop/tests/test_isomorphism_matrix.py",
                                   "跑矩阵")
        self.assertTrue(any("test_isomorphism_matrix.py" in i
                            for i in matrix_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_matrix.md")


if __name__ == "__main__":
    unittest.main()
