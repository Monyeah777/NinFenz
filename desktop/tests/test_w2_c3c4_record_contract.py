#!/usr/bin/env python3
"""docs/41_波C_W2_C3_C4 契约：快照状态 + 三处修复现状 + 扫描面活绑定 + 复现口径。

为什么必须有：这份记录的核心不是数值，而是「**3 例真实事件断链已修复**」这个结论——后续轮次若
把发布方补丁回退、或扫描面翻几倍却没人复核，读者会在一个过期结论上做判断。实测本轮确认：
M50 publish intent_received / M90 publish doc_delta_committed / M97 publish term_conflict_detected
仍在册，扫描面已从 44 模块扩到 248 模块（官方 13 + 社区 235）。本轮把「结论仍成立」与
「扫描面数字 = 现行模块数」立成机检断言。

范围：只判本文与现行模块面/修复现场的自洽（不改历史数值）。同族判据：
test_semantic_conflict.py（check26 判据）/ test_c1c2_record_contract.py（同类快照口径）/
test_doc_reachability.py（本文登记在 ARCHIVE_DOCS，故路径用 glob 间接定位）。
契约：标题 + 快照横幅、C3/C4/门禁与回归/现状对照/复现口径五段按序、历史数值保留、
扫描面「248 = 官方 13 + 社区 235」与文件系统一致、三处 publish 修复仍在现场、
check26 在 verify.sh、semantic_conflict/related_of 载体在场、复现三命令在 CLI。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HITS = sorted((ROOT / "docs").glob("41_波C_W2_C3*_实测记录.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-w2.md"
SECTIONS = ("## C3 语义矛盾扫描", "## C4 图书馆 See-Also", "## 门禁与回归",
            "## 现状对照", "## 复现与引用口径")
HISTORICAL = ("44 模块", "PASS=39", "396 OK", "check26")
CURRENT = ("248", "官方 13 + 社区 235", "仍在册", "复现与引用口径")
REPAIRS = (
    ("04_模块库/通用类/M50_调度器.md", "intent_received"),
    ("04_模块库/技术文档类/M90_结构装配.md", "doc_delta_committed"),
    ("community/技术文档域包/modules/M97_术语管理.md", "term_conflict_detected"),
)


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"W2 记录不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("W2 记录为空")
    return text


def module_counts() -> tuple:
    official = len(list((ROOT / "04_模块库").glob("*/*.md")))
    community = len(list((ROOT / "community").glob("*/modules/*.md")))
    return official, community


def publishing(path: str, event: str) -> bool:
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        if "publish" in line and event in line:
            return True
    return False


def w2_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 41 波C W2"):
        issues.append("缺标题「# 41 波C W2 · C3/C4 实测记录」")
    if "状态：历史实测快照" not in text:
        issues.append("缺「历史实测快照」状态横幅")
    if "不随仓库演进而改写" not in text:
        issues.append("缺「不随演进改写」声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("五段顺序不对")
    for marker in HISTORICAL:
        if marker not in text:
            issues.append(f"历史数值被改写：{marker}")
    for marker in CURRENT:
        if marker not in text:
            issues.append(f"现状对照缺要素：{marker}")
    official, community = module_counts()
    total = official + community
    if (official, community) != (13, 235):
        issues.append(f"模块面已变（官方 {official} + 社区 {community}）：现状对照需复核")
    if str(total) not in text:
        issues.append(f"未写当前扫描面（{total} 模块）")
    if "官方 13 + 社区 235" not in text:
        issues.append("现状对照未写明 官方 13 + 社区 235")
    for rel, event in REPAIRS:
        if not (ROOT / rel).is_file():
            issues.append(f"修复载体缺件：{rel}")
            continue
        if not publishing(rel, event):
            issues.append(f"修复疑似回退：{rel} 未 publish {event}")
        if event not in text:
            issues.append(f"正文缺修复事件：{event}")
    if "仍在册" not in text:
        issues.append("缺「三处修复仍在册」复核结论")
    verify = (ROOT / "verify.sh").read_text(encoding="utf-8")
    if "check26" not in verify:
        issues.append("verify.sh 缺 check26（语义矛盾扫描）")
    for rel in ("desktop/src/core/semantic_conflict.py",
                "desktop/tests/test_semantic_conflict.py"):
        if not (ROOT / rel).is_file():
            issues.append(f"缺载体：{rel}")
    analyzer_path = ROOT / "desktop" / "src" / "core" / "market_analyzer.py"
    analyzer = analyzer_path.read_text(encoding="utf-8")
    if "related_of" not in analyzer:
        issues.append("market_analyzer 缺 related_of（See-Also 载体）")
    nf = (ROOT / "scripts" / "nf.py").read_text(encoding="utf-8")
    if 'add_parser("related"' not in nf:
        issues.append("CLI 缺 related 子命令")
    for cmd in ("related 技术文档域包", "related M90", "module ls"):
        if "nf.py " + cmd not in text:
            issues.append(f"复现口径缺命令：nf.py {cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class W2RecordContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_w2_record_matches_contract(self):
        self.assertEqual([], w2_issues(self.text), "W2 记录不满足契约")

    def test_repairs_still_in_place(self):
        for rel, event in REPAIRS:
            self.assertTrue(publishing(rel, event), f"{rel} 未 publish {event}")

    def test_scan_surface_is_live(self):
        official, community = module_counts()
        self.assertEqual((13, 235), (official, community))
        self.assertIn(str(official + community), self.text)

    def test_contract_catches_mutations(self):
        """变异自证：去快照横幅 / 数值回退 / 修复回退叙述 / 缺现状对照段 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史实测快照**", "> **状态：现行**", 1)
        self.assertTrue(any("历史实测快照" in i for i in w2_issues(no_banner)))
        old_number = self.text.replace("248", "44")
        self.assertTrue(any("扫描面" in i or "248" in i for i in w2_issues(old_number)))
        reverted = self.text.replace("仍在册", "已回退")
        self.assertTrue(any("仍在册" in i for i in w2_issues(reverted)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 备注")
        self.assertTrue(any("缺段" in i for i in w2_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py module ls", "看模块清单")
        self.assertTrue(any("module ls" in i for i in w2_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_w2.md")


if __name__ == "__main__":
    unittest.main()
