#!/usr/bin/env python3
"""docs/ccos/evidence-bundle-v0.md 契约：判定顺序/矩阵/向量/判据数与实现一致。

为什么必须有：这份规范是「给外部人一个文件就能验」的承诺——判定顺序、fail-closed 口径、攻击矩阵
条数、向量集条数、两套实现同判，任何一处漂移都会让读者按错的检查清单复验。本轮修复的真实缺陷是
**跨段数字失同步**（三形态表「10 条全判」实为 13 条；攻击矩阵「25 种」实为 38 条）——正是这类
跨段不一致最难靠人眼发现，故把四处数字全部活绑定。

范围：只判本文与 evidence 实现/数据/测试事实自洽（不改判定）。同族判据：
test_evidence.py（66 例）/ test_evidence_vectors.py（8 例）/ test_ccos_abi_docs.py（向量数守卫）/
test_doc_hygiene.py / test_doc_examples.py。
契约：⛔ 标识 + last-updated + 复核位、判定表 13 条（1–13 含 8b）、三形态 13 条全判、
攻击矩阵 38 条（_bench_run 恰 38 用例）、向量集 28 条、66+8 项判据、容器安全第 13 条、
现状对照与复现四命令。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "evidence-bundle-v0.md"
EVID = ROOT / "desktop" / "src" / "core" / "evidence.py"
TEST_EV = ROOT / "desktop" / "tests" / "test_evidence.py"
TEST_VEC = ROOT / "desktop" / "tests" / "test_evidence_vectors.py"
VECTORS = ROOT / "results" / "ccos" / "evidence_verdict_vectors.json"
NF = ROOT / "scripts" / "nf.py"
SECTIONS = ("## 是什么", "## 布局", "## 判定", "## 三种可验形态", "## 怎么用",
            "## 跨语言一致性", "## 判据（可证）", "## 攻击矩阵基准", "## 现状对照",
            "## 复现与引用口径", "## 与既有验证器的关系")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"证据包文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("证据包文档为空")
    return text


def bench_cases() -> int:
    return len(re.findall(r"_bench_run\(rows, ", EVID.read_text(encoding="utf-8")))


def count_cases(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("def test")


def vectors() -> dict:
    return json.loads(VECTORS.read_text(encoding="utf-8"))


def bundle_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 证据包 v0"):
        issues.append("缺标题「# 证据包 v0（evidence bundle）」")
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
    for n in range(1, 14):
        if ("| " + str(n) + " |") not in text:
            issues.append(f"判定表缺序号：{n}")
    if "上面 **13 条**全判" not in text:
        issues.append("三形态表未写 13 条全判")
    n_bench = bench_cases()
    if n_bench != 38:
        issues.append(f"攻击矩阵用例数已变（{n_bench}）")
    if "**38 条**已知攻击" not in text:
        issues.append("攻击矩阵小节未写 38 条")
    n_vec = int(vectors()["count"])
    if n_vec != 28:
        issues.append(f"向量集已变（{n_vec}）")
    if "**28 条**" not in text:
        issues.append("未写向量集 28 条")
    n_ev = count_cases(TEST_EV)
    n_vex = count_cases(TEST_VEC)
    if n_ev != 66:
        issues.append(f"test_evidence 例数已变（{n_ev}）")
    if n_vex != 8:
        issues.append(f"test_evidence_vectors 例数已变（{n_vex}）")
    for label in ("66 项", "8 项"):
        if label not in text:
            issues.append(f"未写判据数：{label}")
    for marker in ("容器结构安全", "双点段", "不可抵赖"):
        if marker not in text:
            issues.append(f"边界缺要素：{marker}")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("pack", "verify", "bench"):
        if 'add_parser("' + sub + '"' not in nf:
            issues.append(f"evidence 缺子命令：{sub}")
    for cmd in ("python scripts/nf.py evidence bench",
                "python scripts/nf.py evidence verify --selfcheck",
                "python -m pytest desktop/tests/test_evidence_vectors.py",
                "python -m pytest desktop/tests/test_evidence.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class EvidenceBundleDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_bundle_matches_contract(self):
        self.assertEqual([], bundle_issues(self.text), "证据包文档不满足契约")

    def test_numbers_live(self):
        self.assertEqual(38, bench_cases())
        self.assertEqual(28, int(vectors()["count"]))
        self.assertEqual(66, count_cases(TEST_EV))
        self.assertEqual(8, count_cases(TEST_VEC))

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 三形态回退 10 条 / 矩阵回退 25 / 向量漂移 / 缺段 / 缺命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in bundle_issues(no_date)))
        old13 = self.text.replace("上面 **13 条**全判", "上面 **10 条**全判")
        self.assertTrue(any("13 条" in i for i in bundle_issues(old13)))
        old38 = self.text.replace("**38 条**已知攻击", "**25 种**已知攻击")
        self.assertTrue(any("38 条" in i for i in bundle_issues(old38)))
        old_vec = self.text.replace("**28 条**", "**27 条**")
        self.assertTrue(any("28 条" in i for i in bundle_issues(old_vec)))
        no_sec = self.text.replace("## 三种可验形态", "## 三形态")
        self.assertTrue(any("缺段" in i for i in bundle_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py evidence bench", "跑基准")
        self.assertTrue(any("evidence bench" in i for i in bundle_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_bundle.md")


if __name__ == "__main__":
    unittest.main()
