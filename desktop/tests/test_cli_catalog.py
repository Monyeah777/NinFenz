# -*- coding: utf-8 -*-
"""T11.3 CLI IA 机读层回归：目录确定性 / 幂等 / 覆盖率负例 / 与 check39 同结论。

判据分层
--------
1. **canonical 数据**：同输入逐字节同输出（digest 稳定），命令/族/用途/flags/has_json 齐全；
2. **落盘幂等**：`--write` 两次字节一致；`--check` 对实时重算逐字节对账（临时目录，不碰真源）；
3. **覆盖率负例**：未归族 / 重复归族 / 空族 / 族内虚指 都必须报；与 terminal.self_check 同结论；
4. **文档同源**：docs/cli-map.md 由同一数据渲染，确定性且覆盖全部命令；
5. **CLI 面**：`nf cli map [--write|--check] [--json]` 形状与退出码。

跑法：`cd desktop && python -m unittest tests.test_cli_catalog -v`
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import cli_catalog as cc  # noqa: E402
from core import terminal  # noqa: E402

NF = ROOT / "scripts" / "nf.py"


def _load_nf():
    spec = importlib.util.spec_from_file_location("nf_cli_map_test", NF)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_NF = _load_nf()
_PARSER = _NF._build_parser()


def _families() -> list:
    return copy.deepcopy([dict(f) for f in terminal.FAMILIES])


class MapDataTest(unittest.TestCase):
    """1 canonical 数据形状与确定性。"""

    def test_deterministic_across_two_builds(self):
        a = cc.build(_PARSER)
        b = cc.build(_PARSER)
        self.assertEqual(json.dumps(a, ensure_ascii=False, sort_keys=True),
                         json.dumps(b, ensure_ascii=False, sort_keys=True))
        self.assertEqual(a["digest"], b["digest"])
        self.assertTrue(a["digest"].startswith("sha256:"))

    def test_digest_covers_map_body(self):
        import hashlib

        doc = cc.build(_PARSER)
        body = {k: v for k, v in doc.items() if k != "digest"}
        want = "sha256:" + hashlib.sha256(
            json.dumps(body, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(want, doc["digest"])

    def test_commands_are_complete_and_owned(self):
        doc = cc.build(_PARSER)
        cov = doc["coverage"]
        self.assertEqual(cov["commands"], len(doc["commands"]))
        self.assertEqual(cov["commands"], cov["covered"])
        self.assertEqual([], cov["uncurated"])
        self.assertEqual({}, cov["duplicates"])
        self.assertEqual([], cov["empty_families"])
        names = [c["name"] for c in doc["commands"]]
        self.assertEqual(sorted(names), names)
        for row in doc["commands"]:
            self.assertTrue(row["group"], row)
            self.assertTrue(row["one_line"], row)
            self.assertTrue(row["usage"].startswith("usage: nf "), row)
            self.assertIn("--help", row["flags"])
            self.assertEqual("--json" in row["flags"], row["has_json"])

    def test_related_docs_are_real_and_mention_command(self):
        doc = cc.build(_PARSER)
        for row in doc["commands"]:
            for rel in row["related_docs"]:
                path = ROOT / rel
                self.assertTrue(path.is_file(), rel)
                self.assertIn("nf %s" % row["name"],
                              path.read_text(encoding="utf-8"))

    def test_families_are_consumed_not_rederived(self):
        doc = cc.build(_PARSER)
        want = {f["id"]: sorted(str(c) for c in f["commands"])
                for f in terminal.FAMILIES}
        got = {f["id"]: f["commands"] for f in doc["families"]}
        self.assertEqual(want, got)


class WriteCheckTest(unittest.TestCase):
    """2 落盘幂等 + 对账漂移（临时目录）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_cli_map_")
        self.root = Path(self._tmp.name)
        (self.root / "protocol").mkdir()
        (self.root / "docs").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_is_idempotent(self):
        cc.write(self.root, _PARSER)
        first = ((self.root / cc.MAP_REL).read_bytes(),
                 (self.root / cc.DOC_REL).read_bytes())
        cc.write(self.root, _PARSER)
        second = ((self.root / cc.MAP_REL).read_bytes(),
                  (self.root / cc.DOC_REL).read_bytes())
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first[0].decode("utf-8"))["kind"], "cli-map")

    def test_check_passes_after_write(self):
        cc.write(self.root, _PARSER)
        issues, diffs, doc = cc.check(self.root, _PARSER)
        self.assertEqual([], issues)
        self.assertEqual({}, diffs)
        self.assertTrue(doc["coverage"]["commands"] > 0)

    def test_check_detects_missing_artifact(self):
        issues, diffs, _ = cc.check(self.root, _PARSER)
        self.assertTrue(any("缺生成件" in i for i in issues), issues)
        self.assertEqual("missing", diffs.get("json"))

    def test_check_detects_stale_doc(self):
        cc.write(self.root, _PARSER)
        p = self.root / cc.DOC_REL
        p.write_text(p.read_text(encoding="utf-8") + "\n手改一行\n", encoding="utf-8")
        issues, diffs, _ = cc.check(self.root, _PARSER)
        self.assertTrue(any("人读件与实时重算不一致" in i for i in issues), issues)
        self.assertEqual("stale", diffs.get("md"))


