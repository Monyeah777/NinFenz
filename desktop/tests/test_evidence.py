"""证据包（evidence bundle）单测——cc_verify 的四词判定与 fail-closed 面。

判据覆盖：ok / invalid / revoked / expired 四词各自可达且**只由对应条件触发**；
确定性打包；信封强度如实回填（hmac 缺密钥一律拒绝，不降级）；
叶定义与 receipts 同源（防止第二套摘要悄悄长出来）。
"""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import attest, evidence, receipts


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_evidence_t_")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        (self.tmp / "docs").mkdir()
        self.a = self.tmp / "docs" / "a.md"
        self.b = self.tmp / "docs" / "b.md"
        self.a.write_text("# A\n\n正文甲\n", encoding="utf-8")
        self.b.write_text("# B\n\n正文乙\n", encoding="utf-8")
        self.key = b"0123456789abcdef0123456789abcdef"

    def _pack(self, targets=("docs/a.md", "docs/b.md"), **kw):
        data, info = evidence.build(str(self.tmp), list(targets), **kw)
        out = Path(self._tmp.name) / "bundle.zip"
        out.write_bytes(data)
        return str(out), info, data


class TestLeafSameSource(_Base):
    def test_leaf_matches_receipts(self):
        """叶定义必须与 receipts.build_scope 逐字节同源（否则根永远对不上真源）。"""
        doc = receipts.build_scope(str(self.tmp), ["docs/a.md"], scope="evidence")
        e = doc["entries"][0]
        self.assertEqual(evidence._leaf(e["path"], e["digest"]), e["leaf"])


