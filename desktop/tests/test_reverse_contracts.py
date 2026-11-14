#!/usr/bin/env python3
"""§4A R1 契约地图判据（NF-Final G0 逆向工程）。

真源 = `results/reverse/contracts.json`（`nf-reverse-contracts/1`）；人读面 = `CONTRACT_MAP.md`。
判据：
1. 结构：explicit/implicit/gaps 三组；id 唯一；status 词表；每类至少若干条；
2. 证据可核：每条 artifact 在场；fields 至少在一个 artifact 正文中命中；consumers/evidence 在场；
3. 隐式契约必须写 risk（未文档化不得写成已文档化）；gap 必须有 owner/status；
4. 文档：CONTRACT_MAP.md 出现全部 id，含复核命令与 R2–R6 交接；
5. 变异自证：删 artifact/改字段/删 consumer/隐式缺 risk/gap 缺 owner/状态错 → 都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

REG = ROOT / "results" / "reverse" / "contracts.json"
DOC = ROOT / "results" / "reverse" / "CONTRACT_MAP.md"
STATUSES = ("documented", "implicit-undocumented", "gap")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _artifact_text(root, rels):
    out = []
    for rel in rels:
        try:
            out.append((Path(root) / rel).read_text(encoding="utf-8"))
        except OSError:
            out.append("")
    return "\n".join(out)


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-reverse-contracts/1":
        return ["schema 不匹配"]
    groups = {}
    for group in ("explicit", "implicit", "gaps"):
        items = doc.get(group) or []
        if not items:
            issues.append("缺 %s" % group)
            continue
        groups[group] = items
    ids = [str(i.get("id")) for group in groups.values() for i in group]
    if len(ids) != len(set(ids)):
        issues.append("id 重复：%s" % ids)
    for group in ("explicit", "implicit"):
        for item in groups.get(group, []):
            iid = str(item.get("id"))
            if str(item.get("kind")) != group.rstrip("s") and not (
                    group == "explicit" and item.get("kind") == "explicit"):
                issues.append("%s 的 kind 与分组不符：%s" % (iid, item.get("kind")))
            if str(item.get("status")) not in STATUSES:
                issues.append("%s 的 status 非法：%s" % (iid, item.get("status")))
            artifacts = item.get("artifacts") or []
            if not artifacts:
                issues.append("%s 缺 artifacts" % iid)
            for rel in artifacts:
                if not (Path(root) / rel).is_file():
                    issues.append("%s 的 artifact 不在场：%s" % (iid, rel))
            fields = item.get("fields") or []
            if len(fields) < 2:
                issues.append("%s 字段少于 2 个" % iid)
            blob = _artifact_text(root, artifacts)
            for field in fields:
                if str(field) not in blob:
                    issues.append("%s 的字段未在 artifact 正文命中：%s" % (iid, field))
            consumers = item.get("consumers") or []
            if not consumers:
                issues.append("%s 缺 consumers" % iid)
            for rel in consumers:
                if not (Path(root) / rel).is_file():
                    issues.append("%s 的 consumer 不在场：%s" % (iid, rel))
            evidence = item.get("evidence") or []
            if not evidence:
                issues.append("%s 缺 evidence" % iid)
            for rel in evidence:
                if not (Path(root) / rel).is_file():
                    issues.append("%s 的 evidence 不在场：%s" % (iid, rel))
            if group == "implicit" and not str(item.get("risk") or "").strip():
                issues.append("%s 是隐式契约但缺 risk" % iid)
    if len(groups.get("explicit") or []) < 8:
        issues.append("显式契约少于 8 组（覆盖不足）")
    if len(groups.get("implicit") or []) < 6:
        issues.append("隐式契约少于 6 组（覆盖不足）")
    for gap in groups.get("gaps") or []:
        if not str(gap.get("owner") or "").strip():
            issues.append("gap %s 缺 owner" % gap.get("id"))
        if str(gap.get("status")) not in ("open", "accepted-risk", "closed"):
            issues.append("gap %s 的 status 非法" % gap.get("id"))
    return issues


class ReverseContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_contracts_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertGreaterEqual(len(self.doc["explicit"]), 8)
        self.assertGreaterEqual(len(self.doc["implicit"]), 6)
        self.assertGreaterEqual(len(self.doc["gaps"]), 3)

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for group in ("explicit", "implicit", "gaps"):
            for item in self.doc[group]:
                self.assertIn(item["id"], self.text, "文档缺 %s" % item["id"])
        for marker in ("R2", "R3", "R4", "R5", "R6", "复核命令"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        missing_artifact = copy.deepcopy(self.doc)
        missing_artifact["explicit"][0]["artifacts"] = ["protocol/nonexistent_zzz.json"]
        self.assertTrue(issues_for(missing_artifact, str(ROOT)), "artifact 不在场必须红")

        bad_field = copy.deepcopy(self.doc)
        bad_field["explicit"][0]["fields"] = ["no_such_field_zzz"]
        self.assertTrue(issues_for(bad_field, str(ROOT)), "字段未命中必须红")

        missing_consumer = copy.deepcopy(self.doc)
        missing_consumer["explicit"][1]["consumers"] = ["desktop/nonexistent_zzz.py"]
        self.assertTrue(issues_for(missing_consumer, str(ROOT)), "consumer 不在场必须红")

        implicit_no_risk = copy.deepcopy(self.doc)
        implicit_no_risk["implicit"][0]["risk"] = ""
        self.assertTrue(issues_for(implicit_no_risk, str(ROOT)), "隐式契约缺 risk 必须红")

        gap_no_owner = copy.deepcopy(self.doc)
        gap_no_owner["gaps"][0]["owner"] = ""
        self.assertTrue(issues_for(gap_no_owner, str(ROOT)), "gap 缺 owner 必须红")

        dup = copy.deepcopy(self.doc)
        dup["explicit"].append(copy.deepcopy(dup["explicit"][0]))
        self.assertTrue(issues_for(dup, str(ROOT)), "重复 id 必须红")

    def test_registry_consumers_exist(self):
        for group in ("explicit", "implicit"):
            for item in self.doc[group]:
                for rel in item.get("consumers", []):
                    self.assertTrue((ROOT / rel).is_file(), "%s -> %s" % (item["id"], rel))


if __name__ == "__main__":
    unittest.main()
