#!/usr/bin/env python3
"""ADR-0000 决策记录契约：meta 决策的每一条声明都必须可机器核验。

为什么必须有：ADR-0000 是「决策记录外置到私有仓」的 meta 决策——它一边约束公开面只留模板，
一边自身是 accepted 状态（须回执锚定）。此前没有判据逐条核验它的声明：frontmatter 字段合法、
evidence 全部可解析、正文三段齐全、四条决策项在场、它与 INDEX 投影 / 目录白名单
(test_publish_boundary.py) / npm 发布策略 (payload-policy.mjs INTERNAL_DIRS) / ERRATA schema
四处事实一致。本轮补「可核验面」段并把这些立成机检断言。

范围：只判本 ADR 与公开面事实的自洽（不改决策语义）。同族判据：
test_decisions.py（ADR 工具链语义）/ test_publish_boundary.py（目录白名单）/
test_decisions 的 INDEX 投影漂移用例 / check33（决策层面）/ test_adr_9000_9001 模板面。
契约：frontmatter 合法（id/status/date/evidence 可解析）、三段齐全、四条决策项在场、
INDEX 行与 frontmatter 一致、白名单/发布策略/ERRATA/RECEIPTS 四处事实一致、模板 ADR 同构。
"""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "decisions" / "ADR-0000-决策记录外置到私有仓.md"
INDEX = ROOT / "decisions" / "INDEX.md"
README = ROOT / "decisions" / "README.md"
ERRATA = ROOT / "decisions" / "ERRATA.json"
RECEIPTS = ROOT / "protocol" / "RECEIPTS.json"
VERIFY = ROOT / "verify.sh"
PAYLOAD = ROOT / "packaging" / "npm" / "tools" / "payload-policy.mjs"
TEMPLATES = (ROOT / "decisions" / "ADR-9000-示例-决策格式模板.md",
             ROOT / "decisions" / "ADR-9001-示例-证据必须可解析.md")

DECISION_ITEMS = ("私有 Plan 仓", "ADR-9xxx", "payload-policy.mjs", "test_publish_boundary.py")
SECTIONS = ("## 背景", "## 决策", "## 后果")


def load_text(path: Path = ADR) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ADR-0000 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ADR-0000 为空")
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
    raw = fm.get("evidence") or "[]"
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [x.strip() for x in raw.split(",") if x.strip()]


def check_numbers() -> set:
    return set(re.findall(r"^(check\d+)\(\)\{", VERIFY.read_text(encoding="utf-8"), re.M))


def index_row() -> list:
    text = INDEX.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("| ADR-0000 |"):
            return [c.strip() for c in line.strip("|").split("|")]
    return []


def publish_patterns() -> list:
    spec = importlib.util.spec_from_file_location(
        "publish_boundary_mod", ROOT / "desktop" / "tests" / "test_publish_boundary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PATTERNS["decisions"]


def internal_dirs() -> list:
    text = PAYLOAD.read_text(encoding="utf-8")
    m = re.search(r"INTERNAL_DIRS\s*=\s*\[([^\]]+)\]", text)
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()] if m else []


