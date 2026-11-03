"""NF Evidence MCP（本地只读证据面）回归：卡生成/校验/差异/契约列表/越界拒绝。"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import evidence_mcp as em  # noqa: E402


class EvidenceCardTest(unittest.TestCase):
    def test_card_and_verify_roundtrip(self):
        card = em.evidence_card("docs/mcp.md", ROOT)
        self.assertEqual(em.SCHEMA, card["schema"])
        self.assertEqual("docs/mcp.md", card["subject"]["path"])
        self.assertTrue(em.verify_card(card, ROOT)["ok"])

    def test_tampered_card_is_detected(self):
        card = em.evidence_card("docs/mcp.md", ROOT)
        card["subject"]["sha256"] = "0" * 64
        res = em.verify_card(card, ROOT)
        self.assertFalse(res["ok"])
        self.assertTrue(any("漂移" in i for i in res["issues"]), res)

    def test_path_escape_rejected(self):
        with self.assertRaises(Exception):
            em.evidence_card("../secret.md", ROOT)

    def test_diff_cards(self):
        a = em.evidence_card("docs/mcp.md", ROOT)
        b = em.evidence_card("docs/mcp.md", ROOT, contract="大语言模型")
        d = em.diff_cards(a, b)
        self.assertTrue(d["same_subject"])  # 同主体
        self.assertTrue(any(c["field"] == "contract" for c in d["changed"]))

    def test_contract_drift_is_detected(self):
        card = em.evidence_card("community/大语言模型域包/assets/DOMAIN_SPEC.md", ROOT,
                                contract="大语言模型")
        self.assertEqual("A01", card["contract"]["code"])
        self.assertTrue(all(c["ok"] for c in card["contract"]["checks"]),
                        card["contract"]["checks"])
        self.assertEqual(12, card["contract"]["rules_count"])
        self.assertTrue(card["contract"]["rules_digest"])
        rules = {c["rule"] for c in card["contract"]["checks"]}
        self.assertEqual({"contract_yaml", "contract_subdivisions",
                          "contract_outputs_index", "contract_modules_registered",
                          "contract_coverage"}, rules)
        card["contract"]["sha256"] = "0" * 64
        res = em.verify_card(card, ROOT)
        self.assertFalse(res["ok"])
        self.assertTrue(any("契约漂移" in i for i in res["issues"]), res)

    def test_coverage_is_enforced(self):
        covered = em.evidence_card("community/大语言模型域包/assets/DOMAIN_SPEC.md", ROOT,
                                   contract="大语言模型")
        self.assertTrue(covered["contract"]["coverage"]["ok"])
        self.assertTrue(em.verify_card(covered, ROOT)["ok"])
        partial = em.evidence_card("docs/mcp.md", ROOT, contract="大语言模型")
        self.assertFalse(partial["contract"]["coverage"]["ok"])
        self.assertFalse(em.verify_card(partial, ROOT)["ok"])
        strict = em.evidence_card("community/大语言模型域包/assets/DOMAIN_SPEC.md", ROOT,
                                  contract="大语言模型", min_names=12, min_fields=19)
        self.assertTrue(strict["contract"]["coverage"]["ok"])
        loose = em.evidence_card("community/大语言模型域包/assets/DOMAIN_SPEC.md", ROOT,
                                 contract="大语言模型", min_fields=20)
        self.assertFalse(loose["contract"]["coverage"]["ok"])

    def test_evidence_card_with_cognition(self):
        import os, tempfile
        from core.meta_cockpit import cognition_event as ce
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev = ce.build({
                    "schema": "nf-cockpit-manifest/1", "prompt_digest": "a" * 64,
                    "machine_digest": "b" * 64, "runtime_digest": "c" * 64,
                    "journal_digest": "d" * 64, "handoff_digest": "e" * 64,
                    "context_digest": "f" * 64, "status": "pass",
                    "termination": "max-turns", "complete": False, "turns": 1,
                    "context_units_spent": 1, "abstention_status": "none",
                    "human_action_required": False,
                })
                ce.write(ev)
                card = em.evidence_card("docs/mcp.md", ROOT, cognition=ev)
                self.assertTrue(em.verify_card(card, ROOT)["ok"])
                card["cognition"]["handoff_digest"] = "0" * 64
                self.assertFalse(em.verify_card(card, ROOT)["ok"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_cognition_evidence_roles_propagate_and_mismatch_detected(self):
        import os, tempfile
        from core.meta_cockpit import cognition_event as ce
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                roles = {"local-trusted": 1, "derived": 1,
                         "external-advisory": 1}
                ev = ce.build({
                    "schema": "nf-cockpit-manifest/1", "prompt_digest": "a" * 64,
                    "machine_digest": "b" * 64, "runtime_digest": "c" * 64,
                    "journal_digest": "d" * 64, "handoff_digest": "e" * 64,
                    "context_digest": "f" * 64, "status": "pass",
                    "termination": "max-turns", "complete": False, "turns": 1,
                    "context_units_spent": 1, "abstention_status": "none",
                    "human_action_required": False,
                }, evidence_roles=roles)
                ce.write(ev)
                card = em.evidence_card("docs/mcp.md", ROOT, cognition=ev)
                # 卡透传同值 + 校验通过
                self.assertEqual(roles, card["cognition"]["evidence_roles"])
                self.assertTrue(em.verify_card(card, ROOT)["ok"])
                # 篡改角色（尝试把外部建议升级为派生）→ 一致性校验必须报错
                card["cognition"]["evidence_roles"] = {
                    "local-trusted": 1, "derived": 2,
                    "external-advisory": 0}
                res = em.verify_card(card, ROOT)
                self.assertFalse(res["ok"])
                self.assertTrue(any("cognition evidence_roles 不一致" in i
                                    for i in res["issues"]), res["issues"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_cognition_evidence_roles_whitelist_in_card(self):
        import os, tempfile
        from core.meta_cockpit import cognition_event as ce
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                roles = {"local-trusted": 1, "derived": 1}
                ev = ce.build({
                    "schema": "nf-cockpit-manifest/1", "prompt_digest": "a" * 64,
                    "machine_digest": "b" * 64, "runtime_digest": "c" * 64,
                    "journal_digest": "d" * 64, "handoff_digest": "e" * 64,
                    "context_digest": "f" * 64, "status": "pass",
                    "termination": "max-turns", "complete": False, "turns": 1,
                    "context_units_spent": 1, "abstention_status": "none",
                    "human_action_required": False,
                }, evidence_roles=roles)
                ce.write(ev)
                card = em.evidence_card("docs/mcp.md", ROOT, cognition=ev)
                self.assertEqual(roles, card["cognition"]["evidence_roles"])
                self.assertTrue(em.verify_card(card, ROOT)["ok"])
                # 卡片 roles 非法（未知键 / 负数 / bool）→ verify 报 issue
                for bad_roles in ({"bogus": 1},
                                  {"local-trusted": -1},
                                  {"derived": True}):
                    bad = json.loads(json.dumps(card))
                    bad["cognition"]["evidence_roles"] = bad_roles
                    res = em.verify_card(bad, ROOT)
                    self.assertFalse(res["ok"], bad_roles)
                    self.assertTrue(any("cognition card evidence_roles 非法"
                                        in i for i in res["issues"]),
                                    res["issues"])
                # 事件侧 roles 非法（先重算 digest 让事件自洽）→ 也报 issue
                bad_ev = json.loads(json.dumps(ev))
                bad_ev["evidence_roles"] = {"unknown": 1}
                bad_ev["digest"] = ce.digest(
                    {k: v for k, v in bad_ev.items() if k != "digest"})
                ce.write(bad_ev) if False else None
                # evidence_card 直接拒绝非法事件 roles（fail-closed）
                with self.assertRaises(ValueError):
                    em.evidence_card("docs/mcp.md", ROOT, cognition=bad_ev)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_unknown_contract_rejected(self):
        with self.assertRaises(Exception):
            em.evidence_card("docs/mcp.md", ROOT, contract="不存在的域")

    def test_list_contracts(self):
        packs = em.list_contracts(ROOT, "大语言模型")
        self.assertTrue(isinstance(packs, list))
        self.assertGreaterEqual(len(packs), 1)


class ArtifactChecksTest(unittest.TestCase):
    def test_json_and_markdown_checks(self):
        self.assertTrue(all(c["ok"] for c in em.artifact_checks("protocol/mcp_package.json", ROOT)))
        rules = {c["rule"] for c in em.artifact_checks("docs/mcp.md", ROOT)}
        self.assertIn("utf8", rules)
        self.assertNotIn("json_parse", rules)

    def test_check_result_change_detected(self):
        card = em.evidence_card("docs/mcp.md", ROOT)
        card["checks"][0]["ok"] = False
        res = em.verify_card(card, ROOT)
        self.assertFalse(res["ok"])
        self.assertTrue(any("检查结果变化" in i for i in res["issues"]), res)


class CockpitLogTest(unittest.TestCase):
    def test_append_and_list(self):
        import os
        import tempfile
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                from core import cockpit_log as cl
                r = cl.append({"kind": "decision", "text": "采用本地证据层",
                               "evidence": ["docs/mcp.md"]})
                self.assertTrue(r["ok"])
                rows = cl.records()
                self.assertEqual(1, len(rows))
                self.assertEqual("decision", rows[0]["kind"])
                dup = cl.append({"kind": "decision", "text": "采用本地证据层",
                                 "evidence": ["docs/mcp.md"]})
                self.assertTrue(dup["duplicate"])
                self.assertEqual(1, len(cl.records()))
            finally:
                if old is None:
                    os.environ.pop("NF_COCKPIT_HOME", None)
                else:
                    os.environ["NF_COCKPIT_HOME"] = old

    def test_close_action_requires_evidence(self):
        import os, tempfile
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                with self.assertRaises(Exception):
                    em.call_tool("close_action", {"action_id": "A-1", "evidence": []}, ROOT)
                got = em.call_tool("close_action",
                                   {"action_id": "A-1", "evidence": ["docs/mcp.md"],
                                    "result": "done"}, ROOT)
                payload = json.loads(got["content"][0]["text"])
                self.assertTrue(payload["ok"])
                self.assertEqual("action", payload["record"]["kind"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_invalid_kind_rejected(self):
        from core import cockpit_log as cl
        with self.assertRaises(ValueError):
            cl.append({"kind": "note", "text": "x"})


class JsonRpcTest(unittest.TestCase):
    def test_tools_list_and_unknown_method(self):
        r = em.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, ROOT)
        names = {t["name"] for t in r["result"]["tools"]}
        self.assertEqual({"evidence_card", "verify_card", "diff_cards", "contract_rules",
                          "check_artifact", "attach_decision", "close_action",
                          "cockpit_summary", "list_decisions", "list_contracts",
                          "cognition_event"}, names)
        r = em.handle({"jsonrpc": "2.0", "id": 2, "method": "nope"}, ROOT)
        self.assertEqual(-32601, r["error"]["code"])

    def test_tool_call_shape(self):
        r = em.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                       "params": {"name": "evidence_card",
                                  "arguments": {"path": "docs/mcp.md"}}}, ROOT)
        payload = json.loads(r["result"]["content"][0]["text"])
        self.assertEqual("docs/mcp.md", payload["subject"]["path"])
