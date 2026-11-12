#!/usr/bin/env python3
"""docs/41_波C_W3 契约：历史实测记录必须「快照状态 + C8/C9 接续指引 + 交付件在场 + 复现口径」。

为什么必须有：这份记录汇总了 6 项交付，其中 **C8（transport 评估）与 C9（指针 v0）都已被后续
轮次接续**（C8 落地本地 HTTP 面；C9 升级为回合状态头 v1）。若不指明接续关系，读者会把「暂不做」
当现行 transport 结论、把 v0 当现行指针格式。本轮补快照横幅、C8/C9「后续状态」段、现状对照表、
复现口径，并把交付件在场 + 三项历史数值保留立成机检断言。

范围：只判本文与接续件/交付件的自洽（不改历史数值）。同族判据：
test_c8_transport_contract.py / test_c9_pointer_contract.py（接续件口径）/
test_c1c2_record_contract.py（同类快照模板）/ test_doc_reachability.py（本文登记在 ARCHIVE_DOCS，
故路径用 glob 间接定位）。
契约：标题 + 快照横幅、七段按序、历史数值保留（PASS=39 / 401 OK / 396）、
C8/C9 接续指引在场且接续件含复评标记、交付件六件在场、design/serve/CLI 复现命令在册、
README 现行 Windows 口径（只承诺 Git Bash）。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HITS = sorted((ROOT / "docs").glob("41_波C_W3*_实测记录.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-w3.md"
SECTIONS = ("## C6", "## C8", "## C9", "## D 组", "## 门禁与回归",
            "## 现状对照", "## 复现与引用口径")
HISTORICAL = ("PASS=39", "401 OK", "396")
DELIVERABLES = ("docs/需求收敛模板.md", "docs/迁移指南-基于nf-sig-diff.md",
                "docs/41_波C_C8_transport评估.md", "docs/41_波C_C9_回合装载指针_v0.md",
                "docs/42_M2_回合状态头_v1.md", "desktop/tests/test_nf_cli.py")
FOLLOWUPS = ("后续状态", "§结论复评", "§现状核对", "回合状态头 v1", "nf serve --http")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"W3 记录不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("W3 记录为空")
    return text


def w3_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 41 波C W3 实测记录"):
        issues.append("缺标题「# 41 波C W3 实测记录」")
    if "状态：历史实测快照" not in text:
        issues.append("缺「历史实测快照」状态横幅")
    if "不随仓库演进而改写" not in text:
        issues.append("缺「不随演进改写」声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("七段顺序不对")
    for marker in HISTORICAL:
        if marker not in text:
            issues.append(f"历史数值被改写：{marker}")
    for rel in DELIVERABLES:
        if not (ROOT / rel).is_file():
            issues.append(f"交付件不存在：{rel}")
    for marker in FOLLOWUPS:
        if marker not in text:
            issues.append(f"接续指引缺要素：{marker}")
    text_c8 = (ROOT / "docs" / "41_波C_C8_transport评估.md").read_text(encoding="utf-8")
    text_c9 = (ROOT / "docs" / "41_波C_C9_回合装载指针_v0.md").read_text(encoding="utf-8")
    if "结论复评" not in text_c8:
        issues.append("C8 评估件缺「结论复评」（接续未落到真源）")
    if "现状核对" not in text_c9:
        issues.append("C9 指针件缺「现状核对」（接续未落到真源）")
    if "docs/41_波C_C8_transport评估.md" not in text:
        issues.append("正文未指向 C8 评估件")
    if "docs/41_波C_C9_回合装载指针_v0.md" not in text:
        issues.append("正文未指向 C9 指针件")
    nf = (ROOT / "scripts" / "nf.py").read_text(encoding="utf-8")
    if 'add_parser("design"' not in nf:
        issues.append("CLI 缺 design 子命令（C6 流转链入口）")
    if '"steelman"' not in nf or '"audit"' not in nf:
        issues.append("design 缺 steelman/audit 子命令")
    if '"--http"' not in nf:
        issues.append("serve 缺 --http（C8 现行本地 HTTP 面）")
    for sub in ("sig", "diff", "explain", "related", "pipeline", "module", "demo"):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append(f"CLI 缺子命令：{sub}")
    for cmd in ("design steelman init", "design audit init", "serve --help", "--help"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：nf {cmd}")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "Git Bash" not in readme:
        issues.append("README 缺 Windows Git Bash 口径")
    if "不再明示 WSL" not in text:
        issues.append("缺 D6 现行口径说明（README 只承诺 Git Bash）")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class W3RecordContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_w3_record_matches_contract(self):
        self.assertEqual([], w3_issues(self.text), "W3 记录不满足契约")

    def test_followups_have_markers(self):
        c8 = (ROOT / "docs" / "41_波C_C8_transport评估.md").read_text(encoding="utf-8")
        c9 = (ROOT / "docs" / "41_波C_C9_回合装载指针_v0.md").read_text(encoding="utf-8")
        self.assertIn("结论复评", c8)
        self.assertIn("现状核对", c9)
        self.assertIn("回合状态头 v1", self.text)

    def test_deliverables_exist(self):
        for rel in DELIVERABLES:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_contract_catches_mutations(self):
        """变异自证：去快照横幅 / 数值回退 / 去接续指引 / 缺现状对照段 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史实测快照**", "> **状态：现行**", 1)
        self.assertTrue(any("历史实测快照" in i for i in w3_issues(no_banner)))
        old_value = self.text.replace("401 OK", "999 OK")
        self.assertTrue(any("401 OK" in i for i in w3_issues(old_value)))
        no_follow = self.text.replace("后续状态", "备注")
        self.assertTrue(any("接续指引" in i for i in w3_issues(no_follow)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in w3_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py serve --help", "看 serve 帮助")
        self.assertTrue(any("serve --help" in i for i in w3_issues(no_cmd)))
        no_ref = self.text.replace("docs/41_波C_C8_transport评估.md", "C8 评估件")
        self.assertTrue(any("C8 评估件" in i for i in w3_issues(no_ref)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_w3.md")


if __name__ == "__main__":
    unittest.main()
