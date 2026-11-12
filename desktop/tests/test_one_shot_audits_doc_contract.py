#!/usr/bin/env python3
"""docs/ccos/one-shot-audits.md 契约：文档表必须与孤儿棘轮冻结集合逐项一致（且脚本在场）。

为什么必须有：这份清单是「历史证据不删」的唯一依据——它列的一次性审计脚本必须真的在 scripts/ 下，
且必须与 test_script_orphans.ORPHANS 冻结集合逐项相等；漏一个，孤儿棘轮会把已登记脚本当「新的孤儿」
判红；多一个，说明文档在给不存在的证据记账。本轮补最后更新位、现状对照与复现口径，并把两侧
（文档表 vs ORPHANS）做成双向活绑定，同时核实移出件已获判据入口这一理由。

本判据刻意不硬编码脚本名：名字从文档表解析（scripts/xxx.py），否则测试自身会给这些脚本制造
「有引用」，触发孤儿棘轮要求从 ORPHANS 删条目（等价于把证据清单清零）。

范围：只判本文与 scripts/孤儿棘轮/判据入口事实自洽（不删脚本）。同族判据：
test_script_orphans.py（5 例）/ test_third_party_notices_contract.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、5 行脚本、ORPHANS == 表内 5 名、移出件有判据入口且不在 ORPHANS、
5 例判据、现状对照 + 复现三命令。
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORPHAN_TEST = ROOT / "desktop" / "tests" / "test_script_orphans.py"

DOC = ROOT / "docs" / "ccos" / "one-shot-audits.md"
MOVED_OUT = "gen_third_party_notices"
SECTIONS = ("## 为什么不删", "## 现状对照", "## 复现与引用口径")
ROW = re.compile(r"scripts/([a-z0-9_]+)\.py")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"一次性审计清单不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("一次性审计清单为空")
    return text


def doc_scripts(text: str) -> list:
    seen = []
    for name in ROW.findall(text):
        if name not in seen:
            seen.append(name)
    return seen


def frozen() -> frozenset:
    spec = importlib.util.spec_from_file_location("_orphan_test", ORPHAN_TEST)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_orphan_test"] = mod
    spec.loader.exec_module(mod)
    return frozenset(mod.ORPHANS)


def orphan_cases() -> int:
    return ORPHAN_TEST.read_text(encoding="utf-8").count("def test")


def moved_out_has_entry() -> bool:
    for path in (ROOT / "desktop" / "tests").glob("*.py"):
        if MOVED_OUT in path.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def audit_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 一次性审计脚本"):
        issues.append("缺标题「# 一次性审计脚本（历史证据，不删）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    names = doc_scripts(text)
    if len(names) != 5:
        issues.append(f"文档表脚本数应 5（实测 {len(names)}）：{names}")
    for name in names:
        if not (ROOT / "scripts" / (name + ".py")).is_file():
            issues.append(f"脚本不存在：scripts/{name}.py")
    fo = frozen()
    if frozenset(names) != fo:
        issues.append(f"ORPHANS 与文档表不一致：doc={sorted(names)} frozen={sorted(fo)}")
    if "5 个" not in text:
        issues.append("未写「5 个」")
    if MOVED_OUT in fo:
        issues.append(f"移出件仍在 ORPHANS：{MOVED_OUT}")
    if not moved_out_has_entry():
        issues.append(f"移出件缺判据入口：{MOVED_OUT}")
    if MOVED_OUT not in text:
        issues.append("未写移出件理由")
    bad_moved = [ln for ln in text.splitlines()
                 if MOVED_OUT in ln and ("在 ORPHANS" in ln or "仍在冻结" in ln)]
    if bad_moved:
        issues.append(f"移出件被写成仍在 ORPHANS：{MOVED_OUT}")
    n_cases = orphan_cases()
    if n_cases != 5:
        issues.append(f"test_script_orphans 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写判据数（{n_cases} 例）")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    run_sec = text[text.find("## 复现与引用口径"):]
    if "python scripts/" not in run_sec:
        issues.append("复现口径缺「python scripts/」审计命令")
    if "python -m pytest desktop/tests/test_script_orphans.py" not in run_sec:
        issues.append("复现口径缺孤儿棘轮判据命令")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class OneShotAuditsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_audits_match_contract(self):
        self.assertEqual([], audit_issues(self.text), "一次性审计清单不满足契约")

    def test_doc_table_matches_frozen_list(self):
        names = doc_scripts(self.text)
        for name in names:
            self.assertTrue((ROOT / "scripts" / (name + ".py")).is_file(), name)
        self.assertEqual(frozenset(names), frozen())
        self.assertTrue(moved_out_has_entry())
        self.assertNotIn(MOVED_OUT, frozen())
        self.assertEqual(5, orphan_cases())

    def test_contract_catches_mutations(self):
        """变异自证：多一行 / 数目回退 / 移出件回潮 / 缺命令。"""
        extra = self.text + "\n| scripts/fake_audit.py | x | y |\n"
        self.assertTrue(any("文档表脚本数" in i or "不一致" in i
                            for i in audit_issues(extra)))
        old_n = self.text.replace("5 个", "4 个")
        self.assertTrue(any("5 个" in i for i in audit_issues(old_n)))
        moved_back = self.text + "\n移出件 gen_third_party_notices 在 ORPHANS。\n"
        self.assertTrue(any("移出件" in i for i in audit_issues(moved_back)))
        no_cmd = self.text.replace(
            "python -m pytest desktop/tests/test_script_orphans.py", "跑判据")
        self.assertTrue(any("孤儿棘轮" in i for i in audit_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_oneshot.md")


if __name__ == "__main__":
    unittest.main()
