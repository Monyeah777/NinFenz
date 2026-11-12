#!/usr/bin/env python3
"""STYLE_DNA 资产契约：profile 配置槽必须「文件头 ⇄ 台账 ⇄ 键词表 ⇄ schema 速览」四源一致。

为什么必须有：STYLE_DNA 是 M80 质量门的 profile 配置槽（域中立示例，可整体替换）。此前没有判据
保证：文件头 nf-asset 的 version/status 与 provenance.json 台账一致、schema 字段与键清单速览
一致、三式配置面完整（资产键 / protocol.yaml / 缺省）、示例档表头与字段同构、且本槽不越界
（阈值与判定逻辑归 M80 §3）。本轮补读法/机检验段并把这些立成机检断言。

范围：只判本文件结构自洽与跨源同源（不改 profile 语义）。同族判据：
test_user_assets_readme_contract（键清单父登记）/ test_module_m80_contract（消费方）/
test_asset_library_readme_contract（五接口/台账）/ check23（供应链）/ check16-B（寻址授权）。
契约：读法段 + 五节按序、文件头与台账一致、schema 四字段与键清单速览一致、三式配置面完整、
示例档 P1–P3 四列同构、M80 消费与 Phase 2 迁移口径在场、不含阈值声明、围栏配平。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLE = ROOT / "05_资产库" / "用户自定义" / "STYLE_DNA.md"
USER_README = ROOT / "05_资产库" / "用户自定义" / "README.md"
PROVENANCE = ROOT / "05_资产库" / "provenance.json"
ASSET_KEYS = ROOT / "protocol" / "asset_keys.json"
M80 = ROOT / "04_模块库" / "通用类" / "M80_输出质检门.md"
FENCE = chr(96) * 3

FIELDS = ("dna_id", "name", "rule", "applies_to")
REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）", "## 1. 配置机制",
                     "## 2. 资产键表", "## 3. 示例档", "## 4. 登记记录",
                     "## 5. 三原则")
REQUIRED_MARKERS = ("nf asset add", "nf asset verify", "check23", "asset_get",
                    "protocol.yaml", "可判定", "不含阈值", "STYLE_DNA", "provenance.json")


def load_text(path: Path = STYLE) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"STYLE_DNA 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("STYLE_DNA 为空")
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
        if item.get("key") == "STYLE_DNA":
            return item
    return {}


def user_schema_fields() -> list:
    text = USER_README.read_text(encoding="utf-8")
    body = text.split("## 2. 条目 schema 速览", 1)[1].split("\n## ", 1)[0]
    for line in body.splitlines():
        if line.startswith("| STYLE_DNA |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            return [x.strip() for x in cells[1].split(",") if x.strip()]
    return []


def table_schema_fields(text: str) -> list:
    """§2 资产键表 schema 列的四字段（花括号内）。"""
    body = text.split("## 2. 资产键表", 1)[1].split("\n## ", 1)[0]
    m = re.search(r"\{([^}]+)\}", body)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def example_table(text: str) -> list:
    body = text.split("## 3. 示例档", 1)[1].split("\n## ", 1)[0]
    return [ln for ln in body.splitlines() if ln.strip().startswith("|")]


def style_issues(text: str) -> list:
    issues = []
    positions = [text.find(s) for s in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("读法段与五节顺序不对")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    head = header(text)
    if head.get("key") != "STYLE_DNA":
        issues.append(f"文件头 nf-asset key 应为 STYLE_DNA：{head}")
    entry = provenance_entry()
    if not entry:
        issues.append("provenance.json 缺 STYLE_DNA 台账项")
    else:
        if entry.get("version") != head.get("version"):
            issues.append(f"文件头 version {head.get('version')!r} ≠ 台账 {entry.get('version')!r}")
        if entry.get("status") != head.get("status"):
            issues.append(f"文件头 status {head.get('status')!r} ≠ 台账 {entry.get('status')!r}")
        if entry.get("module") != "M80":
            issues.append(f"台账 module 应为 M80：{entry.get('module')}")
    keys = json.loads(ASSET_KEYS.read_text(encoding="utf-8")).get("keys") or {}
    if "STYLE_DNA" not in keys:
        issues.append("protocol/asset_keys.json 未在册 STYLE_DNA")
    elif (keys["STYLE_DNA"].get("scope") or "") != "user_asset":
        issues.append("asset_keys scope 应为 user_asset")
    for field in FIELDS:
        if field not in text:
            issues.append(f"schema 缺字段：{field}")
    declared = user_schema_fields()
    if declared != list(FIELDS):
        issues.append(f"键清单 §2 schema 速览与四字段不一致：{declared}")
    table_fields = table_schema_fields(text)
    if table_fields != list(FIELDS):
        issues.append(f"§2 资产键表 schema 列与四字段不一致：{table_fields}")
    if "| a. 资产键 |" not in text or "| b. protocol.yaml 字段 |" not in text or \
            "| c. 缺省（未配置） |" not in text:
        issues.append("§1 三式配置面不完整（资产键 / protocol.yaml / 缺省）")
    if "不得双源声明" not in text:
        issues.append("§1 缺「不得双源声明」纪律")
    table = example_table(text)
    if len(table) < 5:
        issues.append(f"§3 示例档表行不足（含表头至少 5 行）：{len(table)}")
    else:
        header_cells = [c.strip() for c in table[0].strip("|").split("|")]
        if len(header_cells) != 4:
            issues.append(f"§3 示例档表头应为四列：{header_cells}")
        for row in table[2:5]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) != 4:
                issues.append(f"§3 示例条目列数不符：{cells}")
        for row_id in ("P1", "P2", "P3"):
            if f"| {row_id} |" not in text:
                issues.append(f"§3 缺示例条目：{row_id}")
    m80 = M80.read_text(encoding="utf-8")
    if "STYLE_DNA" not in m80:
        issues.append("M80 文档未声明消费 STYLE_DNA")
    if "输出 profile" not in m80:
        issues.append("M80 文档缺 Phase 2「输出 profile」迁移口径")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class StyleDnaContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_style_dna_matches_contract(self):
        self.assertEqual([], style_issues(self.text), "STYLE_DNA 不满足资产契约")

    def test_header_and_ledger_agree(self):
        head = header(self.text)
        entry = provenance_entry()
        self.assertEqual("STYLE_DNA", head.get("key"))
        self.assertEqual(entry.get("version"), head.get("version"))
        self.assertEqual(entry.get("status"), head.get("status"))

    def test_schema_matches_key_registry(self):
        self.assertEqual(list(FIELDS), user_schema_fields())
        for field in FIELDS:
            self.assertIn(field, self.text)

    def test_contract_catches_mutations(self):
        """变异自证：文件头版本漂移 / schema 字段缺 / 三式缺 / 示例列缺 / 缺节 / 围栏。"""
        bad_version = self.text.replace('version="1.0"', 'version="2.0"', 1)
        self.assertTrue(any("version" in i for i in style_issues(bad_version)))
        no_field = self.text.replace("applies_to", "applies", 1)
        self.assertTrue(any("applies_to" in i or "schema" in i
                            for i in style_issues(no_field)))
        no_form = self.text.replace("| b. protocol.yaml 字段 |", "| b. 字段 |", 1)
        self.assertTrue(any("三式" in i for i in style_issues(no_form)))
        no_row = self.text.replace("| P3 | 受众适配 | 按目标读者调整详略与术语密度 | ['*'] |",
                                   "| P3 | 受众适配 |", 1)
        self.assertTrue(any("示例" in i for i in style_issues(no_row)))
        no_section = self.text.replace("## 4. 登记记录", "## 4. 记录")
        self.assertTrue(any("缺节" in i for i in style_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in style_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_style_dna.md")


if __name__ == "__main__":
    unittest.main()
