"""Batch A 覆盖节点：claim / budget / migration / audit / trust。"""

from __future__ import annotations

import hashlib

from conftest import run_core_raw


def _ok(core, op, req):
    code, out, err = run_core_raw(core, op, req)
    assert code == 0, (op, out[:500], err[:500])
    import json
    return json.loads(out)["result"]


def _err(core, op, req, expected):
    code, out, err = run_core_raw(core, op, req)
    assert code != 0, (op, out[:500])
    import json
    env = json.loads(out)
    assert env["error"]["code"] == expected, env


def test_claim_add_and_verify_tamper(core):
    req = {
        "created_at": "2026-01-01T00:00:00Z",
        "ledger_id": "demo",
        "claim": {"id": "c1", "statement": "s", "status": "verified", "evidence_sha256": "0" * 64, "source": "test"},
    }
    res = _ok(core, "claim-add", req)
    ledger = res["ledger"]
    assert ledger["ledger_sha256"] != "0" * 64
    ok = _ok(core, "claim-verify", {"ledger": ledger})
    assert ok["ok"] is True
    ledger["claims"][0]["statement"] = "tampered"
    code, out, _ = run_core_raw(core, "claim-verify", {"ledger": ledger})
    assert code == 1
    assert "ledger_sha256" in out.decode()


def test_budget_fail_and_warn(core):
    base = {"schema": "nf-budget/1", "name": "x", "limits": {"seconds": 1, "peak_mb": 1, "pages": 1, "blocks": 1}, "observed": {"seconds": 2, "peak_mb": 2, "pages": 2, "blocks": 2}, "ok": False, "policy": "fail"}
    code, out, _ = run_core_raw(core, "budget-check", {"budget": base})
    assert code == 1
    base["policy"] = "warn"
    res = _ok(core, "budget-check", {"budget": base})
    assert res["ok"] is False and res["violations"]


def test_migration_nf_doc_to_sdir(core):
    doc = {"schema": "nf-doc/1", "meta": {"title": "T", "sources": []}, "blocks": [{"id": "b1", "type": "paragraph", "text": "hello"}]}
    plan = _ok(core, "migrate-plan", {"from_schema": "nf-doc/1", "to_schema": "nf-sdir/1"})["plan"]
    code, out, _ = run_core_raw(core, "migrate-apply", {"plan": plan, "doc": doc, "created_at": "2026-01-01T00:00:00Z"})
    assert code != 0
    res = _ok(core, "migrate-apply", {"plan": plan, "doc": doc, "created_at": "2026-01-01T00:00:00Z", "confirm": True})
    assert res["sdir"]["schema"] == "nf-sdir/1"


def test_audit_chain_and_tamper(core):
    audit = None
    for i in range(3):
        req = {"at": f"2026-01-0{i+1}T00:00:00Z", "actor": "test", "action": "build", "subject_sha256": "0" * 64}
        if audit:
            req["audit"] = audit
        audit = _ok(core, "audit-append", req)["audit"]
    assert _ok(core, "audit-verify", {"audit": audit})["ok"] is True
    audit["records"][1]["action"] = "tampered"
    code, out, _ = run_core_raw(core, "audit-verify", {"audit": audit})
    assert code == 1




def _sdir(core):
    return _ok(core, "sdir-import", {"markdown": "# T\n\n## A\n\n| K | V |\n|---|---|\n| a | 1 |\n", "created_at": "2026-01-01T00:00:00Z", "lang": "en"})


def test_fidelity_and_a11y_reports(core):
    s = _sdir(core)
    f = _ok(core, "report-fidelity", {"sdir": s})
    assert f["kind"] == "fidelity"
    a = _ok(core, "report-a11y", {"sdir": s})
    assert a["kind"] == "a11y" and a["ok"] is True


def test_extension_verify_apply(core):
    m = {"schema": "nf-extension/1", "id": "theme-a", "type": "theme",
         "compat": {"min_app_version": "0.2.0", "schema_version": "nf-extension/1"},
         "capabilities": ["theme"], "config": {"accent": "#123456"}}
    assert _ok(core, "extension-verify", {"manifest": m, "strict": False})["ok"] is True
    assert _ok(core, "extension-apply", {"manifest": m, "strict": False})["config"]["accent"] == "#123456"
    bad = dict(m, config="code")
    code, out, _ = run_core_raw(core, "extension-verify", {"manifest": bad, "strict": False})
    assert code == 1


def test_preset_apply(core):
    p = {"schema": "nf-preset/1", "id": "accessible", "name": "A", "version": 1, "settings": {"theme": "SYSTEM", "profile": "accessible"}}
    r = _ok(core, "preset-apply", {"preset": p, "prefs": {"theme_mode": "LIGHT"}})
    assert r["prefs"]["profile"] == "accessible" and r["reversible"] is True


def test_sdir_export_load(core):
    s = _sdir(core)
    out = _ok(core, "sdir-export", {"sdir": s})
    assert out["sha256"]
    assert _ok(core, "sdir-load", {"sdir": out["json"]})["sdir"]["schema"] == "nf-sdir/1"


def test_portable_export_import(core):
    p = _ok(core, "portable-export", {"created_at": "2026-01-01T00:00:00Z", "projects": [], "prefs": {}, "packs": []})["portable"]
    r = _ok(core, "portable-import", {"portable": p})
    assert r["ok"] is True


def test_trust_root_add_verify_revoke(core):
    pk = "11" * 32
    fp = hashlib.sha256(bytes.fromhex(pk)).hexdigest()
    root = {"id": "r1", "alg": "ed25519", "public_key": pk, "fingerprint": fp, "not_before": "2026-01-01", "not_after": "2030-01-01", "status": "active"}
    trust = _ok(core, "trust-root-add", {"root": root})["trust"]
    assert _ok(core, "trust-root-verify", {"trust": trust, "fingerprint": fp})["ok"] is True
    trust = _ok(core, "trust-root-revoke", {"trust": trust, "fingerprint": fp})["trust"]
    code, out, _ = run_core_raw(core, "trust-root-verify", {"trust": trust, "fingerprint": fp})
    assert code == 1

def test_portable_zip_roundtrip(core, tmp_path):
    out = tmp_path / "portable.zip"
    p = _ok(core, "portable-export", {"created_at": "2026-01-01T00:00:00Z", "projects": [], "prefs": {}, "packs": [], "contents": [{"path": "prefs.json", "data_hex": b"{}".hex()}], "out_path": str(out)})
    assert p["zip_sha256"]
    r = _ok(core, "portable-import", {"zip_path": str(out)})
    assert r["ok"] is True

