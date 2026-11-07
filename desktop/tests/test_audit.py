"""审计/验收（audit）正式与否定用例。"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import audit as au  # noqa: E402


def _mk(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _scene(tmp, digest=None, verdict="pass", accepted_by="作者", accepted_at="2026-09-16"):
    _mk(tmp, "subject.md", "x")
    if digest is None:
        digest = hashlib.sha256(b"x").hexdigest()
    _mk(tmp, au.DECL_REL, (ROOT / au.DECL_REL).read_text(encoding="utf-8"))
    _mk(tmp, "results/audit/docs_audit-99-x.md", """---
id: AUD-0099
date: 2026-09-16
scope: s
verdict: %s
auditor: a
subjects:
  - subject.md:%s
accepted_by: %s
accepted_at: %s
---

## 结论
ok
""" % (verdict, digest, accepted_by, accepted_at))
    return tmp


def _minimal_decl(tmp, legacy=()):
    _mk(tmp, au.DECL_REL, json.dumps({
        "schema": au.SCHEMA,
        "required_fields": ["id", "date", "scope", "verdict", "auditor", "subjects"],
        "verdict_vocabulary": ["pass", "fail", "warn"],
        "legacy_records": {"paths": [
            {"path": rel, "reason": "测试用历史记录"} for rel in legacy
        ]},
        "rules": ["测试规则"],
    }, ensure_ascii=False))


class TestRealRepo(unittest.TestCase):
    def test_scan_clean_with_legacy_warns(self):
        issues, warns, stats = au.scan(str(ROOT))
        self.assertEqual(issues, [])
        self.assertGreaterEqual(stats["with_header"], 1)
        self.assertTrue(any("legacy" in w for w in warns))

    def test_header_digests_match(self):
        issues, st = au.check_doc(str(ROOT), "results/audit/docs_audit-49-audit-protocol.md")
        self.assertEqual(issues, [])
        self.assertGreaterEqual(st["subjects"], 6)


class TestNegatives(unittest.TestCase):
    def test_subject_digest_drift_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(), digest="0" * 64)
        self.assertTrue(any("旧审计失效" in i
                            for i in au.check_doc(tmp, "results/audit/docs_audit-99-x.md")[0]))

    def test_bad_verdict_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(), verdict="maybe")
        self.assertTrue(any("verdict 越词表" in i
                            for i in au.check_doc(tmp, "results/audit/docs_audit-99-x.md")[0]))

    def test_acceptance_without_date_is_fail(self):
        tmp = _scene(tempfile.mkdtemp(), accepted_at="—")
        self.assertTrue(any("签收须双要素" in i
                            for i in au.check_doc(tmp, "results/audit/docs_audit-99-x.md")[0]))

    def test_missing_subject_file_is_fail(self):
        tmp = _scene(tempfile.mkdtemp())
        _mk(tmp, "results/audit/docs_audit-98-y.md",
            (Path(tmp, "results/audit/docs_audit-99-x.md").read_text(encoding="utf-8"))
            .replace("subject.md:", "gone.md:"))
        self.assertTrue(any("被审对象不存在" in i
                            for i in au.check_doc(tmp, "results/audit/docs_audit-98-y.md")[0]))

    def test_subject_path_escape_is_fail(self):
        """subjects 只接受仓库根内相对路径；不得把摘要校验变成仓外读。"""
        tmp = _scene(tempfile.mkdtemp())
        audit_path = Path(tmp, "results/audit/docs_audit-99-x.md")
        audit_path.write_text(
            audit_path.read_text(encoding="utf-8").replace(
                "subject.md:", "../outside.md:"),
            encoding="utf-8",
        )
        issues, _stats = au.check_doc(tmp, "results/audit/docs_audit-99-x.md")
        self.assertTrue(any("路径不合法" in issue for issue in issues), issues)

    def test_subject_shape_is_checked_without_traceback(self):
        from core import audit_subject

        issues, ok = audit_subject.check(tempfile.mkdtemp(), {"bad": "shape"})
        self.assertEqual(0, ok)
        self.assertTrue(any("字符串或列表" in issue for issue in issues), issues)

    def test_legacy_is_warn_not_fail(self):
        tmp = tempfile.mkdtemp()
        _minimal_decl(tmp, ("results/audit/docs_audit-90-old.md",))
        _mk(tmp, "results/audit/docs_audit-90-old.md", "# 旧审计\n\n无头。\n")
        issues, warns, stats = au.scan(tmp)
        self.assertEqual(issues, [])
        self.assertEqual(stats["legacy"], 1)
        self.assertTrue(warns)

    def test_unregistered_headerless_audit_is_fail(self):
        """未登记的无头件不是 legacy；删掉审计头也不能绕过必填字段。"""
        tmp = tempfile.mkdtemp()
        _minimal_decl(tmp)
        _mk(tmp, "results/audit/docs_audit-91-new.md", "# 新审计\n\n无头。\n")
        issues, _warns, stats = au.scan(tmp)
        self.assertEqual(0, stats["legacy"])
        self.assertTrue(any("docs_audit-91-new.md" in issue for issue in issues), issues)

    def test_stale_legacy_entry_is_rejected(self):
        """历史件补齐完整审计头后必须移出 legacy 清单，不能继续享受 WARN 豁免。"""
        tmp = _scene(tempfile.mkdtemp())
        data = json.loads((Path(tmp) / au.DECL_REL).read_text(encoding="utf-8"))
        data["legacy_records"] = {"paths": [{
            "path": "results/audit/docs_audit-99-x.md",
            "reason": "测试用历史记录",
        }]}
        _mk(tmp, au.DECL_REL, json.dumps(data, ensure_ascii=False))
        issues, _warns, stats = au.scan(tmp)
        self.assertEqual(0, stats["legacy"])
        self.assertTrue(any("应从清单移除" in issue for issue in issues), issues)

    def test_missing_id_in_header_is_fail_not_legacy(self):
        """有审计头但缺 id 是坏审计，不是历史 legacy——否则删字段即可绕过判据。"""
        tmp = _scene(tempfile.mkdtemp())
        audit_path = Path(tmp, "results/audit/docs_audit-99-x.md")
        audit_path.write_text(
            audit_path.read_text(encoding="utf-8").replace("id: AUD-0099\n", ""),
            encoding="utf-8",
        )
        issues, stats = au.check_doc(tmp, "results/audit/docs_audit-99-x.md")
        self.assertFalse(stats.get("legacy", False))
        self.assertTrue(any("id" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
