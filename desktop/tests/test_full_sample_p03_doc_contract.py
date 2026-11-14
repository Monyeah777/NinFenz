#!/usr/bin/env python3
"""docs/完整版样本_西幻生存流P03.md 契约：冻结证据件——字节不许变（它是保真度裁定的语料）。

为什么必须有：本轮实测发现一个硬约束——这份「完整版样本」不只是文档，还是
core/drill_fidelity.real_corpus 的唯一真实语料：它按 sha256 + 非空白行数 + 逐行命中裁定表
被钉在 desktop/tests/fixtures/execution/rounds/selfrun-2026-10-20.json 里。
本轮尝试在文末加「现状对照 / 复现口径」两节后，drill_fidelity 立刻 FAIL
（problems：sha256 不匹配、非空白行从 185 变 211），按证据完整性已还原字节，
并把这层约束固化成判据：以后谁再想「顺手完善」这份样本，会先撞到这里。

范围：只判本文与裁定表/裁定块事实自洽（不改本文，也不改裁定）。
同族判据：drill_fidelity.real_corpus（本判据会实跑）/ test_drill_fidelity 系列 / check12。
契约：sha256 与裁定块一致、非空白行数一致、逐行裁定条目 5 条、
规则集为 fabricated_id 与 no_citation、反向核对无「TP 消失」、八段标题在场。
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import drill_fidelity as df  # noqa: E402

DOC = ROOT / "docs" / "完整版样本_西幻生存流P03.md"
SAMPLE = (ROOT / "desktop" / "tests" / "fixtures" / "execution" / "rounds"
          / "selfrun-2026-10-20.json")
RULES = {"fabricated_id", "no_citation"}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"完整版样本不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("完整版样本为空")
    return text


def block() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))["real_corpus"]


def live() -> dict:
    return df.real_corpus(str(ROOT))


def sample_issues(text: str) -> list:
    issues = []
    b = block()
    data = text.encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    if sha != b["sha256"]:
        issues.append(f"样本字节已变（sha256 {sha[:8]} != 裁定表 {b['sha256'][:8]}）")
    nonblank = sum(1 for ln in text.splitlines() if ln.strip())
    if nonblank != int(b["nonblank_lines"]):
        issues.append(f"非空白行已变（{nonblank} != {b['nonblank_lines']}）")
    entries = b.get("adjudications") or []
    if len(entries) != 5:
        issues.append(f"裁定条目数已变（{len(entries)}）")
    rules = {str(e.get("rule")) for e in entries}
    if rules != RULES:
        issues.append(f"裁定规则集已变：{sorted(rules)}")
    if not text.startswith("# 叙事世界完整版：西幻生存流（P03）"):
        issues.append("缺标题「# 叙事世界完整版：西幻生存流（P03）」")
    for marker in ("## 0. 装配记录", "## 7. 自检清单"):
        if marker not in text:
            issues.append(f"缺段：{marker}")
    res = live()
    for problem in res.get("problems") or []:
        issues.append(f"裁定运行问题：{problem}")
    if res.get("sha256_matched") is not True:
        issues.append("裁定运行报 sha256 不匹配")
    return issues


class FrozenSampleDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_sample_is_frozen(self):
        self.assertEqual([], sample_issues(self.text), "冻结样本不满足契约")

    def test_corpus_live(self):
        res = live()
        self.assertEqual([], res["problems"])
        self.assertTrue(res["sha256_matched"])
        self.assertEqual(5, res["hits_before"])
        self.assertEqual(5, res["fp_resolved"])
        self.assertEqual(0, res["tp"])

    def test_contract_catches_mutations(self):
        """变异自证：改一个字节 / 追加一节 / 裁定表钉值。"""
        edited = self.text.replace("西幻生存流（P03）", "西幻生存流（P03） ", 1)
        self.assertTrue(any("sha256" in i for i in sample_issues(edited)))
        added = self.text + "\n## 现状对照\n\n- 新增节\n"
        self.assertTrue(any("非空白行" in i for i in sample_issues(added)))
        b = block()
        self.assertEqual("ca3d75b86a84a500", b["sha256"][:16])
        self.assertEqual(185, int(b["nonblank_lines"]))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_sample.md")


if __name__ == "__main__":
    unittest.main()
