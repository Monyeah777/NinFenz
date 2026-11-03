"""M1 端到端演练脚本（scripts/m1_e2e.py）的回归测试。

作者：impl（DSH agent）· 2026-11-02
运行：cd <repo> && python3 -m unittest desktop.tests.test_m1_e2e -v

覆盖（双会话 prev 链 + 证据角色白名单 + card digest + 跨目录事件库 + 索引）：
- run 一次 → 同 work 上 check 两次，report.json / stdout 逐字节相同且 rc=0；
- 16 项 checks：receipt/anchor/event/chain/artifact/card/card_digest/
  roles_card/roles_receipt/roles_valid/index/query/gc_dry/gc_apply/gate/
  ledger；
- 失败面：篡改 artifact、篡改 eventB.prev、删事件库、action 缺 card: 证据、
  篡改 card 内容、篡改 receipt.roles、篡改 card.roles → check FAIL；
- 外部 --event-store：run 后把 W 整体搬走，check 指原事件库仍 PASS。
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "m1_e2e.py"
CHECK_IDS = ["receipt", "anchor", "event", "chain", "artifact", "card",
             "card_digest", "roles_card", "roles_receipt", "roles_valid",
             "index", "query", "gc_dry", "gc_apply", "gate", "ledger"]
ROLES_B = {"local-trusted": 1, "derived": 2, "external-advisory": 0}


def _run(*args, timeout=900):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=str(ROOT),
        capture_output=True, text=True, timeout=timeout)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path, obj):
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def _load_module():
    spec = importlib.util.spec_from_file_location("m1_e2e_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _drop_index_digest(path, digest):
    """从 index.json（dict/list 两种形状）里删掉某个 digest 条目。"""
    data = _load(path)

    def keep(item):
        value = item if isinstance(item, str) else (
            item.get("digest") or item.get("id"))
        return value != digest

    if isinstance(data, dict):
        for key in ("digests", "events", "items", "entries"):
            if isinstance(data.get(key), list):
                data[key] = [x for x in data[key] if keep(x)]
                break
    elif isinstance(data, list):
        data = [x for x in data if keep(x)]
    _write_json(path, data)


def _seal_receipt(path):
    """改完 receipt 字段后按脚本同规则重算 digest（便于测单项校验）。"""
    receipt = _load(path)
    body = {k: v for k, v in receipt.items() if k != "digest"}
    receipt["digest"] = hashlib.sha256(json.dumps(
        body, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    _write_json(path, receipt)


class M1E2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="nf-m1-test-"))
        cls.work = cls.root / "w1"
        cls.run_proc = _run("run", "--work", str(cls.work))
        if cls.run_proc.returncode != 0:
            raise AssertionError(
                "m1 run 失败 rc=%d\nstdout=%s\nstderr=%s"
                % (cls.run_proc.returncode, cls.run_proc.stdout[-800:],
                   cls.run_proc.stderr[-1200:]))
        cls.receipt = _load(cls.work / "receipt.json")
        # 外部事件库固定夹具（多个跨目录用例复用，避免每次重跑 cockpit）
        cls.ext_store = cls.root / "shared-events"
        cls.ext_work = cls.root / "ext-w"
        cls.ext_proc = _run("run", "--work", str(cls.ext_work),
                            "--event-store", str(cls.ext_store))
        if cls.ext_proc.returncode != 0:
            raise AssertionError(
                "m1 run(外置 store) 失败 rc=%d\nstderr=%s"
                % (cls.ext_proc.returncode, cls.ext_proc.stderr[-1200:]))
        cls.ext_receipt = _load(cls.ext_work / "receipt.json")
        # 外锚（HMAC）固定夹具：key 在 W 之外
        cls.anchor_key = cls.root / "anchor.key"
        cls.anchor_key.write_bytes(b"nf-m1-test-anchor-key-0123456789")
        cls.anchor_work = cls.root / "anchor-w"
        cls.anchor_proc = _run("run", "--work", str(cls.anchor_work),
                               "--anchor-key", str(cls.anchor_key))
        if cls.anchor_proc.returncode != 0:
            raise AssertionError(
                "m1 run(带 anchor) 失败 rc=%d\nstderr=%s"
                % (cls.anchor_proc.returncode,
                   cls.anchor_proc.stderr[-1200:]))
        cls.anchor_receipt = _load(cls.anchor_work / "receipt.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.root), ignore_errors=True)

    def _check(self, work, store=""):
        args = ["check", "--work", str(work)]
        if store:
            args += ["--event-store", str(store)]
        proc = _run(*args)
        report = _load(Path(work) / "report.json")
        return proc, report

    def _clone(self, name):
        dst = self.root / name
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(self.work), str(dst))
        return dst

    def _event_path(self, work, digest):
        return work / "cockpit" / "events" / (digest + ".json")

    def _copy_work(self, name, src=None):
        dst = self.root / name
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(src or self.ext_work), str(dst))
        return dst

    def _copy_tree(self, name, src):
        dst = self.root / name
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(src), str(dst))
        return dst

    def _copy_store(self, name):
        dst = self.root / name
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(self.ext_store), str(dst))
        return dst

    # ------------------------------------------------------- run 产物
    def test_run_creates_receipt_and_report(self):
        for name in ("artifact.md", "card.json", "receipt.json",
                     "report.json", "journal_a.json", "manifest_a.json",
                     "event_a.json", "journal_b.json", "manifest_b.json",
                     "event_b.json"):
            self.assertTrue((self.work / name).is_file(), name)
        r = self.receipt
        self.assertEqual(r["schema"], "nf-m1-receipt/1")
        body = {k: v for k, v in r.items() if k != "digest"}
        want = hashlib.sha256(json.dumps(
            body, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(r["digest"], want)
        for key in ("artifact_sha256", "card_digest", "event_a_digest",
                    "event_b_digest", "event_b_prev"):
            self.assertEqual(len(r[key]), 64, key)
        self.assertEqual(r["gate"]["rc"], 0)
        self.assertEqual(r["gate"]["verdict"], "PASS")
        self.assertEqual(len(r["ledger_evidence"]), 3)
        self.assertEqual(r["roles"], ROLES_B)
        self.assertEqual(r["event_store"], "cockpit")   # 相对 W
        report = _load(self.work / "report.json")
        self.assertEqual(report["schema"], "nf-m1-report/1")
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["receipt_digest"], r["digest"])
        self.assertEqual([c["id"] for c in report["checks"]], CHECK_IDS)

    def test_chain_recorded(self):
        r = self.receipt
        self.assertEqual(r["event_b_prev"], r["event_a_digest"])
        a = _load(self._event_path(self.work, r["event_a_digest"]))
        b = _load(self._event_path(self.work, r["event_b_digest"]))
        self.assertEqual(a["digest"], r["event_a_digest"])
        self.assertEqual(b["digest"], r["event_b_digest"])
        self.assertEqual(b["prev"], a["digest"])

    def test_roles_recorded(self):
        r = self.receipt
        a = _load(self._event_path(self.work, r["event_a_digest"]))
        b = _load(self._event_path(self.work, r["event_b_digest"]))
        self.assertEqual(a["evidence_roles"],
                         {"local-trusted": 2, "derived": 1,
                          "external-advisory": 0})
        self.assertEqual(b["evidence_roles"], ROLES_B)
        card = _load(self.work / "card.json")
        self.assertEqual(card["cognition"]["evidence_roles"], ROLES_B)

    def test_report_and_receipt_use_relative_paths(self):
        for name in ("receipt.json", "report.json"):
            text = (self.work / name).read_text(encoding="utf-8")
            self.assertNotIn(str(self.work), text, name)
            self.assertNotIn(str(self.root), text, name)

    # ------------------------------------------------------- check 通过
    def test_check_pass(self):
        proc, report = self._check(self.work)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual([c["id"] for c in report["checks"]], CHECK_IDS)
        self.assertTrue(all(c["ok"] for c in report["checks"]))
        self.assertEqual(json.loads(proc.stdout), report)

    def test_check_replay_byte_identical(self):
        proc1 = _run("check", "--work", str(self.work))
        self.assertEqual(proc1.returncode, 0, proc1.stderr)
        b1 = (self.work / "report.json").read_bytes()
        proc2 = _run("check", "--work", str(self.work))
        self.assertEqual(proc2.returncode, 0, proc2.stderr)
        self.assertEqual(b1, (self.work / "report.json").read_bytes())
        self.assertEqual(proc1.stdout, proc2.stdout)

    def test_run_report_matches_check_report(self):
        run_bytes = (self.work / "report.json").read_bytes()
        proc = _run("check", "--work", str(self.work))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(run_bytes, (self.work / "report.json").read_bytes())

    # ------------------------------------------------------- 失败面
    def test_tampered_artifact_fails(self):
        work = self._clone("tamper-artifact")
        artifact = work / "artifact.md"
        artifact.write_text(artifact.read_text(encoding="utf-8")
                            + "\n篡改追加。\n", encoding="utf-8")
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["artifact"])
        self.assertFalse(checks["card"])
        self.assertFalse(checks["gate"])

    def test_tampered_prev_fails(self):
        work = self._clone("tamper-prev")
        path = self._event_path(work, self.receipt["event_b_digest"])
        event = _load(path)
        event["prev"] = "0" * 64
        _write_json(path, event)
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["chain"])

    def test_deleted_store_events_fail(self):
        work = self._clone("deleted-events")
        for path in (work / "cockpit" / "events").glob("*.json"):
            path.unlink()
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["event"])
        self.assertFalse(checks["chain"])

    def test_action_missing_card_evidence_fails(self):
        work = self._clone("no-card-evidence")
        log = work / "cockpit" / "decisions.jsonl"
        rows = [json.loads(line) for line in
                log.read_text(encoding="utf-8").splitlines() if line.strip()]
        for rec in rows:
            if rec.get("id") == self.receipt["ledger_action_id"]:
                rec["evidence"] = [e for e in rec.get("evidence") or []
                                   if not e.startswith("card:")]
        log.write_text("\n".join(json.dumps(r, ensure_ascii=False,
                                            sort_keys=True)
                                 for r in rows) + "\n", encoding="utf-8")
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["ledger"])

    def test_ledger_wrong_card_digest_fails(self):
        work = self._clone("wrong-card-digest")
        log = work / "cockpit" / "decisions.jsonl"
        rows = [json.loads(line) for line in
                log.read_text(encoding="utf-8").splitlines() if line.strip()]
        for rec in rows:
            if rec.get("id") == self.receipt["ledger_action_id"]:
                rec["evidence"] = [("card:" + "f" * 64)
                                   if e.startswith("card:") else e
                                   for e in rec.get("evidence") or []]
        log.write_text("\n".join(json.dumps(r, ensure_ascii=False,
                                            sort_keys=True)
                                 for r in rows) + "\n", encoding="utf-8")
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["ledger"])
        self.assertTrue(checks["card"])
        self.assertTrue(checks["card_digest"])

    def test_receipt_missing_roles_fails(self):
        work = self._clone("no-roles")
        receipt = _load(work / "receipt.json")
        receipt.pop("roles", None)
        _write_json(work / "receipt.json", receipt)
        _seal_receipt(work / "receipt.json")
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["roles_receipt"])
        self.assertTrue(checks["roles_card"])

    def test_card_bad_json_fails(self):
        work = self._clone("bad-card-json")
        (work / "card.json").write_text("{oops", encoding="utf-8")
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["card"])
        self.assertFalse(checks["card_digest"])

    def test_card_content_changed_fails(self):
        work = self._clone("changed-card")
        card = _load(work / "card.json")
        card["note"] = "tampered"
        _write_json(work / "card.json", card)
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["card_digest"])

    def test_tampered_roles_receipt_fails(self):
        work = self._clone("tamper-roles-receipt")
        receipt = _load(work / "receipt.json")
        receipt["roles"] = {"local-trusted": 0, "derived": 0,
                            "external-advisory": 0}
        _write_json(work / "receipt.json", receipt)
        _seal_receipt(work / "receipt.json")
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["roles_receipt"])
        self.assertTrue(checks["roles_card"])

    def test_card_roles_changed_fails(self):
        work = self._clone("changed-card-roles")
        card = _load(work / "card.json")
        card["cognition"]["evidence_roles"] = {"local-trusted": 9,
                                               "derived": 9,
                                               "external-advisory": 9}
        _write_json(work / "card.json", card)
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["roles_card"])

    # ------------------------------------------------------- roles 白名单
    def test_invalid_role_key_fails_run(self):
        mod = _load_module()
        old = mod.ROLES_A
        try:
            mod.ROLES_A = {"local-trust": 2, "derived": 1,
                           "external-advisory": 0}
            err = io.StringIO()
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(err):
                rc = mod.run_workflow(str(Path(td) / "w"))
            self.assertEqual(rc, 2)
            self.assertIn("修复指引", err.getvalue())
            self.assertIn("local-trust", err.getvalue())
        finally:
            mod.ROLES_A = old

    def test_negative_role_value_fails_run(self):
        mod = _load_module()
        old_b = mod.ROLES_B
        try:
            mod.ROLES_B = {"local-trusted": -1, "derived": 2,
                           "external-advisory": 0}
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()):
                rc = mod.run_workflow(str(Path(td) / "w"))
            self.assertEqual(rc, 2)
        finally:
            mod.ROLES_B = old_b

    def test_all_zero_roles_fails_run(self):
        mod = _load_module()
        old_a = mod.ROLES_A
        try:
            mod.ROLES_A = {"local-trusted": 0, "derived": 0,
                           "external-advisory": 0}
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()):
                rc = mod.run_workflow(str(Path(td) / "w"))
            self.assertEqual(rc, 2)
        finally:
            mod.ROLES_A = old_a

    def test_roles_valid_rejects_zero_receipt_roles(self):
        work = self._clone("zero-roles")
        receipt = _load(work / "receipt.json")
        receipt["roles"] = {"local-trusted": 0, "derived": 0,
                            "external-advisory": 0}
        _write_json(work / "receipt.json", receipt)
        _seal_receipt(work / "receipt.json")
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["roles_valid"])
        self.assertFalse(checks["roles_receipt"])

    # ------------------------------------------------------- 事件库索引
    def test_tampered_index_fails(self):
        work = self._clone("tampered-index")
        index = work / "cockpit" / "events" / "index.json"
        self.assertTrue(index.is_file())
        _drop_index_digest(index, self.receipt["event_a_digest"])
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["index"])
        self.assertTrue(checks["event"])
        self.assertTrue(checks["chain"])

    def test_missing_index_fails(self):
        work = self._clone("missing-index")
        (work / "cockpit" / "events" / "index.json").unlink()
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["index"])

    # ------------------------------------------------------- 查询 / GC
    def test_report_has_sixteen_checks_and_gc_checks_pass(self):
        report = _load(self.work / "report.json")
        self.assertEqual(len(report["checks"]), 16)
        self.assertEqual([c["id"] for c in report["checks"]], CHECK_IDS)
        checks = {c["id"]: c for c in report["checks"]}
        for cid in ("query", "gc_dry", "gc_apply"):
            self.assertTrue(checks[cid]["ok"], cid)
        self.assertTrue(all(checks[cid]["ok"] for cid in CHECK_IDS))
        self.assertEqual(checks["anchor"]["detail"], "no-anchor")
        self.assertFalse((self.work / "gc-probe").exists())

    def test_gc_probe_leaves_no_residue(self):
        self.assertFalse((self.work / "gc-probe").exists())
        proc = _run("check", "--work", str(self.work))
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertFalse((self.work / "gc-probe").exists())

    def test_deleted_event_a_makes_query_fail(self):
        work = self._clone("query-deleted-a")
        (self._event_path(work, self.receipt["event_a_digest"])).unlink()
        proc, report = self._check(work)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["query"])
        self.assertFalse(checks["event"])
        self.assertFalse(checks["chain"])

    # ------------------------------------------------------- 外锚（HMAC）
    def test_anchor_receipt_and_report(self):
        receipt = self.anchor_receipt
        anchor = receipt.get("anchor")
        self.assertIsInstance(anchor, dict)
        self.assertEqual(anchor.get("scheme"), "hmac-sha256")
        self.assertEqual(len(anchor.get("mac") or ""), 64)
        self.assertEqual(len(anchor.get("key_id") or ""), 16)
        report = _load(self.anchor_work / "report.json")
        self.assertEqual(report["verdict"], "PASS")
        checks = {c["id"]: c for c in report["checks"]}
        self.assertTrue(checks["receipt"]["ok"])
        self.assertTrue(checks["anchor"]["ok"])

    def test_anchor_check_pass_with_key(self):
        proc = _run("check", "--work", str(self.anchor_work),
                    "--anchor-key", str(self.anchor_key))
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        report = _load(self.anchor_work / "report.json")
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual([c["id"] for c in report["checks"]], CHECK_IDS)

    def test_anchor_tampered_mac_fails(self):
        work = self._copy_tree("anchor-tampered", self.anchor_work)
        receipt = _load(work / "receipt.json")
        receipt["anchor"]["mac"] = "0" * 64
        _write_json(work / "receipt.json", receipt)
        _seal_receipt(work / "receipt.json")     # receipt 自证仍通过
        proc = _run("check", "--work", str(work),
                    "--anchor-key", str(self.anchor_key))
        self.assertEqual(proc.returncode, 1)
        report = _load(work / "report.json")
        checks = {c["id"]: c for c in report["checks"]}
        self.assertTrue(checks["receipt"]["ok"])
        self.assertFalse(checks["anchor"]["ok"])

    def test_anchor_missing_key_fails(self):
        work = self._copy_tree("anchor-no-key", self.anchor_work)
        proc = _run("check", "--work", str(work))
        self.assertEqual(proc.returncode, 1)
        report = _load(work / "report.json")
        checks = {c["id"]: c for c in report["checks"]}
        self.assertFalse(checks["anchor"]["ok"])
        self.assertIn("anchor-key", checks["anchor"]["detail"])

    def test_anchor_key_inside_work_rejected(self):
        work = self.root / "inside-w"
        work.mkdir(exist_ok=True)
        key = work / "k.bin"
        key.write_bytes(b"x" * 32)
        proc = _run("run", "--work", str(work), "--anchor-key", str(key))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("work 目录内", proc.stderr)
        proc2 = _run("check", "--work", str(work), "--anchor-key", str(key))
        self.assertEqual(proc2.returncode, 2)

    # ------------------------------------------------------- 环境变量
    def test_env_scope_restores_variable(self):
        spec = importlib.util.spec_from_file_location("m1_e2e_mod", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        old = os.environ.get("NF_COCKPIT_HOME")
        sentinel = "/tmp/nf-m1-env-sentinel"
        os.environ["NF_COCKPIT_HOME"] = sentinel
        try:
            with tempfile.TemporaryDirectory() as td:
                with mod._env_home(td):
                    self.assertEqual(os.environ["NF_COCKPIT_HOME"],
                                     str(Path(td)))
                self.assertEqual(os.environ["NF_COCKPIT_HOME"], sentinel)
        finally:
            if old is None:
                os.environ.pop("NF_COCKPIT_HOME", None)
            else:
                os.environ["NF_COCKPIT_HOME"] = old

    # ------------------------------------------------------- 跨目录事件库
    def test_external_event_store_survives_work_copy(self):
        work = self._copy_work("ext-copy")
        receipt = self.ext_receipt
        self.assertEqual(receipt["event_store"], "../shared-events")
        self.assertNotIn(str(self.ext_store),
                         (work / "receipt.json").read_text(
                             encoding="utf-8"))
        self.assertTrue((self.ext_store / "events"
                         / (receipt["event_a_digest"] + ".json")).is_file())
        proc, report = self._check(work, self.ext_store)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(all(c["ok"] for c in report["checks"]))

    def test_mirror_events_not_authoritative(self):
        """删掉 W/cockpit 镜像事件，check 带外部 --event-store 仍 PASS。"""
        work = self._copy_work("ext-mirror-deleted")
        for path in (work / "cockpit" / "events").glob("*.json"):
            path.unlink()
        proc, report = self._check(work, self.ext_store)
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(all(c["ok"] for c in report["checks"]))

    def test_external_store_bad_event_json_fails(self):
        store = self._copy_store("bad-store")
        digest = self.ext_receipt["event_a_digest"]
        (store / "events" / (digest + ".json")).write_text(
            "{broken json", encoding="utf-8")
        work = self._copy_work("ext-bad-store")
        proc, report = self._check(work, store)
        self.assertEqual(proc.returncode, 1)
        checks = {c["id"]: c["ok"] for c in report["checks"]}
        self.assertFalse(checks["event"])
        self.assertFalse(checks["chain"])

    def test_external_store_copy_without_flag_actual(self):
        """如实断言实现行为：不传 --event-store 时回退 W/cockpit 镜像 → PASS。"""
        work = self._copy_work("ext-nostore")
        proc, report = self._check(work)          # 不带 --event-store
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(all(c["ok"] for c in report["checks"]))

    # ------------------------------------------------------- 可选：新目录
    def test_second_work_dir_run_and_check_ok(self):
        work = self.root / "w2"
        proc = _run("run", "--work", str(work))
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        proc2 = _run("check", "--work", str(work))
        self.assertEqual(proc2.returncode, 0, proc2.stderr[-800:])
        self.assertEqual(_load(work / "report.json")["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
