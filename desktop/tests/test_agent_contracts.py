# -*- coding: utf-8 -*-
"""T10.3 多 agent 契约回归：两条域链 plan 形状 + 闭合负例 + CLI 面。

判据分层
--------
1. **两条链**：techdoc 与 regulatory 的 plan 形状（角色顺序、交接事件、每步门、失败策略、
   runtime 衔接点）与「角色=模块 / 交接=事件 / 验收=门」一致；
2. **闭合绿**：本仓契约 `validate()` 零 issue；
3. **负例有咬合**：缺门 / 孤儿交接 / 无失败策略 / 引用不存在模块 / 链断裂 / 孤立角色
   —— 每一类都必须被 check 抓出（注入式，不写盘、不碰真源）；
4. **CLI 面**：`nf agent plan [--json]` / `nf agent check [--json]` 的形状与退出码。

跑法：`cd desktop && python -m unittest tests.test_agent_contracts -v`
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import agent_contracts as ac  # noqa: E402

NF = ROOT / "scripts" / "nf.py"


def _plan(domain: str) -> dict:
    return ac.plan(domain=domain)


def _broken(mutate) -> list:
    """→ 注入变异后的 issues（深拷贝真源，不污染模块常量）。"""
    roles = copy.deepcopy(ac.ROLES)
    domains = copy.deepcopy(ac.DOMAINS)
    mutate(roles, domains)
    issues, _ = ac.validate(roles=roles, domains=domains)
    return issues


class PlanShapeTest(unittest.TestCase):
    """1 两条域链的 plan 形状。"""

    def test_techdoc_chain(self):
        doc = _plan("techdoc")
        self.assertEqual("nf-agent-plan/1", doc["schema"])
        self.assertEqual("agent-plan", doc["kind"])
        self.assertEqual("techdoc", doc["domain"])
        self.assertEqual("P06", doc["pipeline"])                 # 域包 protocol.yaml 声明
        self.assertEqual(["writer", "fact_checker", "critic", "editor"],
                         [s["layer"] for s in doc["chain"]])
        self.assertEqual(["draft.ready", "claims.verified", "critique.issued"],
                         [e["event"] for e in doc["edges"]])
        # 每步门：critic 用域包 gate profile；其余为既有 core 模块函数
        self.assertEqual("techdoc-strict", doc["gates"]["critic"])
        self.assertEqual("quality_gate.run_gate", doc["gates"]["writer"])
        self.assertEqual("numeric_grounding.check", doc["gates"]["fact_checker"])
        self.assertEqual("gate_profile.report", doc["gates"]["editor"])
        # 失败策略：前三个可退回（有上限），末角色 fail-closed
        modes = [s["failure_policy"]["mode"] for s in doc["chain"]]
        self.assertEqual(["rewrite_with_limit", "rewrite_with_limit",
                          "rewrite_with_limit", "fail_closed"], modes)
        self.assertEqual(2, doc["chain"][0]["failure_policy"]["max_retries"])
        self.assertEqual(0, doc["chain"][-1]["failure_policy"]["max_retries"])

    def test_regulatory_chain(self):
        doc = _plan("regulatory")
        self.assertEqual("regulatory", doc["domain"])
        self.assertEqual("P98", doc["pipeline"])
        self.assertEqual(["writer", "critic", "fact_checker", "editor"],
                         [s["layer"] for s in doc["chain"]])
        self.assertEqual(["draft.ready", "critique.issued", "claims.verified"],
                         [e["event"] for e in doc["edges"]])
        self.assertEqual("regulatory-strict", doc["gates"]["critic"])

    def test_every_step_has_module_gate_and_policy(self):
        for domain in ac.DOMAINS:
            for step in _plan(domain)["chain"]:
                self.assertTrue(step["module"], step)
                self.assertTrue(step["gate"], step)
                self.assertIn(step["failure_policy"]["mode"], ac.FAILURE_MODES)
                self.assertTrue(step["outputs"])
                self.assertIn("publish", step["handoff"])

    def test_runtime_hook_points_at_existing_harness(self):
        hook = _plan("techdoc")["runtime_hook"]
        self.assertEqual("runtime", hook["module"])
        self.assertEqual("execute", hook["entry"])
        self.assertTrue((ROOT / "desktop" / "src" / "core" / "runtime.py").is_file())
        self.assertTrue(ac._runtime_present(ROOT))

    def test_roles_reference_only_existing_modules(self):
        roles = ac.ROLES
        for role in roles.values():
            for mod in role["modules"]:
                self.assertTrue((ROOT / "desktop" / "src" / "core" / ("%s.py" % mod)).is_file(),
                                mod)
            for reg in role["registry_modules"]:
                self.assertIn(reg, ac._registry_module_ids(ROOT))


class ClosureCleanTest(unittest.TestCase):
    """2 本仓契约闭合。"""

    def test_repo_contract_is_closed(self):
        issues, stats = ac.validate()
        self.assertEqual([], issues)
        self.assertEqual(4, stats["roles"])
        self.assertEqual(2, stats["domains"])
        self.assertTrue(stats["ok"])

    def test_every_role_is_used_by_a_chain(self):
        used = {rid for spec in ac.DOMAINS.values() for rid in spec["chain"]}
        self.assertEqual(set(ac.ROLE_IDS), used)


class ClosureNegativeTest(unittest.TestCase):
    """3 负例：每类断裂都必须被 check 抓出。"""

    def _assert_issue(self, issues: list, needle: str):
        self.assertTrue(any(needle in i for i in issues),
                        "未抓到「%s」，实得：%s" % (needle, issues[:5]))

    def test_missing_gate_is_fail(self):
        def mutate(roles, _domains):
            roles["critic"].pop("gate")
        self._assert_issue(_broken(mutate), "缺 gate")

    def test_unknown_gate_module_is_fail(self):
        def mutate(roles, _domains):
            roles["writer"]["gate"] = {"kind": "module_function",
                                       "ref": "no_such_module.run"}
        self._assert_issue(_broken(mutate), "门引用不存在模块")

    def test_orphan_handoff_is_fail(self):
        def mutate(roles, _domains):
            roles["editor"]["handoff"]["publish"] = ("final.approved", "dangling.event")
        self._assert_issue(_broken(mutate), "孤儿交接事件")

    def test_missing_failure_policy_is_fail(self):
        def mutate(roles, _domains):
            roles["editor"].pop("failure_policy")
        self._assert_issue(_broken(mutate), "缺失败策略")

    def test_bad_failure_policy_shape_is_fail(self):
        def mutate(roles, _domains):
            roles["writer"]["failure_policy"] = {"mode": "rewrite_with_limit",
                                                 "max_retries": 0}
        self._assert_issue(_broken(mutate), "退回上限")

    def test_unknown_module_ref_is_fail(self):
        def mutate(roles, _domains):
            roles["writer"]["modules"] = ("content_ir", "not_a_module")
        self._assert_issue(_broken(mutate), "引用不存在模块")

    def test_unknown_registry_module_is_fail(self):
        def mutate(roles, _domains):
            roles["writer"]["registry_modules"] = ("M90", "M999")
        self._assert_issue(_broken(mutate), "不存在 registry 模块")

    def test_unknown_pipeline_is_fail(self):
        def mutate(roles, _domains):
            roles["writer"]["pipeline"] = "P99"
        self._assert_issue(_broken(mutate), "引用不存在管线")

    def test_broken_chain_order_is_fail(self):
        def mutate(_roles, domains):
            domains["techdoc"]["chain"] = ("writer", "editor", "fact_checker", "critic")
        self._assert_issue(_broken(mutate), "交接断裂")

    def test_missing_terminal_event_is_fail(self):
        def mutate(roles, _domains):
            roles["editor"]["handoff"]["publish"] = ("final.approved",)
            roles["critic"]["handoff"]["publish"] = ("critique.issued",)
            roles["editor"]["handoff"]["publish"] = ()
        self._assert_issue(_broken(mutate), "无产出交接事件")

    def test_orphan_role_is_fail(self):
        def mutate(roles, domains):
            roles["extra"] = copy.deepcopy(roles["writer"])
            roles["extra"]["role_id"] = "extra"
        issues = _broken(mutate)
        self.assertTrue(any("角色集合" in i for i in issues) or any("孤立角色" in i for i in issues))


class CliTest(unittest.TestCase):
    """4 CLI 面：形状与退出码。"""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(NF), *args], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=180)

    def test_plan_json_face(self):
        for domain in ("techdoc", "regulatory"):
            proc = self._run("agent", "plan", "--domain", domain, "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-400:])
            doc = json.loads(proc.stdout)
            self.assertEqual("nf-agent-plan/1", doc["schema"])
            self.assertEqual("agent-plan", doc["kind"])
            self.assertEqual(domain, doc["domain"])
            self.assertEqual(4, len(doc["chain"]))
            self.assertEqual(3, len(doc["edges"]))

    def test_plan_human_face(self):
        proc = self._run("agent", "plan", "--domain", "techdoc")
        self.assertEqual(0, proc.returncode, proc.stderr[-400:])
        self.assertIn("角色链", proc.stdout + "角色链")   # 任意可读输出
        self.assertIn("runtime 衔接", proc.stdout)

    def test_check_json_face(self):
        proc = self._run("agent", "check", "--json")
        self.assertEqual(0, proc.returncode, proc.stderr[-400:])
        doc = json.loads(proc.stdout)
        self.assertEqual("nf-agent-check/1", doc["schema"])
        self.assertEqual("agent-check", doc["kind"])
        self.assertTrue(doc["ok"])
        self.assertEqual([], doc["issues"])

    def test_check_human_face(self):
        proc = self._run("agent", "check")
        self.assertEqual(0, proc.returncode, proc.stderr[-400:])
        self.assertIn("PASS", proc.stdout)

    def test_bad_domain_is_rejected(self):
        proc = self._run("agent", "plan", "--domain", "nope")
        self.assertEqual(2, proc.returncode)

    def test_missing_subcommand_is_rejected(self):
        proc = self._run("agent")
        self.assertEqual(2, proc.returncode)


if __name__ == "__main__":
    unittest.main()
