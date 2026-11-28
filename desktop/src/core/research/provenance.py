"""Content provenance manifest: digest, parents, assertions, optional HMAC.

This is a tamper-evident manifest, not C2PA and not a PKI signature. It binds
content bytes to recipe/source/parent metadata; verification distinguishes
content integrity from signature authentication.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

SCHEMA = "nf-content-provenance/1"
REPORT = "nf-content-provenance-report/1"
ALG = "hmac-sha256"


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def build(content: bytes | str, filename: str, recipe: dict[str, Any] | None = None,
          creator: dict[str, Any] | None = None, parents: list[dict[str, Any]] | None = None,
          assertions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = content.encode("utf-8") if isinstance(content, str) else content
    return {
        "schema": SCHEMA,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "content": {"filename": filename,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data)},
        "recipe": recipe,
        "creator": creator or {"id": "local", "method": "none"},
        "parents": parents or [],
        "assertions": assertions or [],
        "boundary": "HMAC is a prototype integrity check, not C2PA/PKI",
    }


def sign(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    body = {k: v for k, v in manifest.items() if k != "signature"}
    signed = dict(manifest)
    signed["signature"] = {"alg": ALG,
                           "key_id": hashlib.sha256(key.encode()).hexdigest()[:16],
                           "value": hmac.new(key.encode(), _canonical(body),
                                             hashlib.sha256).hexdigest()}
    return signed


def verify(manifest: dict[str, Any], content: bytes | str,
           key: str | None = None) -> dict[str, Any]:
    data = content.encode("utf-8") if isinstance(content, str) else content
    actual = hashlib.sha256(data).hexdigest()
    expected = (manifest.get("content") or {}).get("sha256")
    checks = [{"name": "content_hash", "ok": actual == expected}]
    sig = manifest.get("signature")
    authenticated = False
    if sig:
        if key is None:
            checks.append({"name": "signature", "ok": None, "reason": "key unavailable"})
        else:
            body = {k: v for k, v in manifest.items() if k != "signature"}
            want = hmac.new(key.encode(), _canonical(body), hashlib.sha256).hexdigest()
            authenticated = hmac.compare_digest(want, str(sig.get("value", "")))
            checks.append({"name": "signature", "ok": authenticated})
    else:
        checks.append({"name": "signature", "ok": None, "reason": "unsigned"})
    ok = all(c["ok"] is not False for c in checks)
    if sig and key is not None:
        ok = ok and authenticated
    return {"schema": REPORT, "verified": ok, "signed": bool(sig),
            "authenticated": authenticated, "checks": checks}