class CoverageNegativeTest(unittest.TestCase):
    """3 覆盖率负例（合成 fixture，不改真源）。"""

    def _broken(self, mutate) -> list:
        fams = _families()
        mutate(fams)
        return cc.coverage_issues(cc.build(_PARSER, fams))

    def test_uncurated_command_is_reported(self):
        def mutate(fams):
            fams[1]["commands"] = tuple(c for c in fams[1]["commands"] if c != "agent")
        issues = self._broken(mutate)
        self.assertTrue(any("未归族命令：agent" in i for i in issues), issues)

    def test_duplicate_family_is_reported(self):
        def mutate(fams):
            fams[0]["commands"] = fams[0]["commands"] + ("agent",)
        issues = self._broken(mutate)
        self.assertTrue(any("命令重复归族：agent" in i for i in issues), issues)

    def test_empty_family_is_reported(self):
        def mutate(fams):
            fams.append({"id": "void", "name": "空族", "summary": "空",
                         "commands": ()})
        issues = self._broken(mutate)
        self.assertTrue(any("空能力族：void" in i for i in issues), issues)

    def test_stray_family_command_is_reported(self):
        def mutate(fams):
            fams[0]["commands"] = fams[0]["commands"] + ("no-such-command",)
        issues = self._broken(mutate)
        self.assertTrue(any("族内虚指命令：no-such-command" in i for i in issues), issues)

    def test_missing_family_metadata_is_reported(self):
        def mutate(fams):
            fams[0]["summary"] = ""
        issues = self._broken(mutate)
        self.assertTrue(any("缺 summary" in i for i in issues), issues)


class Check39ParityTest(unittest.TestCase):
    """4 与 check39（terminal.self_check）同结论。"""

    def test_catalog_and_self_check_agree(self):
        tree = _NF._collect_cli_tree()
        index = _NF._shell_command_index()
        self_issues, _stats = terminal.self_check(index, set(tree["commands"]),
                                                 set(tree["root_flags"]))
        self.assertEqual([], self_issues, self_issues)
        doc = cc.build(_PARSER)
        self.assertEqual([], cc.coverage_issues(doc))
        self.assertEqual(set(tree["commands"]),
                         {row["name"] for row in doc["commands"]})


class RenderTest(unittest.TestCase):
    """5 文档渲染确定性。"""

    def test_render_is_deterministic(self):
        doc = cc.build(_PARSER)
        a = cc.render_md(doc)
        b = cc.render_md(doc)
        self.assertEqual(a, b)
        for row in doc["commands"]:
            self.assertIn("`nf %s`" % row["name"], a)
        for fam in doc["families"]:
            self.assertIn(fam["name"], a)

    def test_render_has_no_timestamp(self):
        text = cc.render_md(cc.build(_PARSER))
        self.assertNotRegex(text, r"20\d\d-\d\d-\d\d")


class CliTest(unittest.TestCase):
    """6 CLI 面。"""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(NF), *args], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=180)

    def test_map_json_face(self):
        proc = self._run("cli", "map", "--json")
        self.assertEqual(0, proc.returncode, proc.stderr[-400:])
        doc = json.loads(proc.stdout)
        self.assertEqual("cli-map", doc["kind"])
        self.assertEqual("nf-cli-map/1", doc["schema"])
        self.assertIn("coverage", doc)

    def test_check_json_face(self):
        proc = self._run("cli", "map", "--check", "--json")
        self.assertEqual(0, proc.returncode, proc.stderr[-400:])
        doc = json.loads(proc.stdout)
        self.assertEqual("cli-map-check", doc["kind"])
        self.assertTrue(doc["ok"])
        self.assertEqual([], doc["issues"])

    def test_check_human_face(self):
        proc = self._run("cli", "map", "--check")
        self.assertEqual(0, proc.returncode, proc.stderr[-400:])
        self.assertIn("PASS", proc.stdout)

    def test_bad_subcommand_is_rejected(self):
        proc = self._run("cli", "nope")
        self.assertEqual(2, proc.returncode)

    def test_write_and_check_roundtrip_on_repo_copy(self):
        """在临时目录里跑 --write 等价路径（不碰真源）。"""
        with tempfile.TemporaryDirectory(prefix="nf_cli_map_cli_") as tmp:
            root = Path(tmp)
            (root / "protocol").mkdir()
            (root / "docs").mkdir()
            cc.write(root, _PARSER)
            issues, _, _ = cc.check(root, _PARSER)
            self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
