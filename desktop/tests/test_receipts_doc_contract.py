#!/usr/bin/env python3
"""docs/receipts.md 契约：回执文档必须「3 条馆藏 / 66 件协议 / 66 节链 / 算法三式」与实读一致。

为什么必须有：这页是外部读者「拿一条回执本地折叠验证」的唯一依据——算法三式、根、链条、
验证器三项输出，任何一项漂移都会让读者验不过或误以为「不可抵赖」。本轮补「§现状对照」与
「§复现与引用口径」，把根与条数与 library/RECEIPTS.json、protocol/RECEIPTS.json、
receipt_chain.json 实读双向绑定。

范围：只判本文与回执/链/验证器事实自洽（不改工件）。
同族判据：test_scale_receipts.py / test_transparency.py /
test_receipt_chain.py（若在）/ test_doc_hygiene.py。
契约：最后更新位 + 复核、3 条馆藏、66 件协议、66 节链、根与链头前 16 位、算法三式、
读者侧三验证项、不提供不可抵赖性、现状对照 + 复现三命令。
"""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "receipts.md"
LIB = ROOT / "library" / "RECEIPTS.json"
PROTO = ROOT / "protocol" / "RECEIPTS.json"
CHAIN = ROOT / "protocol" / "generated" / "receipt_chain.json"
VERIFIER = ROOT / "scripts" / "nf_verify.py"
SECTIONS = ("## 是什么", "## 算法（读者侧按此重建，逐字一致）", "## 怎么用", "## 边界",
            "## 现状对照", "## 复现与引用口径", "## 透明日志")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"回执文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("回执文档为空")
    return text


def facts() -> dict:
    lib = json.loads(LIB.read_text(encoding="utf-8"))
    proto = json.loads(PROTO.read_text(encoding="utf-8"))
    chain = json.loads(CHAIN.read_text(encoding="utf-8"))
    return {"lib": len(lib["entries"]), "lib_root": lib["root"][:16],
            "proto": int(proto["count"]),
            "links": len(chain["links"])}


def receipts_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 馆藏回执与单根"):
        issues.append("缺标题「# 馆藏回执与单根（receipts）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    f = facts()
    if f["lib"] != 3:
        issues.append(f"馆藏回执数已变（{f['lib']}）")
    if f["proto"] != 66:
        issues.append(f"协议回执数已变（{f['proto']}）")
    if f["links"] != 66:
        issues.append(f"链条节数已变（{f['links']}）")
    if f["lib_root"] not in text:
        issues.append(f"未写馆藏根前 16 位（{f['lib_root']}）")
    if "不钉值" not in text:
        issues.append("未声明「链头不钉值」口径")
    for label in ("**3 条**", "**66 件**", "**66 节**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    for marker in ("SHA-256(0x00", "0x01", "折叠"):
        if marker not in text:
            issues.append(f"算法段缺：{marker}")
    for marker in ("inclusion", "content", "anchor"):
        if marker not in text:
            issues.append(f"验证项缺：{marker}")
    if "不提供" not in text or "不可抵赖" not in text:
        issues.append("缺「不提供不可抵赖性」边界")
    if not VERIFIER.is_file():
        issues.append("nf_verify.py 缺失")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py library receipts",
                "python scripts/nf_verify.py --entry",
                "python scripts/nf.py transparency"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "O(log n)" not in text:
        issues.append("缺 O(log n) 折叠口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ReceiptsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_receipts_matches_contract(self):
        self.assertEqual([], receipts_issues(self.text), "回执文档不满足契约")

    def test_artifacts_live(self):
        f = facts()
        self.assertEqual(3, f["lib"])
        self.assertEqual(66, f["proto"])
        self.assertEqual(66, f["links"])
        self.assertEqual(64, len(hashlib.sha256(b"x").hexdigest()))

    def test_contract_catches_mutations(self):
        """变异自证：条数回退 / 缺根 / 缺算法式 / 缺验证项 / 缺命令。"""
        old = self.text.replace("**3 条**", "**5 条**")
        self.assertTrue(any("3 条" in i for i in receipts_issues(old)))
        no_root = self.text.replace(facts()["lib_root"], "deadbeefdeadbeef")
        self.assertTrue(any("馆藏根" in i for i in receipts_issues(no_root)))
        no_algo = self.text.replace("SHA-256(0x00", "SHA256(00")
        self.assertTrue(any("0x00" in i for i in receipts_issues(no_algo)))
        no_anchor = self.text.replace("anchor", "ancor")
        self.assertTrue(any("anchor" in i for i in receipts_issues(no_anchor)))
        no_cmd = self.text.replace("python scripts/nf_verify.py --entry NF-1", "验证")
        self.assertTrue(any("nf_verify" in i for i in receipts_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_receipts.md")


if __name__ == "__main__":
    unittest.main()
