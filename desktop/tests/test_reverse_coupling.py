#!/usr/bin/env python3
"""§4A R3 耦合/重复实现判据（NF-Final G0 逆向工程）。

真源 = `results/reverse/coupling.json`（`nf-reverse-coupling/1`）；人读 = `COUPLING.md`。
判据：
1. 图事实**实时重算**：模块数/边数/环/SDP 违规清单必须与本件一致（图变即红，须重跑 R3）；
2. 重复候选：裁定词表内；候选/证据在场；action 非空；≥5 项；
3. 热点：fan-in/fan-out 条目模块命名且数值正；
4. 缺口 owner 在场；文档交叉（全部 id）；
5. 变异自证：图漂移、候选不在场、非法裁定、证据缺失、action 空、SDP 漂移 → 都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import coupling_metrics  # noqa: E402

REG = ROOT / "results" / "reverse" / "coupling.json"
DOC = ROOT / "results" / "reverse" / "COUPLING.md"
VERDICTS = ("compat-duplicate", "distinct-spec", "distinct-role", "shared-primitive",
            "duplicate-suspected", "documented-exception")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _live_graph(root):
    deps, metrics = coupling_metrics.graph(str(root))
    return {"modules": len(deps), "edges": sum(len(v) for v in deps.values()),
            "cycles": len(coupling_metrics.cycles(deps)),
            "sdp": [list(x) for x in coupling_metrics.sdp_violations(deps, metrics)]}


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-reverse-coupling/1":
        return ["schema 不匹配"]
    graph = doc.get("graph") or {}
    live = _live_graph(root)
    if int(graph.get("modules") or 0) != live["modules"]:
        issues.append("模块数漂移（记录 %s / 实测 %s）" % (graph.get("modules"), live["modules"]))
    if int(graph.get("edges") or 0) != live["edges"]:
        issues.append("边数漂移（记录 %s / 实测 %s）" % (graph.get("edges"), live["edges"]))
    if int(graph.get("cycles") or 0) != live["cycles"]:
        issues.append("环数漂移（记录 %s / 实测 %s）" % (graph.get("cycles"), live["cycles"]))
    if [list(x) for x in graph.get("sdp_violations") or []] != live["sdp"]:
        issues.append("SDP 违规清单漂移（重跑 R3）")
    dups = doc.get("duplicates") or []
    if len(dups) < 5:
        issues.append("重复候选少于 5 项（覆盖不足）")
    for item in dups:
        did = str(item.get("id"))
        if str(item.get("verdict")) not in VERDICTS:
            issues.append("%s 的 verdict 非法：%s" % (did, item.get("verdict")))
        if not str(item.get("theme") or "").strip():
            issues.append("%s 缺 theme" % did)
        for rel in item.get("candidates") or []:
            if not (Path(root) / rel).is_file():
                issues.append("%s 的候选不在场：%s" % (did, rel))
        if not item.get("candidates"):
            issues.append("%s 缺候选" % did)
        for rel in item.get("evidence") or []:
            if not (Path(root) / rel).is_file():
                issues.append("%s 的 evidence 不在场：%s" % (did, rel))
        if not item.get("evidence"):
            issues.append("%s 缺 evidence" % did)
        if not str(item.get("action") or "").strip():
            issues.append("%s 缺 action" % did)
        if not str(item.get("rationale") or "").strip():
            issues.append("%s 缺 rationale" % did)
    hotspots = doc.get("hotspots") or {}
    for key in ("top_fan_in", "top_fan_out"):
        rows = hotspots.get(key) or []
        if not rows:
            issues.append("缺 %s" % key)
        for name, value in rows:
            if not (Path(root) / "desktop" / "src" / "core" / (name + ".py")).is_file() \
                    and not (Path(root) / "desktop" / "src" / "core" / name).is_dir():
                issues.append("%s 的模块不在场：%s" % (key, name))
            if int(value) <= 0:
                issues.append("%s 的值非正：%s" % (key, name))
    for gap in doc.get("gaps") or []:
        if not str(gap.get("owner") or "").strip():
            issues.append("gap %s 缺 owner" % gap.get("id"))
    return issues


class ReverseCouplingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_coupling_valid_and_live(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        live = _live_graph(ROOT)
        self.assertGreater(live["modules"], 200)

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for item in self.doc["duplicates"]:
            self.assertIn(item["id"], self.text)
        for gap in self.doc["gaps"]:
            self.assertIn(gap["id"], self.text)
        for marker in ("SDP", "R6", "复核命令", "裁定"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        drift = copy.deepcopy(self.doc)
        drift["graph"]["modules"] = 1
        self.assertTrue(issues_for(drift, str(ROOT)), "模块数漂移必须红")

        bad_sdp = copy.deepcopy(self.doc)
        bad_sdp["graph"]["sdp_violations"] = [["a", "b"]]
        self.assertTrue(issues_for(bad_sdp, str(ROOT)), "SDP 漂移必须红")

        bad_cand = copy.deepcopy(self.doc)
        bad_cand["duplicates"][0]["candidates"] = ["desktop/src/core/nonexistent_zzz.py"]
        self.assertTrue(issues_for(bad_cand, str(ROOT)), "候选不在场必须红")

        bad_verdict = copy.deepcopy(self.doc)
        bad_verdict["duplicates"][0]["verdict"] = "duplicated"
        self.assertTrue(issues_for(bad_verdict, str(ROOT)), "非法裁定必须红")

        no_evidence = copy.deepcopy(self.doc)
        no_evidence["duplicates"][1]["evidence"] = []
        self.assertTrue(issues_for(no_evidence, str(ROOT)), "缺证据必须红")

        no_action = copy.deepcopy(self.doc)
        no_action["duplicates"][2]["action"] = ""
        self.assertTrue(issues_for(no_action, str(ROOT)), "缺 action 必须红")


if __name__ == "__main__":
    unittest.main()
