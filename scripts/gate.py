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


def _observed(as_json):
    from core import conformance_scan as cs
    face = gf.observed_face(lambda: cs.scan(ROOT), ROOT)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="门禁读面台账（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--observed", action="store_true", help="跑只读扫描器并打印观测读面")
    ap.add_argument("--static-faces", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    args = ap.parse_args(argv)
    if args.observed:
        return _observed(args.json)
    if args.static_faces:
        return _static_faces(args.json)
    if args.manifest:
        return _manifest(args.json)
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
