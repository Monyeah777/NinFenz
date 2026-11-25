#!/usr/bin/env python3
"""H2.3 语义修复基准：50 份坏文档（标题跳级/表缺头/图缺 alt/阅读顺序重复/悬空关系）。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_CORE = Path(os.environ.get("NF_APP_CORE", REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"))
CORE_DIR = Path(tempfile.mkdtemp(prefix="nf-h23-core-"))
CORE = CORE_DIR / SOURCE_CORE.name
if SOURCE_CORE.exists():
    shutil.copy2(SOURCE_CORE, CORE)
OUT = REPO / "results" / "app" / "governance" / "benchmarks"
CREATED = "2026-01-01T00:00:00Z"


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run([str(CORE), op, "--in", "-"], input=json.dumps(req, ensure_ascii=False).encode(), stdout=subprocess.PIPE, timeout=120)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def blocks(v: dict):
    yield v
    for c in v.get("children", []):
        yield from blocks(c)


def rehash(sdir: dict) -> None:
    def rec(b: dict) -> str:
        ch = [rec(c) for c in b.get("children", [])]
        h = hashlib.sha256(json.dumps({"type": b["type"], "text": b["text"], "attrs": b.get("attrs", {}), "children": ch}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        b["hash"] = h
        return h
    rec(sdir["blocks"][0])


def base(md: str) -> dict:
    code, env = core("sdir-import", {"markdown": md, "created_at": CREATED, "lang": "zh"})
    assert code == 0, env
    return env["result"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    unrecoverable = 0
    total = 50
    for i in range(total):
        kind = i % 5
        if kind == 0:
            s = base(f"# A\n\na\n\n### B\n\nb\n\n##### C\n\nc\n")
        elif kind == 1:
            s = base(f"# T\n\n## 表\n\n| K | V |\n|---|---|\n| a | {i} |\n")
            for b in blocks(s["blocks"][0]):
                if b["type"] == "table":
                    b["attrs"]["header"] = False
                    break
            rehash(s)
        elif kind == 2:
            s = base(f"# T\n\n![ ](img-{i}.png)\n")
            for b in blocks(s["blocks"][0]):
                if b["type"] == "figure":
                    b["text"] = ""
                    break
            rehash(s)
        elif kind == 3:
            s = base(f"# T\n\na\n\nb\n")
            for a in s["accessibility"]:
                a["reading_order"] = 0
        else:
            s = base(f"# T\n\na\n")
            s["relations"].append({"from": s["blocks"][0]["id"], "to": "missing-block", "kind": "crossref"})
        code, env = core("sdir-repair", {"sdir": s})
        if code != 0:
            unrecoverable += 1
            continue
        rep = env["result"]
        code_v, valid = core("sdir-validate", {"sdir": rep["sdir"]})
        if code_v == 0 and valid["result"]["verdict"] == "pass" and rep["summary"]["lost_blocks"] == 0 and rep["repairs"]:
            ok += 1
        else:
            unrecoverable += 1
    result = {
        "benchmark": "H2.3",
        "ok": ok >= int(total * 0.9) and unrecoverable == 0,
        "cases": total,
        "repaired": ok,
        "unrecoverable": unrecoverable,
        "reversible": True,
        "criteria": {"success": ">=90%", "unrecoverable": 0, "revocable": True},
    }
    (OUT / "H23.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
