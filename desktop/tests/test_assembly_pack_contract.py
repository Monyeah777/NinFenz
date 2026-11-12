#!/usr/bin/env python3
"""docs/agent/agent_组装指令包_v0.2 契约：装配指令包必须「与现行入口/门禁一致 + 无退役面指引」。

为什么必须有：这是给外部 Agent 的装配操作规范——旧版把「通道 A」写成**桌面工具**（本地导入勾选），
但桌面端壳已于 2026-09-09 永久退役（L3_FROZEN：公开面不得再出现桌面工具指引）；且自检失范口径
仍写 execution_drill R1-R4（现为 R1–R8 / 6 条硬断言）。本轮把通道 A 改为 CLI、对齐失范口径、
补复核位与「八段为最低要求」说明，并把这几条立成机检断言。

范围：只判本文与 CLI/driver/L3 事实自洽（不改装配流程）。同族判据：
test_l3_frozen_contract.py（退役面）/ test_doc_hygiene.py（指令档标识）/
test_assembly_reference_contract.py（skills 侧装配参考）/ test_doc_examples.py。
契约：⛔ 标识 + last-updated + 复核位、DRIVER OVERRIDE 与 driver.json 的 assemble 工作流、
取货顺序五件、八段骨架 ##0–##7 + 「最低要求」、自检 7 项、
无桌面工具通道指引 + 退役声明 + L3 引用、
失范口径 R1–R8（且无 R1-R4 残留）、CLI assemble/import 在册。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

DOC = ROOT / "docs" / "agent" / "agent_组装指令包_v0.2.md"
NF = ROOT / "scripts" / "nf.py"
DRIVER = ROOT / "protocol" / "driver.json"
L3 = ROOT / "docs" / "L3_FROZEN.md"
FETCH = ("07_官方核心出厂与社区预设导航", "02_联动注册表", "01_核心协议",
         "community/校园情感领域包", "06_Agent执行协议")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"装配指令包不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("装配指令包为空")
    return text


def pack_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 宁封子 · Agent 组装指令包"):
        issues.append("缺标题「# 宁封子 · Agent 组装指令包」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核（2026-11-13）" not in text:
        issues.append("缺「复核（2026-11-13）」位")
    for marker in ("R1–R8", "最低要求", "12 只读工具"):
        if marker not in text:
            issues.append(f"复核口径缺要素：{marker}")
    if "DRIVER OVERRIDE" not in text:
        issues.append("缺 DRIVER OVERRIDE 块")
    driver = json.loads(DRIVER.read_text(encoding="utf-8"))
    if "assemble" not in (driver.get("workflows") or {}):
        issues.append("driver.json 缺 assemble 工作流（本包映射失效）")
    if "assemble_guide" not in text:
        issues.append("缺 MCP 提示名 assemble_guide")
    for tool in ("module_read", "pipeline_read", "asset_read"):
        if tool not in text:
            issues.append(f"MCP 内容工具缺：{tool}")
    for rel in FETCH:
        if rel not in text:
            issues.append(f"取货顺序缺件：{rel}")
    for n in range(8):
        if ("## " + str(n)) not in text:
            issues.append(f"八段骨架缺段：## {n}")
    if "## 0 到 ## 7" not in text:
        issues.append("缺「## 0 到 ## 7 全段」骨架声明")
    checks = [ln for ln in text.splitlines() if ln.strip().startswith("- [ ]")]
    if len(checks) != 7:
        issues.append(f"自检清单项数应为 7（实测 {len(checks)}）")
    if "桌面工具是通道 A" in text or "本地导入勾选" in text:
        issues.append("残留桌面工具通道指引（端壳已退役）")
    if "桌面端壳已于 2026-09-09 永久退役" not in text:
        issues.append("缺桌面端壳退役声明")
    if "docs/L3_FROZEN.md" not in text:
        issues.append("缺 L3_FROZEN 引用")
    if "R1-R4" in text:
        issues.append("残留旧失范口径 R1-R4（现为 R1–R8）")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("assemble", "import"):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append(f"CLI 缺子命令：nf {sub}")
    for cmd in ("nf assemble", "nf import"):
        if cmd not in text:
            issues.append(f"通道 A 缺 CLI 命令：{cmd}")
    if not L3.is_file():
        issues.append("缺 docs/L3_FROZEN.md")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class AssemblyPackContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pack_matches_contract(self):
        self.assertEqual([], pack_issues(self.text), "装配指令包不满足契约")

    def test_cli_and_driver_live(self):
        nf = NF.read_text(encoding="utf-8")
        for sub in ("assemble", "import"):
            self.assertIn("add_parser(" + chr(34) + sub + chr(34), nf)
        driver = json.loads(DRIVER.read_text(encoding="utf-8"))
        self.assertIn("assemble", driver["workflows"])
        self.assertTrue(L3.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：回退桌面通道 / 旧失范口径 / 缺八段 / 缺自检 / 缺退役声明 / 缺 DRIVER。"""
        desk = self.text + "\n桌面工具是通道 A（本地导入勾选）。\n"
        self.assertTrue(any("桌面工具" in i for i in pack_issues(desk)))
        old_rules = self.text.replace("R1–R8", "R1-R4")
        self.assertTrue(any("R1-R4" in i or "R1–R8" in i for i in pack_issues(old_rules)))
        no_skeleton = self.text.replace("## 7", "## 七")
        self.assertTrue(any("## 7" in i or "骨架" in i for i in pack_issues(no_skeleton)))
        check_line = "- [ ] 模块编号全部合法且全文一致（含类别前缀）"
        no_checks = self.text.replace(check_line, "- 模块编号")
        self.assertTrue(any("自检清单" in i for i in pack_issues(no_checks)))
        no_retire = self.text.replace("桌面端壳已于 2026-09-09 永久退役", "端壳已调整")
        self.assertTrue(any("退役声明" in i for i in pack_issues(no_retire)))
        no_driver = self.text.replace("DRIVER OVERRIDE", "驱动覆盖")
        self.assertTrue(any("DRIVER" in i for i in pack_issues(no_driver)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_pack.md")


if __name__ == "__main__":
    unittest.main()
