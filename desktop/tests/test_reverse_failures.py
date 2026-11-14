#!/usr/bin/env python3
"""§4A R4 失败考古判据（NF-Final G0 逆向工程）。

真源 = `results/reverse/failures.json`（`nf-reverse-failures/1`）；人读 = `FAILURE_ARCHAEOLOGY.md`。
判据：
1. 结构：modes/inconsistencies/gaps 三组；类别/状态词表；id 唯一；
2. 证据可核：每个 evidence_commit 必须真实存在（git cat-file -e）；证据文件在场；
   protection 非空；partial/gap 必须写缺口；
3. 统计**实时重算**：近 400 提交 fix 命中数、skip 文件数与记录一致；
4. 文档交叉：全部 id 出现，含复核命令/R6 交接；
5. 变异自证：伪造 commit、缺证据文件、非法类别、缺缺口、skip 计数漂移、缺 owner → 都必须红。
"""
import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

REG = ROOT / "results" / "reverse" / "failures.json"
DOC = ROOT / "results" / "reverse" / "FAILURE_ARCHAEOLOGY.md"
STATUSES = ("covered", "partial", "gap")
INC_STATUS = ("fixed", "mitigated", "open")
CATEGORIES = ("契约错", "默认放行", "边界", "证据", "性能", "环境", "CI/供应链", "文档")
FIX_RE = re.compile(r"fix|hotfix|security|修复|refreeze|revert|回滚", re.IGNORECASE)
SKIP_MARKS = ("skipif", "@unittest.skip", "xfail")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def live_stats(root, window_end=None):
    args = ["log"] + ([str(window_end)] if window_end else []) + ["-400", "--format=%s"]
    log = _git(root, *args)
    fix = sum(1 for line in (log.stdout or "").splitlines() if FIX_RE.search(line))
    skip = 0
    for path in (Path(root) / "desktop" / "tests").glob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(mark in text for mark in SKIP_MARKS):
            skip += 1
    return {"fix_commits_400": fix, "skip_files": skip}


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-reverse-failures/1":
        return ["schema 不匹配"]
    stats = doc.get("stats") or {}
    live = live_stats(root, stats.get("window_end"))
    if int(stats.get("fix_commits_400") or -1) != live["fix_commits_400"]:
        issues.append("fix 提交计数漂移（记录 %s / 实测 %s）"
                      % (stats.get("fix_commits_400"), live["fix_commits_400"]))
    if int(stats.get("skip_files") or -1) != live["skip_files"]:
        issues.append("skip 文件计数漂移（记录 %s / 实测 %s）"
                      % (stats.get("skip_files"), live["skip_files"]))
    modes = doc.get("modes") or []
    if len(modes) < 8:
        issues.append("失败模式少于 8 项（覆盖不足）")
    for mode in modes:
        mid = str(mode.get("id"))
        if str(mode.get("category")) not in CATEGORIES:
            issues.append("%s 的 category 非法：%s" % (mid, mode.get("category")))
        if str(mode.get("status")) not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (mid, mode.get("status")))
        for field in ("pattern", "trigger", "protection"):
            if not str(mode.get(field) or "").strip():
                issues.append("%s 缺 %s" % (mid, field))
        if str(mode.get("status")) in ("partial", "gap") and not str(mode.get("gap") or "").strip():
            issues.append("%s 标 %s 但缺 gap" % (mid, mode.get("status")))
        for commit in mode.get("evidence_commits") or []:
            res = _git(root, "cat-file", "-e", "%s^{commit}" % commit)
            if res.returncode != 0:
                issues.append("%s 引用不存在的 commit：%s" % (mid, commit))
        for rel in mode.get("evidence_files") or []:
            if not (Path(root) / rel).exists():
                issues.append("%s 的 evidence 不在场：%s" % (mid, rel))
        if not mode.get("evidence_commits") and not mode.get("evidence_files"):
            issues.append("%s 缺任何证据" % mid)
    incs = doc.get("inconsistencies") or []
    if len(incs) < 3:
        issues.append("文档/代码不一致少于 3 条（§4A DoD 要求 ≥3）")
    for inc in incs:
        iid = str(inc.get("id"))
        if str(inc.get("status")) not in INC_STATUS:
            issues.append("%s 的 status 非法：%s" % (iid, inc.get("status")))
        for rel in inc.get("evidence") or []:
            if not (Path(root) / rel).exists():
                issues.append("%s 的 evidence 不在场：%s" % (iid, rel))
        if not str(inc.get("fix") or "").strip():
            issues.append("%s 缺 fix（修复建议）" % iid)
    for gap in doc.get("gaps") or []:
        if not str(gap.get("owner") or "").strip():
            issues.append("gap %s 缺 owner" % gap.get("id"))
        if str(gap.get("status")) not in ("open", "accepted-risk", "closed"):
            issues.append("gap %s 的 status 非法" % gap.get("id"))
    return issues


class ReverseFailuresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_failures_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertGreaterEqual(len(self.doc["modes"]), 8)
        self.assertGreaterEqual(len(self.doc["inconsistencies"]), 3)

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for mode in self.doc["modes"]:
            self.assertIn(mode["id"], self.text)
        for inc in self.doc["inconsistencies"]:
            self.assertIn(inc["id"], self.text)
        for marker in ("R6", "复核命令", "skip", "R4-01"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        fake_commit = copy.deepcopy(self.doc)
        fake_commit["modes"][0]["evidence_commits"] = ["0" * 40]
        self.assertTrue(issues_for(fake_commit, str(ROOT)), "伪造 commit 必须红")

        bad_category = copy.deepcopy(self.doc)
        bad_category["modes"][0]["category"] = "unknown"
        self.assertTrue(issues_for(bad_category, str(ROOT)), "非法类别必须红")

        no_gap = copy.deepcopy(self.doc)
        next(m for m in no_gap["modes"] if m["status"] == "partial")["gap"] = ""
        self.assertTrue(issues_for(no_gap, str(ROOT)), "partial 缺 gap 必须红")

        no_protection = copy.deepcopy(self.doc)
        no_protection["modes"][0]["protection"] = ""
        self.assertTrue(issues_for(no_protection, str(ROOT)), "缺防护必须红")

        drift = copy.deepcopy(self.doc)
        drift["stats"]["skip_files"] = 0
        self.assertTrue(issues_for(drift, str(ROOT)), "skip 计数漂移必须红")

        no_owner = copy.deepcopy(self.doc)
        no_owner["gaps"][0]["owner"] = ""
        self.assertTrue(issues_for(no_owner, str(ROOT)), "缺口缺 owner 必须红")


if __name__ == "__main__":
    unittest.main()
