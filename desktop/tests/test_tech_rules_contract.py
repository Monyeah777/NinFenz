#!/usr/bin/env python3
"""TECH_RULES 资产契约：规范校验规则必须「schema ⇄ 条目 ⇄ 键清单 ⇄ 台账」四源一致。

为什么必须有：TECH_RULES 是 M90 结构装配的规范校验规则集（结构/术语/引用/修订四类，warn|fail
两档）。此前没有判据保证：schema required_fields 与键清单速览一致、field_types 的 rule_type 枚举
与条目实际取值一致、条目 ID 落 R9xx、文件头与 provenance 台账一致、每条 check 可判定。本轮补
读法/机检验段与规则语义并把这些立成机检断言。

范围：只判本文件结构自洽与跨源同源（不改规则语义）。同族判据：
test_user_assets_readme_contract（键清单父登记）/ test_module_m90_contract（消费方）/
test_style_dna_contract（同族资产模板）/ check23（供应链）。
契约：读法段与四节、文件头/台账一致、schema 字段与键清单一致、rule_type 四枚举与条目取值一致、
action 仅 warn|fail、条目 ID R9xx、M90 消费面在场、可判定声明在场、围栏配平。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TECH_RULES = ROOT / "05_资产库" / "用户自定义" / "TECH_RULES.md"
USER_README = ROOT / "05_资产库" / "用户自定义" / "README.md"
PROVENANCE = ROOT / "05_资产库" / "provenance.json"
ASSET_KEYS = ROOT / "protocol" / "asset_keys.json"
M90 = ROOT / "04_模块库" / "技术文档类" / "M90_结构装配.md"
FENCE = chr(96) * 3

RULE_TYPES = {"structure", "terminology", "reference", "revision"}
ACTIONS = {"warn", "fail"}
REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）", "## schema", "## 规则语义",
                     "## 条目", "## 校验与机检")
REQUIRED_MARKERS = ("nf asset add", "nf asset verify", "check23", "asset_get",
                    "asset_match", "可判定", "R9xx", "provenance.json")


def load_text(path: Path = TECH_RULES) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"TECH_RULES 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("TECH_RULES 为空")
    return text


def header(text: str) -> dict:
    m = re.search(r'<!--\s*nf-asset: key="([^"]+)" version="([^"]+)" status="([^"]+)"\s*-->',
                  text)
    if not m:
        return {}
    return {"key": m.group(1), "version": m.group(2), "status": m.group(3)}


def provenance_entry() -> dict:
    data = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    for item in data.get("assets") or []:
        if item.get("key") == "TECH_RULES":
            return item
    return {}


def user_schema_fields() -> list:
    text = USER_README.read_text(encoding="utf-8")
    body = text.split("## 2. 条目 schema 速览", 1)[1].split("\n## ", 1)[0]
    for line in body.splitlines():
        if line.startswith("| TECH_RULES |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            return [x.strip() for x in cells[1].split(",") if x.strip()]
    return []


def schema_fields(text: str) -> list:
    m = re.search(r"required_fields: \[([^\]]+)\]", text)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def rule_type_enum(text: str) -> set:
    m = re.search(r"rule_type: ([a-z|]+)", text)
    return set(m.group(1).split("|")) if m else set()


def entry_rows(text: str) -> list:
    body = text.split("## 条目", 1)[1].split("\n##", 1)[0]
    rows = []
    for line in body.splitlines():
        m = re.match(r"^\| (R9\d\d) \| ([a-z]+) \| (.+?) \| (warn|fail) \|$", line.strip())
        if m:
            rows.append({"id": m.group(1), "rule_type": m.group(2),
                         "check": m.group(3), "action": m.group(4)})
    return rows


def tech_rules_issues(text: str) -> list:
    issues = []
    positions = [text.find(s) for s in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("读法段与四节顺序不对")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    head = header(text)
    if head.get("key") != "TECH_RULES":
        issues.append(f"文件头 nf-asset key 应为 TECH_RULES：{head}")
    entry = provenance_entry()
    if not entry:
        issues.append("provenance.json 缺 TECH_RULES 台账项")
    else:
        if entry.get("version") != head.get("version"):
            issues.append("文件头 version 与台账不一致")
        if entry.get("status") != head.get("status"):
            issues.append("文件头 status 与台账不一致")
        if entry.get("module") != "M90":
            issues.append(f"台账 module 应为 M90：{entry.get('module')}")
    keys = json.loads(ASSET_KEYS.read_text(encoding="utf-8")).get("keys") or {}
    if "TECH_RULES" not in keys:
        issues.append("protocol/asset_keys.json 未在册 TECH_RULES")
    elif (keys["TECH_RULES"].get("scope") or "") != "user_asset":
        issues.append("asset_keys scope 应为 user_asset")
    fields = schema_fields(text)
    expected_fields = ["id", "rule_type", "check", "action"]
    if fields != expected_fields:
        issues.append(f"schema required_fields 应为四字段：{fields}")
    if user_schema_fields() != expected_fields:
        issues.append(f"键清单 §2 速览与四字段不一致：{user_schema_fields()}")
    enum = rule_type_enum(text)
    if enum != RULE_TYPES:
        issues.append(f"rule_type 枚举应为结构/术语/引用/修订四类：{sorted(enum)}")
    rows = entry_rows(text)
    if len(rows) != 4:
        issues.append(f"条目应四条（实测 {len(rows)}）")
    for row in rows:
        if row["rule_type"] not in RULE_TYPES:
            issues.append(f"{row['id']} rule_type 不在四类枚举：{row['rule_type']}")
        if row["action"] not in ACTIONS:
            issues.append(f"{row['id']} action 应为 warn|fail：{row['action']}")
        if not row["check"].strip():
            issues.append(f"{row['id']} check 为空")
    used_types = {row["rule_type"] for row in rows}
    if used_types != RULE_TYPES:
        issues.append(f"条目未覆盖四类规则（实测 {sorted(used_types)}）")
    m90 = M90.read_text(encoding="utf-8")
    if "TECH_RULES" not in m90:
        issues.append("M90 文档未声明消费 TECH_RULES")
    if "asset_get" not in text or "asset_match" not in text:
        issues.append("缺五接口访问说明（asset_get / asset_match）")
    if "R9xx" not in text:
        issues.append("缺条目 ID 前缀约束 R9xx")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class TechRulesContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_tech_rules_matches_contract(self):
        self.assertEqual([], tech_rules_issues(self.text), "TECH_RULES 不满足资产契约")

    def test_header_and_ledger_agree(self):
        head = header(self.text)
        entry = provenance_entry()
        self.assertEqual("TECH_RULES", head.get("key"))
        self.assertEqual(entry.get("version"), head.get("version"))
        self.assertEqual(entry.get("status"), head.get("status"))

    def test_entries_cover_four_rule_types(self):
        rows = entry_rows(self.text)
        self.assertEqual(4, len(rows))
        self.assertEqual(RULE_TYPES, {row["rule_type"] for row in rows})
        for row in rows:
            self.assertIn(row["action"], ACTIONS)
            self.assertRegex(row["id"], r"^R9\d\d$")

    def test_contract_catches_mutations(self):
        """变异自证：文件头版本漂移 / schema 字段缺 / 枚举缺类 / 条目缺行 / 缺节 / 围栏。"""
        bad_version = self.text.replace('version="1.0"', 'version="2.0"', 1)
        self.assertTrue(any("version" in i for i in tech_rules_issues(bad_version)))
        no_field = self.text.replace("required_fields: [id, rule_type, check, action]",
                                     "required_fields: [id, check, action]", 1)
        self.assertTrue(any("required_fields" in i for i in tech_rules_issues(no_field)))
        no_revision = self.text.replace("rule_type: structure|terminology|reference|revision",
                                        "rule_type: structure|terminology|reference", 1)
        self.assertTrue(any("枚举" in i for i in tech_rules_issues(no_revision)))
        no_row = self.text.replace(
            "| R904 | revision | 每次变更须追加修订记录（ver/date/change） | warn |",
                                   "", 1)
        self.assertTrue(any("四类" in i or "四条" in i
                            for i in tech_rules_issues(no_row)))
        no_section = self.text.replace("## 校验与机检", "## 机检")
        self.assertTrue(any("缺节" in i for i in tech_rules_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in tech_rules_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_tech_rules.md")


if __name__ == "__main__":
    unittest.main()
