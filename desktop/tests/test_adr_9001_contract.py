#!/usr/bin/env python3
"""ADR-9001 证据纪律示例契约：允许/禁止写法必须与 decisions.py 的实际校验逐条对齐。

为什么必须有：ADR-9001 是「evidence 只写可解析项」的示例决策，它列出的允许/禁止写法就是后续
ADR 的写作口径。如果示例与代码校验漂移（例如示例说允许而代码判 FAIL），照抄的决策会被门禁打红。
实测本轮修掉一个真实错证：本条 evidence 原引 check35（深化面：管线/馆藏/边界/批准/工件/无效语料，
不含决策层），已改指 check33（新面汇总的决策层面）并补测试用例路径。现在把「示例 ⇄ decisions.py
常量与 TestEvidenceBoundaries 用例 ⇄ INDEX 投影」立成机检断言。

范围：只判本示例与校验代码/投影的自洽（不改证据纪律本身）。同族判据：
test_decisions.py（工具链语义）/ test_adr_0000_contract.py（meta 决策）/
test_adr_9000_contract.py（格式模板）/ check33（决策层面）。
契约：frontmatter 合法且 evidence 可解析（三类允许形式）、三段 + 示例段齐全、禁止项逐条在场、
常量与 decisions.py 一致（512 / 三段 / 状态词表）、示例表覆盖正反例、INDEX 行一致、同伴键集同构。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import decisions as dc  # noqa: E402

ADR = ROOT / "decisions" / "ADR-9001-示例-证据必须可解析.md"
INDEX = ROOT / "decisions" / "INDEX.md"
VERIFY = ROOT / "verify.sh"
TEST = ROOT / "desktop" / "tests" / "test_decisions.py"
PEERS = (ROOT / "decisions" / "ADR-0000-决策记录外置到私有仓.md",
         ROOT / "decisions" / "ADR-9000-示例-决策格式模板.md")

FRONTMATTER_KEYS = {"id", "title", "status", "date", "supersedes", "superseded_by", "evidence"}
SECTIONS = ("## 背景", "## 决策", "## 后果", "## 证据写法")
STATUSES = ("proposed", "accepted", "superseded", "deprecated")
REQUIRED_MARKERS = ("绝对路径", "路径穿越", "不是文件", "空项", "512", "MAX_EVIDENCE_LEN",
                    "TestEvidenceBoundaries", "在册 ADR", "check33", "ERRATA.json")


def load_text(path: Path = ADR) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ADR-9001 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ADR-9001 为空")
    return text


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def evidence_items(fm: dict) -> list:
    raw = (fm.get("evidence") or "[]").strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [x.strip() for x in raw.split(",") if x.strip()]


def check_numbers() -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", VERIFY.read_text(encoding="utf-8"), re.M))


def decision_ids() -> set:
    return {p.name.split("-")[0] + "-" + p.name.split("-")[1]
            for p in (ROOT / "decisions").glob("ADR-*.md")}


def index_row() -> list:
    text = INDEX.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| ADR-9001 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def example_rows(text: str) -> list:
    if "## 证据写法" not in text:
        return []
    body = text.split("## 证据写法", 1)[1].split("\n## ", 1)[0]
    return [ln.strip() for ln in body.splitlines() if ln.strip().startswith("|")]


def adr_9001_issues(text: str) -> list:
    issues = []
    fm = frontmatter(text)
    if not fm:
        issues.append("缺 frontmatter")
        return issues
    if set(fm) != FRONTMATTER_KEYS:
        issues.append(f"frontmatter 键集应为七键：{sorted(set(fm) ^ FRONTMATTER_KEYS)}")
    if fm.get("id") != "ADR-9001":
        issues.append(f"id 应为 ADR-9001：{fm.get('id')!r}")
    if fm.get("status") not in STATUSES:
        issues.append(f"status 越词表：{fm.get('status')!r}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fm.get("date") or ""):
        issues.append(f"date 非 YYYY-MM-DD：{fm.get('date')!r}")
    checks = check_numbers()
    adr_ids = decision_ids()
    for item in evidence_items(fm):
        if re.match(r"^check\d+$", item):
            if item not in checks:
                issues.append(f"evidence 引用了不存在的检查：{item}")
            continue
        if re.match(r"^ADR-\d{4}$", item):
            if item not in adr_ids:
                issues.append(f"evidence 引用了不在册 ADR：{item}")
            continue
        if not (ROOT / item).is_file():
            issues.append(f"evidence 不是可解析文件：{item}")
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"缺要素：{marker}")
    if dc.MAX_EVIDENCE_LEN != 512:
        issues.append(f"decisions.py MAX_EVIDENCE_LEN 应为 512：{dc.MAX_EVIDENCE_LEN}")
    if tuple(dc.SECTIONS) != ("## 背景", "## 决策", "## 后果"):
        issues.append(f"decisions.py SECTIONS 漂移：{dc.SECTIONS}")
    if set(dc.STATUSES) != {"proposed", "accepted", "superseded", "deprecated"}:
        issues.append(f"decisions.py STATUSES 漂移：{dc.STATUSES}")
    if "class TestEvidenceBoundaries" not in TEST.read_text(encoding="utf-8"):
        issues.append("test_decisions.py 缺 TestEvidenceBoundaries 用例")
    rows = example_rows(text)
    if len(rows) < 8:
        issues.append(f"示例表行不足（表头 + 正反例至少 8 行，实测 {len(rows)}）")
    good = [r for r in rows if "✅" in r]
    bad = [r for r in rows if "❌" in r]
    if len(good) < 2:
        issues.append(f"示例表正例不足：{len(good)}")
    if len(bad) < 5:
        issues.append(f"示例表反例不足：{len(bad)}")
    for token in ("/etc/passwd", "../outside.md", "ADR-9999"):
        if token not in text:
            issues.append(f"示例表缺典型反例：{token}")
    row = index_row()
    if len(row) < 5:
        issues.append("INDEX 缺 ADR-9001 投影行")
    else:
        if row[1] != fm.get("title"):
            issues.append(f"INDEX 标题与 frontmatter 不一致：{row[1]!r}")
        if row[2] != fm.get("status"):
            issues.append(f"INDEX 状态与 frontmatter 不一致：{row[2]!r}")
        if row[3] != fm.get("date"):
            issues.append(f"INDEX 日期与 frontmatter 不一致：{row[3]!r}")
    for peer in PEERS:
        peer_fm = frontmatter(peer.read_text(encoding="utf-8"))
        if set(peer_fm) != FRONTMATTER_KEYS:
            diffs = sorted(set(peer_fm) ^ FRONTMATTER_KEYS)
            issues.append(f"{peer.name} 键集与示例不同构：{diffs}")
    return issues


class Adr9001ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_adr_9001_matches_contract(self):
        self.assertEqual([], adr_9001_issues(self.text), "ADR-9001 不满足证据纪律契约")

    def test_evidence_is_resolvable(self):
        fm = frontmatter(self.text)
        checks = check_numbers()
        adr_ids = decision_ids()
        for item in evidence_items(fm):
            if re.match(r"^check\d+$", item):
                self.assertIn(item, checks, item)
            elif re.match(r"^ADR-\d{4}$", item):
                self.assertIn(item, adr_ids, item)
            else:
                self.assertTrue((ROOT / item).is_file(), item)

    def test_examples_match_code_boundaries(self):
        self.assertEqual(512, dc.MAX_EVIDENCE_LEN)
        text = self.text
        for token in ("绝对路径", "路径穿越", "不是文件", "空项", "512"):
            self.assertIn(token, text)

    def test_contract_catches_mutations(self):
        """变异自证：绝对路径证据 / 常量漂移 / 缺反例 / 缺段 / 状态漂移 / 标题漂移。"""
        good_ev = ("evidence: [decisions/ADR-0000-决策记录外置到私有仓.md, "
                   "desktop/tests/test_decisions.py, check33]")
        bad_ev = self.text.replace(good_ev, "evidence: [/etc/passwd]", 1)
        self.assertTrue(any("evidence" in i for i in adr_9001_issues(bad_ev)))
        no_512 = self.text.replace("512", "1024")
        self.assertTrue(any("512" in i for i in adr_9001_issues(no_512)))
        tick = chr(96)
        bad_row = "| " + tick + "evidence: [/etc/passwd]" + tick + " | ❌ |"
        no_bad = self.text.replace(bad_row, bad_row.replace("❌", "✅"), 1)
        self.assertTrue(any("反例" in i for i in adr_9001_issues(no_bad)))
        no_section = self.text.replace("## 证据写法（示例）", "## 写法")
        self.assertTrue(any("缺段" in i for i in adr_9001_issues(no_section)))
        bad_status = self.text.replace("status: proposed", "status: accepted", 1)
        self.assertTrue(any("status" in i or "INDEX" in i for i in adr_9001_issues(bad_status)))
        bad_title = self.text.replace(
            "title: （示例）evidence 字段只写可解析的仓库路径或 checkN",
            "title: （示例）证据要可解析", 1)
        self.assertTrue(any("INDEX" in i for i in adr_9001_issues(bad_title)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_adr9001.md")


if __name__ == "__main__":
    unittest.main()
