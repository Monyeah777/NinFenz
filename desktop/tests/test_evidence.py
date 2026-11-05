"""证据包（evidence bundle）单测——cc_verify 的四词判定与 fail-closed 面。

判据覆盖：ok / invalid / revoked / expired 四词各自可达且**只由对应条件触发**；
确定性打包；信封强度如实回填（hmac 缺密钥一律拒绝，不降级）；
叶定义与 receipts 同源（防止第二套摘要悄悄长出来）。
"""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import attest, evidence, receipts


def _bundle_members(data):
    """证据包字节 → {成员名: 字节}（测试内小工具）。"""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


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
        self.assertEqual(res["total"], 38)
        self.assertTrue(res["ok"])

    def test_bench_markdown(self):
        md = evidence.bench_markdown(evidence.bench())
        self.assertIn("攻击矩阵", md)
        self.assertIn("| # | 用例 |", md)
        self.assertIn("不**证明", md)


class TestStandaloneParity(_Base):
    """两套独立实现判据必须一致：core 版（复验器）vs scripts/nf_verify.py（零依赖单文件）。

    不一致就说明至少一边有 bug——那时「第三方复验」的结论不可信，所以这条判据是硬门。
    """

    SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "nf_verify.py"

    def _run(self, *args):
        import subprocess
        proc = subprocess.run([sys.executable, str(self.SCRIPT), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        return proc.returncode, proc.stdout, proc.stderr

    def _verdict(self, path, key_file="", root="", revocations=""):
        args = ["--evidence", str(path), "--json"]
        if key_file:
            args += ["--key-file", str(key_file)]
        if root:
            args += ["--root", str(root)]
        if revocations:
            args += ["--revocations", str(revocations)]
        _rc, out, err = self._run(*args)
        try:
            return json.loads(out)["verdict"]
        except (ValueError, KeyError):
            self.fail(f"零依赖验证器没给出可解析结论：{err[:300]}")

    def _key_file(self):
        path = Path(self._tmp.name, "key.bin")
        path.write_bytes(self.key)
        return path

    def test_bundle_ok_and_tamper_agree(self):
        path, _info, data = self._pack(key=self.key)
        kf = self._key_file()
        self.assertEqual(self._verdict(path, key_file=kf),
                         evidence.verify_any(path, key=self.key)["verdict"])
        self.assertEqual(self._verdict(path),
                         evidence.verify_any(path)["verdict"])
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["payload/docs/a.md"] = "改".encode()
        bad = Path(self._tmp.name, "bad.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        self.assertEqual(self._verdict(str(bad), key_file=kf),
                         evidence.verify_any(str(bad), key=self.key)["verdict"])

    def test_revoked_and_expired_agree(self):
        path, _info, _data = self._pack(key=self.key, expires_at="2020-01-01T00:00:00Z")
        kf = self._key_file()
        self.assertEqual(self._verdict(path, key_file=kf),
                         evidence.verify_any(path, key=self.key)["verdict"])
        ok_path, _i2, _d2 = self._pack(key=self.key)
        rev = {"schema": evidence.REVOCATION_SCHEMA,
               "revoked": [{"path": "docs/a.md", "reason": "x"}]}
        rev_file = Path(self._tmp.name, "rev.json")
        rev_file.write_text(json.dumps(rev), encoding="utf-8")
        self.assertEqual(self._verdict(str(ok_path), key_file=kf, revocations=rev_file),
                         evidence.verify_any(str(ok_path), key=self.key, revocations=rev)
                         ["verdict"])

    def test_anchor_verdicts_agree(self):
        """双实现必须同判锚点相关判定（anchored ok / 截断 / 分叉）。"""
        import subprocess
        kf = self._key_file()
        tmp = Path(self._tmp.name)
        for n in ("a.md", "b.md", "c.md"):
            (tmp / "docs" / n).write_text(f"# {n}\n\nx\n", encoding="utf-8")
        b2, _i2 = evidence.build(str(self.tmp), ["docs/a.md", "docs/b.md"],
                                 created_at="2026-01-01T00:00:00Z", key=self.key)
        v2 = tmp / "v2.zip"
        v2.write_bytes(b2)
        head2 = {"count": 2, "head": evidence.verify(str(v2), key=self.key)["head"]}
        b3, _i3 = evidence.build(str(self.tmp), ["docs/a.md", "docs/b.md", "docs/c.md"],
                                 created_at="2026-01-02T00:00:00Z", key=self.key,
                                 anchor=head2)
        v3 = tmp / "v3.zip"
        v3.write_bytes(b3)
        head3 = {"count": 3, "head": evidence.verify(str(v3), key=self.key)["head"]}

        def standalone(path, anchor):
            af = Path(self._tmp.name, "anchor.json")
            af.write_text(json.dumps(anchor), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(self.SCRIPT), "--evidence", str(path),
                                   "--json", "--key-file", str(kf), "--anchor", str(af)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
            return json.loads(proc.stdout)["verdict"]

        cases = [(v3, head2, "ok"), (v2, head3, "invalid"),
                 (v3, {"count": 2, "head": "0" * 64}, "invalid")]
        for path, anchor, want in cases:
            core = evidence.verify(str(path), key=self.key, anchor=anchor)["verdict"]
            self.assertEqual(want, core, str(path))
            self.assertEqual(core, standalone(path, anchor), str(path))
    def test_container_attacks_agree(self):
        """双实现必须同判容器面攻击（遍历 / 重名）——第三方复验也吃同一口径。"""
        import subprocess
        tmp = str(self._tmp.name)
        base, _info = evidence.build(str(self.tmp), ["docs/a.md"],
                                     created_at="2026-01-01T00:00:00Z")
        members = _bundle_members(base)
        meta = json.loads(members["bundle.json"].decode())
        meta["entries"][0].update({"path": "../escape.md", "id": "../escape.md"})
        members["bundle.json"] = json.dumps(meta, ensure_ascii=False,
                                            sort_keys=True).encode()
        trav = Path(tmp, "trav.zip")
        trav.write_bytes(evidence._zip_bytes(list(members.items())))
        dup = Path(tmp, "dup.zip")
        with zipfile.ZipFile(dup, "w", zipfile.ZIP_STORED) as zf:
            for name, raw in sorted(_bundle_members(base).items()):
                zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                zf.writestr(zi, raw)
            zi = zipfile.ZipInfo("payload/docs/a.md", date_time=(1980, 1, 1, 0, 0, 0))
            zf.writestr(zi, b"shadow")
        for path in (trav, dup):
            core = evidence.verify(str(path))["verdict"]
            self.assertEqual("invalid", core, path.name)
            proc = subprocess.run([sys.executable, str(self.SCRIPT), "--evidence", str(path),
                                   "--json"], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            self.assertEqual(1, proc.returncode, proc.stderr[-200:])
            self.assertEqual("invalid", json.loads(proc.stdout)["verdict"], path.name)

    def test_receipts_and_attest_forms_agree(self):
        doc = receipts.build_scope(str(self.tmp), ["docs/a.md", "docs/b.md"], scope="ev")
        rec = Path(self._tmp.name, "RECEIPTS.json")
        rec.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self._verdict(str(rec), root=str(self.tmp)),
                         evidence.verify_any(str(rec), root=str(self.tmp))["verdict"])
        envs = [attest.sign_hmac(attest.build(rel, str(self.tmp)), self.key)
                for rel in ("docs/a.md", "docs/b.md")]
        aset = Path(self._tmp.name, "ATTEST.json")
        aset.write_text(json.dumps({"schema": "nf-attest-set/1", "attestations": envs},
                                   ensure_ascii=False), encoding="utf-8")
        kf = self._key_file()
        self.assertEqual(self._verdict(str(aset), key_file=kf, root=str(self.tmp)),
                         evidence.verify_any(str(aset), key=self.key, root=str(self.tmp))
                         ["verdict"])


class TestReplay(_Base):
    """cc_replay：推导过程摊成 trace——每步可复算、可 diff、篡改必现。"""

    def test_bundle_replay_ok_and_deterministic(self):
        path, info, _data = self._pack(key=self.key)
        res = evidence.replay(path, key=self.key)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(res["schema"], evidence.REPLAY_SCHEMA)
        self.assertEqual(res["kind"], "bundle")
        self.assertEqual(res["recomputed_root"], info["root"])
        self.assertEqual(res["recomputed_head"], info["head"])
        # trace 不含时间戳：同一输入两次逐字节一致
        again = evidence.replay(path, key=self.key)
        self.assertEqual(json.dumps(res, sort_keys=True, ensure_ascii=False),
                         json.dumps(again, sort_keys=True, ensure_ascii=False))

    def test_replay_steps_are_ordered(self):
        path, _info, _data = self._pack()
        res = evidence.replay(path)
        for ent in res["entries"]:
            steps = [s["step"] for s in ent["steps"]]
            self.assertEqual(steps, sorted(steps))
            self.assertEqual(ent["steps"][0]["rule"], "sha256-bytes")
            self.assertEqual(ent["steps"][1]["rule"], "rfc6962-leaf")

    def test_replay_entry_filter(self):
        path, _info, _data = self._pack()
        res = evidence.replay(path, entry="docs/a.md")
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual([e["path"] for e in res["entries"]], ["docs/a.md"])

    def test_replay_detects_tamper(self):
        path, _info, _data = self._pack()
        with zipfile.ZipFile(path) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["payload/docs/a.md"] = "改".encode()
        bad = Path(self._tmp.name, "rbad.zip")
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.replay(str(bad))
        self.assertFalse(res["ok"])
        self.assertTrue(any("叶复算不符" in i for i in res["issues"]), res["issues"])

    def test_receipts_replay_ok(self):
        doc = receipts.build_scope(str(self.tmp), ["docs/a.md", "docs/b.md"], scope="ev")
        rec = Path(self._tmp.name, "R.json")
        rec.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        res = evidence.replay(str(rec), root=str(self.tmp))
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(res["kind"], "receipts")
        self.assertEqual(res["recomputed_root"], doc["root"])

    def test_attest_replay_ok(self):
        env = attest.sign_hmac(attest.build("docs/a.md", str(self.tmp)), self.key)
        path = Path(self._tmp.name, "A.json")
        path.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
        res = evidence.replay(str(path), root=str(self.tmp), key=self.key)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(res["kind"], "attest")
        self.assertEqual(res["entries"][0]["steps"][1]["rule"], "nf-attest-envelope")


    def test_strict_chain_and_revocation_agree(self):
        """两套实现必须同时把「坏件」判 invalid：缺 chain / 空链头 / 吊销表坏 JSON。"""
        path, _info, data = self._pack(key=self.key)
        kf = Path(self._tmp.name, "key.bin")
        kf.write_bytes(self.key)

        def mutate(name, fn):
            with zipfile.ZipFile(path) as zf:
                members = {n: zf.read(n) for n in zf.namelist()}
            meta = json.loads(members["bundle.json"].decode())
            fn(members, meta)
            members["bundle.json"] = json.dumps(meta, ensure_ascii=False, indent=2,
                                                sort_keys=True).encode()
            out = Path(self._tmp.name, name)
            out.write_bytes(evidence._zip_bytes(list(members.items())))
            return str(out)

        cases = [
            ("nochain.zip", lambda m, meta: meta.pop("chain", None)),
            ("emptyhead.zip", lambda m, meta: meta["chain"].__setitem__("head", "")),
            ("badrev.zip", lambda m, meta: m.__setitem__("revocations.json", b"{not json")),
        ]
        import subprocess
        for name, fn in cases:
            bad = mutate(name, fn)
            core = evidence.verify(bad, key=self.key)["verdict"]
            self.assertEqual(core, "invalid", name)
            proc = subprocess.run([sys.executable, str(TestStandaloneParity.SCRIPT),
                                   "--evidence", bad, "--json", "--key-file", str(kf)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
            self.assertEqual(json.loads(proc.stdout)["verdict"], core, name)


    def test_anchor_truncation_is_caught(self):
        """G1：外部锚点防「整链截断成更早版本」——包只有 2 条、锚点记 3 条即 invalid。"""
        tmp = Path(self._tmp.name)
        (tmp / "d").mkdir(exist_ok=True)
        for n in ("a.md", "b.md", "c.md"):
            (tmp / "d" / n).write_text(f"# {n}\n\nx\n", encoding="utf-8")
        b2, _i2 = evidence.build(str(tmp), ["d/a.md", "d/b.md"],
                                 created_at="2026-01-01T00:00:00Z", key=self.key)
        v2 = tmp / "v2.zip"
        v2.write_bytes(b2)
        head2 = evidence.verify(str(v2), key=self.key)["head"]
        b3, _i3 = evidence.build(str(tmp), ["d/a.md", "d/b.md", "d/c.md"],
                                 created_at="2026-01-02T00:00:00Z", key=self.key,
                                 anchor={"count": 2, "head": head2})
        v3 = tmp / "v3.zip"
        v3.write_bytes(b3)
        good = evidence.verify(str(v3), key=self.key,
                               anchor={"count": 2, "head": head2})
        self.assertEqual("ok", good["verdict"])
        self.assertTrue(good["anchor_verified"])
        head3 = evidence.verify(str(v3), key=self.key)["head"]
        cut = evidence.verify(str(v2), key=self.key, anchor={"count": 3, "head": head3})
        self.assertEqual("invalid", cut["verdict"])
        self.assertIn("截断", " ".join(cut["issues"]))
        fork = evidence.verify(str(v3), key=self.key,
                               anchor={"count": 2, "head": "0" * 64})
        self.assertEqual("invalid", fork["verdict"])
        noisy = evidence.verify(str(v3), key=self.key)
        self.assertEqual("ok", noisy["verdict"], "缺锚点材料不判死")
        self.assertFalse(noisy["anchor_verified"], "缺锚点材料不得声称已核对")
        self.assertTrue(noisy["warnings"], "缺锚点材料必须留下 warning")


class TestContainerHardening(unittest.TestCase):
    """**容器面**判据：验证器要敢拿敌意包来验——越界写、歧义 zip、zip 炸弹都必须判 invalid。

    这三条是 2026-11-05 审计出来的真实攻击面（不是假想）：
    1. 成员路径来自不可信包，而验证会把成员拼进临时目录落盘 → 不拦「两点号段」就是验证即任意写；
    2. 重名成员在 zip 里是合法的，不同实现取到的字节可能不同 → 判定不可复算；
    3. DEFLATE 能把 1 KB 膨胀成 1 GB → 验证器不能按声明无限解包。
    """

    def _base(self, tmp):
        for name, body in (("a.md", "# A\n"),):
            (Path(tmp) / "d").mkdir(parents=True, exist_ok=True)
            (Path(tmp) / "d" / name).write_text(body, encoding="utf-8")
        return evidence.build(str(tmp), ["d/a.md"], created_at="2026-01-01T00:00:00Z")[0]

    def _members(self, data):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return {n: zf.read(n) for n in zf.namelist()}

    def test_safe_rel_rejects_traversal(self):
        for bad in ("../escape.md", "d/../../x", "./a.md", "d//a.md", "C:/x.md", "d/ /a.md"):
            with self.assertRaises(evidence.UnsafeBundleError, msg=bad):
                evidence._safe_rel(bad)

    def test_safe_rel_accepts_normal_paths(self):
        for ok in ("d/a.md", "docs/x/y.md", "a.md"):
            self.assertEqual(ok, evidence._safe_rel(ok))

    def test_traversal_entry_does_not_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            data = self._base(root)
            members = _bundle_members(data)
            members["payload/../escape.md"] = members.pop("payload/d/a.md")
            meta = json.loads(members["bundle.json"].decode())
            meta["entries"][0]["path"] = "../escape.md"
            meta["entries"][0]["id"] = "../escape.md"
            members["bundle.json"] = json.dumps(meta, ensure_ascii=False,
                                                sort_keys=True).encode()
            bad = Path(tmp) / "bad.zip"
            bad.write_bytes(evidence._zip_bytes(list(members.items())))
            res = evidence.verify(str(bad))
            self.assertEqual("invalid", res["verdict"])
            escaped = Path(tmp) / "escape.md"
            self.assertFalse(escaped.exists(), "验证过程不得在临时目录外落任何文件")

    def test_duplicate_members_are_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            data = self._base(root)
            members = _bundle_members(data)
            dup = Path(tmp) / "dup.zip"
            with zipfile.ZipFile(dup, "w", zipfile.ZIP_STORED) as zf:
                for name, raw in sorted(members.items()):
                    zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    zf.writestr(zi, raw)
                zi = zipfile.ZipInfo("payload/d/a.md", date_time=(1980, 1, 1, 0, 0, 0))
                zf.writestr(zi, b"shadow")
            res = evidence.verify(str(dup))
            self.assertEqual("invalid", res["verdict"])
            self.assertIn("重名成员", " ".join(res["issues"]))

    def test_oversized_member_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            data = self._base(root)
            members = _bundle_members(data)
            import hashlib
            huge = b"\x00" * (evidence.MAX_MEMBER_BYTES + 1)
            digest = hashlib.sha256(huge).hexdigest()
            members["payload/big.bin"] = huge
            meta = json.loads(members["bundle.json"].decode())
            meta["entries"].append({"path": "big.bin", "id": "big.bin", "digest": digest,
                                    "leaf": evidence._leaf("big.bin", digest), "proof": []})
            members["bundle.json"] = json.dumps(meta, ensure_ascii=False,
                                                sort_keys=True).encode()
            bomb = Path(tmp) / "bomb.zip"
            with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, raw in sorted(members.items()):
                    zf.writestr(name, raw)
            res = evidence.verify(str(bomb))
            self.assertEqual("invalid", res["verdict"])
            self.assertIn("上限", " ".join(res["issues"]))




class TestDecisionBinding(_Base):
    """Q0：decision 进签名信封——自洽可证、换策略/删声明面必红、旧包不受影响。"""

    def _decision(self):
        import hashlib
        obj = hashlib.sha256((self.tmp / "docs" / "a.md").read_bytes()).hexdigest()
        return {"syscall": "cc_check",
                "policy_digest": hashlib.sha256(b"policy").hexdigest(),
                "verdict": "ok", "object_sha256": obj}

    def test_declared_digest_only(self):
        path, _info, _data = self._pack(decision=self._decision())
        res = evidence.verify(path)
        self.assertEqual(("ok", "declared"),
                         (res["verdict"], res["decision_status"]), res["issues"])
        self.assertEqual(self._decision(), res["decision"])

    def test_bound_with_hmac(self):
        path, _info, _data = self._pack(decision=self._decision(), key=self.key)
        res = evidence.verify(path, key=self.key)
        self.assertEqual(("ok", "bound"),
                         (res["verdict"], res["decision_status"]), res["issues"])

    def test_old_bundle_stays_absent(self):
        path, _info, _data = self._pack()
        res = evidence.verify(path)
        self.assertEqual(("ok", "absent"),
                         (res["verdict"], res["decision_status"]), res["issues"])
        self.assertIsNone(res["decision"])

    def test_policy_swap_is_invalid(self):
        """只改声明面的 policy_digest：绑定面（信封摘要）覆盖不到 → 必红。"""
        path, _info, data = self._pack(decision=self._decision())
        members = _bundle_members(data)
        meta = json.loads(members["bundle.json"].decode("utf-8"))
        meta["decision"]["policy_digest"] = "1" * 64
        members["bundle.json"] = json.dumps(meta, ensure_ascii=False,
                                            sort_keys=True).encode("utf-8")
        bad = Path(self._tmp.name) / "swap.zip"
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.verify(str(bad))
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("不一致", " ".join(res["issues"]))

    def test_strip_declaration_is_invalid(self):
        """删顶层声明面而绑定面仍在：两条面不一致 → 必红（不许静默降级）。"""
        path, _info, data = self._pack(decision=self._decision())
        members = _bundle_members(data)
        meta = json.loads(members["bundle.json"].decode("utf-8"))
        meta.pop("decision", None)
        members["bundle.json"] = json.dumps(meta, ensure_ascii=False,
                                            sort_keys=True).encode("utf-8")
        bad = Path(self._tmp.name) / "strip.zip"
        bad.write_bytes(evidence._zip_bytes(list(members.items())))
        res = evidence.verify(str(bad))
        self.assertEqual("invalid", res["verdict"])

    def test_bad_decision_rejected_at_build(self):
        dec = self._decision()
        dec["policy_digest"] = "not-hex"
        with self.assertRaises(ValueError) as ctx:
            evidence.build(str(self.tmp), ["docs/a.md"], decision=dec)
        self.assertIn("修复指引", str(ctx.exception))

    def test_expected_policy_matches(self):
        dec = self._decision()
        path, _info, _data = self._pack(decision=dec)
        res = evidence.verify(path, expected_policy_digest=dec["policy_digest"])
        self.assertEqual("ok", res["verdict"], res["issues"])
        self.assertTrue(res["policy_verified"])

    def test_expected_policy_mismatch_is_invalid(self):
        path, _info, _data = self._pack(decision=self._decision())
        res = evidence.verify(path, expected_policy_digest="1" * 64)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("不符", " ".join(res["issues"]))

    def test_expected_without_decision_warns_not_fails(self):
        path, _info, _data = self._pack()
        res = evidence.verify(path, expected_policy_digest="1" * 64)
        self.assertEqual("ok", res["verdict"], res["issues"])
        self.assertFalse(res["policy_verified"])
        self.assertTrue(any("无法比对" in w for w in res["warnings"]), res["warnings"])

    def test_standalone_policy_digest_parity(self):
        import subprocess
        dec = self._decision()
        path, _info, _data = self._pack(decision=dec)
        script = Path(__file__).resolve().parent.parent.parent / "scripts" / "nf_verify.py"

        def run(digest):
            proc = subprocess.run(
                [sys.executable, str(script), "--evidence", path, "--json",
                 "--policy-digest", digest],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            return proc.returncode, json.loads(proc.stdout)["verdict"]

        self.assertEqual((0, "ok"), run(dec["policy_digest"]))
        self.assertEqual((1, "invalid"), run("1" * 64))
        core_ok = evidence.verify(path, expected_policy_digest=dec["policy_digest"])
        core_bad = evidence.verify(path, expected_policy_digest="1" * 64)
        self.assertEqual(("ok", "invalid"), (core_ok["verdict"], core_bad["verdict"]))

if __name__ == "__main__":
    unittest.main()
