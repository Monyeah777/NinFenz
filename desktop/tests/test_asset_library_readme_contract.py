#!/usr/bin/env python3
"""05_资产库 README 契约：资产层总索引必须「五接口同源、台账可核、货架单层、引用不另立」。

为什么必须有：05_资产库/README.md 是资产数据层的总索引 + 扩增协议（48→行），运行期寻址一律
经 01 §3 五接口。此前没有判据保证：五接口清单与 01 §3 真源一致、provenance.json 台账覆盖三件
机制资产、protocol/asset_keys.json 词表在册、货架单层硬规在场、§6 模块引用映射与 04/P90 文档
一致。本轮补读法/机检验段并把这些立成机检断言。

范围：只判本文件结构自洽与跨源同源（不改资产语义）。同族判据：
test_module_m80_contract（消费方 STYLE_DNA）/ test_module_m90_contract（消费方模板/规则）/
test_doc_reachability（路径在场）/ check23（供应链台账）/ check16-B（寻址授权）。
契约：读法段 + 六节按序、五接口清单与 01 §3 逐名一致、provenance/asset_keys/用户自定义三源覆盖
三键、单层货架硬规在场、§6 引用映射与 M80/M90/P90 一致、围栏配平。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "05_资产库" / "README.md"
USER_DIR = ROOT / "05_资产库" / "用户自定义"
PROVENANCE = ROOT / "05_资产库" / "provenance.json"
ASSET_KEYS = ROOT / "protocol" / "asset_keys.json"
PROTOCOL = ROOT / "01_核心协议.md"
M80 = ROOT / "04_模块库" / "通用类" / "M80_输出质检门.md"
M90 = ROOT / "04_模块库" / "技术文档类" / "M90_结构装配.md"
P90 = ROOT / "03_管线库" / "P90_结构装配管线.md"
VERIFY = ROOT / "verify.sh"
FENCE = chr(96) * 3

INTERFACES = ("asset_get", "asset_query", "asset_match", "asset_roll", "asset_register")
ASSETS = ("STYLE_DNA", "TECH_TEMPLATES", "TECH_RULES")
REQUIRED_SECTIONS = ("## 读法（本文件怎么用、怎么验）", "## 1. 资产归属总览",
                     "## 2. 目录结构", "## 3. 运行期访问接口", "## 4. 资产溯源",
                     "## 5. 扩增协议", "## 6. 模块-资产引用映射")
REQUIRED_MARKERS = ("provenance.json", "check23", "check16-B", "protocol/asset_keys.json",
                    "单层货架不变量", "不要建子目录", "nf asset verify", "禁止模块直读",
                    "community/<域包>/assets/", "用户自定义/")


def load_text(path: Path = README) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"05_资产库 README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("05_资产库 README 为空")
    return text


def interface_rows(text: str) -> list:
    return re.findall(r"^\| (asset_\w+)\(.*?\|", text, re.M)


def provenance_text() -> str:
    return PROVENANCE.read_text(encoding="utf-8")


def asset_keys() -> dict:
    return json.loads(ASSET_KEYS.read_text(encoding="utf-8"))


def tree_block(text: str) -> str:
    m = re.search(FENCE + r"\n(05_资产库/[\s\S]*?)\n" + FENCE, text)
    return m.group(1) if m else ""


def readme_issues(text: str) -> list:
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
    rows = interface_rows(text)
    if rows != list(INTERFACES):
        issues.append(f"§3 五接口清单不符（应为 get/query/match/roll/register）：{rows}")
    protocol = PROTOCOL.read_text(encoding="utf-8")
    for name in INTERFACES:
        if name not in protocol:
            issues.append(f"01 §3 真源缺接口名：{name}")
    prov = provenance_text()
    if '"schema_version"' not in prov:
        issues.append("provenance.json 缺 schema_version")
    for key in ASSETS:
        if key not in prov:
            issues.append(f"provenance.json 未覆盖机制资产：{key}")
        if key not in asset_keys().get("keys", {}):
            issues.append(f"protocol/asset_keys.json 未在册：{key}")
        if key not in text:
            issues.append(f"README 未提及资产键：{key}")
    if '"official"' not in prov and "official" not in prov:
        issues.append("provenance.json 缺 official 分层标记")
    user_readme = (USER_DIR / "README.md").read_text(encoding="utf-8")
    for key in ASSETS:
        if key not in user_readme:
            issues.append(f"用户自定义/README 键清单缺：{key}")
        if not (USER_DIR / f"{key}.md").is_file():
            issues.append(f"资产文件不在场：用户自定义/{key}.md")
    tree = tree_block(text)
    for token in ("README.md", "provenance.json", "用户自定义/", "STYLE_DNA.md",
                  "TECH_RULES.md", "TECH_TEMPLATES.md"):
        if token not in tree:
            issues.append(f"§2 目录树缺：{token}")
    if "community/<域包>/assets/" not in text:
        issues.append("§1 缺域包资产位置")
    m80 = M80.read_text(encoding="utf-8")
    if "STYLE_DNA" not in m80:
        issues.append("M80 文档未声明消费 STYLE_DNA")
    m90 = M90.read_text(encoding="utf-8")
    for key in ("TECH_TEMPLATES", "TECH_RULES"):
        if key not in m90:
            issues.append(f"M90 文档未声明消费 {key}")
        if key not in P90.read_text(encoding="utf-8"):
            issues.append(f"P90 素材层键缺 {key}")
    if "check23()" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("verify.sh 缺 check23")
    if not (ROOT / "desktop" / "src" / "core" / "asset_ledger.py").is_file():
        issues.append("缺资产供应链实现 asset_ledger.py")
    if text.count(FENCE) % 2 != 0:
        issues.append("代码围栏未配平")
    return issues


class AssetLibraryReadmeContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "05_资产库 README 不满足契约")

    def test_five_interfaces_match_protocol_truth(self):
        self.assertEqual(list(INTERFACES), interface_rows(self.text))
        protocol = PROTOCOL.read_text(encoding="utf-8")
        for name in INTERFACES:
            self.assertIn(name, protocol, name)

    def test_ledger_covers_official_assets(self):
        prov = provenance_text()
        for key in ASSETS:
            self.assertIn(key, prov, key)
            self.assertIn(key, asset_keys().get("keys", {}), key)
            self.assertTrue((USER_DIR / f"{key}.md").is_file(), key)

    def test_contract_catches_mutations(self):
        """变异自证：接口缺失 / 台账缺键 / 单层规则缺失 / 域包路径缺失 / 缺节 / 围栏。"""
        drop_iface = self.text.replace("| asset_roll(key, 权重表) |", "| asset_random(key) |", 1)
        self.assertTrue(any("五接口" in i for i in readme_issues(drop_iface)))
        bad_key = self.text.replace("STYLE_DNA", "STYLE_PROFILE")
        self.assertTrue(any("STYLE_DNA" in i or "资产键" in i
                            for i in readme_issues(bad_key)))
        no_layer = self.text.replace("单层货架不变量", "多层货架不变量", 1)
        self.assertTrue(any("单层" in i or "不建子目录" in i
                            for i in readme_issues(no_layer)))
        no_community = self.text.replace("community/<域包>/assets/", "community/assets/")
        self.assertTrue(any("域包" in i for i in readme_issues(no_community)))
        no_section = self.text.replace("## 6. 模块-资产引用映射（核准结论）",
                                       "## 6. 引用映射")
        self.assertTrue(any("缺节" in i for i in readme_issues(no_section)))
        odd = self.text + "\n" + FENCE + "\n"
        self.assertTrue(any("围栏" in i for i in readme_issues(odd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_asset_readme.md")


if __name__ == "__main__":
    unittest.main()
