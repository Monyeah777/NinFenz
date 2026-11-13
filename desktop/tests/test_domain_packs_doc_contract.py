#!/usr/bin/env python3
"""docs/domain-packs.md 契约：域包文档必须「100 包/1200 细分/标准目录/绑定/空壳台账与真源一致」。

为什么必须有：这份文档是「100 类域包工程」的结构口径来源——包数、细分、标准目录覆盖、双锚绑定、
空壳台账，任何一项漂移都会让「覆盖面 ≠ 能力面」被误读成实际能力。本轮修三处陈旧：可达标准
330→332、不可达 40→38、绑定「2400 条」→ 1200 条记录（2400 锚位）；并补「公开仓 domain specs
显示 0 属预期（规格在内部档案）」这一可见性说明。本判据把包数、细分、密度下限、目录统计
（条数/机构/层分布/可达/依赖边）、绑定记录数、空壳基线、域码段分布全部活绑定。

范围：只判本文与 domain_packs/standards_catalog/standards_binding/shell_ledger 事实自洽
（不改域包）。同族判据：test_domain_pack.py / test_domain_pack_render.py /
test_ai_domain_closure.py / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、100 包与 1200 细分、密度下限、目录 370/194/332/38/206、
绑定 1200 记录 + 2400 锚位、空壳 73 包 36 处 2628、六段包数、现状对照 + 复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import shell_ledger  # noqa: E402

DOC = ROOT / "docs" / "domain-packs.md"
PACKS = ROOT / "protocol" / "domain_packs.json"
CATALOG = ROOT / "protocol" / "standards_catalog.json"
BINDING = ROOT / "protocol" / "standards_binding.json"
SECTIONS = ("## 是什么", "## 机验率", "## 可扩展标准对齐", "## 命令", "## 已建 100 包",
            "## 现状对照", "## 复现与引用口径", "## 度量族", "## 边界（不宣称）", "## 派生空壳台账")
SEGMENTS = {"A": 14, "B": 18, "C": 18, "D": 20, "E": 20, "F": 10}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"域包文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("域包文档为空")
    return text


def packs() -> dict:
    return json.loads(PACKS.read_text(encoding="utf-8"))


def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def binding() -> dict:
    return json.loads(BINDING.read_text(encoding="utf-8"))


def domain_issues(text: str) -> list:
    issues = []
    if not text.startswith("# AI 品类域包"):
        issues.append("缺标题「# AI 品类域包（domain packs）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    dp = packs()
    if dp.get("count") != 100 or len(dp.get("packs") or []) != 100:
        issues.append(f"包数已变（count={dp.get('count')}）")
    if dp.get("subdivisions_total") != 1200:
        issues.append(f"细分总数已变（{dp.get('subdivisions_total')}）")
    if "100 包" not in text or "1200" not in text:
        issues.append("正文缺 100 包 / 1200 细分")
    if abs(float(dp.get("concept_density_min") or 0) - 1.2647) > 1e-6:
        issues.append(f"密度下限已变（{dp.get('concept_density_min')}）")
    if "1.2647" not in text:
        issues.append("未写密度下限 1.2647")
    cov = catalog().get("coverage") or {}
    want = {"standards": 370, "reachable": 332, "unreachable": 38,
            "depends_edges": 206, "bodies": 194}
    for k, v in want.items():
        if int(cov.get(k) or 0) != v:
            issues.append(f"目录统计 {k} 已变（{cov.get(k)}）")
    if "370" not in text or "332" not in text or "206" not in text:
        issues.append("正文缺目录统计（370/332/206）")
    for stale in ("330 条本机可达", "不可达 40 条"):
        if stale in text:
            issues.append(f"仍残留陈旧说法：{stale}")
    b = binding()
    if int(b.get("bindings_total") or 0) != 1200:
        issues.append(f"绑定记录数已变（{b.get('bindings_total')}）")
    if "1200 条绑定记录" not in text or "2400" not in text:
        issues.append("未写 1200 条记录 / 2400 锚位")
    baseline = getattr(shell_ledger, "BASELINE", {})
    if baseline.get("packs_with_shell") != 73:
        issues.append(f"空壳包数基线已变（{baseline.get('packs_with_shell')}）")
    if "73/100 包有壳" not in text:
        issues.append("未写空壳 73/100")
    if "2628" not in text:
        issues.append("未写空壳命中 2628")
    seg = {}
    for p in dp["packs"]:
        head = str(p.get("code") or "")[:1]
        seg[head] = seg.get(head, 0) + 1
    if dict(seg) != SEGMENTS:
        issues.append(f"段分布已变：{sorted(seg.items())}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("domain shells --json", "output verify", "output meter"):
        if ("nf " + cmd) not in text and ("nf.py " + cmd) not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "domain specs" not in text:
        issues.append("缺 domain specs 可见性说明")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class DomainPacksDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_domain_packs_matches_contract(self):
        self.assertEqual([], domain_issues(self.text), "域包文档不满足契约")

    def test_data_live(self):
        dp = packs()
        self.assertEqual(100, dp["count"])
        self.assertEqual(1200, dp["subdivisions_total"])
        cov = catalog()["coverage"]
        self.assertEqual(332, cov["reachable"])
        self.assertEqual(38, cov["unreachable"])
        self.assertEqual(206, cov["depends_edges"])
        self.assertEqual(1200, int(binding()["bindings_total"]))
        self.assertEqual(73, shell_ledger.BASELINE["packs_with_shell"])
        seg = {}
        for p in dp["packs"]:
            head = str(p["code"])[:1]
            seg[head] = seg.get(head, 0) + 1
        self.assertEqual(SEGMENTS, seg)

    def test_contract_catches_mutations(self):
        """变异自证：可达数回退 / 绑定数回退 / 空壳回退 / 缺命令 / 缺可见性说明。"""
        back = self.text.replace("332", "330")
        self.assertTrue(any("332" in i or "目录统计" in i for i in domain_issues(back)))
        old_b = self.text.replace("1200 条绑定记录", "2400 条绑定")
        self.assertTrue(any("1200 条记录" in i for i in domain_issues(old_b)))
        old_s = self.text.replace("73/100 包有壳", "70/100 包有壳")
        self.assertTrue(any("73/100" in i for i in domain_issues(old_s)))
        no_cmd = self.text.replace("nf.py output verify", "输出机检")
        self.assertTrue(any("output verify" in i for i in domain_issues(no_cmd)))
        no_spec = self.text.replace("domain specs", "规格命令")
        self.assertTrue(any("domain specs" in i for i in domain_issues(no_spec)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_domain.md")


if __name__ == "__main__":
    unittest.main()
