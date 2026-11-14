#!/usr/bin/env python3
"""docs/paste_card.md 契约：冻结归档卡必须「8 段/编号域/7 项/分片规则 + 防篡改锚」不变。

为什么必须有：这张卡是 2026-09-07 作者裁决免除 B2 通道后**冻结留档**的纯文本装配协议——
八段硬骨架、M91–M99 编号域、七项自检、防静默截断的分片规则，是它有资格留档的全部理由。
它「不再维护」，所以最需要的不是描述而是**防篡改锚**：本轮只补索引与 sha256 前 16 位锚，
正文一个字未动；判据校验锚，任何改动必须先说明理由再同步锚。

范围：只判本文与冻结原文事实自洽（不改卡面正文）。
同族判据：test_doc_hygiene.py / test_live_doc_counts.py / test_doc_examples.py。
契约：最后更新位 + 复核、8 段逐段在文、M91–M99、自检 7 项、分片 2 段、v0.3 冻结口径、
sha256 锚（正文 976 字符 / 前 16 位）与实测相等、核验命令。
"""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "paste_card.md"
MARK = "## 以下为冻结原文（v0.3）"
DIGEST = "2e8ff216bf31bfb8"
SECTIONS = tuple(str(n) for n in range(8))
STAGES = ("装配记录", "世界速览", "管线", "注册表投影", "模块库", "资产",
          "装载指引", "自检清单")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"粘贴卡不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("粘贴卡为空")
    return text


def frozen_body(text: str) -> str:
    return text.split(MARK)[-1].lstrip()


def card_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 粘贴卡 paste_card"):
        issues.append("缺标题「# 粘贴卡 paste_card · 纯文本创作（归档 · 不再维护）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    body = frozen_body(text)
    for stage in STAGES:
        if stage not in body:
            issues.append(f"冻结正文缺段名：{stage}")
    for n in SECTIONS:
        if (chr(10) + n + ". ") not in body and (n + ". ") not in body:
            issues.append(f"冻结正文缺段号：{n}")
    if "M91–M99" not in body:
        issues.append("冻结正文缺编号域 M91–M99")
    if "【自检七项】" not in body:
        issues.append("冻结正文缺【自检七项】")
    if "===第 1 部分完" not in body:
        issues.append("冻结正文缺分片标记")
    if "v0.3" not in text:
        issues.append("缺冻结版本 v0.3 口径")
    if "不再维护" not in text:
        issues.append("缺「不再维护」状态")
    if "**8**" not in text:
        issues.append("未写 8 段")
    if "**7 项**" not in text:
        issues.append("未写 7 项自检")
    if "**2 段**" not in text:
        issues.append("未写分片 2 段")
    actual = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    if actual != DIGEST:
        issues.append(f"冻结正文被改动（sha256 {actual} ≠ {DIGEST}）")
    if DIGEST not in text:
        issues.append("正文未记录 sha256 锚")
    if "976 字符" not in text:
        issues.append("未写正文长度 976 字符")
    if "test_paste_card_doc_contract.py" not in text:
        issues.append("缺核验判据点名")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PasteCardDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_card_matches_contract(self):
        self.assertEqual([], card_issues(self.text), "粘贴卡不满足契约")

    def test_frozen_digest_live(self):
        body = frozen_body(self.text)
        self.assertEqual(976, len(body))
        self.assertEqual(DIGEST, hashlib.sha256(body.encode("utf-8")).hexdigest()[:16])

    def test_contract_catches_mutations(self):
        """变异自证：改正文（锚红）/ 缺自检项 / 缺编号域 / 缺分片 / 缺长度。"""
        mutated = self.text.replace("③每个触发必有对应结算（事件闭合）",
                                    "③每个触发对应结算")
        self.assertTrue(any("sha256" in i for i in card_issues(mutated)))
        no_self = self.text.replace("【自检七项】", "【自检】")
        self.assertTrue(any("自检七项" in i for i in card_issues(no_self)))
        no_dom = self.text.replace("M91–M99", "M91-M99")
        self.assertTrue(any("M91–M99" in i for i in card_issues(no_dom)))
        no_shard = self.text.replace("===第 1 部分完", "===第一部分完")
        self.assertTrue(any("分片" in i for i in card_issues(no_shard)))
        no_len = self.text.replace("976 字符", "若干字符")
        self.assertTrue(any("976" in i for i in card_issues(no_len)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_card.md")


if __name__ == "__main__":
    unittest.main()
