#!/usr/bin/env python3
"""docs/bench.md 契约：执行结果跑分台文档必须「五维权重/用例/旗标与实现一致 + 端壳边界 + 复现」。

为什么必须有：本文是跑分台的用法规范——旧版只列 5 维名称不写权重（真源 core/bench.WEIGHTS）、
用例写 1 例（现 2 例）、run 旗标只提 3 个（现 5 个）；更重要的是它与**已退役的端壳 GUI 基准**
同名，不划边界就会被当成同一样东西（甚至被引去跑不存在的 GUI bench）。本轮补权重表、旗标表、
端壳边界、现状对照与复现口径，并把权重/用例数/子命令/端壳退役事实立成机检断言。

范围：只判本文与 bench 实现/套件/L3 事实自洽（不改评分机制）。同族判据：
test_governance_faces.py（bench 治理面）/ test_l3_frozen_contract.py（端壳退役）/
test_doc_hygiene.py / test_doc_examples.py（命令块）。
契约：⛔ 标识 + last-updated + 复核位、五维权重表（0.30/0.30/0.20/0.10/0.10）、
run 五旗标在册、用例套件 2 例、expected 两键、端壳边界（退役 / 同名不同物）、
check36 治理面消费、复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import bench  # noqa: E402

DOC = ROOT / "docs" / "bench.md"
NF = ROOT / "scripts" / "nf.py"
SUITE = ROOT / "desktop" / "tests" / "fixtures" / "benchmark" / "suite"
L3 = ROOT / "docs" / "L3_FROZEN.md"
CASES = ("p02-campus-emotion", "p03-western-cross")
FLAGS = ("--case", "--artifact", "--model", "--out", "--json")
SECTIONS = ("## 是什么", "## 怎么用", "## 边界", "## 现状对照", "## 复现与引用口径")
WEIGHTS = {"structure": 0.30, "traceability": 0.30, "closure": 0.20,
           "prose": 0.10, "selfcheck": 0.10}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"bench 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("bench 文档为空")
    return text


def bench_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 执行结果跑分台（bench）"):
        issues.append("缺标题「# 执行结果跑分台（bench）」")
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
    if dict(getattr(bench, "WEIGHTS", {})) != WEIGHTS:
        issues.append(f"实现权重已变：{bench.WEIGHTS}")
    for dim, weight in WEIGHTS.items():
        if dim not in text:
            issues.append(f"正文缺维度：{dim}")
        if format(weight, ".2f") not in text:
            issues.append(f"正文缺权重：{dim}={format(weight, '.2f')}")
    names = sorted(p.name for p in SUITE.iterdir() if p.is_dir())
    if names != sorted(CASES):
        issues.append(f"用例套件已变：{names}")
    if "2 例" not in text:
        issues.append("未写现行用例数（2 例）")
    for case in CASES:
        if case not in text:
            issues.append(f"正文缺用例：{case}")
    for key in ("min_total", "min_segments"):
        if key not in text:
            issues.append(f"缺用例判据键：{key}")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("bench",):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append("CLI 缺 bench 入口")
    for sub in ("run", "compare", "report"):
        if 'add_parser("' + sub + '"' not in nf:
            issues.append(f"bench 缺子命令：{sub}")
    for flag in FLAGS:
        if '"' + flag + '"' not in nf:
            issues.append(f"bench run 缺旗标：{flag}")
        if flag not in text:
            issues.append(f"正文缺旗标：{flag}")
    for marker in ("端壳", "退役", "同名不同物"):
        if marker not in text:
            issues.append(f"端壳边界缺要素：{marker}")
    if not L3.is_file():
        issues.append("缺 docs/L3_FROZEN.md")
    if "L3_FROZEN.md" not in text:
        issues.append("缺 L3_FROZEN 引用")
    if "check36" not in text:
        issues.append("缺 check36 治理面消费口径")
    for cmd in ("python scripts/nf.py bench run",
                "python scripts/nf.py bench compare",
                "python scripts/nf.py bench report"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不替代" not in text:
        issues.append("缺「不替代 verify 门禁」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class BenchDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_bench_matches_contract(self):
        self.assertEqual([], bench_issues(self.text), "bench 文档不满足契约")

    def test_weights_cases_flags_live(self):
        self.assertEqual(WEIGHTS, dict(bench.WEIGHTS))
        names = sorted(p.name for p in SUITE.iterdir() if p.is_dir())
        self.assertEqual(sorted(CASES), names)
        for case in CASES:
            data = json.loads((SUITE / case / "case.json").read_text(encoding="utf-8"))
            self.assertEqual({"min_total", "min_segments"}, set(data["expected"]))
        self.assertTrue((ROOT / "desktop" / "tests" / "test_governance_faces.py").is_file())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 权重漂移 / 用例回退 / 缺旗标 / 去端壳边界 / 缺命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in bench_issues(no_date)))
        old_w = self.text.replace("0.30", "0.25")
        self.assertTrue(any("权重" in i for i in bench_issues(old_w)))
        old_cases = self.text.replace("2 例", "1 例")
        self.assertTrue(any("2 例" in i or "用例" in i for i in bench_issues(old_cases)))
        no_flag = self.text.replace("--artifact", "--doc")
        self.assertTrue(any("--artifact" in i for i in bench_issues(no_flag)))
        no_bound = self.text.replace("同名不同物", "另一个").replace("端壳", "前端")
        self.assertTrue(any("端壳" in i for i in bench_issues(no_bound)))
        no_cmd = self.text.replace("python scripts/nf.py bench compare", "比对")
        self.assertTrue(any("bench compare" in i for i in bench_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_bench.md")


if __name__ == "__main__":
    unittest.main()
