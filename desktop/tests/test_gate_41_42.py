#!/usr/bin/env python3
"""check41 / check42 的判据单测（含**变异夹具**：每条判据都必须能红）。

对应步骤4 的两个 P0 能力空洞：
- 构建隔离（SLSA L3 Build isolation）→ core.build_isolation；
- 不可伪造 provenance（SLSA L3 Non-falsifiable provenance）→ core.provenance_external。

纪律：只测判据本身（合成根 + 注入验签器），不在测试里跑真门禁；
真实仓库的绿灯由 verify.sh 的 check41/42 守着。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import build_isolation as bi  # noqa: E402
from core import provenance_external as pe  # noqa: E402

PINNED = "python:3.11-slim@sha256:" + "a" * 64


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _build_root(tmp, entry="const x = 1;\n", docker="FROM %s\n" % PINNED,
                engines='"node": ">=18.17"'):
    _write(tmp, "packaging/npm/tools/build.mjs", entry)
    _write(tmp, "packaging/npm/package.json",
           '{"name": "x", "engines": {%s}}' % engines)
    _write(tmp, "engine/rust/Cargo.lock", "")
    _write(tmp, "Dockerfile.crosscheck", docker)
    return tmp


def _receipts_root(tmp):
    _write(tmp, "protocol/RECEIPTS.json",
           json.dumps({"schema": pe.RECEIPTS_SCHEMA, "scope": "protocol", "count": 2,
                       "entries": [{"path": "a", "sha256": "a" * 64},
                                   {"path": "b", "sha256": "b" * 64}],
                       "root": "c" * 64}, ensure_ascii=False))
    return tmp


class BuildIsolationTest(unittest.TestCase):
    def test_real_repo_is_isolated(self):
        issues, stats = bi.scan(str(ROOT))
        self.assertEqual(issues, [])
        self.assertGreaterEqual(stats["base_images"], 1, "容器基座未被扫到（判据空转）")

    def test_network_token_in_build_entry_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_root(tmp, entry="await fetch('https://example.com/x');\n")
            issues, _ = bi.scan(tmp)
            self.assertTrue(any("取网/取包" in i for i in issues), issues)

    def test_unpinned_base_image_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_root(tmp, docker="FROM python:3.11-slim\n")
            issues, _ = bi.scan(tmp)
            self.assertTrue(any("未按 digest 钉" in i for i in issues), issues)

    def test_latest_tag_is_red_even_with_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_root(tmp, docker="FROM python:latest@sha256:" + "b" * 64 + "\n")
            issues, _ = bi.scan(tmp)
            self.assertTrue(any("未按 digest 钉" in i for i in issues), issues)

    def test_missing_engines_and_lock_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_root(tmp, engines='"npm": ">=10"')
            (Path(tmp) / "engine" / "rust" / "Cargo.lock").unlink()
            issues, _ = bi.scan(tmp)
            self.assertTrue(any("engines.node" in i for i in issues), issues)
            self.assertTrue(any("Cargo.lock" in i for i in issues), issues)

    def test_ci_setup_without_version_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_root(tmp)
            _write(tmp, ".github/workflows/ci.yml",
                   "steps:\n  - uses: actions/setup-python@v5\n")
            issues, _ = bi.scan(tmp)
            self.assertTrue(any("setup-python 未给具体版本号" in i for i in issues), issues)


class ProvenanceExternalTest(unittest.TestCase):
    def test_real_repo_verifies_out_of_process_and_detects_tamper(self):
        issues, stats = pe.scan(str(ROOT))
        self.assertEqual(issues, [])
        self.assertTrue(stats["tamper_detected"])
        self.assertTrue(stats["verified"])

    def test_receipts_missing_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues, _ = pe.scan(tmp)
            self.assertTrue(any("RECEIPTS.json" in i for i in issues), issues)

    def test_blind_verifier_must_be_red(self):
        """变异夹具：验签器恒真 ⇒ 篡改检测失效，必须报红（否则这条对账是空转）。"""
        with tempfile.TemporaryDirectory() as tmp:
            _receipts_root(tmp)
            issues, _ = pe.scan(tmp, verifier=lambda _payload: True)
            self.assertTrue(any("篡改未被检出" in i for i in issues), issues)

    def test_rejecting_verifier_must_be_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            _receipts_root(tmp)
            issues, _ = pe.scan(tmp, verifier=lambda _payload: False)
            self.assertTrue(any("独立进程验签失败" in i for i in issues), issues)

    def test_verifier_receives_both_real_and_tampered_subject(self):
        seen = []

        def probe(payload):
            seen.append(payload["att"]["subject"]["sha256"])
            return payload["att"]["subject"]["sha256"] != "0" * 64

        with tempfile.TemporaryDirectory() as tmp:
            _receipts_root(tmp)
            issues, _ = pe.scan(tmp, verifier=probe)
        self.assertEqual(issues, [])
        self.assertEqual(len(seen), 2, "验签器应各收一次真件与篡改件")
        self.assertNotEqual(seen[0], seen[1], "篡改件没有真的被改过")


if __name__ == "__main__":
    unittest.main()
