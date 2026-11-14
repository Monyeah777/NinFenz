#!/usr/bin/env python3
"""01 核心协议契约：协议根必须「节号可寻址、机检映射同源、引用零悬空」。

为什么必须有：01_核心协议.md 是协议契约根（7 节 + 11 条迁移记录），外部文档大量按
「§1.1 / §1.6.11 / §7 V1」寻址，但文件本身零结构判据。实测本轮补的真缺口：§7 章下混着
「### 1.x 迁移记录」编号（外部按 §1.x 寻址、不能重排，需显式说明桥）、文件末尾重复分隔线、
§4 与 §5 之间缺空行、以及「哪条规则由哪个 check 常驻」此前只能靠人记。

范围：只判本文件的结构自洽与机检同源（不改任何协议语义）。同族判据：
test_doc_reachability（全仓路径与 nf 命令）/ test_deep_dive_contract（三正交与不变式同源）/
test_check_merge_equivalence（不变式 token 落点）/ test_conformance_scan（规范件扫描）。
契约：读法段与七节按序、机检映射表逐行 check 真实存在、§引用可解析、编号桥在场、
迁移记录 11 条在场、末尾零重复分隔、机读真源件在场。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "01_核心协议.md"
VERIFY = ROOT / "verify.sh"

#: 七个编号节（顺序 = 阅读顺序）
REQUIRED_SECTIONS = ("## 1. 模块协议", "## 2. 管线规范", "## 3. 资产库接口",
                     "## 4. 联动注册表结构", "## 5. 五条核心不变式",
                     "## 6. 平台规则", "## 7. 版本与兼容")
#: 读法段必须点到的机读真源（文件件号）
MACHINE_SOURCES = ("protocol/schema/contract.schema.json", "protocol/EXTENSION.md",
                   "protocol/assertions.json")
#: 迁移记录（外部按 §1.x 寻址；少一条 = 历史记录丢失）
MIGRATION_HEADS = tuple(f"### 1.{i} 迁移记录" for i in range(1, 7)) + \
    tuple(f"**1.6.{i} " for i in range(1, 12))
REQUIRED_MARKERS = ("## 读法（本文件怎么用、怎么验）", "机器面同源", "引用约定",
                    "编号说明", "最后更新：")


def load_text(path: Path = PROTOCOL) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"01_核心协议 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("01_核心协议 为空")
    return text


def check_funcs(verify_text: str) -> set:
    """verify.sh 里真实存在的 checkN 函数名集合。"""
    return set(re.findall(r"^(check\d+)\(\)\{", verify_text, re.M))


def section_ids(text: str) -> set:
    """本文件可寻址的节号：标题节 + 迁移记录粗体条。"""
    ids = set()
    for line in text.splitlines():
        m = re.match(r"^#{2,3} (\d+(?:\.\d+)*)", line.strip())
        if m:
            ids.add(m.group(1))
        m2 = re.match(r"^\*\*(\d+(?:\.\d+)*) ", line.strip())
        if m2:
            ids.add(m2.group(1))
    return ids


def bare_refs(text: str) -> list:
    """本文件内的裸节号引用（跳过「02 §」这类跨文件引用）。"""
    refs = []
    for m in re.finditer(r"§(\d+(?:\.\d+)*)", text):
        before = text[max(0, m.start() - 24):m.start()]
        if re.search(r"[A-Za-z0-9_.]+ +$", before):
            continue            # 跨文件引用（02 §8.3 / CONTRIBUTING §4.2 等）
        refs.append(m.group(1))
    return refs


def mapping_rows(text: str) -> list:
    """读法段的「节 → 常驻机检」表数据行。"""
    if "## 读法" not in text:
        return []
    body = text.split("## 读法", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("| §") and "---" not in s:
            rows.append(s)
    return rows


def protocol_issues(text: str, verify_text: str = None) -> list:
    if verify_text is None:
        verify_text = VERIFY.read_text(encoding="utf-8")
    issues = []
    positions = [text.find(section) for section in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(pos >= 0 for pos in positions) and positions != sorted(positions):
        issues.append("七节顺序不对")
    if ("## 读法" in text and "## 1. 模块协议" in text
            and text.find("## 读法") > text.find("## 1. 模块协议")):
        issues.append("读法段必须在 §1 之前")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for head in MIGRATION_HEADS:
        if head not in text:
            issues.append(f"缺迁移记录：{head}")
    ids = section_ids(text)
    for ref in sorted(set(bare_refs(text))):
        if ref not in ids:
            issues.append(f"§引用无法解析：§{ref}")
    funcs = check_funcs(verify_text)
    if len(funcs) < 40:
        issues.append(f"verify.sh check 函数面解析失败（{len(funcs)} 条）")
    rows = mapping_rows(text)
    if len(rows) < 7:
        issues.append(f"机检映射表不足 7 行（实测 {len(rows)} 行）")
    for row in rows:
        for num in re.findall(r"check(\d+)", row):
            if "check" + num not in funcs:
                issues.append(f"机检映射引用了不存在的检查：check{num}")
    for source in MACHINE_SOURCES:
        if source not in text:
            issues.append(f"读法段缺机读真源：{source}")
        if not (ROOT / source).is_file():
            issues.append(f"机读真源不在场：{source}")
    if "---\n---" in text:
        issues.append("末尾 / 正文出现重复分隔线")
    if "\r" in text:
        issues.append("含 CR 行尾（应为 LF）")
    return issues


class CoreProtocolContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_core_protocol_matches_contract(self):
        self.assertEqual([], protocol_issues(self.text), "01 不满足协议根契约")

    def test_sections_and_migrations_in_order(self):
        positions = [self.text.find(s) for s in REQUIRED_SECTIONS]
        self.assertTrue(all(p >= 0 for p in positions), "七节不全")
        self.assertEqual(sorted(positions), positions, "七节顺序不对")
        for head in MIGRATION_HEADS:
            self.assertIn(head, self.text)

    def test_section_refs_and_checks_resolve(self):
        ids = section_ids(self.text)
        for ref in set(bare_refs(self.text)):
            self.assertIn(ref, ids, f"§引用无法解析：§{ref}")
        funcs = check_funcs(VERIFY.read_text(encoding="utf-8"))
        for row in mapping_rows(self.text):
            for num in re.findall(r"check(\d+)", row):
                self.assertIn("check" + num, funcs)

    def test_contract_catches_mutations(self):
        """变异自证：删读法 / 悬空 §引用 / 假 check / 删迁移记录 / 重复分隔线。"""
        no_readme = self.text.replace("## 读法（本文件怎么用、怎么验）", "## 前言")
        self.assertTrue(any("读法" in i for i in protocol_issues(no_readme)))
        dangling = self.text + "\n见 §9.9 的说明。\n"
        self.assertTrue(any("§9.9" in i for i in protocol_issues(dangling)))
        fake_check = self.text.replace("check16 · check28 · check29", "check99 · check28")
        self.assertTrue(any("check99" in i for i in protocol_issues(fake_check)))
        no_migration = self.text.replace("**1.6.11 ", "**1.6.99 ")
        self.assertTrue(any("1.6.11" in i for i in protocol_issues(no_migration)))
        duplicated = self.text + "\n---\n---\n"
        self.assertTrue(any("重复分隔线" in i for i in protocol_issues(duplicated)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_core_protocol.md")


if __name__ == "__main__":
    unittest.main()
