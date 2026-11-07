"""吊销分发件 v0（core/revocations.py + nf evidence revocations CLI）判据。

判据重点：签名在就必须过（缺密钥不降级）、序号链防回滚/防分叉、合并「一份不过则整次失败」。
为什么这么严：吊销面一旦被回滚，已吊销的错签会重新「生效」——这是比缺表更危险的状态。
新鲜度（expires_at/ttl）只进输出：默认只 WARN，--require-fresh-revocations 才升级成 invalid，
且「命中吊销」与「证据过期」都压过它（revoked > expired > 新鲜度 > ok）。
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "nf.py"
KEY = b"k" * 32
# 新鲜度判据用的固定时刻（不依赖墙钟：ttl/expires_at 的比较是纯字符串比较）
FUTURE = "2099-01-01T00:00:00Z"
STALE_FROM = "2026-01-01T00:00:00Z"
STALE_TO = "2026-02-01T00:00:00Z"


def _rv():
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    spec = importlib.util.spec_from_file_location(
        "nf_revocations", ROOT / "desktop" / "src" / "core" / "revocations.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ev():
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from core import evidence
    return evidence


def _row(digest="a" * 64, reason="错签"):
    return {"digest": digest, "reason": reason}


class TestSignVerify(unittest.TestCase):
    def setUp(self):
        self.rv = _rv()
        self.t1 = self.rv.make_table([_row()])
        self.f1 = self.rv.sign(self.t1, KEY, issuer="acme", seq=1)

    def test_roundtrip_ok(self):
        res = self.rv.verify(self.f1, key=KEY)
        self.assertEqual("ok", res["verdict"])
        self.assertTrue(res["signed"])
        self.assertEqual(1, res["seq"])
        self.assertEqual(1, res["count"])

    def test_digest_is_deterministic(self):
        self.assertEqual(self.rv.digest(self.f1), self.rv.digest(self.f1))

    def test_tampered_table_fails(self):
        bad = dict(self.f1)
        bad["table"] = self.rv.make_table([_row("b" * 64)])
        res = self.rv.verify(bad, key=KEY)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("签名不匹配", " ".join(res["issues"]))

    def test_wrong_key_fails(self):
        self.assertEqual("invalid", self.rv.verify(self.f1, key=b"w" * 32)["verdict"])

    def test_missing_key_does_not_downgrade(self):
        res = self.rv.verify(self.f1)
        self.assertEqual("invalid", res["verdict"], "签名在就必须给密钥，缺密钥不降级")
        self.assertIn("缺密钥", " ".join(res["issues"]))

    def test_unsigned_table_warns(self):
        res = self.rv.verify(self.t1)
        self.assertEqual("ok", res["verdict"], "裸表形状可判")
        self.assertTrue(res["warnings"])
        self.assertFalse(res["signed"])

    def test_bad_seq_fails(self):
        bad = dict(self.f1)
        bad["seq"] = -1
        self.assertEqual("invalid", self.rv.verify(bad, key=KEY)["verdict"])

    def test_unknown_schema_fails(self):
        self.assertEqual("invalid", self.rv.verify({"schema": "x"})["verdict"])

    def test_table_missing_fails(self):
        doc = {"schema": "nf-revocation-feed/1"}
        self.assertEqual("invalid", self.rv.verify(doc)["verdict"])


class TestChain(unittest.TestCase):
    def setUp(self):
        self.rv = _rv()
        self.f1 = self.rv.sign(self.rv.make_table([_row()]), KEY, seq=1)
        t2 = self.rv.make_table([_row(), _row("b" * 64)])
        self.f2 = self.rv.sign(t2, KEY, seq=2, prev=self.f1)

    def test_chain_ok(self):
        self.assertEqual("ok", self.rv.verify(self.f2, key=KEY, prev=self.f1)["verdict"])

    def test_rollback_detected(self):
        res = self.rv.verify(self.f1, key=KEY, prev=self.f2)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("序号不连续", " ".join(res["issues"]))

    def test_fork_detected(self):
        other = self.rv.sign(self.rv.make_table([_row("c" * 64)]), KEY, seq=2)
        res = self.rv.verify(other, key=KEY, prev=self.f1)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("前序摘要", " ".join(res["issues"]))


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.rv = _rv()
        self.f1 = self.rv.sign(self.rv.make_table([_row()]), KEY, seq=1)
        t2 = self.rv.make_table([_row(), _row("b" * 64)])
        self.f2 = self.rv.sign(t2, KEY, seq=2, prev=self.f1)

    def test_merge_union_sorted(self):
        res = self.rv.merge([self.f2, self.f1], key=KEY)
        self.assertTrue(res["ok"])
        self.assertEqual(2, res["count"])
        self.assertEqual(2, res["feeds"])
        digests = [r["digest"] for r in res["table"]["revoked"]]
        self.assertEqual(sorted(digests), digests, "合并结果必须稳定排序")

    def test_merge_forged_fails_whole(self):
        bad = dict(self.f2)
        bad["table"] = self.rv.make_table([_row("z" * 64)])
        self.assertFalse(self.rv.merge([self.f1, bad], key=KEY)["ok"],
                         "一份不过则整次失败")

    def test_merge_without_key_fails(self):
        self.assertFalse(self.rv.merge([self.f1], key=None)["ok"])


class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "evidence", "revocations", *args],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def _fixtures(self, td):
        key = Path(td, "k.bin")
        key.write_bytes(KEY)
        t1 = Path(td, "t1.json")
        t1.write_text(json.dumps({"schema": "nf-revocation/1", "revoked": [_row()]}),
                      encoding="utf-8")
        return key, t1

    def test_sign_verify_merge_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            key, t1 = self._fixtures(td)
            f1 = Path(td, "f1.json")
            proc = self._run("sign", "--table", str(t1), "--key-file", str(key),
                             "--seq", "1", "--out", str(f1), "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            proc = self._run("verify", str(f1), "--key-file", str(key), "--json")
            self.assertEqual(0, proc.returncode)
            self.assertEqual("ok", json.loads(proc.stdout)["verdict"])
            merged = Path(td, "m.json")
            proc = self._run("merge", str(f1), "--key-file", str(key), "--out", str(merged),
                             "--json")
            self.assertEqual(0, proc.returncode)
            self.assertEqual(1, json.loads(merged.read_text(encoding="utf-8"))["count"])

    def test_verify_without_key_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            key, t1 = self._fixtures(td)
            f1 = Path(td, "f1.json")
            self._run("sign", "--table", str(t1), "--key-file", str(key), "--out", str(f1))
            proc = self._run("verify", str(f1), "--json")
            self.assertEqual(1, proc.returncode, "缺密钥必须 invalid，不降级")


class TestFreshnessFields(unittest.TestCase):
    """T1/T2/T4/T5/T6：feed 可选字段的形状与 freshness 输出（**不参与** verdict）。"""

    def setUp(self):
        self.rv = _rv()
        self.t1 = self.rv.make_table([_row()])

    def test_fresh_feed_reports_fresh(self):
        """T1：未过期 feed → freshness=fresh，verdict 仍是 ok。"""
        f = self.rv.sign(self.t1, KEY, seq=1, expires_at=FUTURE)
        res = self.rv.verify(f, key=KEY)
        self.assertEqual("fresh", res["freshness"]["state"])
        self.assertEqual("expires_at", res["freshness"]["basis"])
        self.assertEqual(FUTURE, res["freshness"]["expires_at"])
        self.assertEqual("ok", res["verdict"])

    def test_no_validity_is_unknown_not_fatal(self):
        """T2：无新字段的 feed / 裸表 → unknown，但**不判死**。"""
        f = self.rv.sign(self.t1, KEY, seq=1)
        self.assertNotIn("expires_at", f, "未给出有效期时不得写 null/空值")
        self.assertNotIn("ttl", f)
        res = self.rv.verify(f, key=KEY)
        self.assertEqual("unknown", res["freshness"]["state"])
        self.assertEqual("none", res["freshness"]["basis"])
        self.assertEqual("ok", res["verdict"])
        bare = self.rv.verify(self.t1)
        self.assertEqual("unknown", bare["freshness"]["state"])
        self.assertEqual("ok", bare["verdict"], "裸表没有信封可读有效期，不是陈旧")

    def test_ttl_expiry_is_issued_at_plus_ttl(self):
        """§4：ttl 换算成 expires_at（issued_at + ttl 秒），basis=ttl。"""
        f = self.rv.sign(self.t1, KEY, seq=1, issued_at=STALE_FROM, ttl=86400)
        at = "2026-01-01T12:00:00Z"
        res = self.rv.verify(f, key=KEY, at=at)
        self.assertEqual("fresh", res["freshness"]["state"])
        self.assertEqual("ttl", res["freshness"]["basis"])
        self.assertEqual("2026-01-02T00:00:00Z", res["freshness"]["expires_at"])
        late = self.rv.verify(f, key=KEY, at="2026-01-03T00:00:00Z")
        self.assertEqual("stale", late["freshness"]["state"])

    def test_expires_before_issued_invalid(self):
        """T4：expires_at 早于 issued_at → sign 与 verify 同判 invalid。"""
        with self.assertRaises(ValueError) as ctx:
            self.rv.sign(self.t1, KEY, seq=1, issued_at="2026-06-01T00:00:00Z",
                         expires_at="2026-05-01T00:00:00Z")
        self.assertIn("早于 issued_at", str(ctx.exception))
        f = self.rv.sign(self.t1, KEY, seq=1, issued_at="2026-06-01T00:00:00Z",
                         expires_at="2026-07-01T00:00:00Z")
        f["expires_at"] = "2026-05-01T00:00:00Z"
        res = self.rv.verify(f, key=KEY)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("早于 issued_at", " ".join(res["issues"]))

    def test_bad_ttl_invalid(self):
        """T5：ttl 为 0 / 负数 / 字符串 → invalid（形状段在签名之前就拦下）。"""
        f = self.rv.sign(self.t1, KEY, seq=1, ttl=86400)
        for bad in (0, -1, "86400"):
            res = self.rv.verify(dict(f, ttl=bad), key=KEY)
            self.assertEqual("invalid", res["verdict"], f"ttl={bad!r}")
            self.assertIn("ttl", " ".join(res["issues"]))
        with self.assertRaises(ValueError) as ctx:
            self.rv.sign(self.t1, KEY, ttl=31536001)
        self.assertIn("--ttl", str(ctx.exception))

    def test_tampered_expires_at_breaks_signature(self):
        """T6：改 expires_at 一个字节 → 签名不匹配，且 digest 变化（新字段进签名体）。"""
        f = self.rv.sign(self.t1, KEY, seq=1, issued_at="2026-11-06T00:00:00Z",
                         expires_at="2026-12-06T00:00:00Z")
        bad = dict(f, expires_at="2026-12-07T00:00:00Z")
        res = self.rv.verify(bad, key=KEY)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("签名不匹配", " ".join(res["issues"]))
        self.assertNotEqual(self.rv.digest(f), self.rv.digest(bad))
        self.assertEqual(self.rv.digest(f), self.rv.digest(f), "同一 feed 两次 digest 必须相同")

    def test_status_uri_only_recorded(self):
        """status_uri 只在给出时写入、只记录（不联网、不验可达性）。"""
        f = self.rv.sign(self.t1, KEY, seq=1, status_uri="https://example.invalid/r.json")
        self.assertEqual("https://example.invalid/r.json", f["status_uri"])
        self.assertEqual("ok", self.rv.verify(f, key=KEY)["verdict"])
        signed = self.rv.sign(self.t1, KEY, seq=1)
        self.assertNotIn("status_uri", signed)


class TestFreshnessEvidence(unittest.TestCase):
    """T2/T3/T7/T9 + B 组缺陷修复：证据复验侧的吊销新鲜度（三处调用点同口径）。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="nf_rev_fresh_")
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "a.md").write_text("# A\n", encoding="utf-8")
        self.rv = _rv()
        self.ev = _ev()
        self.table = self.rv.make_table([_row()])
        self.hit_table = self.rv.make_table([{"path": "docs/a.md", "reason": "下架"}])

    def _bundle(self, **kw):
        data, _info = self.ev.build(str(self.tmp), ["docs/a.md"], **kw)
        out = Path(self._td.name) / "bundle.zip"
        out.write_bytes(data)
        return out

    def _feed(self, table, name, **kw):
        doc = self.rv.sign(table, KEY, **kw)
        out = Path(self._td.name) / name
        out.write_text(json.dumps(doc), encoding="utf-8")
        return doc, out

    def test_table_source_freshness_unknown_only_warns(self):
        """T2（证据侧）：吊销来源在场但没给有效期 → unknown + WARN，verdict 不变。"""
        path = self._bundle()
        res = self.ev.verify(str(path), revocations=self.table)
        self.assertEqual("ok", res["verdict"])
        self.assertEqual("unknown", res["revocations_fresh"])
        self.assertEqual("external", res["revocations_source"])
        self.assertTrue(any("未给有效期" in w for w in res["warnings"]), res["warnings"])
        strict = self.ev.verify(str(path), revocations=self.table,
                                require_fresh_revocations=True)
        self.assertEqual("invalid", strict["verdict"], "严格开关下 unknown 也必须判死")
        self.assertTrue(any("未给有效期" in i for i in strict["issues"]), strict["issues"])

    def test_strict_stale_revocation_invalid(self):
        """T3：默认只 WARN；严格开关下过期表 → invalid。"""
        path = self._bundle()
        feed, _out = self._feed(self.table, "stale.json", seq=1,
                                issued_at=STALE_FROM, expires_at=STALE_TO)
        self.assertEqual("ok", self.ev.verify(str(path), revocations=feed)["verdict"],
                         "默认只 WARN，不改四词判定")
        res = self.ev.verify(str(path), revocations=feed, require_fresh_revocations=True)
        self.assertEqual("invalid", res["verdict"])
        self.assertTrue(any("吊销表已过期" in i for i in res["issues"]), res["issues"])

    def test_cli_strict_stale_exits_1(self):
        """T3（CLI）：--require-fresh-revocations 下过期表 → 退出码 1。"""
        path = self._bundle()
        _feed, out = self._feed(self.table, "stale.json", seq=1,
                                issued_at=STALE_FROM, expires_at=STALE_TO)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "evidence", "verify", str(path),
             "--revocations", str(out), "--require-fresh-revocations", "--json"],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(1, proc.returncode, proc.stderr[-400:])
        payload = json.loads(proc.stdout)
        self.assertEqual("invalid", payload["verdict"])
        self.assertIn("吊销表已过期", " ".join(payload["issues"]))

    def test_revoked_beats_stale(self):
        """T7：命中吊销是事实，压过新鲜度（严格开关下仍是 revoked，不是 invalid）。"""
        path = self._bundle()
        feed, _out = self._feed(self.hit_table, "hit-stale.json", seq=1,
                                issued_at=STALE_FROM, expires_at=STALE_TO)
        res = self.ev.verify(str(path), revocations=feed, require_fresh_revocations=True)
        self.assertEqual("revoked", res["verdict"])
        self.assertTrue(res["revoked_by"], "revoked_by 必须给出命中条目")

    def test_expired_beats_stale(self):
        """T9：expired 是更具体的正向判定，压过「表陈旧」。"""
        path = self._bundle(expires_at="2020-01-01T00:00:00Z")
        feed, _out = self._feed(self.table, "stale2.json", seq=1,
                                issued_at=STALE_FROM, expires_at=STALE_TO)
        res = self.ev.verify(str(path), revocations=feed, require_fresh_revocations=True)
        self.assertEqual("expired", res["verdict"])

    def test_feed_accepted_as_revocations_source(self):
        """B 组缺陷：--revocations 传签名 feed 必须命中（此前静默不命中判 ok）。"""
        path = self._bundle()
        feed, out = self._feed(self.hit_table, "hit.json", seq=1, expires_at=FUTURE)
        res = self.ev.verify(str(path), revocations=feed)
        self.assertEqual("revoked", res["verdict"])
        self.assertEqual("fresh", res["revocations_fresh"], "吃 feed 时要读它的有效期")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "evidence", "verify", str(path),
             "--revocations", str(out), "--json"],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(2, proc.returncode, proc.stderr[-400:])
        self.assertEqual("revoked", json.loads(proc.stdout)["verdict"])

    def test_bad_revocations_shape_fails_closed(self):
        """M11：--revocations 形状坏 → invalid（不许静默不命中）。"""
        path = self._bundle()
        res = self.ev.verify(str(path), revocations={"schema": "nf-other/1"})
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("既不是 nf-revocation/1 表也不是 nf-revocation-feed/1",
                      " ".join(res["issues"]))

    def test_no_source_never_fails_strict(self):
        """完全没有吊销来源 ≠ unknown：严格开关下也不得判死。"""
        path = self._bundle()
        res = self.ev.verify(str(path), require_fresh_revocations=True)
        self.assertEqual("ok", res["verdict"])
        self.assertEqual("none", res["revocations_source"])
        self.assertEqual("unknown", res["revocations_fresh"])


    def _receipts(self):
        """最小可验回执：单成员 docs/a.md（leaf/proof 按 core.receipts 同一算法）。"""
        from core import receipts as rc
        data = (self.tmp / "docs" / "a.md").read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        payload = json.dumps({"id": "docs/a.md", "digest": digest}, sort_keys=True,
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        leaf = rc.leaf_hash(payload).hex()
        doc = {"schema": rc.SCHEMA, "root": leaf, "count": 1,
               "algorithm": "RFC6962-style sha256 domain-separated",
               "entries": [{"id": "docs/a.md", "path": "docs/a.md", "digest": digest,
                            "leaf": leaf, "proof": []}]}
        out = Path(self._td.name) / "receipts.json"
        out.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return out

    def test_receipts_form_honours_at(self):
        """receipts 形态必须与 bundle/attest 同口径吃 --at（2026-11-06 复核阻断项）。"""
        feed, _p = self._feed(self.table, "stale_feed2.json", seq=1,
                              issued_at=STALE_FROM, expires_at=STALE_TO)
        receipts_path = self._receipts()
        early = self.ev.verify_any(str(receipts_path), root=str(self.tmp),
                                   revocations=feed, at=STALE_FROM)
        self.assertEqual("fresh", early["revocations_fresh"], early)
        self.assertEqual("ok", early["verdict"], early["issues"])
        late = self.ev.verify_any(str(receipts_path), root=str(self.tmp),
                                  revocations=feed, at="2026-03-01T00:00:00Z")
        self.assertEqual("stale", late["revocations_fresh"])
        self.assertEqual("ok", late["verdict"], "默认只 WARN，不判死")
        strict = self.ev.verify_any(str(receipts_path), root=str(self.tmp),
                                    revocations=feed, at="2026-03-01T00:00:00Z",
                                    require_fresh_revocations=True)
        self.assertEqual("invalid", strict["verdict"])


class TestMergeFreshness(unittest.TestCase):
    def test_merge_freshness_takes_strictest(self):
        """T8：一份 fresh + 一份 stale → 汇总 stale，逐份状态可查。"""
        rv = _rv()
        f1 = rv.sign(rv.make_table([_row()]), KEY, seq=1,
                     issued_at=STALE_FROM, expires_at=STALE_TO)
        f2 = rv.sign(rv.make_table([_row(), _row("b" * 64)]), KEY, seq=2, prev=f1,
                     expires_at=FUTURE)
        res = rv.merge([f2, f1], key=KEY)
        self.assertTrue(res["ok"])
        self.assertEqual("stale", res["freshness"]["state"])
        self.assertEqual(2, len(res["freshness"]["parts"]))
        self.assertEqual([1, 2], [p["seq"] for p in res["freshness"]["parts"]])
        self.assertEqual(2, res["table"]["count"], "表 schema 与并集语义不变")


class Ed25519FeedTest(unittest.TestCase):
    """非对称吊销面：验证方只持公钥——拿到验证能力不等于拿到伪造能力。

    这是跨组织吊销成立的前提：hmac 把密钥给出去就等于把伪造权给出去。
    """

    SEED = bytes(range(32))

    def setUp(self):
        self.rv = _rv()

    def _feed(self, **kw):
        table = self.rv.make_table([{"digest": "a" * 64, "reason": "文案违规"}])
        return self.rv.sign(table, self.SEED, issuer="org-a", seq=1, scheme=self.rv.ALG_ED25519,
                       issued_at="2026-11-07T00:00:00Z", **kw)

    def test_sign_then_verify_with_public_key(self):
        from core import ed25519
        feed = self._feed()
        self.assertEqual(self.rv.ALG_ED25519, feed["signature"]["alg"])
        self.assertEqual(ed25519.public_key(self.SEED).hex(), feed["signature"]["pub"])
        res = self.rv.verify(feed, key=ed25519.public_key(self.SEED))
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(self.rv.ALG_ED25519, res["scheme"])

    def test_wrong_public_key_is_invalid(self):
        from core import ed25519
        feed = self._feed()
        res = self.rv.verify(feed, key=ed25519.public_key(bytes(32)))
        self.assertFalse(res["ok"])
        self.assertTrue(any("公钥" in i for i in res["issues"]))

    def test_tampered_body_is_invalid(self):
        from core import ed25519
        feed = self._feed()
        feed["table"]["revoked"].append({"digest": "b" * 64})
        res = self.rv.verify(feed, key=ed25519.public_key(self.SEED))
        self.assertFalse(res["ok"])
        self.assertTrue(any("ed25519 签名不匹配" in i for i in res["issues"]))

    def test_missing_public_key_is_fail_closed(self):
        res = self.rv.verify(self._feed())
        self.assertFalse(res["ok"])
        self.assertTrue(any("缺公钥不降级" in i for i in res["issues"]))

    def test_seed_as_key_is_rejected(self):
        """把 32 字节种子当公钥给：长度一样但必然验不过——要给出「别把种子当公钥」的指引。"""
        res = self.rv.verify(self._feed(), key=self.SEED)
        self.assertFalse(res["ok"])
        self.assertTrue(any("公钥" in i for i in res["issues"]))

    def test_scheme_must_be_known(self):
        table = self.rv.make_table([{"digest": "a" * 64}])
        with self.assertRaises(ValueError) as ctx:
            self.rv.sign(table, self.SEED, scheme="rsa-2048")
        self.assertIn("不支持", str(ctx.exception))

    def test_ed25519_requires_32_byte_seed(self):
        table = self.rv.make_table([{"digest": "a" * 64}])
        with self.assertRaises(ValueError) as ctx:
            self.rv.sign(table, b"short", scheme=self.rv.ALG_ED25519)
        self.assertIn("32 字节", str(ctx.exception))

    def test_hmac_path_unchanged(self):
        table = self.rv.make_table([{"digest": "a" * 64}])
        feed = self.rv.sign(table, b"shared-secret")
        self.assertEqual(self.rv.ALG, feed["signature"]["alg"])
        self.assertTrue(self.rv.verify(feed, key=b"shared-secret")["ok"])

    def test_chain_still_checked_for_ed25519(self):
        from core import ed25519
        pub = ed25519.public_key(self.SEED)
        first = self._feed()
        second = self.rv.sign(self.rv.make_table([{"digest": "c" * 64}]), self.SEED, issuer="org-a",
                         seq=2, prev=first, scheme=self.rv.ALG_ED25519,
                         issued_at="2026-11-08T00:00:00Z")
        self.assertTrue(self.rv.verify(second, key=pub, prev=first)["ok"])
        # 跳号：第三份必须紧接第二份，接在第一份后面判死（链检查对 ed25519 同样生效）
        third = self.rv.sign(self.rv.make_table([{"digest": "d" * 64}]), self.SEED,
                             issuer="org-a", seq=3, prev=first, scheme=self.rv.ALG_ED25519,
                             issued_at="2026-11-09T00:00:00Z")
        res = self.rv.verify(third, key=pub, prev=first)
        self.assertFalse(res["ok"], "跳号仍须判死")
        self.assertTrue(any("序号不连续" in i for i in res["issues"]), res["issues"])


if __name__ == "__main__":
    unittest.main()
