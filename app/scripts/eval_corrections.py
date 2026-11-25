#!/usr/bin/env python3
"""C2-09 纠错语料评估：60 条坏文档，测 sdir-repair 的 P/R/F1 与不可恢复。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "app" / "core" / "target" / "release" / "nf-app-core.exe"
OUT = ROOT / "results" / "app" / "governance" / "benchmarks" / "C2.json"
CREATED = "2026-01-01T00:00:00Z"


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run([str(CORE), op, "--in", "-"], input=json.dumps(req, ensure_ascii=False).encode(), stdout=subprocess.PIPE, timeout=120)
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def walk(v):
    yield v
    for c in v.get("children", []): yield from walk(c)


def rehash(sdir: dict) -> None:
    def rec(b):
        ch = [rec(c) for c in b.get("children", [])]
        h = hashlib.sha256(json.dumps({"type": b["type"], "text": b["text"], "attrs": b.get("attrs", {}), "children": ch}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        b["hash"] = h
        return h
    rec(sdir["blocks"][0])


def main() -> int:
    kinds = ["heading_level", "table_header", "figure_alt", "reading_order", "dangling_relations"]
    tp = fp = fn = unrecoverable = 0
    for i in range(60):
        kind = kinds[i % 5]
        if kind == "heading_level":
            md = "# A\n\na\n\n### B\n\nb\n\n##### C\n\nc\n"
        elif kind == "table_header":
            md = "# T\n\n| K | V |\n|---|---|\n| a | 1 |\n"
        elif kind == "figure_alt":
            md = "# T\n\n![ ](x.png)\n"
        else:
            md = "# T\n\na\n\nb\n"
        code, env = core("sdir-import", {"markdown": md, "created_at": CREATED, "lang": "zh"})
        assert code == 0, env
        s = env["result"]
        if kind == "table_header":
            for b in walk(s["blocks"][0]):
                if b["type"] == "table": b["attrs"]["header"] = False; break
            rehash(s)
        elif kind == "figure_alt":
            for b in walk(s["blocks"][0]):
                if b["type"] == "figure": b["text"] = ""; break
            rehash(s)
        elif kind == "reading_order":
            for a in s["accessibility"]: a["reading_order"] = 0
        elif kind == "dangling_relations":
            s["relations"].append({"from": s["blocks"][0]["id"], "to": "missing", "kind": "crossref"})
        code, env = core("sdir-repair", {"sdir": s})
        if code != 0:
            unrecoverable += 1; fn += 1; continue
        rep = env["result"]
        got = {r["kind"] for r in rep["repairs"]}
        code_v, valid = core("sdir-validate", {"sdir": rep["sdir"]})
        if code_v != 0 or rep["summary"]["lost_blocks"] != 0:
            unrecoverable += 1
        if kind in got:
            tp += 1
        else:
            fn += 1
        fp += len(got - {kind})
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    result = {"benchmark": "C2.09", "ok": precision >= 0.9 and recall >= 0.85 and unrecoverable == 0, "cases": 60, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "unrecoverable": unrecoverable}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
