#!/usr/bin/env python3
"""docs/assertions.md 契约：数据化断言表文档必须「封闭集/表自身过门 + 现状活绑定 + 复现口径」。

为什么必须有：这是「断言即数据」的规范——它写的行字段（6 键）与现行数据（6 必填 + capability +
evidence）、表级字段（severity/capability 词表 + 能力索引）、条数（未计数 → 24）、severity 现状
（全 fail）都需与 protocol/assertions.json 与 runner 逐项一致；否则读者按旧字段写新断言会被
表自身判据打红而不知为何。本轮补字段表、现状对照、复现口径，并把封闭集/词表/条数/能力面立成断言。

范围：只判本文与 assertions.json/runner 事实自洽（不改机制）。同族判据：
test_assertions.py（21 例，表自身过门）/ test_lint.py（四型写法）/
test_doc_hygiene.py / test_doc_examples.py（命令块）。
契约：⛔ 标识 + last-updated + 复核位、四型封闭集表、字段表（6 必填 + capability/evidence）、
表级 schema/两词表/能力索引、现状 24 条全 fail、21 例判据、复现三命令、边界段保留。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import assertions as core_assertions  # noqa: E402

DOC = ROOT / "docs" / "assertions.md"
DATA = ROOT / "protocol" / "assertions.json"
TEST = ROOT / "desktop" / "tests" / "test_assertions.py"
NF = ROOT / "scripts" / "nf.py"
SECTIONS = ("## 是什么", "## 怎么用", "## 判据", "## 现状对照", "## 复现与引用口径", "## 边界")
KINDS = ("regex_absent", "regex_present", "count_at_least", "json_value")
REQUIRED = ("id", "severity", "kind", "params", "message", "fix")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"断言文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("断言文档为空")
    return text


def load_data() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def case_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def assertion_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 断言表（assertions）"):
        issues.append("缺标题「# 断言表（assertions）」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
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
    data = load_data()
    rows = data.get("assertions") or []
    if len(rows) != 24:
        issues.append(f"断言条数已变（{len(rows)}）：现状对照需复核")
    if "24 条" not in text:
        issues.append("未写现行条数（24 条）")
    kinds = sorted({r.get("kind") for r in rows})
    if kinds != sorted(KINDS):
        issues.append(f"kind 集合与封闭集不一致：{kinds}")
    for kind in KINDS:
        if kind not in text:
            issues.append(f"正文缺 kind：{kind}")
    if tuple(data.get("severity_vocabulary") or ()) != core_assertions.SEVERITIES:
        issues.append("数据 severity_vocabulary 与 runner 不一致")
    for field in REQUIRED:
        if field not in text:
            issues.append(f"字段缺：{field}")
    for field in ("capability", "evidence"):
        if field not in text:
            issues.append(f"字段缺：{field}")
    for marker in ("schema", "severity_vocabulary", "capability_vocabulary",
                   "capability_index"):
        if marker not in text:
            issues.append(f"表级字段缺：{marker}")
    cap_vocab = data.get("capability_vocabulary") or []
    cap_index = data.get("capability_index") or {}
    if len(cap_vocab) != 16 or len(cap_index) != 16:
        issues.append(f"能力面已变（vocab={len(cap_vocab)}, index={len(cap_index)}）")
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != len(ids):
        issues.append("断言 id 重复")
    for row in rows:
        for key in REQUIRED:
            if key not in row:
                issues.append(f"断言 {row.get('id')} 缺必填键：{key}")
        if not row.get("fix"):
            issues.append(f"断言 {row.get('id')} 缺 fix")
        if str(row.get("severity")) not in core_assertions.SEVERITIES:
            issues.append(f"断言 {row.get('id')} severity 越词表")
    if "全 fail" not in text and "全为 fail" not in text:
        issues.append("未写 severity 现状（现行 24 条全 fail）")
    n_cases = case_count()
    if n_cases != 21:
        issues.append(f"test_assertions 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写常驻判据例数（{n_cases} 例）")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("assertions", "lint"):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append(f"CLI 缺子命令：nf {sub}")
    for cmd in ("python scripts/nf.py assertions",
                "python scripts/nf.py assertions --json",
                "python -m pytest desktop/tests/test_assertions.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不扩表达力" not in text:
        issues.append("缺「不扩表达力」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class AssertionsDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_assertions_matches_contract(self):
        self.assertEqual([], assertion_issues(self.text), "断言文档不满足契约")

    def test_data_and_runner_live(self):
        data = load_data()
        self.assertEqual("nf-assertions/1", data.get("schema"))
        self.assertEqual(24, len(data["assertions"]))
        self.assertEqual(4, len({r["kind"] for r in data["assertions"]}))
        self.assertEqual(tuple(core_assertions.SEVERITIES), ("fail", "warn"))
        self.assertEqual(21, case_count())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 条数回退 / 缺 kind / 缺 capability / 假称 severity / 缺命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in assertion_issues(no_date)))
        old_n = self.text.replace("24 条", "10 条")
        self.assertTrue(any("24" in i for i in assertion_issues(old_n)))
        no_kind = self.text.replace("json_value", "json_ok")
        self.assertTrue(any("json_value" in i for i in assertion_issues(no_kind)))
        no_cap = self.text.replace("capability_vocabulary", "cap_vocab")
        self.assertTrue(any("capability" in i for i in assertion_issues(no_cap)))
        wrong_sev = self.text.replace("全为 fail", "全为 warn").replace("全 fail", "全 warn")
        self.assertTrue(any("severity" in i or "fail" in i
                            for i in assertion_issues(wrong_sev)))
        no_cmd = self.text.replace("python scripts/nf.py assertions --json", "看全表")
        self.assertTrue(any("--json" in i for i in assertion_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_assertions.md")


if __name__ == "__main__":
    unittest.main()
