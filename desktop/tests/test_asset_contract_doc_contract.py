#!/usr/bin/env python3
"""docs/asset_contract.md 契约：四面/声明/CLI/同源判据与实现一致 + 现状活绑定。

为什么必须有：这是「声明即契约」的格式规范——读者按它写声明表；若文档漏掉现行 CLI 旗标（--freeze
是显式棘轮、--run-tests 默认关闭）或条数/资产面现状，人会误传「扫描器会自动重冻」「门禁会跑被声明
代码」。本轮补复核位、现状对照、复现口径，并把四面声明计数、六旗标、同源 check40、导出件、常驻
判据例数立成机检断言。

范围：只判本文与 asset_contracts/CLI/check40 事实自洽（不改规范）。同族判据：
test_asset_contract.py（59 例）/ test_asset_contract_faces.py /
test_asset_density.py / test_doc_hygiene.py / test_doc_examples.py。
契约：四面表 4 行、声明计数 10/7/4/1/1、六旗标在册、check40 同源、frictionless 导出件在场、
data_contracts 登记册在场、资产面 103/308/0/0、59 例判据、现状对照与复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import asset_ledger  # noqa: E402

DOC = ROOT / "docs" / "asset_contract.md"
DATA = ROOT / "protocol" / "asset_contracts.json"
SCHEMA = ROOT / "protocol" / "schema" / "asset_contracts.schema.json"
REGISTRY = ROOT / "protocol" / "data_contracts.json"
EXPORT = ROOT / "protocol" / "generated" / "asset_contract.frictionless.json"
NF = ROOT / "scripts" / "nf.py"
VERIFY = ROOT / "verify.sh"
TEST = ROOT / "desktop" / "tests" / "test_asset_contract.py"
FACES = ("data", "code", "script", "index")
FLAGS = ("--root", "--face", "--export", "--freeze", "--run-tests", "--json")
SECTIONS = ("## 这份规范解决什么", "## 四面", "## 便携格式", "## 带自己的资产来验",
            "## 现状对照", "## 复现与引用口径", "## 纪律")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"资产契约文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("资产契约文档为空")
    return text


def contracts() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def case_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def asset_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 数字资产契约"):
        issues.append("缺标题「# 数字资产契约（asset contracts）」")
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
    data = contracts()
    counts = {k: len(data.get(k) or []) for k in ("data", "code", "script", "index",
                                                  "chains")}
    expect = {"data": 10, "code": 7, "script": 4, "index": 1, "chains": 1}
    if counts != expect:
        issues.append(f"声明计数已变：{counts}")
    for face in FACES:
        if face not in text:
            issues.append(f"正文缺面：{face}")
    for label in ("22 面条", "1 链", "data 10", "code 7", "script 4", "index 1"):
        if label not in text:
            issues.append(f"现状计数缺要素：{label}")
    nf = NF.read_text(encoding="utf-8")
    for flag in FLAGS:
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺旗标：{flag}")
    for flag in FLAGS:
        if flag not in text:
            issues.append(f"正文缺旗标：{flag}")
    verify = VERIFY.read_text(encoding="utf-8")
    if "check40" not in verify:
        issues.append("verify.sh 缺 check40（同源判据失效）")
    if "check40" not in text:
        issues.append("未写与 check40 同源")
    for path in (SCHEMA, REGISTRY, EXPORT):
        if not path.is_file():
            issues.append(f"缺件：{path.relative_to(ROOT).as_posix()}")
    if "frictionless" not in text:
        issues.append("缺 frictionless 导出面说明")
    if "data_contracts" not in text:
        issues.append("缺登记册 data_contracts")
    _issues, stats = asset_ledger.verify_root(str(ROOT))
    if stats.get("ledgers") != 103:
        issues.append(f"资产台账数已变（{stats.get('ledgers')}）")
    if stats.get("assets") != 308:
        issues.append(f"托管资产数已变（{stats.get('assets')}）")
    if stats.get("untracked") != 0 or stats.get("orphans") != 0:
        issues.append("资产面未闭合（未托管/孤儿头非 0）")
    for marker in ("台账 103", "托管 308", "未托管 0", "孤儿头 0"):
        if marker not in text:
            issues.append(f"资产面现状缺：{marker}")
    n_cases = case_count()
    if n_cases != 59:
        issues.append(f"test_asset_contract 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写常驻判据例数（{n_cases} 例）")
    for cmd in ("python scripts/nf.py asset contract --json",
                "python scripts/nf.py asset contract --face data",
                "python scripts/nf.py asset verify"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不许登记" not in text:
        issues.append("缺「指不出判据的资产不许登记」原则")
    if "显式棘轮" not in text:
        issues.append("缺 --freeze 显式棘轮口径")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class AssetContractDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_asset_contract_matches_contract(self):
        self.assertEqual([], asset_issues(self.text), "资产契约文档不满足契约")

    def test_counts_and_files_live(self):
        data = contracts()
        self.assertEqual(10, len(data["data"]))
        self.assertEqual(7, len(data["code"]))
        self.assertEqual(4, len(data["script"]))
        self.assertEqual(1, len(data["index"]))
        self.assertEqual(1, len(data["chains"]))
        for path in (SCHEMA, REGISTRY, EXPORT):
            self.assertTrue(path.is_file(), path)
        self.assertEqual(59, case_count())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 计数回退 / 缺旗标 / 缺 check40 / 缺导出面 / 缺资产面 / 缺命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in asset_issues(no_date)))
        old_counts = self.text.replace("data 10", "data 8")
        self.assertTrue(any("计数" in i or "10" in i for i in asset_issues(old_counts)))
        no_flag = self.text.replace("--run-tests", "--run")
        self.assertTrue(any("--run-tests" in i for i in asset_issues(no_flag)))
        no_check = self.text.replace("check40", "某 check")
        self.assertTrue(any("check40" in i for i in asset_issues(no_check)))
        no_export = self.text.replace("frictionless", "导出件")
        self.assertTrue(any("frictionless" in i for i in asset_issues(no_export)))
        no_face = self.text.replace("托管 308", "托管很多")
        self.assertTrue(any("托管" in i for i in asset_issues(no_face)))
        no_cmd = self.text.replace("python scripts/nf.py asset verify", "看资产")
        self.assertTrue(any("asset verify" in i for i in asset_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_asset.md")


if __name__ == "__main__":
    unittest.main()
