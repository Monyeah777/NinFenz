#!/usr/bin/env python3
"""§4A R2 行为重建判据（NF-Final G0 逆向工程）。

真源 = `results/reverse/behavior.json`（`nf-reverse-behavior/1`）；人读 = `BEHAVIOR.md`；
契约引用需与 R1 `contracts.json` 对齐。判据：
1. 流：id 唯一；entry/outputs 在场；checks 标签在 verify.sh 命中；失败语义 exit∈{0,1,2}
   且 evidence 在场；documented 流必须有 stages/contracts；gap 流必须写 gap id（须在 R1 gaps）；
2. 状态机：evidence 在场；states≥2；transitions 端点合法；规则非空；
3. 契约对齐：flow.contracts ⊆ R1 的 X-xx / I-xx；
4. 文档：BEHAVIOR.md 出现全部 id，含失败语义/状态机/交接；
5. 变异自证：入口不在场、generated 不在场、check 不存在、exit 非法、迁移端点非法、
   未登记 gap、未登记 contract → 都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

REG = ROOT / "results" / "reverse" / "behavior.json"
CONTRACTS = ROOT / "results" / "reverse" / "contracts.json"
DOC = ROOT / "results" / "reverse" / "BEHAVIOR.md"
STATUSES = ("documented", "partial", "gap")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-reverse-behavior/1":
        return ["schema 不匹配"]
    contracts_doc = _json(CONTRACTS)
    contract_ids = {str(x.get("id")) for group in ("explicit", "implicit")
                    for x in contracts_doc.get(group) or []}
    gap_ids = {str(x.get("id")) for x in contracts_doc.get("gaps") or []}
    verify_text = _text(Path(root) / "verify.sh")
    flows = doc.get("flows") or []
    if len(flows) < 6:
        issues.append("flows 少于 6 条")
    ids = [str(f.get("id")) for f in flows if isinstance(f, dict)]
    if len(ids) != len(set(ids)):
        issues.append("flow id 重复：%s" % ids)
    for flow in flows:
        if not isinstance(flow, dict):
            issues.append("flows 含非对象")
            continue
        fid = str(flow.get("id"))
        status = str(flow.get("status"))
        if status not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (fid, status))
        entry = str(flow.get("entry") or "")
        if not entry or not (Path(root) / entry).is_file():
            issues.append("%s 的 entry 不在场：%s" % (fid, entry))
        if not str(flow.get("command") or "").strip():
            issues.append("%s 缺 command" % fid)
        stages = flow.get("stages") or []
        if status == "documented" and len(stages) < 2:
            issues.append("%s 缺 stages" % fid)
        for rel in flow.get("outputs") or []:
            if not (Path(root) / rel).exists():
                issues.append("%s 的 output 不在场：%s" % (fid, rel))
        for label in flow.get("checks") or []:
            if status == "gap":
                continue  # 未实现流的 check 编号是计划值，不要求已接线
            if str(label) not in verify_text:
                issues.append("%s 的 check 标签未在 verify.sh 命中：%s" % (fid, label))
        for rel in flow.get("contracts") or []:
            if str(rel) not in contract_ids:
                issues.append("%s 引用了未登记契约：%s" % (fid, rel))
        if status == "documented" and not flow.get("contracts"):
            issues.append("%s 缺 contracts 引用" % fid)
        if status == "gap":
            gap = str(flow.get("gap") or "")
            if gap not in gap_ids:
                issues.append("%s 的 gap 未在 R1 gaps 登记：%s" % (fid, gap))
        for fail in flow.get("failures") or []:
            if not isinstance(fail, dict):
                issues.append("%s failures 含非对象" % fid)
                continue
            if not str(fail.get("condition") or "").strip():
                issues.append("%s failure 缺 condition" % fid)
            if fail.get("exit") not in (0, 1, 2):
                issues.append("%s failure 的 exit 非法：%s" % (fid, fail.get("exit")))
            ev = str(fail.get("evidence") or "")
            if not ev or not (Path(root) / ev).is_file():
                issues.append("%s failure evidence 不在场：%s" % (fid, ev))
    machines = doc.get("state_machines") or []
    if not machines:
        issues.append("缺 state_machines")
    for machine in machines:
        if not isinstance(machine, dict):
            issues.append("state_machines 含非对象")
            continue
        mid = str(machine.get("id"))
        ev = str(machine.get("evidence") or "")
        if not ev or not (Path(root) / ev).is_file():
            issues.append("%s 的 evidence 不在场：%s" % (mid, ev))
        states = [str(s) for s in machine.get("states") or []]
        if len(states) < 2:
            issues.append("%s 状态少于 2" % mid)
        for trans in machine.get("transitions") or []:
            if str(trans.get("from")) not in states or str(trans.get("to")) not in states:
                issues.append("%s 迁移端点非法：%r" % (mid, trans))
            if not str(trans.get("cmd") or "").strip():
                issues.append("%s 迁移缺 cmd" % mid)
        if not str(machine.get("rule") or "").strip():
            issues.append("%s 缺 rule" % mid)
    return issues


class ReverseBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_behavior_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertGreaterEqual(len(self.doc["flows"]), 6)
        self.assertGreaterEqual(len(self.doc["state_machines"]), 2)
        docs = [f for f in self.doc["flows"] if f["status"] == "documented"]
        gaps = [f for f in self.doc["flows"] if f["status"] == "gap"]
        self.assertTrue(docs and gaps, "既要有 documented 也要有 gap 流")

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for flow in self.doc["flows"]:
            self.assertIn(flow["id"], self.text)
        for machine in self.doc["state_machines"]:
            self.assertIn(machine["id"], self.text)
        for marker in ("失败语义", "状态机", "R3", "R6", "复核命令"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        bad_entry = copy.deepcopy(self.doc)
        bad_entry["flows"][0]["entry"] = "scripts/nonexistent_zzz.py"
        self.assertTrue(issues_for(bad_entry, str(ROOT)), "entry 不在场必须红")

        bad_output = copy.deepcopy(self.doc)
        bad_output["flows"][0]["outputs"] = ["protocol/nonexistent_zzz.json"]
        self.assertTrue(issues_for(bad_output, str(ROOT)), "output 不在场必须红")

        bad_check = copy.deepcopy(self.doc)
        bad_check["flows"][0]["checks"] = ["check999"]
        self.assertTrue(issues_for(bad_check, str(ROOT)), "不存在 check 必须红")

        bad_exit = copy.deepcopy(self.doc)
        bad_exit["flows"][0]["failures"][0]["exit"] = 9
        self.assertTrue(issues_for(bad_exit, str(ROOT)), "非法 exit 必须红")

        bad_trans = copy.deepcopy(self.doc)
        bad_trans["state_machines"][0]["transitions"][0]["to"] = "nowhere"
        self.assertTrue(issues_for(bad_trans, str(ROOT)), "迁移端点非法必须红")

        bad_gap = copy.deepcopy(self.doc)
        next(f for f in bad_gap["flows"] if f["status"] == "gap")["gap"] = "OPEN-NOT-EXIST"
        self.assertTrue(issues_for(bad_gap, str(ROOT)), "未登记 gap 必须红")

        bad_contract = copy.deepcopy(self.doc)
        bad_contract["flows"][0]["contracts"] = ["X-99"]
        self.assertTrue(issues_for(bad_contract, str(ROOT)), "未登记 contract 必须红")


if __name__ == "__main__":
    unittest.main()
