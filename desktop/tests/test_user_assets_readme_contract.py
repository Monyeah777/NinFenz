#!/usr/bin/env python3
"""05_资产库/用户自定义 README 契约：登记面必须「键清单 ⇄ schema 速览 ⇄ 资产文件 ⇄ 台账」四源一致。

为什么必须有：这个扩展槽是官方核心机制资产（STYLE_DNA / TECH_TEMPLATES / TECH_RULES）的登记面，
键清单与 schema 速览若与资产文件漂移，作者按 README 新增条目就会产出不合 schema 的条目。
本轮把「键清单三件、TECH_* required_fields 与资产文件逐字段一致、nf-asset 文件头与 provenance
的 version/status 一致、货架单层无子目录、ID 前缀 T9xx/R9xx」立成机检断言。

范围：只判本文件结构自洽与跨源同源（不改资产语义）。同族判据：
test_asset_library_readme_contract（父层索引）/ test_module_m80_contract（STYLE_DNA 消费方）/
test_module_m90_contract（模板/规则消费方）/ check23（供应链）/ check16-B（寻址授权）。
契约：读法段 + 六节按序、键清单三件与文件在场、TECH_* required_fields 与资产文件一致、
STYLE_DNA 字段在示例档表头、nf-asset 文件头与 provenance 的 version/status 对账、
asset_keys.json 词表在册（scope=user_asset）、货架无子目录、条目 ID 前缀合规。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USER_DIR = ROOT / "05_资产库" / "用户自定义"
README = USER_DIR / "README.md"
PROVENANCE = ROOT / "05_资产库" / "provenance.json"
ASSET_KEYS = ROOT / "protocol" / "asset_keys.json"
FENCE = chr(96) * 3

ASSETS = {"STYLE_DNA": "STYLE_DNA.md",
          "TECH_TEMPLATES": "TECH_TEMPLATES.md",
          "TECH_RULES": "TECH_RULES.md"}
REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）", "## 1. 资产键清单",
                     "## 2. 条目 schema 速览", "## 3. 登记记录",
                     "## 4. 文件头与台账对账", "## 5. 校验与机检",
                     "## 6. 三原则")
REQUIRED_MARKERS = ("asset_register", "nf-asset", "protocol/asset_keys.json",
                    "provenance.json", "check23", "nf asset verify",
                    "900+", "单层", "asset_get")


def load_text(path: Path = README) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"用户自定义 README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("用户自定义 README 为空")
    return text


def asset_file(key: str) -> Path:
    return USER_DIR / ASSETS[key]


def nf_asset_header(text: str) -> dict:
    m = re.search(r'<!--\s*nf-asset: key="([^"]+)" version="([^"]+)" status="([^"]+)"\s*-->',
                  text)
    if not m:
        return {}
    return {"key": m.group(1), "version": m.group(2), "status": m.group(3)}


def provenance_assets() -> dict:
    data = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    out = {}
    for item in data.get("assets") or []:
        if item.get("key"):
            out[item["key"]] = item
    return out


def asset_key_entries() -> dict:
    return json.loads(ASSET_KEYS.read_text(encoding="utf-8")).get("keys") or {}


def file_required_fields(key: str) -> list:
    text = asset_file(key).read_text(encoding="utf-8")
    m = re.search(r"required_fields: \[([^\]]+)\]", text)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def readme_schema_fields(text: str, key: str) -> list:
    """§2 schema 速览表的 required_fields 列（逐键）。"""
    marker = "## 2. 条目 schema 速览"
    if marker not in text:
        return []
    body = text.split(marker, 1)[1].split("\n## ", 1)[0]
    for line in body.splitlines():
        if line.startswith("| " + key + " |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            return [x.strip() for x in cells[1].split(",") if x.strip()]
    return []


def id_prefix_ok(key: str) -> bool:
    text = asset_file(key).read_text(encoding="utf-8")
    prefix = "T9" if key == "TECH_TEMPLATES" else "R9"
    rows = re.findall(r"^\| (" + prefix + r"\d\d) ", text, re.M)
    return bool(rows)


def user_readme_issues(text: str) -> list:
    issues = []
    positions = [text.find(s) for s in REQUIRED_SECTIONS]
    for section, pos in zip(REQUIRED_SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("读法段与六节顺序不对")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    keys = asset_key_entries()
    prov = provenance_assets()
    for key, filename in ASSETS.items():
        path = asset_file(key)
        if not path.is_file():
            issues.append(f"资产文件不在场：{filename}")
            continue
        if f"| {key} |" not in text:
            issues.append(f"§1 键清单缺：{key}")
        if key not in keys:
            issues.append(f"protocol/asset_keys.json 缺词表项：{key}")
        elif (keys[key].get("scope") or "") != "user_asset":
            issues.append(f"asset_keys 词表 scope 应为 user_asset：{key}")
        header = nf_asset_header(path.read_text(encoding="utf-8"))
        if header.get("key") != key:
            issues.append(f"{filename} 文件头 nf-asset key 不符：{header}")
        entry = prov.get(key)
        if not entry:
            issues.append(f"provenance.json 缺台账项：{key}")
        else:
            if entry.get("version") != header.get("version"):
                issues.append(f"{key} 台账 version 与文件头不一致")
            if entry.get("status") != header.get("status"):
                issues.append(f"{key} 台账 status 与文件头不一致")
        if key.startswith("TECH_"):
            fields = file_required_fields(key)
            if not fields:
                issues.append(f"{filename} 缺 required_fields 声明")
            else:
                for field in fields:
                    if field not in text:
                        issues.append(f"§2 schema 速览缺 {key} 字段：{field}")
            declared = readme_schema_fields(text, key)
            if declared != fields:
                issues.append(f"§2 {key} required_fields 与资产文件不一致："
                              f"{declared} ≠ {fields}")
            if not id_prefix_ok(key):
                issues.append(f"{filename} 条目 ID 前缀不合（T9xx/R9xx）")
    style = asset_file("STYLE_DNA").read_text(encoding="utf-8")
    for field in ("dna_id", "name", "rule", "applies_to"):
        if field not in style:
            issues.append(f"STYLE_DNA 示例档缺字段：{field}")
        if field not in text:
            issues.append(f"§2 schema 速览缺 STYLE_DNA 字段：{field}")
    subdirs = [p.name for p in USER_DIR.iterdir() if p.is_dir()]
    if subdirs:
        issues.append(f"货架单层被破坏，存在子目录：{subdirs}")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class UserAssetsReadmeContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_user_assets_readme_matches_contract(self):
        self.assertEqual([], user_readme_issues(self.text), "用户自定义 README 不满足契约")

    def test_headers_match_provenance(self):
        prov = provenance_assets()
        for key in ASSETS:
            header = nf_asset_header(asset_file(key).read_text(encoding="utf-8"))
            self.assertEqual(key, header.get("key"))
            self.assertEqual(prov[key]["version"], header.get("version"), key)
            self.assertEqual(prov[key]["status"], header.get("status"), key)

    def test_tech_schemas_match_asset_files(self):
        for key in ("TECH_TEMPLATES", "TECH_RULES"):
            fields = file_required_fields(key)
            self.assertTrue(fields, key)
            for field in fields:
                self.assertIn(field, self.text, f"{key}:{field}")

    def test_contract_catches_mutations(self):
        """变异自证：schema 字段漂移 / 键名漂移 / 单层规则缺失 / 缺节 / 围栏。"""
        drift = self.text.replace("| TECH_RULES | id, rule_type, check, action |",
                                 "| TECH_RULES | id, rule_kind, check, action |", 1)
        self.assertTrue(any("TECH_RULES" in i or "字段" in i
                            for i in user_readme_issues(drift)))
        bad_key = self.text.replace("TECH_TEMPLATES", "TECH_TPL")
        self.assertTrue(any("TECH_TEMPLATES" in i or "键清单" in i
                            for i in user_readme_issues(bad_key)))
        no_layer = self.text.replace("货架单层", "货架多层")
        self.assertTrue(any("单层" in i for i in user_readme_issues(no_layer)))
        no_section = self.text.replace("## 4. 文件头与台账对账（check23）",
                                       "## 4. 台账对账")
        self.assertTrue(any("缺节" in i for i in user_readme_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in user_readme_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_user_assets_readme.md")


if __name__ == "__main__":
    unittest.main()
