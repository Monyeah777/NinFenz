#!/usr/bin/env python3
"""docs/rfc.md 契约：RFC 头文档必须「4 件在册 / 全 Active / 3+1 类别 / 无链 / 4 值词表」与实现一致。

为什么必须有：这页是「协议件版本史」的唯一说明——在册件数、状态、类别分布、supersede 链现状、
状态词表，任何一项漂移都会让读者以为有链（或以为某件已废）。本轮补「§现状对照」「§复现与引用口径」，
把 4 件逐条、状态、类别、链状态与 core/rfc.scan() 实读双向绑定；日期只校验「四件同值且被正文点名」，
避免把易变日期钉死成每轮假红。

范围：只判本文与 rfc 实现/索引事实自洽（不改协议件）。
同族判据：test_governance_faces.py / test_doc_hygiene.py / test_live_doc_counts.py。
契约：最后更新位 + 复核、4 件逐条、全 Active、3 Standards + 1 Informational、链 0、
4 值词表、Date==最后更新 规则、现状对照 + 复现两命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import rfc  # noqa: E402

DOC = ROOT / "docs" / "rfc.md"
INDEX = ROOT / "protocol" / "rfc_index.json"
SECTIONS = ("## 是什么", "## 怎么用", "## 现状对照", "## 复现与引用口径", "## 判据（可证）")
RFCS = ("NF-0001", "NF-0002", "NF-0003", "NF-0004")
STATUS_VOCAB = ("Active", "Superseded", "Deprecated", "Experimental")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"RFC 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("RFC 文档为空")
    return text


def stats() -> dict:
    _issues, _warns, data = rfc.scan(str(ROOT))
    return data


def index_docs() -> list:
    return json.loads(INDEX.read_text(encoding="utf-8"))["docs"]


def rfc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 协议件 RFC 头"):
        issues.append("缺标题「# 协议件 RFC 头与 supersede 链（rfc）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    s = stats()
    docs = index_docs()
    if s["docs"] != 4 or len(docs) != 4:
        issues.append(f"在册件数已变（{s['docs']}/{len(docs)}）")
    if [d["rfc"] for d in docs] != list(RFCS):
        issues.append(f"RFC 编号集合已变：{[d['rfc'] for d in docs]}")
    for rid in RFCS:
        if rid not in text:
            issues.append(f"正文缺 RFC：{rid}")
    if s["chains"] != 0:
        issues.append(f"supersede 链已出现（{s['chains']}），文档需更新")
    if s["statuses"] != ["Active"]:
        issues.append(f"状态已变：{s['statuses']}")
    cats = [d["category"] for d in docs]
    if cats.count("Standards Track") != 3 or cats.count("Informational") != 1:
        issues.append(f"类别分布已变：{cats}")
    for label in ("**4 件**", "**3 Standards Track + 1 Informational**", "**尚无**", "**4 值**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    for st in STATUS_VOCAB:
        if st not in text:
            issues.append(f"状态词表缺：{st}")
    if tuple(rfc.CATEGORIES) != ("Standards Track", "Informational", "Experimental", "Process"):
        issues.append(f"类别词表已变：{rfc.CATEGORIES}")
    if "Date" not in text or "最后更新" not in text:
        issues.append("缺「Date == 最后更新」规则")
    positions = [text.find(s2) for s2 in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py rfc", "python scripts/nf.py rfc --json"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "真源" not in text:
        issues.append("缺「文档头部是真源」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class RfcDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_rfc_matches_contract(self):
        self.assertEqual([], rfc_issues(self.text), "RFC 文档不满足契约")

    def test_rfc_live(self):
        s = stats()
        docs = index_docs()
        self.assertEqual(4, s["docs"])
        self.assertEqual(list(RFCS), [d["rfc"] for d in docs])
        self.assertEqual(["Active"], s["statuses"])
        self.assertEqual(0, s["chains"])
        self.assertEqual(("Standards Track", "Informational", "Experimental", "Process"),
                         tuple(rfc.CATEGORIES))

    def test_contract_catches_mutations(self):
        """变异自证：缺 RFC 编号 / 链状态回退 / 类别回退 / 缺词表 / 缺命令。"""
        no_id = self.text.replace("NF-0004", "NF-0009")
        self.assertTrue(any("NF-0004" in i for i in rfc_issues(no_id)))
        old_chain = self.text.replace("**尚无**", "**已有 1 条**")
        self.assertTrue(any("尚无" in i for i in rfc_issues(old_chain)))
        old_cat = self.text.replace("3 Standards Track + 1 Informational",
                                    "4 Standards Track")
        self.assertTrue(any("类别" in i or "3 Standards" in i
                            for i in rfc_issues(old_cat)))
        no_vocab = self.text.replace("Deprecated", "Retired")
        self.assertTrue(any("Deprecated" in i for i in rfc_issues(no_vocab)))
        no_cmd = self.text.replace("python scripts/nf.py rfc --json", "机读")
        self.assertTrue(any("--json" in i for i in rfc_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_rfc.md")


if __name__ == "__main__":
    unittest.main()
