#!/usr/bin/env python3
"""原子不变量 A1–A5 与候选健康 B1–B5 的可复算出口。

- 原子：派生 nf/atom-catalog/2（不改 v1 文件），跑 A1–A5；存量死码记债（atom_debt.json），
  新增死码 fail-closed；
- 候选：读候选 JSON，跑 B1–B5，输出 candidate-ok / candidate-insufficient。

用法：
  python scripts/atom_invariants.py --write        # 写 results/ccos/atom_invariants.json
  python scripts/atom_invariants.py --check        # 校验提交件 == 重算
  python scripts/atom_invariants.py --json         # 打印（人看/机读都可）
  python scripts/atom_invariants.py --candidates c.json --budget 8 --broken k1,k2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.meta_cockpit import atom_catalog, candidate_health  # noqa: E402

OUT_REL = "results/ccos/atom_invariants.json"
SCHEMA = "nf-atom-invariants-report/1"
GUIDE = "修复指引："


def build_report() -> dict[str, Any]:
    catalog = atom_catalog.build(str(ROOT))
    inv = atom_catalog.invariants(catalog)
    return {"schema": SCHEMA, "catalog": {"schema": catalog["schema"],
                                          "count": catalog["count"],
                                          "pack_references": len(catalog["pack_references"]),
                                          "atom_debt": len(catalog.get("atom_debt") or [])},
            "invariants": inv,
            "atoms": [{"id": atom["id"], "name": atom["name"],
                       "composed_of": atom["composed_of"],
                       "status": atom["status"]} for atom in catalog["atoms"]]}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="atom_invariants",
                                 description="原子不变量 A1–A5 / 候选健康 B1–B5")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--candidates", default="", help="候选 JSON（数组）")
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--broken", default="", help="逗号分隔的 broken keys")
    args = ap.parse_args(argv)

    if args.candidates:
        path = Path(args.candidates)
        if not path.is_file():
            print("候选文件不在场：" + args.candidates + "（" + GUIDE + "给 JSON 数组）",
                  file=sys.stderr)
            return 2
        try:
            candidates = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("候选文件不可读：" + str(exc), file=sys.stderr)
            return 2
        try:
            res = candidate_health.assess(candidates, budget=args.budget,
                                          broken_keys=[k for k in args.broken.split(",") if k])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if res["verdict"] == candidate_health.VERDICT_OK else 1

    report = build_report()
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(report), encoding="utf-8")
        print("OK 已写入 " + OUT_REL + "（原子 " + str(report["catalog"]["count"]) + " 个）")
        return 0
    if args.check:
        path = ROOT / OUT_REL
        if not path.is_file():
            print("缺 " + OUT_REL + "（" + GUIDE + "跑 --write）", file=sys.stderr)
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if render(recorded) != render(report):
            print("不变量报告与重算不一致（" + GUIDE + "重跑 --write）", file=sys.stderr)
            return 1
        print("OK 不变量报告与重算一致")
        return 0
    print(render(report), end="")
    return 0 if report["invariants"]["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
