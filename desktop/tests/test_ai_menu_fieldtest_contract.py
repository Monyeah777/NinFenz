#!/usr/bin/env python3
"""docs/ai-menu-fieldtest-v1 契约：执行状态如实 + 与菜单 v0.3 口径同步 + 回填位在。

为什么必须有：这是外部实测（Y5）的作业书，而外部实测按 STRATEGY 封闭期**封存挂账**——若文档不标
「尚未执行」，读者/外部 AI 会把作业书当「已有实测结果」；同时它配套菜单已升到 v0.3（样本节号、
九层口径、M22 挂载、Y5 回填位都变了），旧口径会让实测项照着过时菜单跑。本轮补状态、现状对照、
v0.3 口径同步与回填位，并把「未执行 + 四处口径 + 回填位」立成机检断言。

范围：只判本文与 ai-menu/回填位事实自洽（不跑实测、不改实测项结构）。同族判据：
test_doc_hygiene.py（指令档标识）/ test_doc_examples.py（命令块）/
test_doc_reachability.py（路径可达）/ docs/ai-menu.md（配套菜单真源）。
契约：⛔ 标识 + last-updated + 执行状态（尚未执行/封存/作者显式触发）、8 个实测项（第 0–7）、
防污染红线两条、菜单 v0.3 与 8 个展开段一致、样本节号/九层口径/M22 挂 P30/回填位四处同步、
回填文件存在、汇总回执 8 行。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

DOC = ROOT / "docs" / "ai-menu-fieldtest-v1.md"
MENU = ROOT / "docs" / "ai-menu.md"
BACKFILL = ROOT / "results" / "docs_external-validation-v2.7.md"
ITEMS = tuple("第 " + str(n) + " 项" for n in range(8))


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Y5 作业书不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("Y5 作业书为空")
    return text


def menu_sections() -> int:
    return sum(1 for ln in MENU.read_text(encoding="utf-8").splitlines()
               if ln.startswith("### ") and "️⃣" in ln)


def fieldtest_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 🧪 NF 菜单 · 逐项实测作业书"):
        issues.append("缺标题「# 🧪 NF 菜单 · 逐项实测作业书」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    for marker in ("尚未执行", "封存挂账", "作者显式触发"):
        if marker not in text:
            issues.append(f"执行状态缺要素：{marker}")
    for item in ITEMS:
        if item not in text:
            issues.append(f"缺实测项：{item}")
    if "第 5 项禁止真发 Issue" not in text or "第 6 项禁止真入库" not in text:
        issues.append("缺防污染红线两条")
    menu = MENU.read_text(encoding="utf-8")
    if "v0.3" not in menu:
        issues.append("配套菜单不是 v0.3（口径同步前提失效）")
    if "v0.3" not in text:
        issues.append("本文未声明配套菜单 v0.3")
    n_sec = menu_sections()
    if n_sec != 8:
        issues.append(f"菜单展开段已变（{n_sec}）：实测项需复核")
    for marker in ("## 6. 装载指引", "九层装配流", "P00–P80", "P01/P90", "骨架 P00",
                   "M22", "P30", "Y5 记录位"):
        if marker not in text:
            issues.append(f"v0.3 口径缺要素：{marker}")
    if "docs_external-validation-v2.7.md" not in text:
        issues.append("缺回填位路径")
    if not BACKFILL.is_file():
        issues.append("回填位文件不存在")
    if "docs_external-validation-v2.7.md" not in menu:
        issues.append("菜单 v0.3 缺 Y5 回填位（两侧不一致）")
    for n in range(8):
        if not any(ln.strip().startswith("[" + str(n) + "]") for ln in text.splitlines()):
            issues.append(f"汇总回执缺行：[{n}]")
    if "菜单v0.3 / 作业书v1" not in text:
        issues.append("汇总回执标题未标菜单 v0.3")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ImageMenuFieldtestContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_fieldtest_matches_contract(self):
        self.assertEqual([], fieldtest_issues(self.text), "Y5 作业书不满足契约")

    def test_menu_version_and_backfill_live(self):
        menu = MENU.read_text(encoding="utf-8")
        self.assertIn("v0.3", menu)
        self.assertEqual(8, menu_sections())
        self.assertTrue(BACKFILL.is_file())
        self.assertIn("docs_external-validation-v2.7.md", menu)

    def test_contract_catches_mutations(self):
        """变异自证：去执行状态 / 去 v0.3 / 缺实测项 / 缺防污染 / 缺回填位 / 回执缺行。"""
        no_status = self.text.replace("尚未执行", "进行中")
        self.assertTrue(any("尚未执行" in i for i in fieldtest_issues(no_status)))
        old_menu = self.text.replace("v0.3", "v0.2")
        self.assertTrue(any("v0.3" in i for i in fieldtest_issues(old_menu)))
        no_item = self.text.replace("第 4 项", "第 4 步")
        self.assertTrue(any("第 4 项" in i for i in fieldtest_issues(no_item)))
        no_guard = self.text.replace("第 6 项禁止真入库", "第 6 项照常入库")
        self.assertTrue(any("防污染" in i for i in fieldtest_issues(no_guard)))
        no_backfill = self.text.replace("docs_external-validation-v2.7.md", "回填文件")
        self.assertTrue(any("回填位" in i for i in fieldtest_issues(no_backfill)))
        no_line = self.text.replace("[7] 实测总结", "总结")
        self.assertTrue(any("[7]" in i for i in fieldtest_issues(no_line)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_fieldtest.md")


if __name__ == "__main__":
    unittest.main()
