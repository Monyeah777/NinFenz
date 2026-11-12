#!/usr/bin/env python3
"""docs/41_波C_C9_回合装载指针_v0 契约：v0 指针规格必须「标明已被 v1 接续 + 样例装配数与真源一致」。

为什么必须有：这是「回合装载指针 v0」的格式出处——但它在运行态已升级为**回合状态头 v1**
（round_header.py + 06 §11 + docs/42_M2）。记录若不说接续关系，读者会照着 v0 三区格式实现旧面；
更糟的是 §二 样例有两处笔误（「P30 default = 生存:M10 / 西幻:M22」——生存:M10 实际在 P60，
西幻:M22 应为官方核心 事件:M22），且装配数「24」与 P03 真源（27 槽位/去重 23）不符。

范围：只判本文与 P03 真源/v1 规范的接续自洽（不改 v0 字段定义本身）。同族判据：
test_round_header.py（v1 运行态）/ test_c7_record_contract.py（同类历史口径）/
test_doc_reachability.py / 06 §11（协议位真源）。
契约：标题 + 「v0 快照 + 已被 v1 接续」双状态、四段按序、指针格式字段齐、
P03 装配数（27 槽位 / 去重 23 = 核心 10 + 题材 13）与真源解析一致、
「事件:M22」正确且无「西幻:M22」、生存:M10 归属 P60、v1 三件引用件在场、复现命令在 CLI。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "41_波C_C9_回合装载指针_v0.md"
P03 = ROOT / "community" / "西幻生存领域包" / "pipelines" / "P03_西幻生存流管线.md"
MODS = ROOT / "community" / "西幻生存领域包" / "modules"
RHEAD = ROOT / "desktop" / "src" / "core" / "round_header.py"
RHEAD_DOC = ROOT / "docs" / "42_M2_回合状态头_v1.md"
RHEAD_TEST = ROOT / "desktop" / "tests" / "test_round_header.py"
AGENT = ROOT / "06_Agent执行协议.md"
SECTIONS = ("## 一、指针格式定义（v0）", "## 二、P03 西幻生存流回合样例",
            "## 三、v0 试点结论", "## 现状核对与复现口径")
FIELDS = ("回合指针 v0", "管线路径", "[常驻]", "[热区]", "[冷区]", "回合：")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"C9 指针文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("C9 指针文档为空")
    return text


def p03_stats() -> tuple:
    text = P03.read_text(encoding="utf-8")
    lists = [m.group(1) for m in re.finditer(r"default_modules: \[(.*?)\]", text)]
    slots = []
    for item in lists:
        slots.extend(part.strip() for part in item.split(",") if part.strip())
    proto = ROOT / "community" / "西幻生存领域包" / "protocol.yaml"
    core = re.search(r"core_modules:\s*\[(.*?)\]", proto.read_text(encoding="utf-8"))
    core_count = len([p for p in core.group(1).split(",") if p.strip()]) if core else 0
    return len(lists), len(slots), len(set(slots)), core_count


def c9_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 41 波C C9"):
        issues.append("缺标题「# 41 波C C9 · 回合装载指针 v0」")
    for marker in ("v0 试点规格", "已被 v1 接续", "回合状态头 v1"):
        if marker not in text:
            issues.append(f"缺状态口径：{marker}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("四段顺序不对")
    for field in FIELDS:
        if field not in text:
            issues.append(f"指针格式缺字段：{field}")
    layers, slots, distinct, core_count = p03_stats()
    if layers != 9:
        issues.append(f"P03 层数已变（{layers}）：样例核对需复核")
    if slots != 27:
        issues.append(f"P03 default 槽位已变（{slots}）：样例核对需复核")
    if distinct != 23:
        issues.append(f"P03 default 去重数已变（{distinct}）：样例核对需复核")
    if core_count != 12:
        issues.append(f"P03 core_modules 已变（{core_count}）：样例核对需复核")
    if "27 个槽位" not in text:
        issues.append("未写当前 default 槽位数（应写 27 个槽位）")
    if "23 件" not in text:
        issues.append("未写去重件数（23）")
    if "核心配套 **10 件**" not in text:
        issues.append("未写核心配套件数（10）")
    if "题材 **13 件**" not in text:
        issues.append("未写题材件数（13）")
    if "事件:M22" not in text:
        issues.append("P30 样例缺官方核心全限定名：事件:M22")
    if "西幻:M22" in text:
        issues.append("残留错误类别：西幻:M22（应为 事件:M22）")
    if "生存:M10" not in text:
        issues.append("缺 生存:M10（死亡重生）口径")
    if "P60" not in text:
        issues.append("未说明 生存:M10 归属 P60 层")
    for path in (RHEAD, RHEAD_DOC, RHEAD_TEST):
        if not path.is_file():
            issues.append(f"缺 v1 引用件：{path.relative_to(ROOT).as_posix()}")
    agent = AGENT.read_text(encoding="utf-8")
    if "回合状态头 v1" not in agent:
        issues.append("06 协议缺「回合状态头 v1」协议位")
    if "§11" not in text:
        issues.append("缺 06 §11 协议位引用")
    if "pipeline dryrun" not in text:
        issues.append("复现口径缺 pipeline dryrun")
    if "market community/西幻生存领域包" not in text:
        issues.append("复现口径缺 market 包清单命令")
    if "PASS 39" not in text:
        issues.append("历史数值 PASS 39 被改写（历史快照不应改写）")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class C9PointerContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_c9_matches_contract(self):
        self.assertEqual([], c9_issues(self.text), "C9 指针文档不满足契约")

    def test_p03_numbers_are_live(self):
        layers, slots, distinct, core_count = p03_stats()
        self.assertEqual((9, 27, 23, 12), (layers, slots, distinct, core_count))
        self.assertIn("27 个槽位", self.text)

    def test_v1_successor_artifacts_exist(self):
        for path in (RHEAD, RHEAD_DOC, RHEAD_TEST):
            self.assertTrue(path.is_file(), path)
        self.assertIn("§11", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：装配数漂移 / 错类别 / 去接续状态 / 缺现状核对段 / 缺复现命令。"""
        wrong = self.text.replace("27 个槽位", "24 个槽位")
        self.assertTrue(any("27 个槽位" in i for i in c9_issues(wrong)))
        bad_cat = self.text.replace("事件:M22", "西幻:M22")
        self.assertTrue(any("事件:M22" in i or "西幻:M22" in i for i in c9_issues(bad_cat)))
        no_v1 = self.text.replace("已被 v1 接续", "仍为现行")
        self.assertTrue(any("v1 接续" in i for i in c9_issues(no_v1)))
        no_sec = self.text.replace("## 现状核对与复现口径（2026-11-13）", "## 备注")
        self.assertTrue(any("缺段" in i for i in c9_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py pipeline dryrun", "检查管线")
        self.assertTrue(any("dryrun" in i for i in c9_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_c9.md")


if __name__ == "__main__":
    unittest.main()
