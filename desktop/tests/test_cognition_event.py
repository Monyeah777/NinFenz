"""Cognition Event：manifest+journal → 可复算事件；无评分；事件库。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import cognition_event as ce  # noqa: E402

MANIFEST = {
    "schema": "nf-cockpit-manifest/1",
    "prompt_digest": "a" * 64, "machine_digest": "b" * 64, "runtime_digest": "c" * 64,
    "journal_digest": "d" * 64, "handoff_digest": "e" * 64, "context_digest": "f" * 64,
    "status": "pass", "termination": "max-turns", "complete": False, "turns": 2,
    "context_units_spent": 100, "abstention_status": "evidence-required",
    "human_action_required": True,
}
JOURNAL = {"events": [
    {"seq": 1, "status": "pass", "event_digest": "1" * 64,
     "atom_trace": [{"atom_id": "k.partition"}, {"atom_id": "e.falsify"}]},
    {"seq": 2, "status": "pass", "event_digest": "2" * 64,
     "atom_trace": [{"atom_id": "s.synthesize"}]},
]}


class CognitionEventTest(unittest.TestCase):
    def test_build_verify_and_atoms(self):
        ev = ce.build(MANIFEST, JOURNAL)
        self.assertEqual([], ce.verify(ev))
        self.assertEqual(["k.partition", "e.falsify", "s.synthesize"], ev["atoms"])
        self.assertEqual(2, len(ev["rounds"]))
        self.assertTrue(ev["no_scoring"])
        self.assertEqual(ce.build(MANIFEST, JOURNAL)["digest"], ev["digest"])

    def test_tamper_detected(self):
        ev = ce.build(MANIFEST, JOURNAL)
        ev["status"] = "fail"
        self.assertIn("digest", ce.verify(ev))

    def test_store_and_load(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev = ce.build(MANIFEST, JOURNAL)
                ce.write(ev)
                self.assertEqual(ev["digest"], ce.load(ev["digest"])["digest"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_evidence_roles_optional_and_digest_stable(self):
        base = ce.build(MANIFEST, JOURNAL)
        self.assertNotIn("evidence_roles", base)
        roles = {"local-trusted": 2, "external-advisory": 1}
        with_roles = ce.build(MANIFEST, JOURNAL, evidence_roles=roles)
        self.assertEqual(roles, with_roles["evidence_roles"])
        self.assertEqual([], ce.verify(with_roles))
        # roles 参与 digest：带 roles 的事件 digest 与旧事件不同
        self.assertNotEqual(base["digest"], with_roles["digest"])
        # 缺省 / 空 dict / 非 dict：一律不加键，旧 digest 保持稳定
        for empty in ({}, None, "x", ["local-trusted"]):
            ev = ce.build(MANIFEST, JOURNAL, evidence_roles=empty)
            self.assertNotIn("evidence_roles", ev)
            self.assertEqual(base["digest"], ev["digest"])

    def _store_events(self, manifest=None):
        """造 A(旧)→B(新 prev=A) + C(独立、最旧) 三事件并写库。"""
        base = dict(MANIFEST if manifest is None else manifest)
        ev_a = ce.build(dict(base, turns=1), JOURNAL, session_id="A")
        ev_b = ce.build(dict(base, turns=2), JOURNAL, session_id="B")
        ev_b["prev"] = ev_a["digest"]
        ev_b["digest"] = ce.digest(
            {k: v for k, v in ev_b.items() if k != "digest"})
        ev_c = ce.build(dict(base, turns=3), JOURNAL, session_id="C")
        events_dir = Path(os.environ["NF_COCKPIT_HOME"]) / "events"
        for ev, mtime in ((ev_a, 1000.0), (ev_b, 2000.0), (ev_c, 500.0)):
            ce.write(ev)
            os.utime(events_dir / (ev["digest"] + ".json"),
                     (mtime, mtime))
        ce.rebuild_index()
        return ev_a, ev_b, ev_c

    def test_query_filters(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev_a, ev_b, ev_c = self._store_events()
                self.assertEqual(3, len(ce.query()))
                self.assertEqual([ev_a["digest"]],
                                 [e["digest"] for e in
                                  ce.query(session_id="A")])
                self.assertEqual(3, len(ce.query(status="pass")))
                fail_mf = dict(MANIFEST, status="fail")
                ev_d = ce.build(fail_mf, JOURNAL, session_id="D")
                ce.write(ev_d)
                self.assertEqual([ev_d["digest"]],
                                 [e["digest"] for e in
                                  ce.query(status="fail")])
                self.assertEqual(3, len(ce.query(status="pass")))
                self.assertEqual([ev_b["digest"]],
                                 [e["digest"] for e in
                                  ce.query(digest=ev_b["digest"])])
                self.assertEqual(1, len(ce.query(limit=1)))
                # 按 digest 排序
                digests = [e["digest"] for e in ce.query()]
                self.assertEqual(sorted(digests), digests)
                # sessions 列表按 session_id 排序
                sids = [s["session_id"] for s in ce.list_sessions()]
                self.assertEqual(sorted(sids), sids)
                for bad in (0, 501, -1, True):
                    with self.assertRaises(ValueError, msg=repr(bad)):
                        ce.query(limit=bad)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_dry_run_and_apply(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev_a, ev_b, ev_c = self._store_events()
                events_dir = Path(tmp) / "events"
                before = sorted(p.name for p in events_dir.glob("*.json")
                                if p.name != ce.INDEX_NAME)
                # dry-run：默认不删
                res = ce.gc(keep_last=1)
                after = sorted(p.name for p in events_dir.glob("*.json")
                               if p.name != ce.INDEX_NAME)
                self.assertEqual(before, after)
                self.assertTrue(res["dry_run"])
                self.assertIn(ev_c["digest"], res["removed"])
                self.assertIn(ev_a["digest"], res["kept"])   # 祖先 A 保留
                self.assertIn(ev_b["digest"], res["kept"])   # 最新会话 B
                self.assertEqual(2, res["sessions_kept"])
                self.assertEqual(1, res["sessions_removed"])
                # keep_last 大于会话数：no-op
                noop = ce.gc(keep_last=99, dry_run=True)
                self.assertEqual([], noop["removed"])
                # apply：删 C、A/B 链保留、索引一致
                applied = ce.gc(keep_last=1, dry_run=False)
                self.assertFalse(applied["dry_run"])
                self.assertEqual([], ce.verify_index())
                kept = set(ce.build_index()["digests"])
                self.assertEqual({ev_a["digest"], ev_b["digest"]}, kept)
                self.assertFalse((events_dir
                                  / (ev_c["digest"] + ".json")).exists())
                self.assertEqual(2, len(ce.query()))
                # 幂等：再 apply 不再删
                again = ce.gc(keep_last=1, dry_run=False)
                self.assertEqual([], again["removed"])
                self.assertEqual([], ce.verify_index())
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_invalid_params(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for bad in (0, -1, True, "3"):
                    with self.assertRaises(ValueError, msg=repr(bad)):
                        ce.gc(keep_last=bad)
                for bad in ("zz", "A" * 64, 12, "a" * 63):
                    with self.assertRaises(ValueError, msg=repr(bad)):
                        ce.gc(keep_digests=[bad])
                with self.assertRaises(ValueError):
                    ce.gc(keep_digests="a" * 64)   # 单字符串不接受
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def _make_event(self, session_id, turns, status="pass", prev=None,
                    mtime=None):
        manifest = dict(MANIFEST, status=status)
        ev = ce.build(dict(manifest, turns=turns), JOURNAL,
                      session_id=session_id)
        if prev is not None:
            ev["prev"] = prev
            ev["digest"] = ce.digest(
                {k: v for k, v in ev.items() if k != "digest"})
        ce.write(ev)
        if mtime is not None:
            path = (Path(os.environ["NF_COCKPIT_HOME"]) / "events"
                    / (ev["digest"] + ".json"))
            os.utime(path, (mtime, mtime))
        return ev

    def test_retention_policy_precedence(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        old_env = os.environ.get(ce.RETENTION_ENV)
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            os.environ.pop(ce.RETENTION_ENV, None)
            try:
                for idx in range(3):
                    self._make_event("S%d" % idx, idx + 1,
                                     mtime=1000.0 + idx)
                ce.rebuild_index()
                # 1) 内置默认
                res = ce.gc()
                self.assertEqual(20, res["policy"]["keep_last"])
                self.assertEqual([], res["policy"]["keep_status"])
                self.assertIsNone(res["policy"]["max_events"])
                self.assertTrue(res["policy"]["dry_run"])
                # 2) 文件策略（<store>/retention.json）
                policy_file = Path(tmp) / ce.RETENTION_FILE
                policy_file.write_text(json.dumps({
                    "schema": ce.POLICY_SCHEMA, "keep_last": 2,
                    "keep_status": ["fail"]}), encoding="utf-8")
                res = ce.gc()
                self.assertEqual(2, res["policy"]["keep_last"])
                self.assertEqual(["fail"], res["policy"]["keep_status"])
                # 3) 环境变量覆盖文件
                os.environ[ce.RETENTION_ENV] = json.dumps({
                    "schema": ce.POLICY_SCHEMA, "keep_last": 1,
                    "max_events": 3})
                res = ce.gc()
                self.assertEqual(1, res["policy"]["keep_last"])
                self.assertEqual(3, res["policy"]["max_events"])
                self.assertEqual(["fail"], res["policy"]["keep_status"])
                # 4) 显式参数覆盖环境变量
                res = ce.gc(keep_last=3, max_events=2, dry_run=False)
                self.assertEqual(3, res["policy"]["keep_last"])
                self.assertEqual(2, res["policy"]["max_events"])
                self.assertFalse(res["policy"]["dry_run"])
                # 5) config 路径（替代文件 tier），env 仍更高
                cfg = Path(tmp) / "my-policy.json"
                cfg.write_text(json.dumps({
                    "schema": ce.POLICY_SCHEMA, "keep_last": 5}),
                    encoding="utf-8")
                os.environ.pop(ce.RETENTION_ENV, None)
                res = ce.gc(config=cfg)
                self.assertEqual(5, res["policy"]["keep_last"])
                # config 替代文件 tier：未写的字段回落到内置默认
                self.assertEqual([], res["policy"]["keep_status"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old
                if old_env is None: os.environ.pop(ce.RETENTION_ENV, None)
                else: os.environ[ce.RETENTION_ENV] = old_env

    def test_retention_keep_status_keeps_whole_session(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                a = self._make_event("A", 1, status="pass", mtime=1000.0)
                b1 = self._make_event("B", 2, status="fail", mtime=1200.0)
                b2 = self._make_event("B", 3, status="pass", mtime=1200.0,
                                      prev=b1["digest"])
                c = self._make_event("C", 4, status="pass", mtime=2000.0)
                res = ce.gc(keep_last=1, keep_status=["fail"])
                # A 是旧会话且未被 keep_status/祖先命中 → 删
                self.assertIn(a["digest"], res["removed"])
                # B 会话因含 fail 整组保留（b1+b2 都留）
                self.assertIn(b1["digest"], res["kept"])
                self.assertIn(b2["digest"], res["kept"])
                # 最新会话 C 保留
                self.assertIn(c["digest"], res["kept"])
                self.assertTrue(res["dry_run"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_retention_max_events_truncation(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                # 三个独立会话；max_events=2 只留最新两个会话事件
                evs = [self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                       for i in range(3)]
                res = ce.gc(keep_last=3, max_events=2)
                self.assertEqual(2, len(res["kept"]))
                self.assertIn(evs[2]["digest"], res["kept"])   # 最新
                self.assertIn(evs[0]["digest"], res["removed"])  # 最旧
                self.assertEqual(2, res["policy"]["max_events"])
                # 单会话 prev 链：截断到最新 1 个后仍补回祖先
                a = self._make_event("X", 1, mtime=3000.0)
                b = self._make_event("X", 2, mtime=3001.0,
                                     prev=a["digest"])
                c = self._make_event("X", 3, mtime=3002.0,
                                     prev=b["digest"])
                res = ce.gc(keep_last=1, max_events=1)
                self.assertEqual({a["digest"], b["digest"], c["digest"]},
                                 set(res["kept"]))
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_retention_default_dry_run_keeps_files(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for i in range(3):
                    self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                events_dir = Path(tmp) / "events"
                before = sorted(p.name for p in events_dir.glob("*.json")
                                if p.name != ce.INDEX_NAME)
                res = ce.gc(keep_last=1)          # 不传 dry_run → 默认 True
                after = sorted(p.name for p in events_dir.glob("*.json")
                               if p.name != ce.INDEX_NAME)
                self.assertTrue(res["dry_run"])
                self.assertEqual(before, after)
                self.assertTrue(res["removed"])   # 有可删项但没删
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_retention_invalid_config(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        old_env = os.environ.get(ce.RETENTION_ENV)
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            os.environ.pop(ce.RETENTION_ENV, None)
            try:
                self._make_event("A", 1, mtime=1000.0)
                bad_configs = [
                    {"schema": "nf-other/1"},
                    {"keep_last": 0}, {"keep_last": -1},
                    {"keep_last": True}, {"keep_last": 2.5},
                    {"keep_status": "fail"}, {"keep_status": [1]},
                    {"keep_status": [""]},
                    {"max_events": 0}, {"dry_run": "yes"},
                    {"unknown_field": 1},
                ]
                for bad in bad_configs:
                    with self.assertRaises(ValueError, msg=repr(bad)):
                        ce.gc(config=bad)
                # 坏 JSON 配置文件
                bad_file = Path(tmp) / "bad-retention.json"
                bad_file.write_text("{bad", encoding="utf-8")
                with self.assertRaises(ValueError):
                    ce.gc(config=bad_file)
                # 坏 JSON 环境变量
                os.environ[ce.RETENTION_ENV] = "{bad"
                with self.assertRaises(ValueError):
                    ce.gc()
                # config 类型非法
                with self.assertRaises(ValueError):
                    ce.gc(config=123)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old
                if old_env is None: os.environ.pop(ce.RETENTION_ENV, None)
                else: os.environ[ce.RETENTION_ENV] = old_env

    def test_retention_dry_run_and_apply_idempotent(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for i in range(3):
                    self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                events_dir = Path(tmp) / "events"
                cfg = Path(tmp) / "retention.json"
                cfg.write_text(json.dumps({
                    "schema": ce.POLICY_SCHEMA, "keep_last": 1,
                    "dry_run": True}), encoding="utf-8")
                before = sorted(p.name for p in events_dir.glob("*.json")
                                if p.name != ce.INDEX_NAME)
                # 策略 dry_run=true：只算不删
                res = ce.gc(config=cfg)
                self.assertTrue(res["dry_run"])
                after = sorted(p.name for p in events_dir.glob("*.json")
                               if p.name != ce.INDEX_NAME)
                self.assertEqual(before, after)
                # 显式 dry_run=False 覆盖策略 → 真删 + 索引一致 + 幂等
                applied = ce.gc(config=cfg, dry_run=False)
                self.assertFalse(applied["dry_run"])
                self.assertEqual([], ce.verify_index())
                self.assertEqual(1, len(ce.query()))
                again = ce.gc(config=cfg, dry_run=False)
                self.assertEqual([], again["removed"])
                self.assertEqual([], ce.verify_index())
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def _audit_store(self, n=3):
        events_dir = Path(os.environ["NF_COCKPIT_HOME"]) / "events"
        for i in range(n):
            self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
        ce.rebuild_index()
        return events_dir

    def test_gc_audit_deterministic_and_idempotent(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                events_dir = self._audit_store()
                before = sorted(p.name for p in events_dir.glob("*.json"))
                first = ce.gc_audit()
                audit_dir = Path(tmp) / "audit"
                files = sorted(audit_dir.glob("*.json"))
                self.assertEqual(1, len(files))
                bytes_first = files[0].read_bytes()
                stat_first = files[0].stat().st_mtime_ns
                second = ce.gc_audit()
                self.assertEqual(first["digest"], second["digest"])
                self.assertEqual(1, len(list(audit_dir.glob("*.json"))))
                self.assertEqual(bytes_first, files[0].read_bytes())
                self.assertEqual(stat_first, files[0].stat().st_mtime_ns)
                # 审计不动真实库
                after = sorted(p.name for p in events_dir.glob("*.json"))
                self.assertEqual(before, after)
                self.assertEqual([], ce.verify_index())
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_schema_and_policy_digest(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._audit_store()
                audit = ce.gc_audit(config={"keep_last": 1})
                self.assertEqual(ce.AUDIT_SCHEMA, audit["schema"])
                self.assertEqual(ce.digest(audit["policy"]),
                                 audit["policy_digest"])
                self.assertTrue(audit["dry_run"])
                self.assertEqual(sorted(audit["kept"]), audit["kept"])
                self.assertEqual(sorted(audit["removed"]), audit["removed"])
                store_digests = sorted(
                    p.stem for p in (Path(tmp) / "events").glob("*.json")
                    if p.name != ce.INDEX_NAME)
                self.assertEqual(store_digests, audit["store_digests"])
                # 文件名 == digest
                path = Path(tmp) / "audit" / (audit["digest"] + ".json")
                self.assertTrue(path.is_file())
                other = ce.gc_audit(config={"keep_last": 3,
                                            "keep_status": ["pass"]})
                self.assertNotEqual(audit["digest"], other["digest"])
                self.assertNotEqual(audit["policy_digest"],
                                    other["policy_digest"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_canary_leaves_real_store_untouched(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                events_dir = self._audit_store()
                before = sorted(p.name for p in events_dir.glob("*.json"))
                audit = ce.gc_audit(config={"keep_last": 1}, canary=True)
                canary = audit["canary"]
                self.assertTrue(canary["applied"])
                self.assertTrue(canary["index_ok"])
                self.assertIn("removed", canary)
                after = sorted(p.name for p in events_dir.glob("*.json"))
                self.assertEqual(before, after)
                self.assertEqual([], ce.verify_index())
                self.assertTrue(any(Path(tmp).glob("canary-*/events")))
                # 影子库确实被 apply：影子事件数 == 审计 kept 数
                shadow = sorted(Path(tmp).glob("canary-*/events"))[0]
                shadow_events = [p for p in shadow.glob("*.json")
                                 if p.name != ce.INDEX_NAME]
                self.assertEqual(len(audit["kept"]), len(shadow_events))
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_canary_idempotent(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                events_dir = self._audit_store()
                before = sorted(p.name for p in events_dir.glob("*.json"))
                one = ce.gc_audit(config={"keep_last": 1}, canary=True)
                two = ce.gc_audit(config={"keep_last": 1}, canary=True)
                self.assertEqual(one["digest"], two["digest"])
                self.assertEqual(one["canary"]["kept"], two["canary"]["kept"])
                self.assertEqual(one["canary"]["removed"],
                                 two["canary"]["removed"])
                self.assertEqual(before,
                                 sorted(p.name for p in
                                        events_dir.glob("*.json")))
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_invalid_config(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._audit_store()
                for bad in ({"keep_last": 0}, {"keep_last": True},
                            {"unknown": 1}, {"schema": "x"}):
                    with self.assertRaises(ValueError, msg=repr(bad)):
                        ce.gc_audit(config=bad)
                with self.assertRaises(ValueError):
                    ce.gc_audit(canary="yes")
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_skips_event_scan(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._audit_store()
                count = len(ce.query())
                for keep in (1, 2, 3):
                    ce.gc_audit(config={"keep_last": keep})
                self.assertEqual(count, len(ce.query()))
                self.assertEqual([], ce.verify_index())
                self.assertEqual(3, len(ce.list_audits()))
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_list_audits_sorted_and_query_filters(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._audit_store()
                audits = [ce.gc_audit(config={"keep_last": k})
                          for k in (1, 2, 3)]
                digests = sorted(a["digest"] for a in audits)
                listed = [a["digest"] for a in ce.list_audits()]
                self.assertEqual(digests, listed)
                removed = [a for a in audits if a["removed"]]
                self.assertTrue(removed)
                target = audits[0]["policy_digest"]
                rows = ce.query_audits(policy_digest=target)
                self.assertEqual([a["digest"] for a in rows
                                  if a["policy_digest"] == target],
                                 [r["digest"] for r in rows])
                self.assertTrue(all(r["policy_digest"] == target
                                    for r in rows))
                has = ce.query_audits(has_removed=True)
                self.assertTrue(all(r["removed"] for r in has))
                no = ce.query_audits(has_removed=False)
                self.assertTrue(all(not r["removed"] for r in no))
                self.assertEqual(1, len(ce.query_audits(limit=1)))
                for bad in (0, 501, True):
                    with self.assertRaises(ValueError):
                        ce.query_audits(limit=bad)
                with self.assertRaises(ValueError):
                    ce.query_audits(has_removed="yes")
                with self.assertRaises(ValueError):
                    ce.query_audits(policy_digest="zz")
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_audit_summary_counts_and_empty(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                # 空库零值
                empty = ce.audit_summary()
                self.assertEqual(ce.AUDIT_SUMMARY_SCHEMA, empty["schema"])
                self.assertEqual(0, empty["total"])
                self.assertEqual({}, empty["by_policy_digest"])
                self.assertEqual(0, empty["total_removed"])
                self.assertEqual(0, empty["total_kept"])
                self.assertIsNone(empty["max_removed"])
                # 三条审计（不同策略）→ 计数与 max_removed 正确
                self._audit_store()
                audits = [ce.gc_audit(config={"keep_last": k})
                          for k in (1, 2, 3)]
                summary = ce.audit_summary()
                self.assertEqual(3, summary["total"])
                self.assertEqual(
                    sum(len(a["removed"]) for a in audits),
                    summary["total_removed"])
                self.assertEqual(
                    sum(len(a["kept"]) for a in audits),
                    summary["total_kept"])
                expected_max = max(audits,
                                   key=lambda a: (len(a["removed"]),
                                                  a["digest"]))
                self.assertEqual(expected_max["digest"],
                                 summary["max_removed"]["digest"])
                self.assertEqual(len(expected_max["removed"]),
                                 summary["max_removed"]["removed"])
                self.assertEqual(
                    {a["policy_digest"]: 1 for a in audits},
                    summary["by_policy_digest"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_audit_bad_files_fail_closed(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._audit_store()
                audit_dir = Path(tmp) / "audit"
                audit_dir.mkdir(parents=True)
                (audit_dir / ("a" * 64 + ".json")).write_text(
                    "{bad", encoding="utf-8")
                for fn in (ce.list_audits, ce.audit_summary, ce.query_audits):
                    with self.assertRaises(ValueError):
                        fn()
                (audit_dir / ("a" * 64 + ".json")).unlink()
                wrong = {"schema": "nf-other/1", "digest": "b" * 64}
                (audit_dir / ("b" * 64 + ".json")).write_text(
                    json.dumps(wrong), encoding="utf-8")
                with self.assertRaises(ValueError):
                    ce.list_audits()
                (audit_dir / ("b" * 64 + ".json")).unlink()
                name_mismatch = {"schema": ce.AUDIT_SCHEMA,
                                 "digest": "c" * 64}
                (audit_dir / ("d" * 64 + ".json")).write_text(
                    json.dumps(name_mismatch), encoding="utf-8")
                with self.assertRaises(ValueError):
                    ce.list_audits()
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def _alerts_store(self):
        self._audit_store()
        first = ce.gc_audit(config={"keep_last": 1})
        second = ce.gc_audit(config={"keep_last": 2})
        return first, second

    def test_audit_alerts_clean_by_default(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                # 空库 clean
                empty = ce.audit_anomalies()
                self.assertTrue(empty["clean"])
                self.assertEqual([], empty["findings"])
                self._alerts_store()
                alert = ce.audit_anomalies()
                self.assertEqual(ce.ALERT_REPORT_SCHEMA, alert["schema"])
                self.assertTrue(alert["clean"])
                self.assertEqual([], alert["findings"])
                self.assertIn("digest", alert)
                again = ce.audit_anomalies()
                self.assertEqual(alert["digest"], again["digest"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_audit_alerts_max_removed(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                first, _second = self._alerts_store()
                self.assertTrue(first["removed"])
                alert = ce.audit_anomalies(config={"max_removed": 0})
                self.assertFalse(alert["clean"])
                hits = [f for f in alert["findings"]
                        if f["kind"] == "max_removed"]
                self.assertTrue(hits)
                self.assertTrue(all(f["severity"] == "fail" for f in hits))
                self.assertIn(first["digest"],
                              [f["audit"] for f in hits])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_audit_alerts_removed_ratio_and_min_audits(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._alerts_store()
                alert = ce.audit_anomalies(
                    config={"max_removed_ratio": 0.0,
                            "min_audits_for_ratio": 1})
                kinds = [f["kind"] for f in alert["findings"]]
                self.assertIn("removed_ratio", kinds)
                # min_audits_for_ratio 提高后不再计算 ratio
                high = ce.audit_anomalies(
                    config={"max_removed_ratio": 0.0,
                            "min_audits_for_ratio": 99})
                self.assertNotIn("removed_ratio",
                                 [f["kind"] for f in high["findings"]])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_audit_alerts_policy_churn(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._alerts_store()
                alert = ce.audit_anomalies(
                    config={"max_policy_churn": 0})
                hits = [f for f in alert["findings"]
                        if f["kind"] == "policy_churn"]
                self.assertTrue(hits)
                self.assertFalse(alert["clean"])
                self.assertEqual("warn", hits[0]["severity"])
                self.assertIsNone(hits[0]["audit"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_audit_alerts_invalid_rules(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                bad_rules = [
                    {"schema": "nf-other/1"},
                    {"max_removed": -1}, {"max_removed": True},
                    {"max_removed": 1.5},
                    {"max_removed_ratio": 1.5}, {"max_removed_ratio": -0.1},
                    {"max_removed_ratio": "0.5"},
                    {"max_policy_churn": -1},
                    {"min_audits_for_ratio": -1},
                    {"unknown": 1},
                ]
                for bad in bad_rules:
                    with self.assertRaises(ValueError, msg=repr(bad)):
                        ce.audit_anomalies(config=bad)
                bad_file = Path(tmp) / "bad-alerts.json"
                bad_file.write_text("{bad", encoding="utf-8")
                with self.assertRaises(ValueError):
                    ce.audit_anomalies(config=bad_file)
                with self.assertRaises(ValueError):
                    ce.audit_anomalies(config=Path(tmp) / "missing.json")
                with self.assertRaises(ValueError):
                    ce.audit_anomalies(config=123)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_audit_alerts_deterministic_and_sorted(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._alerts_store()
                rules = {"max_removed": 0, "max_removed_ratio": 0.0,
                         "max_policy_churn": 0}
                one = ce.audit_anomalies(config=rules)
                two = ce.audit_anomalies(config=rules)
                self.assertEqual(one["digest"], two["digest"])
                self.assertFalse(one["clean"])
                kinds = [f["kind"] for f in one["findings"]]
                self.assertEqual(sorted(kinds), kinds)
                keys = [(f["kind"], str(f.get("audit") or ""))
                        for f in one["findings"]]
                self.assertEqual(sorted(keys), keys)
                self.assertNotIn("as_of", one)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_alert_record_idempotent(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._alerts_store()
                first = ce.record_alert_report()
                alerts_dir = Path(tmp) / "alerts"
                files = sorted(alerts_dir.glob("*.json"))
                self.assertEqual(1, len(files))
                bytes_first = files[0].read_bytes()
                stat_first = files[0].stat().st_mtime_ns
                second = ce.record_alert_report()
                self.assertEqual(first["digest"], second["digest"])
                self.assertEqual(1, len(list(alerts_dir.glob("*.json"))))
                self.assertEqual(bytes_first, files[0].read_bytes())
                self.assertEqual(stat_first, files[0].stat().st_mtime_ns)
                history = ce.audit_alert_history()
                self.assertEqual([first["digest"]],
                                 [r["digest"] for r in history])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_alert_history_sorted(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._alerts_store()
                clean = ce.record_alert_report()
                dirty = ce.record_alert_report(
                    config={"max_policy_churn": 0})
                self.assertNotEqual(clean["digest"], dirty["digest"])
                history = ce.audit_alert_history()
                self.assertEqual(sorted(r["digest"] for r in history),
                                 [r["digest"] for r in history])
                self.assertEqual(2, len(history))
                self.assertTrue(all(r["schema"] == ce.ALERT_REPORT_SCHEMA
                                    for r in history))
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_alert_trend_counts_and_deterministic(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._alerts_store()
                ce.record_alert_report()
                ce.record_alert_report(config={"max_policy_churn": 0})
                trend = ce.audit_alert_trend()
                self.assertEqual(ce.ALERT_TREND_SCHEMA, trend["schema"])
                self.assertEqual(2, trend["reports"])
                self.assertEqual(1, trend["clean"])
                self.assertEqual(1, trend["dirty"])
                self.assertEqual({"policy_churn": 1}, trend["by_kind"])
                self.assertEqual({"warn": 1}, trend["by_severity"])
                history = ce.audit_alert_history()
                self.assertEqual(history[-1]["digest"], trend["latest"])
                self.assertEqual(trend, ce.audit_alert_trend())
                self.assertNotIn("as_of", trend)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_alert_history_empty_store(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self.assertEqual([], ce.audit_alert_history())
                trend = ce.audit_alert_trend()
                self.assertEqual(0, trend["reports"])
                self.assertEqual(0, trend["clean"])
                self.assertEqual(0, trend["dirty"])
                self.assertEqual({}, trend["by_kind"])
                self.assertEqual({}, trend["by_severity"])
                self.assertIsNone(trend["latest"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_alert_history_bad_files_fail_closed(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._alerts_store()
                alerts_dir = Path(tmp) / "alerts"
                alerts_dir.mkdir(parents=True, exist_ok=True)
                (alerts_dir / ("a" * 64 + ".json")).write_text(
                    "{bad", encoding="utf-8")
                for fn in (ce.audit_alert_history, ce.audit_alert_trend):
                    with self.assertRaises(ValueError):
                        fn()
                (alerts_dir / ("a" * 64 + ".json")).unlink()
                wrong = {"schema": "nf-other/1", "digest": "b" * 64}
                (alerts_dir / ("b" * 64 + ".json")).write_text(
                    json.dumps(wrong), encoding="utf-8")
                with self.assertRaises(ValueError):
                    ce.audit_alert_history()
                (alerts_dir / ("b" * 64 + ".json")).unlink()
                mismatch = {"schema": ce.ALERT_REPORT_SCHEMA,
                            "digest": "c" * 64}
                (alerts_dir / ("d" * 64 + ".json")).write_text(
                    json.dumps(mismatch), encoding="utf-8")
                with self.assertRaises(ValueError):
                    ce.audit_alert_history()
                with self.assertRaises(ValueError):
                    ce.record_alert_report(config={"max_removed": -1})
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_evidence_roles_whitelist(self):
        # 合法：白名单三键 + 非负整数
        roles = {"local-trusted": 1, "derived": 1,
                 "external-advisory": 1}
        self.assertEqual(roles, ce.validate_roles(roles))
        ev = ce.build(MANIFEST, JOURNAL, evidence_roles=roles)
        self.assertEqual(roles, ev["evidence_roles"])
        self.assertEqual([], ce.verify(ev))
        # 非法：未知键 / 负数 / bool / 浮点 / 字符串 / 非 dict
        bad_cases = [
            {"unknown": "derived"},
            {"event_a": "derived", "notes": "trusted"},   # 未知值域
            {"event_a": -1},
            {"event_a": True},
            {"event_a": 1.5},
            {"event_a": "1"},
            ["local-trusted"],
            "local-trusted",
        ]
        for bad in bad_cases:
            with self.assertRaises(ValueError, msg=repr(bad)):
                ce.validate_roles(bad)
            if isinstance(bad, dict):
                # 非空 dict 在 build 落键前校验，非法直接 ValueError
                with self.assertRaises(ValueError, msg=repr(bad)):
                    ce.build(MANIFEST, JOURNAL, evidence_roles=bad)
            else:
                # 非 dict 与缺省同语义：不加键、旧 digest 不变
                ev2 = ce.build(MANIFEST, JOURNAL, evidence_roles=bad)
                self.assertNotIn("evidence_roles", ev2)
                self.assertEqual(ce.build(MANIFEST, JOURNAL)["digest"],
                                 ev2["digest"])

    def test_event_index_rebuild_and_verify(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev_a = ce.build(MANIFEST, JOURNAL, session_id="A")
                ev_b = ce.build(MANIFEST, JOURNAL, session_id="B")
                ev_b["prev"] = ev_a["digest"]
                ev_b["digest"] = ce.digest(
                    {k: v for k, v in ev_b.items() if k != "digest"})
                ce.write(ev_a)
                ce.write(ev_b)
                index_path = Path(tmp) / "events" / ce.INDEX_NAME
                self.assertTrue(index_path.is_file())
                self.assertEqual([], ce.verify_index())
                index = ce.build_index()
                self.assertEqual(ce.INDEX_SCHEMA, index["schema"])
                self.assertEqual(sorted([ev_a["digest"], ev_b["digest"]]),
                                 index["digests"])
                self.assertEqual(["A", "B"], sorted(index["sessions"]))
                self.assertEqual([ev_a["digest"]],
                                 index["sessions"]["A"]["events"])
                self.assertEqual(
                    [ev_a["digest"], ev_b["digest"]],
                    index["sessions"]["B"]["prev_chain"])
                # 幂等：两次重建字节相同
                first = index_path.read_bytes()
                ce.rebuild_index()
                second = index_path.read_bytes()
                ce.rebuild_index()
                self.assertEqual(first, second)
                self.assertEqual(first, index_path.read_bytes())
                self.assertNotIn(b"2026-", first)   # 无时间戳
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_event_index_prev_cycle_is_terminating(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev_a = ce.build(MANIFEST, JOURNAL, session_id="A")
                # 同会话但内容不同（turns 不同 → digest 不同），才能构造互指环
                ev_b = ce.build(dict(MANIFEST, turns=3), JOURNAL,
                                session_id="A")
                # 构造互相指向的坏链（确定性索引仍须收敛，不得死循环）
                ev_a["prev"] = ev_b["digest"]
                ev_b["prev"] = ev_a["digest"]
                for ev in (ev_a, ev_b):
                    ev["digest"] = ce.digest(
                        {k: v for k, v in ev.items() if k != "digest"})
                    ce.write(ev)
                index = ce.rebuild_index()
                self.assertEqual(sorted([ev_a["digest"], ev_b["digest"]]),
                                 index["digests"])
                self.assertTrue(index["sessions"]["A"]["prev_chain"])
                self.assertEqual([], ce.verify_index())
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_event_index_tamper_detected(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                ev = ce.build(MANIFEST, JOURNAL, session_id="A")
                ce.write(ev)
                events = Path(tmp) / "events"
                index_path = events / ce.INDEX_NAME
                raw = json.loads(index_path.read_text(encoding="utf-8"))
                # 1) 缺条目
                broken = json.loads(json.dumps(raw))
                broken["digests"] = []
                index_path.write_text(json.dumps(broken), encoding="utf-8")
                self.assertTrue(ce.verify_index())
                # 2) session 被改
                broken = json.loads(json.dumps(raw))
                broken["sessions"]["Z"] = broken["sessions"].pop("A")
                index_path.write_text(json.dumps(broken), encoding="utf-8")
                self.assertTrue(ce.verify_index())
                # 3) 坏 JSON
                index_path.write_text("{bad", encoding="utf-8")
                self.assertTrue(ce.verify_index())
                # 4) 索引缺失
                index_path.unlink()
                self.assertTrue(ce.verify_index())
                ce.rebuild_index()
                self.assertEqual([], ce.verify_index())
                # 5) 目录多余事件文件（文件名=digest 合法，但索引不含）
                extra = {"schema": ce.SCHEMA, "digest": "f" * 64,
                         "session_id": "A"}
                extra["digest"] = ce.digest(
                    {k: v for k, v in extra.items() if k != "digest"})
                (events / (extra["digest"] + ".json")).write_text(
                    json.dumps(extra), encoding="utf-8")
                self.assertTrue(ce.verify_index())
                (events / (extra["digest"] + ".json")).unlink()
                # 6) 坏事件文件（不是合法 JSON）
                (events / ("c" * 64 + ".json")).write_text("{bad",
                                                           encoding="utf-8")
                issues = ce.verify_index()
                self.assertTrue(any("不是合法 JSON" in i for i in issues),
                                issues)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_deterministic_and_idempotent(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for i in range(3):
                    self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                a1 = ce.gc_audit()
                a2 = ce.gc_audit()
                self.assertEqual("nf-cognition-gc-audit/1", a1["schema"])
                self.assertIn("policy_digest", a1)
                self.assertIsInstance(a1["removed"], list)
                self.assertTrue(a1["dry_run"])
                self.assertEqual(a1["digest"], a2["digest"])
                audits = list((Path(tmp) / "audit").glob("*.json"))
                self.assertEqual(1, len(audits), audits)
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_does_not_touch_live_store(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for i in range(3):
                    self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                events = Path(tmp) / "events"
                before = sorted(p.name for p in events.glob("*.json")
                                if p.name != ce.INDEX_NAME)
                audit = ce.gc_audit(config={"keep_last": 1})
                after = sorted(p.name for p in events.glob("*.json")
                               if p.name != ce.INDEX_NAME)
                self.assertEqual(before, after)
                self.assertTrue(audit["removed"])   # 有可删项但未删
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_canary_never_deletes_live(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for i in range(3):
                    self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                events = Path(tmp) / "events"
                before = sorted(p.name for p in events.glob("*.json")
                                if p.name != ce.INDEX_NAME)
                audit = ce.gc_audit(config={"keep_last": 1}, canary=True)
                canary = audit["canary"]
                self.assertTrue(canary["applied"])
                self.assertTrue(canary["index_ok"])
                after = sorted(p.name for p in events.glob("*.json")
                               if p.name != ce.INDEX_NAME)
                self.assertEqual(before, after)
                self.assertTrue(any(Path(tmp).glob("canary-*")))
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_invalid_config_and_canary(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                self._make_event("A", 1, mtime=1000.0)
                with self.assertRaises(ValueError):
                    ce.gc_audit(config={"keep_last": 0})
                with self.assertRaises(ValueError):
                    ce.gc_audit(canary="yes")
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_policy_digest_tracks_config(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for i in range(3):
                    self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                a = ce.gc_audit(config={"keep_last": 1})
                b = ce.gc_audit(config={"keep_last": 2})
                self.assertNotEqual(a["policy_digest"], b["policy_digest"])
                self.assertNotEqual(a["digest"], b["digest"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_gc_audit_after_apply_removed_empty(self):
        old = os.environ.get("NF_COCKPIT_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NF_COCKPIT_HOME"] = tmp
            try:
                for i in range(3):
                    self._make_event("S%d" % i, i + 1, mtime=1000.0 + i)
                ce.gc(keep_last=1, dry_run=False)
                self.assertEqual([], ce.verify_index())
                audit = ce.gc_audit(config={"keep_last": 1})
                self.assertEqual([], audit["removed"])
            finally:
                if old is None: os.environ.pop("NF_COCKPIT_HOME", None)
                else: os.environ["NF_COCKPIT_HOME"] = old

    def test_bad_manifest_rejected(self):
        with self.assertRaises(ValueError):
            ce.build({"schema": "x"})
