"""架构分层判据（P0）：依赖方向 + ADR/台账单一真源。

两条硬规则：
① **依赖方向**：认知核不得 import 契约核（AST 判据，函数化以便传合成源码做反例）；
   契约核不得 import 认知核（反向同罪）；
② **单一真源**：ADR 同主题至多一条 current、supersedes 无环、evidence 在场；
   16 份文档各一状态、superseded 指向在场 current、与仓库现实对账（reasoning/ 面）。
"""
import ast
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import adr  # noqa: E402

COG = ROOT / "desktop/src/core/cognition_workspace"
FORBIDDEN_IN_COG = ("meta_cockpit", "backends", "core.receipts", "core.evidence",
                    "core.label", "core.check", "core.resolve", "core.verify",
                    "core.timestamp", "core.trust_anchor", "core.key_transparency")
FORBIDDEN_IN_CONTRACT = ("cognition_workspace",)


def imports_in(source: str) -> list[str]:
    """从源码字符串里抽 import 目标（供函数级判据与反例使用）。"""
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
            found.extend(node.module + "." + alias.name for alias in node.names)
    return found


def _matches(target: str, forbidden: str) -> bool:
    """target 是否是 forbidden 包（含子模块、含 from X import Y 形式）。"""
    padded = "." + target + "."
    return ("." + forbidden + ".") in padded


def violations(sources: dict[str, str], forbidden: tuple[str, ...]) -> list[str]:
    bad: list[str] = []
    for name, source in sources.items():
        for target in imports_in(source):
            if any(_matches(target, f) for f in forbidden):
                bad.append(name + " → " + target)
    return bad


def _sources(root: Path) -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(root.glob("*.py"))}


class DependencyDirectionTest(unittest.TestCase):
    def test_cognition_core_does_not_import_contract_core(self):
        self.assertEqual([], violations(_sources(COG), FORBIDDEN_IN_COG))

    def test_contract_core_does_not_import_cognition_core(self):
        meta = ROOT / "desktop/src/core/meta_cockpit"
        self.assertEqual([], violations(_sources(meta), FORBIDDEN_IN_CONTRACT))

    def test_reverse_fixture_is_caught(self):
        """反例：给一段「认知核 import 契约核」的假源码，判据必须红。"""
        fake = {"fake_cog.py": "from core import meta_cockpit\nimport core.receipts\n"}
        bad = violations(fake, FORBIDDEN_IN_COG)
        self.assertEqual(2, len(bad), bad)

    def test_clean_source_passes(self):
        fake = {"ok.py": "import json\nfrom core.cognition_workspace import moves\n"}
        self.assertEqual([], violations(fake, FORBIDDEN_IN_COG))


class AdrRegistryTest(unittest.TestCase):
    def test_registry_is_valid(self):
        bundle = adr.load(str(ROOT))
        self.assertEqual([], adr.validate_adr(bundle["adr"]))

    def test_four_adrs_cover_core_topics(self):
        bundle = adr.load(str(ROOT))
        topics = {a["topic"] for a in bundle["adr"]["adrs"]}
        self.assertTrue({"architecture-core", "abi", "docs", "reasoning-face"} <= topics)

    def test_duplicate_current_topic_is_rejected(self):
        doc = json.loads((ROOT / adr.ADR_REL).read_text(encoding="utf-8"))
        doc["adrs"] = json.loads(json.dumps(doc["adrs"])) + [dict(doc["adrs"][0])]
        self.assertTrue(any("两条 current" in i for i in adr.validate_adr(doc)))

    def test_missing_falsifier_is_rejected(self):
        doc = json.loads((ROOT / adr.ADR_REL).read_text(encoding="utf-8"))
        doc["adrs"] = json.loads(json.dumps(doc["adrs"]))
        doc["adrs"][0].pop("falsifier", None)
        self.assertTrue(any("falsifier" in i for i in adr.validate_adr(doc)))

    def test_bad_status_is_rejected(self):
        doc = json.loads((ROOT / adr.ADR_REL).read_text(encoding="utf-8"))
        doc["adrs"] = json.loads(json.dumps(doc["adrs"]))
        doc["adrs"][0]["status"] = "maybe"
        self.assertTrue(any("status 非法" in i for i in adr.validate_adr(doc)))

    def test_self_supersede_is_rejected(self):
        doc = json.loads((ROOT / adr.ADR_REL).read_text(encoding="utf-8"))
        doc["adrs"] = json.loads(json.dumps(doc["adrs"]))
        doc["adrs"][0]["supersedes"] = [doc["adrs"][0]["id"]]
        self.assertTrue(any("自引用" in i for i in adr.validate_adr(doc)))

    def test_supersede_cycle_is_rejected(self):
        doc = json.loads((ROOT / adr.ADR_REL).read_text(encoding="utf-8"))
        doc["adrs"] = json.loads(json.dumps(doc["adrs"]))
        doc["adrs"][0]["supersedes"] = [doc["adrs"][1]["id"]]
        doc["adrs"][1]["supersedes"] = [doc["adrs"][0]["id"]]
        self.assertTrue(any("成环" in i for i in adr.validate_adr(doc)))


class DocsLedgerTest(unittest.TestCase):
    def test_ledger_has_16_docs(self):
        ledger = json.loads((ROOT / adr.LEDGER_REL).read_text(encoding="utf-8"))
        self.assertEqual(16, len(ledger["docs"]))

    def test_ledger_is_valid(self):
        bundle = adr.load(str(ROOT))
        self.assertEqual([], adr.validate_ledger(bundle["ledger"], bundle["adr"]))

    def test_every_doc_has_one_status(self):
        ledger = json.loads((ROOT / adr.LEDGER_REL).read_text(encoding="utf-8"))
        for item in ledger["docs"]:
            self.assertIn(item["status"], adr.STATUSES, item["name"])

    def test_superseded_points_to_current(self):
        ledger = json.loads((ROOT / adr.LEDGER_REL).read_text(encoding="utf-8"))
        by_name = {d["name"]: d for d in ledger["docs"]}
        for item in ledger["docs"]:
            if item["status"] == "superseded":
                target = by_name[item["superseded_by"]]
                self.assertEqual("current", target["status"], item["name"])

    def test_duplicate_topic_current_is_rejected(self):
        ledger = json.loads((ROOT / adr.LEDGER_REL).read_text(encoding="utf-8"))
        ledger["docs"] = json.loads(json.dumps(ledger["docs"]))
        current = [d for d in ledger["docs"] if d["status"] == "current"][0]
        ledger["docs"].append(dict(current, name="COPY"))
        self.assertTrue(any("两条 current" in i for i in adr.validate_ledger(ledger)))

    def test_missing_superseded_by_is_rejected(self):
        ledger = json.loads((ROOT / adr.LEDGER_REL).read_text(encoding="utf-8"))
        ledger["docs"] = json.loads(json.dumps(ledger["docs"]))
        for item in ledger["docs"]:
            if item["status"] == "superseded":
                item.pop("superseded_by", None)
                break
        self.assertTrue(any("superseded_by" in i for i in adr.validate_ledger(ledger)))


class ReconcileTest(unittest.TestCase):
    def test_repo_matches_adr(self):
        res = adr.reconcile(str(ROOT))
        self.assertTrue(res["ok"], res["findings"][:3])

    def test_adr004_marked_dormant(self):
        bundle = adr.load(str(ROOT))
        adr004 = next(a for a in bundle["adr"]["adrs"] if a["id"] == "ADR-004")
        self.assertIn("dormant", adr004["decision"].lower())


if __name__ == "__main__":
    unittest.main()
