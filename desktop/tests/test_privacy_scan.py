#!/usr/bin/env python3
"""T11.2 隐私与 air-gap 静态审计单测（`core/privacy_scan.py` + `nf privacy scan|check`）。

覆盖（对齐任务卡验收面）：
1. 干净件 0 findings（误报可控）；仓库内容面默认扫描 0 critical；
2. PII：邮箱（保留域 warn / 真实域 critical）、手机号、身份证（GB 11643 校验位）、银行卡
   （Luhn + 卡组织 BIN），掩码不回显完整值；
3. 本机路径：盘符 / `/Users/` / `/home/` / `%APPDATA%`；占位写法（`<user>`/转义双反斜杠）判 warn；
4. 凭据：**单源复用** content_security（monkeypatch 自证接线）+ 前缀粗筛派生自 ingest_common
   （drift guard）；
5. 网络面静态审计：网络 import 命中、`urllib.parse` 不误报、`subprocess curl|wget` 命中、
   数据字面量不误报、白名单生效、陈旧白名单即红；
6. 白名单测试样本：默认跳过并登记；显式传参仍报出但不计退出码；
7. 退出码 0/1/2、JSON 形状（`kind` 判别键 + 相对路径 + 掩码）、确定性；
8. 口径对齐：本模块的本机路径判定与 `test_leak_surface.MACHINE_PATH` 同源（不另立更宽口径）。

运行：cd desktop && python -m unittest tests.test_privacy_scan -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "desktop" / "tests"))

from core import privacy_scan as ps  # noqa: E402

FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "privacy"
CLEAN = FIXTURES / "clean.md"
ALLOWED = FIXTURES / "sample_allowlisted.md"

#: 合成 PII / 本机路径一律**拼接构造**（仓库内不留真实形态串：撞 test_leak_surface 与本门禁
#: 自身，且公开仓不放真实 PII）。
WIN_PATH = "C:" + "\\" + "Users" + "\\" + "alice" + "\\repo"
POSIX_HOME = "/" + "Users" + "/alice/repo"
LINUX_HOME = "/" + "home" + "/bob/.config"
WIN_PLACEHOLDER = "C:" + "\\" + "Users" + "\\" + "<user>" + "\\repo"
FAKE_PHONE = "1380013" + "8000"
FAKE_CARD = "4111" + "1111" + "1111" + "1111"
FAKE_GH = "ghp_" + "A" * 36
FAKE_SK = "sk-" + "b" * 30
PRIVATE_KEY_HEAD = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
_ID_W = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHK = "10X98765432"


def make_id(base17: str = "11010519491231002") -> str:
    """按 GB 11643 生成一个**校验位正确**的合成身份证号（拼接构造，仓库不留字面量）。"""
    return base17 + _ID_CHK[sum(int(a) * b for a, b in zip(base17, _ID_W)) % 11]


def _write(tmp: str, rel: str, text: str) -> str:
    path = os.path.join(tmp, rel)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def _tree(tmp: str, **files: str) -> None:
    for rel, text in files.items():
        _write(tmp, rel.replace("__", "/"), text)


def _kinds(findings) -> set:
    return {f["kind"] for f in findings}


def _defaults_clean(tmp: str, **extra: str) -> None:
    """建齐默认扫描的 5 个根（否则缺目录 → 不可判定 exit 2）。"""
    for base in ps.DEFAULT_PATHS:
        _write(tmp, base + "/ok.md", "# 干净\n")
    for rel, text in extra.items():
        _write(tmp, rel, text)


class CleanTest(unittest.TestCase):
    def test_clean_fixture_has_no_findings(self):
        self.assertEqual([], ps.scan_text(CLEAN.read_text(encoding="utf-8"),
                                          "desktop/tests/fixtures/privacy/clean.md"))

    def test_clean_tree_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp)
            report = ps.scan(root=tmp)
        self.assertEqual(0, report["exit"], report["findings"])
        self.assertTrue(report["ok"])
        self.assertEqual(0, report["summary"]["findings"])

    def test_repo_default_scan_has_no_critical(self):
        """仓库内容面本身：0 critical（warn 允许：保留域邮箱 / 文档占位路径）。"""
        report = ps.scan(root=str(ROOT))
        self.assertEqual(0, report["summary"]["critical"],
                         [f["file"] + ":" + str(f["line"]) for f in report["findings"]
                          if f["severity"] == "critical"][:10])
        self.assertEqual(0, report["exit"])


class PiiTest(unittest.TestCase):
    def test_real_email_is_critical_and_masked(self):
        findings = ps.scan_text("联系 alice@corp-real.com 处理。\n", "x.md")
        hit = next(f for f in findings if f["kind"] == "pii_email")
        self.assertEqual("critical", hit["severity"])
        self.assertNotIn("alice@corp-real.com", hit["masked_evidence"])
        self.assertIn("***@corp-real.com", hit["masked_evidence"])

    def test_reserved_domain_email_is_warn(self):
        findings = ps.scan_text("dpo@example.org\n", "x.md")
        hit = next(f for f in findings if f["kind"] == "pii_email")
        self.assertEqual("warn", hit["severity"])

    def test_phone_is_critical(self):
        findings = ps.scan_text("手机 %s 请勿外传\n" % FAKE_PHONE, "x.md")
        hit = next(f for f in findings if f["kind"] == "pii_phone")
        self.assertEqual("critical", hit["severity"])
        self.assertNotIn(FAKE_PHONE, hit["masked_evidence"])

    def test_valid_id_card_is_critical(self):
        fake_id = make_id()
        findings = ps.scan_text("证件号 %s\n" % fake_id, "x.md")
        hit = next(f for f in findings if f["kind"] == "pii_id")
        self.assertEqual("critical", hit["severity"])
        self.assertNotIn(fake_id, hit["masked_evidence"])

    def test_id_with_bad_checksum_is_ignored(self):
        bad = "110105194912310021"                   # 校验位不对 → 不是身份证号
        self.assertEqual([], ps.scan_text("号码 %s\n" % bad, "x.md"))

    def test_bank_card_is_critical(self):
        findings = ps.scan_text("卡号 %s\n" % FAKE_CARD, "x.md")
        hit = next(f for f in findings if f["kind"] == "pii_bank_card")
        self.assertEqual("critical", hit["severity"])

    def test_long_number_outside_card_bin_is_not_reported(self):
        """18 位图表数值（BIN 不符 + 不是身份证）不得误报为卡号/身份证。"""
        self.assertEqual([], ps.scan_text("值 003774423166091951\n", "x.md"))

    def test_luhn_and_id_helpers(self):
        self.assertTrue(ps.luhn_ok(FAKE_CARD))
        self.assertFalse(ps.luhn_ok("4111111111111112"))
        self.assertTrue(ps.id_card_ok(make_id()))
        self.assertFalse(ps.id_card_ok("110105194912310021"))
        self.assertFalse(ps.id_card_ok("1101051949123100"))       # 位数不足

    def test_pii_exit_code_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp, **{"docs/leak.md": "电话 %s\n" % FAKE_PHONE})
            report = ps.scan(root=tmp)
        self.assertEqual(1, report["exit"])
        self.assertFalse(report["ok"])


class PathTest(unittest.TestCase):
    def test_windows_user_path_is_critical(self):
        findings = ps.scan_text("检出在 " + WIN_PATH + "\n", "x.md")
        hit = next(f for f in findings if f["kind"] == "local_path")
        self.assertEqual("critical", hit["severity"])
        self.assertNotIn("alice", hit["masked_evidence"])

    def test_posix_paths_are_critical(self):
        for value in (POSIX_HOME, LINUX_HOME):
            findings = ps.scan_text("路径 " + value + "\n", "x.md")
            self.assertTrue([f for f in findings if f["kind"] == "local_path"], value)

    def test_win_env_var_is_detected(self):
        findings = ps.scan_text("配置在 %APPDATA%\\nf 下\n", "x.md")
        self.assertIn("win_env_var", {f["rule"] for f in findings})

    def test_placeholder_path_is_warn_only(self):
        findings = ps.scan_text("文档示例 " + WIN_PLACEHOLDER + "\n", "x.md")
        hit = next(f for f in findings if f["kind"] == "local_path")
        self.assertEqual("warn", hit["severity"])

    def test_regex_pattern_is_not_a_path(self):
        pattern = "(?<![A-Za-z0-9])[A-Za-z]:" + "\\\\" + "/]|/" + "Users/|/home/[a-z]"
        self.assertEqual([], ps.scan_text('"pattern": "%s"\n' % pattern, "x.json"))

    def test_plain_text_without_separators_fast_paths(self):
        self.assertEqual([], ps.scan_text("普通一行没有路径\n", "x.md"))


class CredentialTest(unittest.TestCase):
    def test_secret_shapes_are_reused_from_content_security(self):
        for sample, label in ((FAKE_GH, "ghp"), (FAKE_SK, "sk"), (PRIVATE_KEY_HEAD, "pem")):
            findings = ps.scan_text(sample + "\n", "x.md")
            hits = [f for f in findings if f["kind"] == "credential"]
            self.assertTrue(hits, label)
            self.assertTrue(all(f["severity"] == "critical" for f in hits))
            self.assertNotIn(sample, json.dumps(findings, ensure_ascii=False))

    def test_secret_detection_delegates_to_content_security(self):
        from core import content_security as cs
        real = cs.scan_text

        def fake(text, file="<text>", allowlisted=False):
            return [{"kind": "secret_material", "line": 2, "rule": "secret_shape",
                     "masked_evidence": "zzzz…", "column": 0}]

        cs.scan_text = fake
        try:
            findings = ps.scan_text("任意 ghp_ x\n", "x.md")
        finally:
            cs.scan_text = real
        hit = next(f for f in findings if f["kind"] == "credential")
        self.assertEqual(2, hit["line"])
        self.assertEqual("zzzz…", hit["masked_evidence"])

    def test_prefix_prefilter_is_derived_from_ingest_common(self):
        """drift guard：粗筛正则由 `ingest_common._SECRET_SHAPES` 派生（不是第二套形状）。"""
        from core import ingest_common as ic
        self.assertIsNotNone(ps._SECRET_PREFIX_RE, "派生失败（退化为全扫不算错，但此处应有前缀）")
        alternatives = str(ic._SECRET_SHAPES.pattern).split("|")
        self.assertGreaterEqual(len(alternatives), 7, "秘密形状疑似塌缩")
        prefixes = []
        for alt in alternatives:
            buf = ""
            for ch in alt:
                if ch.isalnum() or ch in "_-":
                    buf += ch
                else:
                    break
            prefixes.append(buf)
        self.assertTrue(all(prefixes), "有形状无字面前缀 ⇒ 派生会退化为全扫（sound fallback）")
        for prefix in prefixes:                      # 派生正则必须覆盖真源的字面前缀
            self.assertTrue(ps._SECRET_PREFIX_RE.search(prefix), prefix)
        for sample in (FAKE_GH, FAKE_SK, "AKIA" + "A" * 16, "xoxb-" + "1" * 12,
                       "glpat-" + "a" * 24, "AIza" + "a" * 35,
                       "github_pat_" + "a" * 26):
            self.assertTrue(ps._SECRET_PREFIX_RE.search(sample), sample)

    def test_prefilter_fallback_scans_everything(self):
        real = ps._SECRET_PREFIX_RE
        ps._SECRET_PREFIX_RE = None                  # 派生失败 → 全扫（sound fallback）
        try:
            findings = ps.scan_text(FAKE_GH + "\n", "x.md")
        finally:
            ps._SECRET_PREFIX_RE = real
        self.assertIn("credential", _kinds(findings))


class NetworkAuditTest(unittest.TestCase):
    def _audit(self, tmp: str, files: dict, allowlist=None):
        import unittest.mock as mock
        # 审计面 = 两目录；用例没给的那一边补一个空件，免「审计目录不存在」判不可判定。
        files = dict(files)
        files.setdefault("desktop/src/core/_keep.py", "x = 1\n")
        files.setdefault("scripts/_keep.py", "y = 2\n")
        patch = mock.patch.dict(ps.NETWORK_ALLOWLIST, allowlist or {}, clear=True)
        with patch:
            for rel, text in files.items():
                _write(tmp, rel, text)
            return ps.audit_network(root=tmp)

    def test_network_import_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._audit(tmp, {
                "desktop/src/core/net.py": "import socket\nimport urllib.request\n",
                "scripts/fetch.py": "from http.client import HTTPSConnection\n",
            })
        kinds = {f["kind"] for f in report["findings"]}
        self.assertIn("network_site", kinds)
        self.assertEqual(1, report["exit"])
        self.assertGreaterEqual(report["summary"]["critical"], 3)

    def test_urllib_parse_is_not_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._audit(tmp, {
                "desktop/src/core/parse_only.py": "from urllib.parse import urlparse\n",
            })
        self.assertEqual([], report["findings"])
        self.assertEqual(0, report["exit"])

    def test_shell_fetch_call_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._audit(tmp, {
                "scripts/dl.py": "import subprocess\n"
                                 "subprocess.run(['curl', 'https://x'])\n",
            })
        self.assertTrue(any(f["rule"] == "shell_fetch" for f in report["findings"]))

    def test_data_literal_is_not_a_call(self):
        """`build_isolation.NETWORK_TOKENS` 里的 "curl " 是**数据**，不是调用——不得误报。"""
        with tempfile.TemporaryDirectory() as tmp:
            report = self._audit(tmp, {
                "desktop/src/core/tokens.py": 'TOKENS = ("curl ", "wget ")\n',
            })
        self.assertEqual([], report["findings"])

    def test_allowlisted_site_is_listed_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._audit(tmp, {"desktop/src/core/ipc.py": "import socket\n"},
                                 allowlist={"desktop/src/core/ipc.py": "本机回环 IPC"})
        site = next(f for f in report["findings"] if f["kind"] == "network_site")
        self.assertTrue(site["allowlisted"])
        self.assertEqual("本机回环 IPC", site["reason"])
        self.assertEqual(0, report["exit"])
        self.assertEqual(0, report["summary"]["critical"])

    def test_stale_whitelist_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._audit(tmp, {"desktop/src/core/clean.py": "x = 1\n"},
                                 allowlist={"desktop/src/core/gone.py": "已移除"})
        stale = [f for f in report["findings"] if f["kind"] == "stale_whitelist"]
        self.assertTrue(stale)
        self.assertEqual(1, report["exit"])

    def test_missing_audit_dir_is_undecidable(self):
        import unittest.mock as mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(ps.NETWORK_ALLOWLIST, {}, clear=True):
                report = ps.audit_network(root=tmp)
        self.assertEqual(2, report["exit"])
        self.assertEqual(2, report["summary"]["undecidable"])

    def test_repo_audit_is_clean(self):
        """仓库真实面：所有网络站点都已登记理由（含 10 条白名单条目，0 critical）。"""
        report = ps.audit_network(root=str(ROOT))
        self.assertEqual(0, report["summary"]["critical"], report["findings"][:5])
        self.assertEqual(0, report["exit"])
        self.assertEqual(0, report["summary"]["stale"])
        self.assertGreaterEqual(len(report["allowlist"]), 9)
        self.assertGreaterEqual(len(report["files_with_network"]), 9)


class ExitAndShapeTest(unittest.TestCase):
    def test_missing_path_is_undecidable(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = ps.scan(["no/such/dir"], root=tmp)
        self.assertEqual(2, report["exit"])
        self.assertEqual(1, report["summary"]["undecidable"])
        self.assertTrue(report["errors"])

    def test_binary_and_oversize_are_undecidable(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "docs/ok.md", "# 干净\n")
            with open(os.path.join(tmp, "docs", "bin.md"), "wb") as fh:
                fh.write(b"\x00\x01binary")
            report = ps.scan(["docs"], root=tmp)
        self.assertEqual(2, report["exit"])
        self.assertTrue(any("二进制" in e["reason"] for e in report["errors"]))

    def test_scan_report_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp, **{"docs/leak.md": "电话 %s\n" % FAKE_PHONE})
            report = ps.scan(root=tmp)
        for key in ("kind", "schema", "root", "paths", "allowlist", "skipped",
                    "scanned", "findings", "errors", "summary", "exit", "ok"):
            self.assertIn(key, report)
        self.assertEqual("privacy-scan", report["kind"])
        for f in report["findings"]:
            for key in ("file", "line", "kind", "severity", "rule",
                        "masked_evidence", "fix", "allowlisted"):
                self.assertIn(key, f)
            self.assertIn(f["kind"], ps.FINDING_KINDS)
            self.assertIn(f["severity"], ("critical", "warn"))

    def test_check_report_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "desktop/src/core/x.py", "x = 1\n")
            _write(tmp, "scripts/y.py", "y = 2\n")
            report = ps.audit_network(root=tmp)
        self.assertEqual("privacy-check", report["kind"])
        for key in ("kind", "schema", "root", "dirs", "files_with_network",
                    "allowlist", "excluded", "findings", "errors", "summary",
                    "exit", "ok"):
            self.assertIn(key, report)

    def test_reports_are_portable_and_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp, **{"docs/leak.md": "电话 %s\n" % FAKE_PHONE})
            first = ps.scan(root=tmp)
            second = ps.scan(root=tmp)
        dumped = json.dumps(first, ensure_ascii=False)
        self.assertNotIn(str(ROOT), dumped)
        self.assertEqual(json.dumps(first, sort_keys=True),
                         json.dumps(second, sort_keys=True))


class AllowlistTest(unittest.TestCase):
    def test_allowlisted_sample_is_skipped_and_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp)
            _write(tmp, "desktop/tests/fixtures/privacy/sample.md",
                   "联系人 alice@corp-real.com\n")
            report = ps.scan(root=tmp)
        self.assertEqual([], report["findings"], "白名单样本不应进入默认 findings")
        self.assertIn("desktop/tests/fixtures/privacy/sample.md",
                      [s["file"] for s in report["skipped"]])
        self.assertEqual(0, report["exit"])

    def test_explicit_scan_reports_allowlisted_without_affecting_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "desktop/tests/fixtures/privacy/sample.md",
                   "联系人 alice@corp-real.com\n")
            report = ps.scan(["desktop/tests/fixtures/privacy"], root=tmp)
        self.assertTrue(report["findings"])
        self.assertTrue(all(f["allowlisted"] for f in report["findings"]))
        self.assertEqual(0, report["exit"])

    def test_repo_sample_is_allowlisted_and_scanned(self):
        rel = "desktop/tests/fixtures/privacy/sample_allowlisted.md"
        self.assertTrue(ps.is_allowlisted(rel))
        findings = ps.scan_text(ALLOWED.read_text(encoding="utf-8"), rel)
        self.assertTrue(findings)
        self.assertTrue(all(f["severity"] == "warn" for f in findings))

    def test_allowlist_cannot_hide_content_in_scanned_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp, **{"community/pack/leak.md": "电话 %s\n" % FAKE_PHONE})
            report = ps.scan(root=tmp)
        self.assertEqual(1, report["exit"])


class CliTest(unittest.TestCase):
    def _run(self, argv, cwd=None):
        import cli_harness
        return cli_harness.run_cli(argv, cwd=str(cwd or ROOT))

    def test_cli_scan_json_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp)
            rc, out, _err = self._run(["privacy", "scan", "--root", tmp, "--json"])
        self.assertEqual(0, rc, out)
        doc = json.loads(out)
        self.assertEqual("privacy-scan", doc["kind"])
        self.assertEqual(0, doc["exit"])

    def test_cli_scan_exit_one_on_pii(self):
        with tempfile.TemporaryDirectory() as tmp:
            _defaults_clean(tmp, **{"docs/leak.md": "电话 %s\n" % FAKE_PHONE})
            rc, out, _err = self._run(["privacy", "scan", "--root", tmp])
        self.assertEqual(1, rc, out)
        self.assertIn("CRITICAL", out)

    def test_cli_check_json_allowlisted_repo(self):
        rc, out, _err = self._run(["privacy", "check", "--json"])
        self.assertEqual(0, rc, out)
        doc = json.loads(out)
        self.assertEqual("privacy-check", doc["kind"])
        self.assertEqual(0, doc["exit"])

    def test_cli_check_exit_one_on_unregistered_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "desktop/src/core/net.py", "import socket\n")
            _write(tmp, "scripts/fetch.py", "x = 1\n")
            rc, out, _err = self._run(["privacy", "check", "--root", tmp])
        self.assertEqual(1, rc, out)
        self.assertIn("未登记网络站点", out)

    def test_cli_requires_subcommand(self):
        rc, _out, err = self._run(["privacy"])
        self.assertEqual(2, rc)
        self.assertIn("privacy", err)


class ParityTest(unittest.TestCase):
    """口径对齐：本模块的本机路径判定**不得比公开面门禁（test_leak_surface）更宽**。"""

    def test_machine_path_notion_is_a_subset_of_public_gate(self):
        import test_leak_surface as tls
        samples = (WIN_PATH, POSIX_HOME, LINUX_HOME, WIN_PLACEHOLDER,
                   "见 " + WIN_PATH + " 目录")
        for sample in samples:
            findings = ps.scan_text(sample + "\n", "x.md")
            ours = [f for f in findings if f["kind"] == "local_path"]
            if ours:
                self.assertTrue(tls.MACHINE_PATH.search(sample),
                                "本模块判定为机器路径、但公开面门禁不认：%r" % sample)
        # 反向：公开面门禁认的合成形态，本模块也要抓得到（同一个「本机路径」概念）
        for sample in (WIN_PATH, POSIX_HOME, LINUX_HOME):
            self.assertTrue([f for f in ps.scan_text(sample + "\n", "x.md")
                             if f["kind"] == "local_path"], sample)


if __name__ == "__main__":
    unittest.main()
