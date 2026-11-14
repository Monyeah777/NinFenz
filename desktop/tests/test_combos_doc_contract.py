#!/usr/bin/env python3
"""docs/combos.md 契约：组合引擎文档必须「包数/广度/证书/产物化与实跑一致」。

为什么必须有：这份文档是「任意子集可自由组合」的对外口径——包数、C(n,2) 广度、证书条数、
产物化组合包数，任何一处漂移都会让「广度证明」变成自述。本轮修三处真实陈旧/自相矛盾：
107 包/C(107,2)=5671（实为 111/C(111,2)=6105，且与本页广度表 6105 矛盾）、证书 17→18、产物化 4→5。
本判据把包数、两两全集、证书条数与包数分布、产物化清单、五条不变量全部活绑定。

范围：只判本文与 combo registry/证书/包目录事实自洽（不改引擎）。同族判据：
test_pack_combo.py（24 例）/ check32 combos 子扫描 / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、111 包与 C(111,2)=6105、证书 18 与分布、五产物化包在场且被点名、
五条不变量在文、现状对照 + 复现命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "combos.md"
CERTS = ROOT / "protocol" / "combo_certificates.json"
COMMUNITY = ROOT / "community"
SECTIONS = ("## 是什么", "## 五条不变量", "## 广度证明", "## 组合包产物化",
            "## 证书（可机验产出）", "## 边界与不宣称")
MADE = ("校园西幻轻混组合包", "组合包-检索栈", "组合包-数据管线", "组合包-受监管行业",
        "组合包-轻混与保险")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"组合文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("组合文档为空")
    return text


def certs() -> list:
    data = json.loads(CERTS.read_text(encoding="utf-8"))
    return data.get("certificates") or []


def combo_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 域包自由组合（combos）"):
        issues.append("缺标题「# 域包自由组合（combos）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    if "111" not in text:
        issues.append("未写 111 个已登记包")
    if "C(111,2) = 6105" not in text:
        issues.append("未写 C(111,2)=6105")
    for stale in ("107", "5671", "17 条"):
        bad = [ln for ln in text.splitlines()
               if stale in ln and "原写" not in ln]
        if bad:
            issues.append(f"仍残留陈旧数字：{stale}")
    cs = certs()
    if len(cs) != 18:
        issues.append(f"证书条数已变（{len(cs)}）")
    if "**18 条声明证书**" not in text:
        issues.append("未写 18 条证书")
    from collections import Counter
    dist = Counter(len(c.get("packs") or []) for c in cs)
    want = {0: 1, 2: 7, 3: 4, 4: 5, 111: 1}
    if dict(dist) != want:
        issues.append(f"证书包数分布已变：{sorted(dist.items())}")
    for marker in ("0 包组件级混搭 **1**", "两包 **7**", "三包 **4**", "四包 **5**",
                   "全装极限 **1**"):
        if marker not in text:
            issues.append(f"分布描述缺要素：{marker}")
    dirs = [p.name for p in COMMUNITY.iterdir() if p.is_dir()]
    for name in MADE:
        if name not in dirs:
            issues.append(f"产物化组合包不存在：{name}")
        if name not in text:
            issues.append(f"正文缺产物化组合包：{name}")
    if "5 个组合包" not in text:
        issues.append("未写 5 个产物化组合包")
    for inv in ("模块唯一可定位", "依赖闭合", "事件闭合", "层位堆叠确定", "资产可寻址"):
        if inv not in text:
            issues.append(f"不变量缺：{inv}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("combine plan", "combine breadth", "combine verify"):
        if ("nf " + cmd) not in text and ("nf.py " + cmd) not in text:
            issues.append(f"复现口径缺命令：nf {cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class CombosDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_combos_matches_contract(self):
        self.assertEqual([], combo_issues(self.text), "组合文档不满足契约")

    def test_data_live(self):
        cs = certs()
        self.assertEqual(18, len(cs))
        from collections import Counter
        self.assertEqual({0: 1, 2: 7, 3: 4, 4: 5, 111: 1},
                         dict(Counter(len(c.get("packs") or []) for c in cs)))
        dirs = [p.name for p in COMMUNITY.iterdir() if p.is_dir()]
        for name in MADE:
            self.assertIn(name, dirs)

    def test_contract_catches_mutations(self):
        """变异自证：包数回退 / 广度回退 / 证书数回退 / 缺不变量 / 缺命令。"""
        back = self.text.replace("111", "107")
        self.assertTrue(any("111" in i or "107" in i for i in combo_issues(back)))
        old_g = self.text.replace("C(111,2) = 6105", "C(111,2) = 5671")
        self.assertTrue(any("6105" in i for i in combo_issues(old_g)))
        old_c = self.text.replace("**18 条声明证书**", "**17 条声明证书**")
        self.assertTrue(any("18 条" in i or "证书" in i for i in combo_issues(old_c)))
        no_inv = self.text.replace("事件闭合", "事件")
        self.assertTrue(any("事件闭合" in i for i in combo_issues(no_inv)))
        no_cmd = self.text.replace("nf.py combine verify", "校验组合")
        self.assertTrue(any("combine verify" in i for i in combo_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_combos.md")


if __name__ == "__main__":
    unittest.main()
