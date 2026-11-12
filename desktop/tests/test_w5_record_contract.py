#!/usr/bin/env python3
"""docs/41_波C_W5 契约：历史 lint/日志记录必须「快照状态 + D4 接线现状 + D3/D4 分工 + 复现口径」。

为什么必须有：这份记录写着「mcp_runtime.main 接入 plog 启动/退出日志」——但 2026-10-01 架构收口
为守 SDP **移除了 plog 出边**（换入 json_schema），启动行改为直接 sys.stderr.write。不标明这一点，
维护者会以为日志层仍经 plog 接线；同时 D3 的 ruff 规则集（语法级 E9/F63/F7/F82）与风格棘轮
（E501/I001/F401…）是两套面，也容易被混读成「全库风格门禁」。本轮补快照横幅、现状对照、
复现口径，并把「规则集/接线现状/分工」立成机检断言。

范围：只判本文与现行 ruff/plog 事实自洽（不改历史数值）。同族判据：
test_plog.py（日志层）/ test_style_ratchet.py（风格棘轮）/
test_c1c2_record_contract.py（同类快照模板）/
test_doc_reachability.py（ARCHIVE_DOCS，故 glob 定位）。
契约：标题 + 快照横幅、五段按序、历史值保留（0.16.6 / 406 / PASS=39）、ruff.toml 规则集一致、
lint.yml / plog.py / test_plog.py 在场、D4 接线现状（mcp_runtime 直接 stderr、无 plog 出边）、
D3 与风格棘轮分工声明、复现三命令。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HITS = sorted((ROOT / "docs").glob("41_波C_W5*_实测记录.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-w5.md"
RUFF = ROOT / "ruff.toml"
LINT_YML = ROOT / ".github" / "workflows" / "lint.yml"
PLOG = ROOT / "desktop" / "src" / "core" / "plog.py"
PLOG_TEST = ROOT / "desktop" / "tests" / "test_plog.py"
MCP = ROOT / "desktop" / "src" / "core" / "mcp_runtime.py"
SECTIONS = ("## D3", "## D4", "## 回归", "## 现状对照", "## 复现与引用口径")
HISTORICAL = ("0.16.6", "406", "PASS=39")
CURRENT = ("0.16.8", "已改", "sys.stderr.write", "test_style_ratchet", "规则集不变")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"W5 记录不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("W5 记录为空")
    return text


def ruff_select() -> list:
    text = RUFF.read_text(encoding="utf-8")
    m = re.search(r"select\s*=\s*\[([^\]]+)\]", text)
    if not m:
        return []
    return [part.strip().strip('"').strip("'") for part in m.group(1).split(",") if part.strip()]


def w5_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 41 波C W5 实测记录"):
        issues.append("缺标题「# 41 波C W5 实测记录」")
    if "状态：历史实测快照" not in text:
        issues.append("缺「历史实测快照」状态横幅")
    if "不随仓库演进而改写" not in text:
        issues.append("缺「不随演进改写」声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("五段顺序不对")
    for marker in HISTORICAL:
        if marker not in text:
            issues.append(f"历史数值被改写：{marker}")
    for marker in CURRENT:
        if marker not in text:
            issues.append(f"现状对照缺要素：{marker}")
    select = ruff_select()
    if select != ["E9", "F63", "F7", "F82"]:
        issues.append(f"ruff.toml 规则集已变（{select}）：现状对照需复核")
    if "E9/F63/F7/F82" not in text:
        issues.append("未写 D3 规则集 E9/F63/F7/F82")
    for path in (LINT_YML, PLOG, PLOG_TEST):
        if not path.is_file():
            issues.append(f"交付件不存在：{path.relative_to(ROOT).as_posix()}")
    mcp = MCP.read_text(encoding="utf-8")
    if "import plog" in mcp or "from core import plog" in mcp:
        issues.append("mcp_runtime 仍 import plog（与「已移出 plog 出边」叙述矛盾）")
    if "sys.stderr.write" not in mcp:
        issues.append("mcp_runtime 缺直接 stderr 启动行")
    if "test_style_ratchet" not in text:
        issues.append("缺 D3 与风格棘轮的分工声明")
    for cmd in ("ruff check desktop/src scripts --select E9,F63,F7,F82",
                "python -m pytest desktop/tests/test_plog.py", "python -m py_compile"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class W5RecordContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_w5_record_matches_contract(self):
        self.assertEqual([], w5_issues(self.text), "W5 记录不满足契约")

    def test_rule_set_and_plog_facts(self):
        self.assertEqual(["E9", "F63", "F7", "F82"], ruff_select())
        self.assertNotIn("from core import plog", MCP.read_text(encoding="utf-8"))
        self.assertIn("sys.stderr.write", MCP.read_text(encoding="utf-8"))

    def test_contract_catches_mutations(self):
        """变异自证：去快照横幅 / 数值回退 / 接线现状 / 缺分工 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史实测快照**", "> **状态：现行**", 1)
        self.assertTrue(any("历史实测快照" in i for i in w5_issues(no_banner)))
        old_version = self.text.replace("0.16.6", "0.13.0")
        self.assertTrue(any("0.16.6" in i for i in w5_issues(old_version)))
        no_fact = self.text.replace("sys.stderr.write", "写日志")
        self.assertTrue(any("stderr" in i for i in w5_issues(no_fact)))
        no_split = self.text.replace("test_style_ratchet", "风格门禁")
        self.assertTrue(any("test_style_ratchet" in i for i in w5_issues(no_split)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in w5_issues(no_sec)))
        ruff_cmd = "ruff check desktop/src scripts --select E9,F63,F7,F82"
        no_cmd = self.text.replace(ruff_cmd, "跑 ruff")
        self.assertTrue(any("ruff check" in i for i in w5_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_w5.md")


if __name__ == "__main__":
    unittest.main()
