#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁读面台账 CLI（W-03 的消费者面，只读）。

用法：
  python scripts/gate.py                 # 三源对账（audit）
  python scripts/gate.py --json          # 机器面
  python scripts/gate.py --static-faces  # 代码面静态读面统计
  python scripts/gate.py --observed      # 跑一次只读扫描器并打印其观测读面
  python scripts/gate.py --manifest      # 打印声明面（缺件即空表）
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import gate_faces as gf  # noqa: E402


def _emit(kind, payload, as_json, lines):
    if as_json:
        print(json.dumps(dict(kind=kind, **payload), ensure_ascii=False, indent=2, sort_keys=True))
        return
    for ln in lines:
        print(ln)


def _observed(as_json, use_hook=False):
    from core import conformance_scan as cs
    face = gf.observed_face(lambda: cs.scan(ROOT), ROOT, use_hook=use_hook)
    _emit("gate-observed", {"observed": len(face), "sample": face[:10]}, as_json,
          ["== 观测读面 ==", "  %d 件（示例 %s）" % (len(face), face[:3])])
    return 0


def _static_faces(as_json):
    faces = gf.static_faces(ROOT)
    with_paths = sum(1 for v in faces.values() if v)
    _emit("gate-static-faces", {"modules": len(faces), "with_paths": with_paths}, as_json,
          ["== 静态读面 ==", "  模块 %d（含路径样字面量 %d）" % (len(faces), with_paths)])
    return 0


def _manifest(as_json):
    doc = gf.load_manifest(ROOT)
    _emit("gate-manifest", {"experts": len(doc), "ids": sorted(doc)}, as_json,
          ["== 声明面 ==", "  专家 %d：%s" % (len(doc), sorted(doc))])
    return 0


def _derive(as_json):
    doc = gf.load_manifest(ROOT)
    rows = []
    for eid, e in sorted(doc.items()):
        level, why = gf.derive_skip_safety(ROOT, e)
        rows.append({"id": eid, "declared": e.get("skip_safety"),
                     "derived": level, "why": why[:3]})
    _emit("gate-derive", {"rows": rows}, as_json,
          ["== 级别推导 =="] + ["  %s 声明=%s 推导=%s" % (r["id"], r["declared"], r["derived"])
                                for r in rows])
    return 0


def _route(changed, as_json):
    from core import gate_router as gr
    experts = gf.load_manifest(ROOT)
    issues, plan, stats = gr.route(ROOT, changed or [], experts=experts)
    issues += gr.audit_route(ROOT, plan, experts)
    lines = ["== 路由（策略 S）==", "  changed=%d dense=%d routed=%d dormant=%d"
             % (stats["changed"], stats["dense"], stats["routed"], stats["dormant"])]
    for r in plan["routed"]:
        lines.append("  [跑] %s（%s）" % (r["id"], r["via"]))
    for d in plan["dormant"]:
        lines.append("  [眠] %s（%s）" % (d["id"], d["reason"]))
    _emit("gate-route", {"issues": issues, "plan": plan, "stats": stats}, as_json, lines)
    return 1 if issues else 0


def _route_datalog(changed, as_json):
    """P-A5：规则层路由（Part 2 后端）× 门禁影响图（Part 1）的同语义路径。"""
    from core import gate_datalog as gd
    from core import gate_graph as gg
    experts = gf.load_manifest(ROOT)
    mods = sorted(gg.changed_modules(changed or []))
    hits, got = gd.routed(ROOT, mods, experts=experts, backend="dag")
    g = got.get("graph") or {}
    lines = ["== 规则层路由（P-A5 · dag 后端）==",
             "  changed_modules=%s" % mods, "  hits=%s" % hits,
             "  gate 推导图：nodes=%d edges=%d depth=%d fuel=%d/%d"
             % (g.get("nodes", 0), g.get("edges", 0), g.get("depth", 0),
                got["fuel_used"], got["fuel_total"])]
    _emit("gate-route-datalog", {"hits": hits, "graph": g, "status": got["status"],
                                 "changed_modules": mods}, as_json, lines)
    return 0 if got["status"] == "OK" else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="门禁读面台账（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--observed", action="store_true", help="跑只读扫描器并打印观测读面")
    ap.add_argument("--observed-hook", action="store_true",
                    help="观测读面用 audit hook（与实现无关；默认走 memo）")
    ap.add_argument("--static-faces", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--derive", action="store_true", help="声明级别 vs 源码推导")
    ap.add_argument("--route", nargs="*", default=None, metavar="PATH",
                    help="按变更路径求路由（策略 S）并自检")
    ap.add_argument("--route-datalog", nargs="*", default=None, metavar="PATH",
                    help="按变更路径用**规则层（P-A5 dag 后端）**求路由并打印 gate 推导图统计")
    args = ap.parse_args(argv)
    if args.observed:
        return _observed(args.json, use_hook=getattr(args, "observed_hook", False))
    if args.static_faces:
        return _static_faces(args.json)
    if args.manifest:
        return _manifest(args.json)
    if args.derive:
        return _derive(args.json)
    if args.route is not None:
        return _route(args.route, args.json)
    if args.route_datalog is not None:
        return _route_datalog(args.route_datalog, args.json)
    issues, stats = gf.audit(ROOT)
    if args.json:
        print(json.dumps({"kind": "gate-audit", "issues": issues, "stats": stats},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if issues else 0
    print("== 门禁读面三源对账 ==")
    for w in stats.get("warns", []):
        print("  [WARN] %s" % w)
    for i in issues:
        print("  [FAIL] %s" % i, file=sys.stderr)
    print("  专家 %d · 缺口 %d" % (stats.get("experts", 0), len(issues)))
    return 1 if issues else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
