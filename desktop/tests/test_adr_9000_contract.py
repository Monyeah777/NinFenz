#!/usr/bin/env python3
"""ADR-9000 模板契约：公开面决策格式模板必须「机读合法 + 写法指引齐全 + INDEX 投影一致」。

为什么必须有：ADR-9000 是公开仓唯一保留的「ADR 写法」模板——开发者照它写真实决策（进私有仓），
模板漂移会让后续决策缺键/缺段/证据不可解析。此前工具链只校验「某条 ADR 是否合法」，没有判据
校验**模板自身的完整性**：七键说明是否覆盖全部 frontmatter 键、三段写法要点是否在场、投影与
勘误纪律是否写明、与仓库内既有 ADR/INDEX 是否一致。本轮补「写法指引」段并立成机检断言。

范围：只判本模板与其被引用事实的自洽（不改模板语义）。同族判据：
test_decisions.py（ADR 工具链语义）/ test_adr_0000_contract.py（meta 决策）/
test_publish_boundary.py（目录白名单）/ check33（决策层面）。
契约：frontmatter 七键合法且 evidence 可解析、三段 + 写法指引齐全、七键说明覆盖全部键、
投影/勘误/私有仓纪律在场、INDEX 行一致、与 ADR-9001/ADR-0000 键集同构。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "decisions" / "ADR-9000-示例-决策格式模板.md"
INDEX = ROOT / "decisions" / "INDEX.md"
VERIFY = ROOT / "verify.sh"
PEERS = (ROOT / "decisions" / "ADR-9001-示例-证据必须可解析.md",
         ROOT / "decisions" / "ADR-0000-决策记录外置到私有仓.md")
TICK = chr(96)

FRONTMATTER_KEYS = {"id", "title", "status", "date", "supersedes", "superseded_by", "evidence"}
SECTIONS = ("## 背景", "## 决策", "## 后果", "## 写法指引")
STATUSES = ("proposed", "accepted", "superseded", "deprecated")
GUIDANCE_MARKERS = ("仓库相对路径", "checkN", "勿手改", "nf decisions reindex",
                    "ERRATA.json", "governance/decisions-archive/", "ADR-0000")


def load_text(path: Path = ADR) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ADR-9000 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ADR-9000 为空")
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


def index_row() -> list:
    text = INDEX.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| ADR-9000 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def adr_9000_issues(text: str) -> list:
    issues = []
    fm = frontmatter(text)
    if not fm:
        issues.append("缺 frontmatter")
        return issues
    if set(fm) != FRONTMATTER_KEYS:
        issues.append(f"frontmatter 键集应为七键：{sorted(set(fm) ^ FRONTMATTER_KEYS)}")
    if fm.get("id") != "ADR-9000":
        issues.append(f"id 应为 ADR-9000：{fm.get('id')!r}")
    if fm.get("status") not in STATUSES:
        issues.append(f"status 越词表：{fm.get('status')!r}")
    if fm.get("status") != "proposed":
        issues.append(f"模板状态应为 proposed：{fm.get('status')!r}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fm.get("date") or ""):
        issues.append(f"date 非 YYYY-MM-DD：{fm.get('date')!r}")
    if fm.get("supersedes") != "—" or fm.get("superseded_by") != "—":
        issues.append("模板不应有取代关系（应为 —）")
    checks = check_numbers()
    for item in evidence_items(fm):
        if re.match(r"^check\d+$", item):
            if item not in checks:
                issues.append(f"evidence 引用了不存在的检查：{item}")
            continue
        if not (ROOT / item).exists():
            issues.append(f"evidence 引用了不存在的路径：{item}")
    for section in SECTIONS:
        if section not in text:
            issues.append(f"缺段：{section}")
    for placeholder in ("写清", "一句话可执行", "可观测的收益", "接受的代价"):
        if placeholder not in text:
            issues.append(f"缺写法占位：{placeholder}")
    for marker in GUIDANCE_MARKERS:
        if marker not in text:
            issues.append(f"写法指引缺纪律：{marker}")
    for key in FRONTMATTER_KEYS:
        if "| " + TICK + key + TICK + " |" not in text:
            issues.append(f"七键说明表缺键：{key}")
    row = index_row()
    if len(row) < 5:
        issues.append("INDEX 缺 ADR-9000 投影行")
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
            issues.append(f"{peer.name} 键集与模板不同构：{diffs}")
    return issues


class Adr9000ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_adr_9000_matches_contract(self):
        self.assertEqual([], adr_9000_issues(self.text), "ADR-9000 模板不满足契约")

    def test_guidance_covers_every_frontmatter_key(self):
        fm = frontmatter(self.text)
        self.assertEqual(FRONTMATTER_KEYS, set(fm))
        for key in FRONTMATTER_KEYS:
            self.assertIn("| " + TICK + key + TICK + " |", self.text, key)

    def test_peers_are_isomorphic(self):
        for peer in PEERS:
            peer_fm = frontmatter(peer.read_text(encoding="utf-8"))
            self.assertEqual(FRONTMATTER_KEYS, set(peer_fm), peer.name)

    def test_contract_catches_mutations(self):
        """变异自证：evidence 坏路径 / 状态漂移 / 缺键说明 / 缺段 / 缺纪律 / 标题漂移。"""
        bad_ev = self.text.replace("evidence: [protocol/decision_layer.json, check33]",
                                   "evidence: [no_such_file.json]", 1)
        self.assertTrue(any("evidence" in i for i in adr_9000_issues(bad_ev)))
        bad_status = self.text.replace("status: proposed", "status: accepted", 1)
        self.assertTrue(any("status" in i or "INDEX" in i for i in adr_9000_issues(bad_status)))
        row = "| " + TICK + "superseded_by" + TICK + " | 新 id 或 — | 与被取代件互指 |\n"
        no_key = self.text.replace(row, "", 1)
        self.assertTrue(any("说明表" in i for i in adr_9000_issues(no_key)))
        no_section = self.text.replace("## 写法指引（本模板怎么用）", "## 指引")
        self.assertTrue(any("缺段" in i for i in adr_9000_issues(no_section)))
        no_disc = self.text.replace("勿手改", "可手改")
        self.assertTrue(any("纪律" in i for i in adr_9000_issues(no_disc)))
        bad_title = self.text.replace(
            "title: （示例）一条决策的写法：背景 / 决策 / 后果 + 可解析证据",
            "title: （示例）决策写法", 1)
        self.assertTrue(any("INDEX" in i for i in adr_9000_issues(bad_title)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_adr9000.md")


if __name__ == "__main__":
    unittest.main()
