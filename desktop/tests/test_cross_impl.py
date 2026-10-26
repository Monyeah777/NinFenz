# -*- coding: utf-8 -*-
"""T8.1 跨实现差分回归（Python canonical ⇄ Node 零依赖第二实现）。

判据分五层
----------
1. **全等**：固定种子的 20 组 registry 子集 + 6 组 canonical 边缘用例，Python 与 Node 的
   digest / bytes_sha256 / bytes 逐组全等；
2. **防漂移金标**：edge-01 的 digest 钉常量——两实现**一起漂**（差分抓不到）也会被这里抓住；
3. **负例有咬合**：篡改 Node 输出（假 digest）或篡改输入字节（wrapper 改 subset）必须被判 red；
4. **确定性**：同种子同分组、同报告逐字节一致；Node 不可用 → 明确 skip（rc=0，不假装通过）；
5. **边界诚实**：报告写明第二实现只覆盖 canonical，W1-W3 仍单实现；JS 只用标准库、零依赖。

跑法：python -m pytest desktop/tests/test_cross_impl.py -q
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))

import cross_impl_check as cic  # noqa: E402
from core import contract_semantics as cs  # noqa: E402

NODE = shutil.which("node")
JS = ROOT / "engine" / "js" / "nf_canonical.js"
CHECK_SCRIPT = ROOT / "scripts" / "cross_impl_check.py"

#: 金标：edge-01（{"z":1,"a":{...},"m":"中文\\路径/混合"}）的规范形 digest。
#: 差分只能证明「两实现一致」；这一条证明「一致在旧语义上」——两实现同步漂移会被抓住。
GOLDEN_EDGE01_DIGEST = ("sha256:84d21195de64c865a99446609df7a8beaa53cfdad1713d6a66"
                        "029c2066f4f507")
GOLDEN_EDGE01_BYTES = 74


def _run_node(payload_bytes: bytes, script: Path = JS) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(script)], cwd=str(ROOT), input=payload_bytes,
                          capture_output=True, timeout=120)


def _wrapper(tmp: Path, name: str, body: str) -> str:
    path = tmp / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def _out_tamper_wrapper(tmp: Path) -> str:
    body = (
        '"use strict";\n'
        'const fs = require("fs");\n'
        "const real = require(%s);\n"
        'const input = JSON.parse(fs.readFileSync(0, "utf8"));\n'
        "const out = real.run(input);\n"
        'out.digest = "sha256:" + "0".repeat(64);\n'
        "process.stdout.write(JSON.stringify(out));\n"
    ) % json.dumps(str(JS))
    return _wrapper(tmp, "tamper_out.js", body)


def _in_tamper_wrapper(tmp: Path) -> str:
    body = (
        '"use strict";\n'
        'const fs = require("fs");\n'
        "const real = require(%s);\n"
        'const req = JSON.parse(fs.readFileSync(0, "utf8"));\n'
        "if (Array.isArray(req.subset)) req.subset = req.subset.concat(['__tamper__']);\n"
        "else req.subset = Object.assign({}, req.subset, {__tamper__: true});\n"
        "process.stdout.write(JSON.stringify(real.run(req)));\n"
    ) % json.dumps(str(JS))
    return _wrapper(tmp, "tamper_in.js", body)


class NodeImplTest(unittest.TestCase):
    """1 全等 + 2 金标 + 5 边界（Node 可用时）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = cic.run_checks()

    def setUp(self) -> None:
        if not NODE:
            self.skipTest("node 不可用（跨实现判据明确 skip）")

    def test_node_is_actually_present_for_this_run(self):
        self.assertEqual("ok", self.report["status"], self.report)

    def test_all_registry_groups_match(self):
        rows = [r for r in self.report["groups"] if r["kind"] == "registry"]
        self.assertGreaterEqual(len(rows), cic.MIN_GROUPS,
                                "registry 子集组数不足 20")
        bad = [(r["id"], r["python_digest"], r["node_digest"])
               for r in rows if not r["match"]]
        self.assertEqual([], bad, "registry 子集跨实现不一致：%s" % bad[:3])

    def test_all_edge_fixtures_match(self):
        rows = [r for r in self.report["groups"] if r["kind"] == "edge"]
        self.assertEqual(len(cic.EDGE_FIXTURES), len(rows))
        self.assertEqual([], [r["id"] for r in rows if not r["match"]])

    def test_golden_edge01_digest(self):
        """金标：两实现同时漂移时差分抓不到，这条常量会抓住。"""
        row = next(r for r in self.report["groups"] if r["id"] == "edge-01")
        self.assertEqual(GOLDEN_EDGE01_DIGEST, row["python_digest"])
        self.assertEqual(GOLDEN_EDGE01_DIGEST, row["node_digest"])
        self.assertEqual(GOLDEN_EDGE01_BYTES, row["bytes"])

    def test_python_side_is_contract_semantics_source(self):
        group = cic.generate_groups()[0]
        expected = cic.python_expected(group)
        payload = cs.canonical_payload({"root": str(ROOT)}, group["subset"])
        self.assertEqual("sha256:" + cs.canonical_digest(payload), expected["digest"])

    def test_boundary_is_stated_not_overclaimed(self):
        text = self.report["boundary"]
        self.assertIn("只覆盖 canonical", text)
        self.assertIn("载荷装配", text)
        self.assertIn("W1-W3", text)
        self.assertIn("单实现", text)


