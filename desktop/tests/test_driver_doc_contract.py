#!/usr/bin/env python3
"""docs/driver.md 契约：指令档路由文档必须「工作流/指令档/工具绑定/判据语义与实现一致」。

为什么必须有：这份文档声明「有机器面就走机器面、派发失败即停」——它的判据语义直接决定读者怎么判断红绿。
本轮修一处**判据过度陈述**：原文写工具名必须与 TOOL_DEFS「逐名一致」（集合相等），实现是**子集**校验
（引用名存在即可）；运行时 12 工具、绑定仅 8 + 1 提示，按「逐名一致」理解会得出相反结论。
本判据把三工作流、三指令档（含 override 块与关键词）、工具/提示子集关系、CLI 用法全部活绑定。

范围：只判本文与 driver.json / mcp_runtime / 三份指令档事实自洽（不改协议）。同族判据：
test_ai_routing_contract.py / test_ai_menu_contract.py / test_assembly_pack_contract.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、三工作流在文与数据、三指令档存在且头 14 行含 DRIVER OVERRIDE + 关键词、
工具绑定 ⊆ TOOL_DEFS（8 / 12）、提示 1、正文不再「逐名一致」、CLI 用法 + 现状对照 + 复现命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime  # noqa: E402

DOC = ROOT / "docs" / "driver.md"
DATA = ROOT / "protocol" / "driver.json"
NF = ROOT / "scripts" / "nf.py"
SECTIONS = ("## 是什么", "## 怎么用", "## 判据（可证）", "## 现状对照",
            "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"指令档路由文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("指令档路由文档为空")
    return text


def driver() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def driver_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 指令档机器面路由"):
        issues.append("缺标题「# 指令档机器面路由（driver override）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    doc = driver()
    wfs = list(doc.get("workflows") or {})
    if len(wfs) != 3:
        issues.append(f"工作流数已变（{len(wfs)}）")
    for wf in wfs:
        if wf not in text:
            issues.append(f"正文缺工作流：{wf}")
    live = {t["name"] for t in mcp_runtime.TOOL_DEFS}
    bound = list((doc.get("bindings") or {}).get("mcp.tools") or [])
    if not set(bound) <= live:
        issues.append("bindings 引用了运行时不存在工具")
    if len(bound) != 8:
        issues.append(f"绑定工具数已变（{len(bound)}）")
    if len(live) != 12:
        issues.append(f"运行时工具数已变（{len(live)}）")
    if "8 个" not in text or "12 个" not in text:
        issues.append("未写绑定 8 / 运行时 12")
    prompts = list((doc.get("bindings") or {}).get("mcp.prompts") or [])
    if len(prompts) != 1:
        issues.append(f"绑定提示数已变（{len(prompts)}）")
    def _quoted(ln: str) -> bool:
        return ln.lstrip().startswith(">") or "原写" in ln or "原文" in ln
    bad = [ln for ln in text.splitlines()
           if "逐名一致" in ln and not _quoted(ln)]
    if bad:
        issues.append("仍写「逐名一致」（实现是子集校验）")
    if "子集" not in text:
        issues.append("缺「子集校验」口径")
    kws = (doc.get("fail_closed") or {}).get("marker_keywords") or []
    docs = doc.get("documents") or []
    if len(docs) != 3:
        issues.append(f"指令档数已变（{len(docs)}）")
    for item in docs:
        rel = str(item.get("path") or "")
        p = ROOT / rel
        if not p.is_file():
            issues.append(f"指令档不存在：{rel}")
            continue
        head = "\n".join(p.read_text(encoding="utf-8").splitlines()[:14])
        if "DRIVER OVERRIDE" not in head:
            issues.append(f"{rel} 头 14 行缺 DRIVER OVERRIDE 块")
        for kw in kws:
            if kw not in head:
                issues.append(f"{rel} 缺 fail-closed 关键词：{kw}")
    nf = NF.read_text(encoding="utf-8")
    if '"--json"' not in nf:
        issues.append("CLI 缺 --json")
    if "driver" not in nf:
        issues.append("CLI 缺 driver")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py driver",
                "python scripts/nf.py driver assemble",
                "python -m pytest desktop/tests/test_ai_routing_contract.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "派发失败即停" not in text:
        issues.append("缺「派发失败即停」边界")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class DriverDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_driver_matches_contract(self):
        self.assertEqual([], driver_issues(self.text), "指令档路由文档不满足契约")

    def test_data_live(self):
        doc = driver()
        self.assertEqual(3, len(doc["workflows"]))
        self.assertEqual(3, len(doc["documents"]))
        self.assertEqual(8, len(doc["bindings"]["mcp.tools"]))
        self.assertEqual(12, len(mcp_runtime.TOOL_DEFS))
        self.assertEqual(1, len(doc["bindings"]["mcp.prompts"]))
        self.assertTrue(set(doc["bindings"]["mcp.tools"]) <=
                        {t["name"] for t in mcp_runtime.TOOL_DEFS})

    def test_contract_catches_mutations(self):
        """变异自证：回退「逐名一致」/ 缺工作流 / 缺工具数 / 缺指令档块 / 缺命令。"""
        back = self.text.replace("子集", "逐名一致")
        self.assertTrue(any("逐名一致" in i for i in driver_issues(back)))
        no_wf = self.text.replace("routing", "route")
        self.assertTrue(any("routing" in i for i in driver_issues(no_wf)))
        old_t = self.text.replace("12 个", "10 个")
        self.assertTrue(any("12" in i for i in driver_issues(old_t)))
        no_p = self.text.replace("python -m pytest desktop/tests/test_ai_routing_contract.py",
                                 "跑判据")
        self.assertTrue(any("test_ai_routing_contract" in i
                            for i in driver_issues(no_p)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_driver.md")


if __name__ == "__main__":
    unittest.main()
