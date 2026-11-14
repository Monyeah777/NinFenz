#!/usr/bin/env python3
"""§4A R5 同行差分判据（NF-Final G0 逆向工程）。

真源 = `results/reverse/peers.json`（`nf-reverse-peers/1`）；人读 = `PEER_DIFF.md`。
判据：
1. peers ≥5；逐项 guarantees/not_covers/interface_model/borrow/avoid_reason 非空；
   borrow_mode ∈ {adopt, adapt, avoid, avoid-build}；repo_evidence 在场；
2. design_decisions ≥1 且至少一条 target ∈ {G1, G3}（DoD：同行差分影响最终设计）；
   decision/rationale/repo_refs 在场；status 词表；
3. 纪律：claims_boundary 必须写明「不作质量背书/机制层」；文档出现全部 id；
4. 变异自证：peer 缺字段、证据不在场、非法 borrow_mode、决策不指向 G1/G3、
   缺 rationale、缺边界声明 → 都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

REG = ROOT / "results" / "reverse" / "peers.json"
DOC = ROOT / "results" / "reverse" / "PEER_DIFF.md"
MODES = ("adopt", "adapt", "avoid", "avoid-build")
DECISION_STATUS = ("decided", "open", "rejected")
TARGETS = ("G1", "G2", "G3", "G4", "G5")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-reverse-peers/1":
        return ["schema 不匹配"]
    peers = doc.get("peers") or []
    if len(peers) < 5:
        issues.append("peers 少于 5 项（覆盖不足）")
    for peer in peers:
        pid = str(peer.get("id"))
        for field in ("name", "category", "guarantees", "not_covers", "interface_model",
                      "borrow", "avoid_reason"):
            if not str(peer.get(field) or "").strip():
                issues.append("%s 缺 %s" % (pid, field))
        if str(peer.get("borrow_mode")) not in MODES:
            issues.append("%s 的 borrow_mode 非法：%s" % (pid, peer.get("borrow_mode")))
        refs = peer.get("repo_evidence") or []
        if not refs:
            issues.append("%s 缺 repo_evidence" % pid)
        for rel in refs:
            if not (Path(root) / rel).exists():
                issues.append("%s 的 repo_evidence 不在场：%s" % (pid, rel))
    decisions = doc.get("design_decisions") or []
    if not decisions:
        issues.append("缺 design_decisions（DoD 要求同行差分影响设计）")
    if not any(str(d.get("target")) in ("G1", "G3") for d in decisions):
        issues.append("design_decisions 没有任何一条指向 G1/G3（DoD 不满足）")
    for dec in decisions:
        did = str(dec.get("id"))
        if str(dec.get("target")) not in TARGETS:
            issues.append("%s 的 target 非法：%s" % (did, dec.get("target")))
        if str(dec.get("status")) not in DECISION_STATUS:
            issues.append("%s 的 status 非法：%s" % (did, dec.get("status")))
        for field in ("decision", "rationale"):
            if not str(dec.get(field) or "").strip():
                issues.append("%s 缺 %s" % (did, field))
        for rel in dec.get("repo_refs") or []:
            if not (Path(root) / rel).exists():
                issues.append("%s 的 repo_ref 不在场：%s" % (did, rel))
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "质量背书" not in boundary:
        issues.append("claims_boundary 必须写明不作质量背书")
    return issues


class ReversePeersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_peers_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertGreaterEqual(len(self.doc["peers"]), 5)
        self.assertTrue(any(d["target"] in ("G1", "G3")
                            for d in self.doc["design_decisions"]))

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for peer in self.doc["peers"]:
            self.assertIn(peer["id"], self.text)
        for dec in self.doc["design_decisions"]:
            self.assertIn(dec["id"], self.text)
        for marker in ("不作质量背书", "R6", "复核命令", "借/不造"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        no_field = copy.deepcopy(self.doc)
        no_field["peers"][0]["not_covers"] = ""
        self.assertTrue(issues_for(no_field, str(ROOT)), "peer 缺字段必须红")

        bad_evidence = copy.deepcopy(self.doc)
        bad_evidence["peers"][0]["repo_evidence"] = ["desktop/nonexistent_zzz.py"]
        self.assertTrue(issues_for(bad_evidence, str(ROOT)), "证据不在场必须红")

        bad_mode = copy.deepcopy(self.doc)
        bad_mode["peers"][0]["borrow_mode"] = "copy"
        self.assertTrue(issues_for(bad_mode, str(ROOT)), "非法 borrow_mode 必须红")

        bad_target = copy.deepcopy(self.doc)
        for dec in bad_target["design_decisions"]:
            dec["target"] = "G5"
        self.assertTrue(issues_for(bad_target, str(ROOT)), "决策不指向 G1/G3 必须红")

        no_rationale = copy.deepcopy(self.doc)
        no_rationale["design_decisions"][0]["rationale"] = ""
        self.assertTrue(issues_for(no_rationale, str(ROOT)), "缺 rationale 必须红")

        no_boundary = copy.deepcopy(self.doc)
        no_boundary["claims_boundary"] = ["同行信息仅参考"]
        self.assertTrue(issues_for(no_boundary, str(ROOT)), "缺边界声明必须红")


if __name__ == "__main__":
    unittest.main()