def adr_issues(text: str) -> list:
    issues = []
    fm = frontmatter(text)
    if not fm:
        issues.append("缺 frontmatter（--- 包裹的 YAML 头）")
        return issues
    if fm.get("id") != "ADR-0000":
        issues.append(f"frontmatter id 应为 ADR-0000：{fm.get('id')!r}")
    if not fm.get("title"):
        issues.append("frontmatter 缺 title")
    if fm.get("status") not in ("proposed", "accepted", "superseded", "deprecated"):
        issues.append(f"status 越词表：{fm.get('status')!r}")
    if fm.get("status") != "accepted":
        issues.append(f"本条 meta 决策应为 accepted（当前 {fm.get('status')!r}）")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fm.get("date") or ""):
        issues.append(f"date 非 YYYY-MM-DD：{fm.get('date')!r}")
    if fm.get("supersedes") != "—" or fm.get("superseded_by") != "—":
        issues.append("本条不应有取代关系（supersedes / superseded_by 应为 —）")
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
    for item in DECISION_ITEMS:
        if item not in text:
            issues.append(f"决策正文缺关键声明：{item}")
    if "可核验面" not in text:
        issues.append("缺「可核验面」段（判据落点）")
    row = index_row()
    if len(row) < 5:
        issues.append("INDEX 缺 ADR-0000 投影行")
    else:
        if row[1] != fm.get("title"):
            issues.append(f"INDEX 标题与 frontmatter 不一致：{row[1]!r}")
        if row[2] != fm.get("status"):
            issues.append(f"INDEX 状态与 frontmatter 不一致：{row[2]!r}")
        if row[3] != fm.get("date"):
            issues.append(f"INDEX 日期与 frontmatter 不一致：{row[3]!r}")
    patterns = publish_patterns()
    if r"ADR-0000-[^/]+\.md" not in patterns:
        issues.append(f"目录白名单缺 ADR-0000 模板位：{patterns}")
    for pattern in (r"README\.md", r"INDEX\.md", r"ERRATA\.json"):
        if pattern not in patterns:
            issues.append(f"目录白名单缺：{pattern}")
    if r"ADR-9\d{3}-[^/]+\.md" not in patterns:
        issues.append(f"目录白名单缺 ADR-9xxx 模板位：{patterns}")
    dirs = internal_dirs()
    for required in ("decisions/", "handovers/", "postmortems/"):
        if required not in dirs:
            issues.append(f"payload-policy INTERNAL_DIRS 缺：{required}")
    if (json.loads(ERRATA.read_text(encoding="utf-8")).get("schema") != "nf-decisions-errata/1"):
        issues.append("ERRATA schema 非 nf-decisions-errata/1")
    receipts = RECEIPTS.read_text(encoding="utf-8")
    if "ADR-0000-决策记录外置到私有仓.md" not in receipts:
        issues.append("accepted 未回执锚定：RECEIPTS 缺本条路径")
    readme = README.read_text(encoding="utf-8")
    for token in ("ADR-0000", "ADR-9xxx", "ERRATA.json", "INDEX.md", "test_publish_boundary.py"):
        if token not in readme:
            issues.append(f"decisions/README 政策说明缺：{token}")
    for template in TEMPLATES:
        body = template.read_text(encoding="utf-8")
        t_fm = frontmatter(body)
        if set(t_fm) != {"id", "title", "status", "date", "supersedes", "superseded_by",
                         "evidence"}:
            issues.append(f"{template.name} frontmatter 键集不符：{sorted(t_fm)}")
        for section in SECTIONS:
            if section not in body:
                issues.append(f"{template.name} 缺段：{section}")
    return issues


class Adr0000ContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_adr_0000_matches_contract(self):
        self.assertEqual([], adr_issues(self.text), "ADR-0000 不满足决策契约")

    def test_evidence_items_resolve(self):
        checks = check_numbers()
        for item in evidence_items(frontmatter(self.text)):
            if re.match(r"^check\d+$", item):
                self.assertIn(item, checks, item)
            else:
                self.assertTrue((ROOT / item).exists(), item)

    def test_public_face_claims_are_true(self):
        self.assertIn(r"ADR-0000-[^/]+\.md", publish_patterns())
        dirs = internal_dirs()
        for required in ("decisions/", "handovers/", "postmortems/"):
            self.assertIn(required, dirs)

    def test_contract_catches_mutations(self):
        """变异自证：evidence 坏路径 / 状态漂移 / 标题漂移 / 缺段 / 缺声明 / 缺可核验面。"""
        bad_ev = self.text.replace(
            "evidence: [STRATEGY.md, desktop/tests/test_publish_boundary.py, check33]",
            "evidence: [no_such_file.md]", 1)
        self.assertTrue(any("evidence" in i for i in adr_issues(bad_ev)))
        bad_status = self.text.replace("status: accepted", "status: proposed", 1)
        self.assertTrue(any("status" in i or "INDEX" in i for i in adr_issues(bad_status)))
        bad_title = self.text.replace(
            "title: 决策记录外置到私有仓：公开仓只留模板与格式声明",
            "title: 决策记录外置", 1)
        self.assertTrue(any("INDEX" in i for i in adr_issues(bad_title)))
        no_section = self.text.replace("## 后果", "## 影响")
        self.assertTrue(any("缺段" in i for i in adr_issues(no_section)))
        no_claim = self.text.replace("私有 Plan 仓", "私有仓")
        self.assertTrue(any("声明" in i for i in adr_issues(no_claim)))
        no_verify = self.text.replace("可核验面", "核验面", 1)
        self.assertTrue(any("核验面" in i for i in adr_issues(no_verify)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_adr.md")


if __name__ == "__main__":
    unittest.main()
