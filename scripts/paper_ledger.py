#!/usr/bin/env python3
"""论文筛选台账（nf-paper-ledger/1）：--write 重写规范形，--check 核存在性与计数。

为什么（2026-11-10）：论文筛选此前只在本仓内部档案里，处置、落点、证据散在正文——
读者无法区分「读到了机制」「移植进了仓」「判定不适用」。本件把它变成可核对象：
每篇必须有处置与理由；adopted 必须有仓内落点与证据面，且逐条核文件存在。

用法：python scripts/paper_ledger.py [--write|--check] [--json] [--stats]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REL = "protocol/paper_ledger.json"
SCHEMA = "nf-paper-ledger/1"
DISPOSITIONS = ("adopted", "deferred", "rejected", "not-applicable")
GUIDE = "修复指引："

sys.path.insert(0, str(ROOT / "desktop" / "src"))


def load() -> dict[str, Any]:
    from core import json_doc

    return json_doc.load(ROOT / REL, dict, what=REL)


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def counts(entries: list) -> dict:
    return {k: sum(1 for e in entries if e.get("disposition") == k) for k in DISPOSITIONS}


def check(doc: dict[str, Any] | None = None) -> list:
    """结构 + 引用面 + 计数 → 问题列表（空 = 通过）。"""
    doc = load() if doc is None else doc
    issues: list = []
    if doc.get("schema") != SCHEMA:
        return [f"schema 不是 {SCHEMA}（{GUIDE}按本脚本 --write 重写）"]
    entries = doc.get("entries") or []
    if not isinstance(entries, list) or not entries:
        return ["entries 为空或不是列表（台账不得为空）"]
    if doc.get("count") != len(entries):
        issues.append(f"count={doc.get('count')} 与 entries={len(entries)} 不一致")
    seen: set = set()
    for e in entries:
        eid = str(e.get("id") or "")
        if not eid:
            issues.append("存在无 id 的条目")
            continue
        if eid in seen:
            issues.append(f"{eid} 重复")
        seen.add(eid)
        if not str(e.get("title") or "").strip():
            issues.append(f"{eid} 缺 title")
        disp = e.get("disposition")
        if disp not in DISPOSITIONS:
            issues.append(f"{eid} disposition={disp!r} 不在 {DISPOSITIONS}")
            continue
        if not str(e.get("reason") or "").strip():
            issues.append(f"{eid} 缺 reason（处置必须有理由）")
        targets = e.get("targets") or []
        evidence = e.get("evidence") or []
        if disp == "adopted":
            if not targets:
                issues.append(f"{eid} adopted 但无 targets（落点必须可核）")
            if not evidence:
                issues.append(f"{eid} adopted 但无 evidence（判据面必须可核）")
        for rel in list(targets) + list(evidence):
            if not (ROOT / str(rel)).exists():
                issues.append(f"{eid} 引用的路径不存在：{rel}")
    want = counts(entries)
    got = doc.get("counts") or {}
    if got != want:
        issues.append(f"counts 记录 {got} ≠ 实测 {want}（{GUIDE}--write 重算）")
    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="paper_ledger", description="论文筛选台账校验")
    ap.add_argument("--write", action="store_true", help="按 entries 重算 count/counts 并落盘")
    ap.add_argument("--check", action="store_true", help="核结构/引用/计数（默认即校验）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--stats", action="store_true", help="只打印分档统计")
    args = ap.parse_args(argv)

    doc = load()
    entries = doc.get("entries") or []
    if args.write:
        doc["count"] = len(entries)
        doc["counts"] = counts(entries)
        issues = check(doc)
        if issues:
            print("；".join(issues[:5]), file=sys.stderr)
            return 1
        from core import atomic_write

        atomic_write.write_text(ROOT / REL, render(doc))
        print(f"OK 已写入 {REL}（{len(entries)} 篇 · {doc['counts']}）")
        return 0
    issues = check(doc)
    if args.stats or args.json:
        payload = {"schema": SCHEMA, "count": len(entries), "counts": counts(entries)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if issues:
        print("；".join(issues[:5]), file=sys.stderr)
        return 1
    if not (args.stats or args.json):
        print(f"OK 论文台账自洽（{len(entries)} 篇 · {counts(entries)}）")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
