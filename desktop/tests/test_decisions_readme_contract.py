#!/usr/bin/env python3
"""decisions/README 契约：公开面政策说明必须「白名单 ⇄ 判据 ⇄ 事实」三面对齐。

为什么必须有：这是 decisions/ handovers/ postmortems/ 三个内部治理目录的公开面政策说明——它既
要向读者解释「真实件在私有仓」，又要与 test_publish_boundary 的白名单、payload-policy 的
INTERNAL_DIRS、ERRATA schema 一致。本轮把「三目录政策段」「路由工具不属公开仓」「判据与入口」
「公开仓不出现真实 ADR 编号」立成机检断言，并修正硬编码本机私有路径的写法（改 <私有仓> 占位）。

范围：只判本文件与公开面事实的自洽（不改政策）。同族判据：
test_publish_boundary.py（白名单）/ test_decisions.py（语义）/
test_adr_0000_contract.py（政策本体）/
test_decisions_index_contract.py（投影）/ check33（决策层面）。
契约：三段结构、白名单与 PATTERNS 逐项对齐、三目录与判据入口在场、路由工具标明不属公开仓且
命令用占位路径、公开仓不出现真实 ADR 编号、payload-policy/ERRATA 事实一致。
"""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "decisions" / "README.md"
PAYLOAD = ROOT / "packaging" / "npm" / "tools" / "payload-policy.mjs"
ERRATA = ROOT / "decisions" / "ERRATA.json"
PROTOCOL = ROOT / "STRATEGY.md"

SECTIONS = ("## 本文件怎么读", "## 自动化路由", "## 判据与入口")
REQUIRED_MARKERS = ("ADR-0000", "ADR-9xxx", "ERRATA.json", "INDEX.md",
                    "test_publish_boundary.py", "nf decisions verify",
                    "nf decisions show", "nf decisions reindex", "check33",
                    "payload-policy.mjs", "INTERNAL_DIRS", "私有 Plan 仓",
                    "公开仓不包含", "dry-run")
WHITELIST_MENTIONS = ("README.md", "INDEX.md", "ERRATA.json", "ADR-0000", "ADR-9xxx")


def load_text(path: Path = README) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"decisions/README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("decisions/README 为空")
    return text


def publish_patterns() -> list:
    spec = importlib.util.spec_from_file_location(
        "publish_boundary_mod2", ROOT / "desktop" / "tests" / "test_publish_boundary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PATTERNS["decisions"]


def internal_dirs() -> list:
    text = PAYLOAD.read_text(encoding="utf-8")
    m = re.search(r"INTERNAL_DIRS\s*=\s*\[([^\]]+)\]", text)
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()] if m else []


def router_commands(text: str) -> list:
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("python ")]


def real_adr_ids(text: str) -> set:
    return set(re.findall(r"ADR-(\d{4})", text))


def readme_issues(text: str) -> list:
    issues = []
    if not text.startswith("# decisions/ · 决策记录"):
        issues.append("缺标题「# decisions/ · 决策记录」")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺节：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("三段顺序不对")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    for token in WHITELIST_MENTIONS:
        if token not in text:
            issues.append(f"白名单说明缺：{token}")
    patterns = publish_patterns()
    expected = [r"README\.md", r"INDEX\.md", r"ERRATA\.json",
                r"ADR-0000-[^/]+\.md", r"ADR-9\d{3}-[^/]+\.md"]
    if patterns != expected:
        issues.append(f"目录白名单与 README 说明不一致：{patterns}")
    for directory in ("decisions/", "handovers/", "postmortems/"):
        if directory not in text:
            issues.append(f"缺三目录之一：{directory}")
    if "STRATEGY.md" not in text:
        issues.append("缺 STRATEGY.md §四 依据")
    dirs = internal_dirs()
    for directory in ("decisions/", "handovers/", "postmortems/"):
        if directory not in dirs:
            issues.append(f"payload-policy INTERNAL_DIRS 缺：{directory}")
    if json.loads(ERRATA.read_text(encoding="utf-8")).get("schema") != "nf-decisions-errata/1":
        issues.append("ERRATA schema 非 nf-decisions-errata/1")
    commands = router_commands(text)
    if len(commands) < 4:
        issues.append(f"路由工具命令不足四条：{len(commands)}")
    for cmd in commands:
        if not cmd.startswith("python <私有仓>/tools/decision-archive-router.py"):
            issues.append(f"路由命令应使用 <私有仓> 占位（不硬编码本机路径）：{cmd}")
    ids = real_adr_ids(text)
    bad_ids = sorted(i for i in ids if i != "0000" and not i.startswith("9"))
    if bad_ids:
        issues.append(f"公开面只应出现 ADR-0000 与 ADR-9xxx 模板位，实测真实编号：{bad_ids}")
    if "不出现真实 ADR 编号" not in text:
        issues.append("缺「不出现真实 ADR 编号」口径")
    if not PROTOCOL.is_file():
        issues.append("缺 STRATEGY.md（依据文件）")
    return issues


class DecisionsReadmeContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_decisions_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "decisions/README 不满足契约")

    def test_whitelist_matches_publish_boundary(self):
        self.assertEqual(publish_patterns(), [r"README\.md", r"INDEX\.md", r"ERRATA\.json",
                                              r"ADR-0000-[^/]+\.md", r"ADR-9\d{3}-[^/]+\.md"])
        for token in WHITELIST_MENTIONS:
            self.assertIn(token, self.text)

    def test_no_real_adr_ids_or_local_paths(self):
        bad = [i for i in real_adr_ids(self.text) if i != "0000" and not i.startswith("9")]
        self.assertEqual([], bad)
        for cmd in router_commands(self.text):
            self.assertNotIn(":", cmd, cmd)

    def test_contract_catches_mutations(self):
        """变异自证：白名单漂移 / 硬编码本机路径 / 真实 ADR 编号 / 缺政策段 / 缺入口。"""
        no_errata = self.text.replace("ERRATA.json", "勘误")
        self.assertTrue(any("ERRATA" in i or "白名单" in i
                            for i in readme_issues(no_errata)))
        hard_path = self.text.replace("python <私有仓>/tools/decision-archive-router.py check",
                                      "python D:/NF-Plan/tools/decision-archive-router.py check", 1)
        self.assertTrue(any("<私有仓>" in i for i in readme_issues(hard_path)))
        real_id = self.text + "\n历史：ADR-0012 已归档。\n"
        self.assertTrue(any("ADR-0000" in i for i in readme_issues(real_id)))
        no_section = self.text.replace("## 本文件怎么读", "## 读法")
        self.assertTrue(any("缺节" in i for i in readme_issues(no_section)))
        no_note = self.text.replace("**公开仓不包含**", "**随仓分发**", 1)
        self.assertTrue(any("公开仓不包含" in i for i in readme_issues(no_note)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_decisions_readme.md")


if __name__ == "__main__":
    unittest.main()
