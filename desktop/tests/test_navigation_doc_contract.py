#!/usr/bin/env python3
"""07 出厂与预设导航契约：导航面必须「节号可寻址、清单同源、验收项有机检映射」。

为什么必须有：07 是官方核心出厂与社区预设的入口导航（8 节），但此前零结构判据——§1 的 13 件
清单是否与 02 模块表同源、§3 两个预设的包 README 是否在场、§7 九条验收项各由哪条 check 守着，
全靠人记。实测本轮补的真缺口：7 个一级标题前缺空行、§8 把 AGENT_START 仍描述成「三句话开场」
（上游已升七段）、§5 未写明机制段余量只剩 M99、验收清单状态列 ☐ 与门禁读数没有区分说明。

范围：只判本文件的结构自洽与清单同源（不改装配语义）。同族判据：
test_core_protocol_contract（01）/ test_execution_protocol_contract（06）/
test_registry_doc_contract（02）/ test_doc_reachability（全仓路径与链接）。
契约：读法段与八节按序、§1 清单 ⊇ 02 模块表 13 件、§3 两包 README 在场、
§7 九项逐项有机检映射且 check 真实、RFC Date == 最后更新、围栏配平、裸 § 引用可解析。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAV = ROOT / "07_官方核心出厂与社区预设导航.md"
REGISTRY_DOC = ROOT / "02_联动注册表.md"
VERIFY = ROOT / "verify.sh"
FENCE = chr(96) * 3

REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）",
                     "## 1. 官方核心出厂", "## 2. 官方核心装配", "## 3. 社区领域预设索引",
                     "## 4. SillyTavern 加载指引", "## 5. 创作者扩展通道",
                     "## 6. 预设切换与数据隔离", "## 7. 验收清单", "## 8. Agent 自助组装入口")
#: §3 两套官方开箱预设的装载手册（在场才可点进去）
PRESET_READMES = ("community/校园情感领域包/README.md", "community/西幻生存领域包/README.md")
REQUIRED_MARKERS = ("本文件怎么用、怎么验", "引用约定", "七段入口", "余量仅 M99",
                    "常驻机检映射", "人工两级结构终验状态位", "最后更新：")


def load_text(path: Path = NAV) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"07 导航 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("07 导航 为空")
    return text


def check_funcs(verify_text: str) -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", verify_text, re.M))


def registry_module_ids() -> list:
    """02 §2 官方核心模块表第一列（13 件，机读清单真源）。"""
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    body = text.split("## 2. 官方核心模块表", 1)[1].split("\n## 3.", 1)[0]
    ids = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0] in ("模块ID", "") or set(cells[0]) <= {"-"}:
            continue
        ids.append(cells[0])
    return ids


def section_body(text: str, heading: str, nxt: str = "\n## ") -> str:
    if heading not in text:
        return ""
    return text.split(heading, 1)[1].split(nxt, 1)[0]


def section_ids(text: str) -> set:
    ids = set()
    for line in text.splitlines():
        m = re.match(r"^#{2,3} (\d+(?:\.\d+)*)", line.strip())
        if m:
            ids.add(m.group(1))
    return ids


def bare_refs(text: str) -> list:
    refs = []
    for m in re.finditer(r"§(\d+(?:\.\d+)*)", text):
        before = text[max(0, m.start() - 24):m.start()]
        if re.search(r"[A-Za-z0-9_.]+ +$", before):
            continue
        refs.append(m.group(1))
    return refs


def mapping_rows(text: str) -> list:
    body = section_body(text, "## 读法")
    return [ln.strip() for ln in body.splitlines()
            if ln.strip().startswith("| §") and "---" not in ln]


def nav_issues(text: str, verify_text: str = None) -> list:
    if verify_text is None:
        verify_text = VERIFY.read_text(encoding="utf-8")
    issues = []
    positions = [text.find(s) for s in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("八节顺序不对")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    sec1 = section_body(text, "## 1. 官方核心出厂", "\n## 2.")
    for module_id in registry_module_ids():
        if module_id not in sec1:
            issues.append(f"§1 清单缺 02 在册模块：{module_id}")
    for readme in PRESET_READMES:
        if readme not in text:
            issues.append(f"§3 缺预设装载手册：{readme}")
        if not (ROOT / readme).is_file():
            issues.append(f"预设装载手册不在场：{readme}")
    for pipeline in ("P02", "P03"):
        if pipeline not in text:
            issues.append(f"§3 缺预设管线：{pipeline}")
    funcs = check_funcs(verify_text)
    rows = mapping_rows(text)
    if len(rows) < 8:
        issues.append(f"机检映射表不足 8 行（实测 {len(rows)} 行）")
    for row in rows:
        for num in re.findall(r"check(\d+)", row):
            if "check" + num not in funcs:
                issues.append(f"映射引用了不存在的检查：check{num}")
    for i in range(1, 10):
        if f"项{i} →" not in text:
            issues.append(f"§7 验收项缺机检映射：项{i}")
    ids = section_ids(text)
    for ref in sorted(set(bare_refs(text))):
        if ref not in ids:
            issues.append(f"§引用无法解析：§{ref}")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    updated = re.search(r"> 最后更新：(\d{4}-\d{2}-\d{2})", text)
    rfc = re.search(r"\*\*Date\*\*: (\d{4}-\d{2}-\d{2})", text)
    if not updated or not rfc:
        issues.append("缺最后更新 / RFC Date")
    elif updated.group(1) != rfc.group(1):
        issues.append(f"RFC Date 与最后更新不一致：{rfc.group(1)} ≠ {updated.group(1)}")
    if "---\n---" in text:
        issues.append("出现重复分隔线")
    return issues


class NavigationDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_navigation_matches_contract(self):
        self.assertEqual([], nav_issues(self.text), "07 不满足导航契约")

    def test_official_core_list_is_same_source(self):
        ids = registry_module_ids()
        self.assertGreaterEqual(len(ids), 13, "02 模块表解析失败")
        sec1 = section_body(self.text, "## 1. 官方核心出厂", "\n## 2.")
        for module_id in ids:
            self.assertIn(module_id, sec1, f"§1 清单缺 02 在册模块：{module_id}")

    def test_preset_manuals_and_checks_resolve(self):
        for readme in PRESET_READMES:
            self.assertTrue((ROOT / readme).is_file(), readme)
        funcs = check_funcs(VERIFY.read_text(encoding="utf-8"))
        for row in mapping_rows(self.text):
            for num in re.findall(r"check(\d+)", row):
                self.assertIn("check" + num, funcs)

    def test_contract_catches_mutations(self):
        """变异自证：清单缺件 / 删读法 / 缺验收映射 / 假 check / 悬空 § / 日期漂移 / 围栏不配平。"""
        drop_module = self.text.replace("M08 环境状态", "", 1)
        self.assertTrue(any("M08" in i for i in nav_issues(drop_module)))
        no_readme = self.text.replace("## 读法（本文件怎么用、怎么验）", "## 前言")
        self.assertTrue(any("读法" in i for i in nav_issues(no_readme)))
        no_map = self.text.replace("项5 → check2 · check9", "", 1)
        self.assertTrue(any("项5" in i for i in nav_issues(no_map)))
        fake = self.text.replace("check7（两包完整）", "check99（两包完整）", 1)
        self.assertTrue(any("check99" in i for i in nav_issues(fake)))
        dangling = self.text + "\n见 §9.1 说明。\n"
        self.assertTrue(any("§9.1" in i for i in nav_issues(dangling)))
        bad_date = self.text.replace("> 最后更新：2026-11-12", "> 最后更新：2026-10-01")
        self.assertTrue(any("更新" in i for i in nav_issues(bad_date)))
        odd_fence = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in nav_issues(odd_fence)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_navigation.md")


if __name__ == "__main__":
    unittest.main()
