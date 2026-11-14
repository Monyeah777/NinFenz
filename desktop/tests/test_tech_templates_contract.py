#!/usr/bin/env python3
"""TECH_TEMPLATES 资产契约：章节骨架模板必须「schema ⇄ 键清单 ⇄ 条目 ⇄ 台账」四源一致。

为什么必须有：TECH_TEMPLATES 是 M90 按文档类型选骨架的模板集（doc_type 四类、sections 顺序即
渲染顺序、required_fields 必须是 sections 子集）。此前没有判据保证：schema 与键清单速览一致、
doc_type 枚举四类各有一例、required_fields 不引用不存在章节、条目 ID 落 T9xx、文件头与台账一致。
本轮补读法/机检验段与模板语义并把这些立成机检断言。

范围：只判本文件结构自洽与跨源同源（不改模板语义）。同族判据：
test_tech_rules_contract（同族规则资产）/ test_user_assets_readme_contract（键清单父登记）/
test_module_m90_contract（消费方）/ test_pipeline_p90_contract（管线引用）/ check23。
契约：读法段与四节、文件头/台账一致、schema 四字段与键清单一致、doc_type 四枚举各一例、
required_fields ⊆ sections、条目 ID T9xx、M90/P90 消费面在场、围栏配平。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "05_资产库" / "用户自定义" / "TECH_TEMPLATES.md"
USER_README = ROOT / "05_资产库" / "用户自定义" / "README.md"
PROVENANCE = ROOT / "05_资产库" / "provenance.json"
ASSET_KEYS = ROOT / "protocol" / "asset_keys.json"
M90 = ROOT / "04_模块库" / "技术文档类" / "M90_结构装配.md"
P90 = ROOT / "03_管线库" / "P90_结构装配管线.md"
FENCE = chr(96) * 3

DOC_TYPES = {"guide", "reference", "tutorial", "note"}
REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）", "## schema", "## 模板语义",
                     "## 条目", "## 校验与机检")
REQUIRED_MARKERS = ("nf asset add", "nf asset verify", "check23", "asset_get",
                    "asset_query", "fail-closed", "T9xx", "provenance.json")


def load_text(path: Path = TEMPLATES) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"TECH_TEMPLATES 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("TECH_TEMPLATES 为空")
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
        if item.get("key") == "TECH_TEMPLATES":
            return item
    return {}


def user_schema_fields() -> list:
    text = USER_README.read_text(encoding="utf-8")
    body = text.split("## 2. 条目 schema 速览", 1)[1].split("\n## ", 1)[0]
    for line in body.splitlines():
        if line.startswith("| TECH_TEMPLATES |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            return [x.strip() for x in cells[1].split(",") if x.strip()]
    return []


def schema_fields(text: str) -> list:
    m = re.search(r"required_fields: \[([^\]]+)\]", text)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def doc_type_enum(text: str) -> set:
    m = re.search(r"doc_type: ([a-z|]+)", text)
    return set(m.group(1).split("|")) if m else set()


def bracket_list(cell: str) -> list:
    inner = cell.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    return [x.strip() for x in inner.split(",") if x.strip()]


def entry_rows(text: str) -> list:
    body = text.split("## 条目", 1)[1].split("\n##", 1)[0]
    rows = []
    for line in body.splitlines():
        if not line.strip().startswith("| T9"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        rows.append({"id": cells[0], "doc_type": cells[1],
                     "sections": bracket_list(cells[2]),
                     "required": bracket_list(cells[3])})
    return rows


def tech_templates_issues(text: str) -> list:
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
    if head.get("key") != "TECH_TEMPLATES":
        issues.append(f"文件头 nf-asset key 应为 TECH_TEMPLATES：{head}")
    entry = provenance_entry()
    if not entry:
        issues.append("provenance.json 缺 TECH_TEMPLATES 台账项")
    else:
        if entry.get("version") != head.get("version"):
            issues.append("文件头 version 与台账不一致")
        if entry.get("status") != head.get("status"):
            issues.append("文件头 status 与台账不一致")
        if entry.get("module") != "M90":
            issues.append(f"台账 module 应为 M90：{entry.get('module')}")
    keys = json.loads(ASSET_KEYS.read_text(encoding="utf-8")).get("keys") or {}
    if "TECH_TEMPLATES" not in keys:
        issues.append("protocol/asset_keys.json 未在册 TECH_TEMPLATES")
    elif (keys["TECH_TEMPLATES"].get("scope") or "") != "user_asset":
        issues.append("asset_keys scope 应为 user_asset")
    fields = schema_fields(text)
    expected_fields = ["id", "doc_type", "sections", "required_fields"]
    if fields != expected_fields:
        issues.append(f"schema required_fields 应为四字段：{fields}")
    if user_schema_fields() != expected_fields:
        issues.append(f"键清单 §2 速览与四字段不一致：{user_schema_fields()}")
    enum = doc_type_enum(text)
    if enum != DOC_TYPES:
        issues.append(f"doc_type 枚举应为 guide|reference|tutorial|note：{sorted(enum)}")
    rows = entry_rows(text)
    if len(rows) < 4:
        issues.append(f"条目应至少四条（doc_type 四类各一，实测 {len(rows)}）")
    covered = set()
    for row in rows:
        if not re.match(r"^T9\d\d$", row["id"]):
            issues.append(f"条目 ID 应落 T9xx：{row['id']}")
        if row["doc_type"] not in DOC_TYPES:
            issues.append(f"{row['id']} doc_type 不在四类枚举：{row['doc_type']}")
        covered.add(row["doc_type"])
        if not row["sections"]:
            issues.append(f"{row['id']} sections 为空")
        missing = [f for f in row["required"] if f not in row["sections"]]
        if missing:
            issues.append(f"{row['id']} required_fields 引用了不存在的章节：{missing}")
    missing_types = DOC_TYPES - covered
    if missing_types:
        issues.append(f"doc_type 四类未各有一例（缺 {sorted(missing_types)}）")
    m90 = M90.read_text(encoding="utf-8")
    if "TECH_TEMPLATES" not in m90:
        issues.append("M90 文档未声明消费 TECH_TEMPLATES")
    if "TECH_TEMPLATES" not in P90.read_text(encoding="utf-8"):
        issues.append("P90 素材层键未声明 TECH_TEMPLATES")
    if "asset_get" not in text or "asset_query" not in text:
        issues.append("缺五接口访问说明（asset_get / asset_query）")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class TechTemplatesContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_tech_templates_matches_contract(self):
        self.assertEqual([], tech_templates_issues(self.text), "TECH_TEMPLATES 不满足资产契约")

    def test_header_and_ledger_agree(self):
        head = header(self.text)
        entry = provenance_entry()
        self.assertEqual("TECH_TEMPLATES", head.get("key"))
        self.assertEqual(entry.get("version"), head.get("version"))
        self.assertEqual(entry.get("status"), head.get("status"))

    def test_entries_cover_doc_types_and_subsets(self):
        rows = entry_rows(self.text)
        self.assertEqual(DOC_TYPES, {row["doc_type"] for row in rows})
        for row in rows:
            self.assertTrue(set(row["required"]) <= set(row["sections"]), row["id"])

    def test_contract_catches_mutations(self):
        """变异自证：文件头版本漂移 / schema 字段缺 / 枚举缺类 / 条目缺一 / 子集违规 / 缺节。"""
        bad_version = self.text.replace('version="1.0"', 'version="2.0"', 1)
        self.assertTrue(any("version" in i for i in tech_templates_issues(bad_version)))
        no_field = self.text.replace(
            "required_fields: [id, doc_type, sections, required_fields]",
            "required_fields: [id, doc_type, sections]", 1)
        self.assertTrue(any("required_fields" in i for i in tech_templates_issues(no_field)))
        no_note = self.text.replace("doc_type: guide|reference|tutorial|note",
                                    "doc_type: guide|reference|tutorial", 1)
        self.assertTrue(any("枚举" in i for i in tech_templates_issues(no_note)))
        no_row = self.text.replace(
            "| T904 | note | [背景, 要点, 结论, 修订记录] | [要点, 修订记录] |", "", 1)
        self.assertTrue(any("四类" in i for i in tech_templates_issues(no_row)))
        bad_subset = self.text.replace(
            "| T901 | guide | [概述, 快速开始, 概念, 操作步骤, 故障排查, 修订记录] "
            "| [概述, 修订记录] |",
            "| T901 | guide | [概述, 快速开始] | [概述, 修订记录] |", 1)
        self.assertTrue(any("不存在" in i or "sections" in i
                            for i in tech_templates_issues(bad_subset)))
        no_section = self.text.replace("## 校验与机检", "## 机检")
        self.assertTrue(any("缺节" in i for i in tech_templates_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in tech_templates_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_tech_templates.md")


if __name__ == "__main__":
    unittest.main()