class DeterminismTest(unittest.TestCase):
    """4 确定性：同种子同分组、同报告逐字节一致。"""

    def test_seed_is_fixed_and_reproducible(self):
        self.assertEqual(20261026, cic.SEED)
        a = cic.generate_groups(seed=cic.SEED, count=cic.MIN_GROUPS)
        b = cic.generate_groups(seed=cic.SEED, count=cic.MIN_GROUPS)
        self.assertEqual(a, b)
        self.assertEqual([g["id"] for g in a],
                         ["registry-%02d" % i for i in range(cic.MIN_GROUPS)]
                         + ["registry-full"]
                         + ["edge-%02d" % i
                            for i in range(1, len(cic.EDGE_FIXTURES) + 1)])

    def test_report_is_byte_stable(self):
        a = cic.run_checks()
        b = cic.run_checks()
        self.assertEqual(json.dumps(a, ensure_ascii=False, sort_keys=True),
                         json.dumps(b, ensure_ascii=False, sort_keys=True))

    def test_python_expected_is_stable_for_edge_fixture(self):
        group = next(g for g in cic.generate_groups(seed=cic.SEED)
                     if g["id"] == "edge-01")
        self.assertEqual(cic.python_expected(group), cic.python_expected(group))


class NegativeTest(unittest.TestCase):
    """3 负例：篡改 Node 输出 / 输入字节必须被差分抓出（status=fail）。"""

    def setUp(self) -> None:
        if not NODE:
            self.skipTest("node 不可用（跨实现判据明确 skip）")

    def test_tampered_node_output_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = cic.run_checks(node_script=_out_tamper_wrapper(Path(tmp)))
        self.assertEqual("fail", report["status"], report["errors"][:2])
        self.assertTrue(report["mismatches"], "假 digest 未被差分抓出")
        self.assertLess(report["matched"], report["checked"])

    def test_tampered_input_bytes_are_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = cic.run_checks(node_script=_in_tamper_wrapper(Path(tmp)))
        self.assertEqual("fail", report["status"], report["errors"][:2])
        self.assertTrue(report["mismatches"], "输入被篡改却仍全等（判据无咬合）")

    def test_unusable_node_output_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = _wrapper(Path(tmp), "not_json.js",
                           "process.stdout.write('not-json');\n")
            report = cic.run_checks(node_script=bad)
        self.assertEqual("fail", report["status"])
        self.assertTrue(report["errors"])


class NodeSkipTest(unittest.TestCase):
    """4 Node 不可用时必须明确 skip，而不是通过。"""

    def test_skip_is_explicit(self):
        report = cic.run_checks(node_bin=None)
        self.assertEqual("skip", report["status"])
        self.assertIn("node 不可用", report["skip_reason"])
        self.assertEqual([], report["groups"])
        self.assertEqual(0, report["matched"])

    def test_cli_skip_is_rc0_with_marker(self):
        env = dict(os.environ, NF_NODE_BIN="none")   # 子进程里模拟「node 不可用」
        proc = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), "--json"], cwd=str(ROOT), env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(0, proc.returncode)
        doc = json.loads(proc.stdout)
        self.assertEqual("skip", doc["status"])
        self.assertIn("未假装通过", json.dumps(doc, ensure_ascii=False))


class JsContractTest(unittest.TestCase):
    """5 JS 实现自身的契约：零依赖 / 输入校验 / CLI 形状。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = JS.read_text(encoding="utf-8")

    def test_uses_only_node_stdlib(self):
        import re

        requires = set(re.findall(r'require\(\s*["\']([^"\']+)["\']', self.src))
        self.assertTrue(requires <= {"crypto", "fs", "path"},
                        "JS 引了非标准库依赖：%s" % sorted(requires - {"crypto", "fs", "path"}))
        self.assertNotIn("node_modules", self.src)
        self.assertNotIn("fetch(", self.src)

    def test_rejects_bad_schema(self):
        if not NODE:
            self.skipTest("node 不可用")
        proc = _run_node(b'{"schema":"bogus/9","subset":{}}')
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("schema", proc.stderr.decode("utf-8", "replace"))

    def test_rejects_non_object_subset(self):
        if not NODE:
            self.skipTest("node 不可用")
        proc = _run_node(b'{"schema":"nf-sem-canon/1","subset":"x"}')
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("subset", proc.stderr.decode("utf-8", "replace"))

    def test_accepts_both_modes_and_reports_three_fields(self):
        if not NODE:
            self.skipTest("node 不可用")
        for request in ({"schema": "nf-sem-canon/1", "subset": {"b": 1, "a": [2, 1]}},
                        {"schema": "nf-sem-canon/1", "subset": ["M00"]}):
            proc = _run_node(json.dumps(request, ensure_ascii=False).encode("utf-8"))
            self.assertEqual(0, proc.returncode, proc.stderr.decode("utf-8", "replace"))
            doc = json.loads(proc.stdout)
            self.assertEqual("nf-sem-canon/1", doc["schema"])
            self.assertTrue(str(doc["digest"]).startswith("sha256:"))
            self.assertEqual(64, len(str(doc["bytes_sha256"])))
            self.assertGreater(int(doc["bytes"]), 0)


class CliTest(unittest.TestCase):
    def test_json_report_face(self):
        if not NODE:
            self.skipTest("node 不可用")
        proc = subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), "--json"], cwd=str(ROOT),
            capture_output=True, text=True, encoding="utf-8", timeout=300)
        self.assertEqual(0, proc.returncode, proc.stderr[-500:])
        doc = json.loads(proc.stdout)
        self.assertEqual(cic.REPORT_SCHEMA, doc["schema"])
        self.assertEqual("ok", doc["status"])
        self.assertGreaterEqual(doc["checked"], cic.MIN_GROUPS + len(cic.EDGE_FIXTURES))
        self.assertEqual([], doc["mismatches"])


if __name__ == "__main__":
    unittest.main()