class TestVerdicts(_Base):
    def test_ok_digest_only(self):
        path, info, _ = self._pack()
        res = evidence.verify(path)
        self.assertEqual(res["verdict"], "ok", res["issues"])
        self.assertEqual(res["level"], "digest_only")
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["root"], info["root"])

    def test_deterministic_bytes(self):
        """固定签发时刻时，两次打包逐字节一致（固定时间戳 + 成员排序 + 不压缩）。"""
        d1, _ = evidence.build(str(self.tmp), ["docs/a.md", "docs/b.md"],
                               created_at="2026-01-01T00:00:00Z")
        d2, _ = evidence.build(str(self.tmp), ["docs/a.md", "docs/b.md"],
                               created_at="2026-01-01T00:00:00Z")
        self.assertEqual(d1, d2)

    def test_tampered_payload_invalid(self):
        path, _info, data = self._pack()
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["payload/docs/a.md"] = "# A\n\n正文被改\n".encode()
        bad = Path(self._tmp.name, "bad.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.verify(str(bad))
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("成员摘要不符" in i for i in res["issues"]), res["issues"])

    def test_missing_payload_invalid(self):
        path, _info, _data = self._pack()
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members.pop("payload/docs/b.md")
        bad = Path(self._tmp.name, "missing.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.verify(str(bad))
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("缺 payload" in i for i in res["issues"]), res["issues"])

    def test_dropped_entry_invalid(self):
        """从清单里删一条（成员集变小）→ 根不一致，不许静默通过。"""
        path, _info, _data = self._pack()
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        meta = json.loads(members["bundle.json"].decode("utf-8"))
        meta["entries"] = meta["entries"][:1]
        members["bundle.json"] = json.dumps(meta, ensure_ascii=False, indent=2,
                                            sort_keys=True).encode("utf-8")
        bad = Path(self._tmp.name, "dropped.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.verify(str(bad))
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("根不一致" in i for i in res["issues"]), res["issues"])

    def test_revoked_by_digest(self):
        path, _info, data = self._pack()
        with zipfile.ZipFile(path) as zf:
            payload = zf.read("payload/docs/a.md")
        import hashlib
        rev = {"schema": evidence.REVOCATION_SCHEMA,
               "revoked": [{"digest": hashlib.sha256(payload).hexdigest(),
                            "revoked_at": "2026-01-01T00:00:00Z", "reason": "错签"}]}
        res = evidence.verify(path, revocations=rev)
        self.assertEqual(res["verdict"], "revoked")
        self.assertEqual((res["revoked_by"] or {}).get("reason"), "错签")

    def test_revoked_by_path(self):
        path, _info, _ = self._pack()
        rev = {"schema": evidence.REVOCATION_SCHEMA,
               "revoked": [{"path": "docs/b.md", "revoked_at": "2026-01-01T00:00:00Z",
                            "reason": "下架"}]}
        self.assertEqual(evidence.verify(path, revocations=rev)["verdict"], "revoked")

    def test_revocation_ignored_when_tampered(self):
        """篡改优先于吊销：先判 invalid，不把坏证据说成「只是被吊销」。"""
        path, _info, _data = self._pack()
        rev = {"schema": evidence.REVOCATION_SCHEMA,
               "revoked": [{"path": "docs/a.md", "reason": "x"}]}
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["payload/docs/a.md"] = b"tampered"
        bad = Path(self._tmp.name, "t.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        self.assertEqual(evidence.verify(str(bad), revocations=rev)["verdict"], "invalid")

    def test_expired(self):
        path, _info, _ = self._pack(expires_at="2020-01-01T00:00:00Z")
        self.assertEqual(evidence.verify(path)["verdict"], "expired")

    def test_not_expired_yet(self):
        path, _info, _ = self._pack(expires_at="2099-01-01T00:00:00Z")
        self.assertEqual(evidence.verify(path)["verdict"], "ok")

    def test_expiry_after_revocation(self):
        """吊销压过时效：已吊销的证据不因「还没过期」而算 ok，也不因过期被说成 expired。"""
        path, _info, _ = self._pack(expires_at="2020-01-01T00:00:00Z")
        rev = {"schema": evidence.REVOCATION_SCHEMA,
               "revoked": [{"path": "docs/a.md", "reason": "x"}]}
        self.assertEqual(evidence.verify(path, revocations=rev)["verdict"], "revoked")

    def test_not_a_bundle(self):
        bad = Path(self._tmp.name, "x.zip")
        bad.write_bytes(b"not a zip at all")
        with self.assertRaises(ValueError) as ctx:
            evidence.verify(str(bad))
        self.assertIn("修复指引", str(ctx.exception))

    def test_missing_bundle(self):
        with self.assertRaises(ValueError) as ctx:
            evidence.verify(str(Path(self._tmp.name, "nope.zip")))
        self.assertIn("修复指引", str(ctx.exception))

    def test_directory_bundle(self):
        """目录形态与 zip 形态同判（便于人工检查证据包）。"""
        path, info, _ = self._pack()
        ddir = Path(self._tmp.name, "unpacked")
        with zipfile.ZipFile(path) as zf:
            zf.extractall(str(ddir))
        res = evidence.verify(str(ddir))
        self.assertEqual(res["verdict"], "ok", res["issues"])
        self.assertEqual(res["root"], info["root"])


class TestStrength(_Base):
    def test_hmac_without_key_is_invalid(self):
        """hmac 级信封缺密钥 → 拒绝（绝不静默降级成 digest_only）。"""
        path, info, _ = self._pack(key=self.key)
        self.assertEqual(info["level"], "hmac-sha256")
        res = evidence.verify(path)
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("信封未全部通过校验" in i for i in res["issues"]),
                        res["issues"])

    def test_hmac_with_key_ok(self):
        path, _info, _ = self._pack(key=self.key)
        res = evidence.verify(path, key=self.key)
        self.assertEqual(res["verdict"], "ok", res["issues"])
        self.assertEqual(res["level"], "hmac-sha256")

    def test_hmac_wrong_key_invalid(self):
        path, _info, _ = self._pack(key=self.key)
        res = evidence.verify(path, key=b"wrong-key-wrong-key-wrong-key")
        self.assertEqual(res["verdict"], "invalid")

    def test_no_attestation_invalid(self):
        path, _info, _ = self._pack()
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        meta = json.loads(members["bundle.json"].decode("utf-8"))
        meta["attestations"] = []
        members["bundle.json"] = json.dumps(meta, ensure_ascii=False, indent=2,
                                            sort_keys=True).encode("utf-8")
        bad = Path(self._tmp.name, "noatt.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.verify(str(bad))
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("无 attestation" in i for i in res["issues"]), res["issues"])


class TestBuildGuards(_Base):
    def test_empty_targets_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            evidence.build(str(self.tmp), [])
        self.assertIn("修复指引", str(ctx.exception))

    def test_missing_target_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            evidence.build(str(self.tmp), ["docs/nope.md"])
        self.assertIn("修复指引", str(ctx.exception))

    def test_non_utf8_target_rejected(self):
        bad = self.tmp / "docs" / "bin.dat"
        bad.write_bytes(b"\xff\xfe\x00\x01")
        with self.assertRaises(ValueError) as ctx:
            evidence.build(str(self.tmp), ["docs/bin.dat"])
        self.assertIn("修复指引", str(ctx.exception))


class TestSelfcheck(_Base):
    def test_selfcheck_passes(self):
        """机制体检必须全绿：PASS 过 / 篡改红 / 吊销 revoked / 过期 expired。"""
        ok, issues, stats = evidence.selfcheck()
        self.assertTrue(ok, issues)
        self.assertEqual(stats["tamper"], "invalid")
        self.assertEqual(stats["revoked"], "revoked")
        self.assertEqual(stats["expired"], "expired")


