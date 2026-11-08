#!/usr/bin/env python3
"""Cross-language DSSE v1 probe: Python and .NET sign/verify the same envelope."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

PAYLOAD_TYPE = "application/vnd.in-toto+json"
PAYLOAD = b'{"v":1,"text":"hello","bytes":[0,1,2,255]}\n'
KEY = b"n" * 32


def run(cmd: list[str], cwd: Path):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=90)  # nosec B603


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--cli", required=True)
    ap.add_argument("--py-exe", required=True)
    args = ap.parse_args()
    root = Path(args.root)
    rows: list[tuple[str, bool, str]] = []
    with tempfile.TemporaryDirectory(prefix="nf-dsse-probe-") as tmp:
        work = Path(tmp)
        payload = work / "payload.bin"
        key = work / "key"
        py_env = work / "python.json"
        cs_env = work / "dotnet.json"
        payload.write_bytes(PAYLOAD)
        key.write_bytes(KEY)
        py_sign = [args.py_exe, str(root / "scripts" / "nf.py"), "dsse", "sign",
                   "--payload", str(payload), "--payload-type", PAYLOAD_TYPE,
                   "--key-file", str(key), "--keyid", "probe-key", "--out", str(py_env)]
        cs_sign = [args.cli, "--root", str(root), "dsse", "sign",
                   "--payload", str(payload), "--payload-type", PAYLOAD_TYPE,
                   "--key-file", str(key), "--keyid", "probe-key", "--out", str(cs_env)]
        a = run(py_sign, root)
        b = run(cs_sign, root)
        rows.append(("Python / .NET sign rc", a.returncode == 0 and b.returncode == 0,
                     f"{a.returncode}/{b.returncode}"))
        same = py_env.read_bytes() == cs_env.read_bytes() if py_env.is_file() and cs_env.is_file() else False
        rows.append(("envelope bytes", same,
                     hashlib.sha256(py_env.read_bytes()).hexdigest()[:16] if py_env.is_file() else "-"))

        py_out = work / "py.verified"
        cs_out = work / "cs.verified"
        py_verify = [args.py_exe, str(root / "scripts" / "nf.py"), "dsse", "verify",
                     "--envelope", str(cs_env), "--key-file", str(key), "--keyid", "probe-key",
                     "--payload-type", PAYLOAD_TYPE, "--out", str(py_out), "--json"]
        cs_verify = [args.cli, "--root", str(root), "dsse", "verify",
                     "--envelope", str(py_env), "--key-file", str(key), "--keyid", "probe-key",
                     "--payload-type", PAYLOAD_TYPE, "--out", str(cs_out), "--json"]
        a = run(py_verify, root)
        b = run(cs_verify, root)
        rows.append(("cross verify rc", a.returncode == 0 and b.returncode == 0,
                     f"{a.returncode}/{b.returncode}"))
        rows.append(("verified payload bytes", py_out.read_bytes() == PAYLOAD and cs_out.read_bytes() == PAYLOAD,
                     f"{py_out.stat().st_size if py_out.is_file() else 0}/"
                     f"{cs_out.stat().st_size if cs_out.is_file() else 0}"))

        tampered = work / "tampered.json"
        doc = json.loads(py_env.read_text(encoding="utf-8"))
        doc["payloadType"] = "application/json"
        tampered.write_text(json.dumps(doc), encoding="utf-8")
        py_bad = run([args.py_exe, str(root / "scripts" / "nf.py"), "dsse", "verify",
                      "--envelope", str(tampered), "--key-file", str(key), "--keyid", "probe-key"],
                     root)
        cs_bad = run([args.cli, "--root", str(root), "dsse", "verify",
                      "--envelope", str(tampered), "--key-file", str(key), "--keyid", "probe-key"],
                     root)
        rows.append(("tampered payloadType rejected", py_bad.returncode != 0 and cs_bad.returncode != 0,
                     f"{py_bad.returncode}/{cs_bad.returncode}"))

        urlsafe = work / "urlsafe.json"
        doc = json.loads(py_env.read_text(encoding="utf-8"))
        doc["payload"] = base64.urlsafe_b64encode(PAYLOAD).decode("ascii")
        doc["signatures"][0]["sig"] = base64.urlsafe_b64encode(
            base64.b64decode(doc["signatures"][0]["sig"])).decode("ascii")
        urlsafe.write_text(json.dumps(doc), encoding="utf-8")
        py_url = run([args.py_exe, str(root / "scripts" / "nf.py"), "dsse", "verify",
                      "--envelope", str(urlsafe), "--key-file", str(key), "--keyid", "probe-key"],
                     root)
        cs_url = run([args.cli, "--root", str(root), "dsse", "verify",
                      "--envelope", str(urlsafe), "--key-file", str(key), "--keyid", "probe-key"],
                     root)
        rows.append(("URL-safe Base64 accepted", py_url.returncode == 0 and cs_url.returncode == 0,
                     f"{py_url.returncode}/{cs_url.returncode}"))

    print("| 判定项 | 结果 | 证据 |")
    print("|---|---|---|")
    for name, ok, evidence in rows:
        print(f"| {name} | {'通过' if ok else '**未达**'} | {evidence} |")
    failed = [row for row in rows if not row[1]]
    print(f"\n结论：{'全部通过' if not failed else f'未达 {len(failed)} 项'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