class TestForms(_Base):
    """cc_verify 的三种输入形态：自包含包 / 协议回执 / 信封集。"""

    def _receipts_doc(self, rels=("docs/a.md", "docs/b.md")):
        return receipts.build_scope(str(self.tmp), list(rels), scope="evidence")

    def test_receipts_form_ok(self):
        doc = self._receipts_doc()
        path = Path(self._tmp.name, "RECEIPTS.json")
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        res = evidence.verify_any(str(path), root=str(self.tmp))
        self.assertEqual(res["verdict"], "ok", res["issues"])
        self.assertEqual(res["level"], "receipts_only")
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["root"], doc["root"])

    def test_receipts_form_tamper(self):
        doc = self._receipts_doc()
        path = Path(self._tmp.name, "RECEIPTS.json")
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        self.a.write_text("# A\n\n被改\n", encoding="utf-8")
        res = evidence.verify_any(str(path), root=str(self.tmp))
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("成员摘要不符" in i for i in res["issues"]), res["issues"])

    def test_receipts_form_missing_member(self):
        doc = self._receipts_doc()
        path = Path(self._tmp.name, "RECEIPTS.json")
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        self.b.unlink()
        res = evidence.verify_any(str(path), root=str(self.tmp))
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("缺成员实体" in i for i in res["issues"]), res["issues"])

    def test_attest_set_ok_with_key(self):
        envs = []
        for rel in ("docs/a.md", "docs/b.md"):
            envs.append(attest.sign_hmac(attest.build(rel, str(self.tmp)), self.key))
        path = Path(self._tmp.name, "ATTEST.json")
        path.write_text(json.dumps({"schema": "nf-attest-set/1", "attestations": envs},
                                   ensure_ascii=False), encoding="utf-8")
        res = evidence.verify_any(str(path), root=str(self.tmp), key=self.key)
        self.assertEqual(res["verdict"], "ok", res["issues"])
        self.assertEqual(res["level"], "hmac-sha256")

    def test_attest_set_without_key_invalid(self):
        envs = [attest.sign_hmac(attest.build("docs/a.md", str(self.tmp)), self.key)]
        path = Path(self._tmp.name, "ATTEST.json")
        path.write_text(json.dumps({"schema": "nf-attest-set/1", "attestations": envs},
                                   ensure_ascii=False), encoding="utf-8")
        self.assertEqual(evidence.verify_any(str(path), root=str(self.tmp))["verdict"],
                         "invalid")

    def test_attest_subject_edit_invalid(self):
        env = attest.build("docs/a.md", str(self.tmp))
        env["subject"]["sha256"] = "0" * 64
        path = Path(self._tmp.name, "A.json")
        path.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
        res = evidence.verify_any(str(path), root=str(self.tmp))
        self.assertEqual(res["verdict"], "invalid")

    def test_container_auto_detect_receipts(self):
        doc = self._receipts_doc()
        Path(self._tmp.name, "RECEIPTS.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        res = evidence.verify_any(str(self.tmp))
        self.assertEqual(res.get("kind"), "receipts")
        self.assertEqual(res["verdict"], "ok", res["issues"])

    def test_unknown_form(self):
        path = Path(self._tmp.name, "x.json")
        path.write_text(json.dumps({"schema": "nothing/1"}), encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            evidence.verify_any(str(path))
        self.assertIn("修复指引", str(ctx.exception))


class TestExtras(_Base):
    def test_extra_member_invalid(self):
        """夹带未登记成员 = 包不干净（多出来的字节没有回执背书）。"""
        path, _info, _data = self._pack()
        import zipfile as _zip
        with _zip.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["payload/docs/sneak.md"] = b"# sneak\n"
        bad = Path(self._tmp.name, "sneak.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.verify(str(bad))
        self.assertEqual(res["verdict"], "invalid")
        self.assertTrue(any("多出未登记成员" in i for i in res["issues"]), res["issues"])


class TestBench(_Base):
    def test_bench_all_cases(self):
        """攻击矩阵必须全过——任何一条不达期望说明复验器有洞。"""
        res = evidence.bench()
        bad = [c for c in res["cases"] if not c["ok"]]
        self.assertEqual(bad, [])
        self.assertEqual(res["total"], 25)
        self.assertTrue(res["ok"])

    def test_bench_markdown(self):
        md = evidence.bench_markdown(evidence.bench())
        self.assertIn("攻击矩阵", md)
        self.assertIn("| # | 用例 |", md)
        self.assertIn("不**证明", md)


if __name__ == "__main__":
    unittest.main()
