#!/usr/bin/env python3
"""门禁读面台账 CLI（W-03 的消费者面，只读）。

用法：
  python scripts/gate.py                 # 三源对账（audit）
  python scripts/gate.py --json          # 机器面
  python scripts/gate.py --static-faces  # 代码面静态读面统计
  python scripts/gate.py --observed      # 跑一次只读扫描器并打印其观测读面
  python scripts/gate.py --manifest      # 打印声明面（缺件即空表）
  python scripts/gate.py --select docs/README.md   # 按改动选出该跑的测试模块（秒级 check 前半）
  python scripts/gate.py --observe --workers 5     # 观测测试模块读面（数据落缓存区，不入库）
  python scripts/gate.py --verdicts docs/README.md # 判定缓存 dry-run（只查不跑：谁会命中）
  python scripts/gate.py --check docs/README.md    # 跑快车道 check（--plan-only 只看计划）
"""
import argparse
import json
import os
import subprocess  # nosec B404 - 只跑仓库内测试（argv 列表、无 shell、路径自仓库）
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import gate_check as gcheck  # noqa: E402
from core import gate_faces as gf  # noqa: E402
from core import gate_observe as go  # noqa: E402
from core import gate_select as gs  # noqa: E402
from core import gate_verdict as gv  # noqa: E402


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


def _invoke_module(mod, timeout=600):
    """真跑一个测试模块 → (退出码, 秒数)。"""
    import time
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "unittest", f"tests.{mod}", "-q"],  # noqa: S603
                          cwd=os.path.join(ROOT, "desktop"), capture_output=True,
                          timeout=timeout)  # nosec B603
    return proc.returncode, round(time.perf_counter() - started, 2)


def _check(changed, workers, as_json, include_slow, use_cache, plan_only):
    """快车道 check：计划期定键 → 并行 → 按钉住的键落盘。"""
    plan_doc = gcheck.plan(changed, root=ROOT, quick_only=not include_slow,
                           use_cache=use_cache)
    cached, to_run = plan_doc["cached"], plan_doc["to_run"]
    if plan_only:
        _emit("gate-check-plan", {"cached": [m for m, _v in cached],
                                  "to_run": [m for m, _p in to_run],
                                  "deferred": plan_doc["deferred"],
                                  "uncacheable": plan_doc["uncacheable"]}, as_json,
              [f"== check 计划 ==  命中 {len(cached)} · 真跑 {len(to_run)} · "
               f"慢车道让位 {len(plan_doc['deferred'])} · 跳过 {len(plan_doc['skipped'])}"])
        return 0
    result = gcheck.execute(plan_doc, _invoke_module, workers=workers)
    result["failed"] = gcheck.failed(result)
    failed = result["failed"]
    lines = [f"== 快车道 check ==  计划 {len(cached) + len(to_run)}"
             f"（命中 {len(cached)} · 真跑 {len(to_run)}）",
             f"  墙钟 {result['wall']}s · 红 {len(failed)} · 慢车道让位 {len(plan_doc['deferred'])}"
             f" · 跳过 {len(plan_doc['skipped'])}"]
    for mod in failed:
        lines.append(f"  [红] {mod}")
    _emit("gate-check", {"failed": failed, "wall": result["wall"],
                         "fresh": result["fresh"],
                         "hits": [m for m, _v in cached],
                         "deferred": plan_doc["deferred"]}, as_json, lines)
    return 1 if failed else 0


def _verdicts(changed, as_json):
    """判定缓存 dry-run：只查不跑，报出「谁会命中 / 谁要真跑 / 谁不可缓存」。"""
    got = gs.select(changed, root=ROOT)
    faces = gs.load_faces(ROOT)
    tdir = Path(ROOT) / "desktop" / "tests"
    hits, misses, uncacheable = [], [], []
    for mod, _why in got["quick"]:
        rec = faces.get(mod, {})
        reads = rec.get("reads") or []
        if not reads or not gs.cacheable(mod, rec, tdir):
            uncacheable.append(mod)
            continue
        (hit, _v), _k, _e, _t = gv.lookup(mod, reads, ROOT, [f"desktop/tests/{mod}.py"])
        (hits if hit else misses).append(mod)
    _emit("gate-verdicts", {"changed": list(changed), "hits": hits, "misses": misses,
                            "uncacheable": uncacheable}, as_json,
          [f"== 判定缓存 dry-run ==  快车道 {len(got['quick'])} 个",
           f"  命中 {len(hits)} · 要真跑 {len(misses)} · 常跑不可缓存 {len(uncacheable)}",
           f"  数据面 {'在场' if faces else '缺席（全部按常跑）'}"])
    return 0


def _observe_all(mods, workers, as_json):
    """观测测试模块读面（可续跑；数据落缓存区，不入库）。"""

    def progress(done, total, mod, rec):
        print(f"  [{done}/{total}] {mod:<34} {rec['status']:<12} reads={len(rec['reads'])}",
              flush=True)

    doc = go.run_all(ROOT, mods=list(mods) if mods else None, workers=workers,
                     on_progress=progress)
    modules = doc.get("modules") or {}
    ok = sum(1 for v in modules.values() if v.get("status") == "ok")
    _emit("gate-observe", {"observed": len(modules), "ok": ok,
                           "path": str(go.faces_path())}, as_json,
          [f"== 读面观测 ==  模块 {len(modules)} · ok {ok}",
           f"  数据落点 {go.faces_path()}（缓存区，不入库）"])
    return 0


def _select(changed, as_json):
    """按改动选「该跑的测试模块」——只打印计划，不执行（执行面见 tests 套件的 check 入口）。"""
    got = gs.select(changed, root=ROOT)
    run = [m for m, _w in got["run"]]
    faces = gs.load_faces(ROOT)
    note = "" if faces else "（读面数据缺席：按 fail-closed 全部常跑）"
    payload = {"changed": list(changed), "run": run, "skip": got["skip"],
               "quick": [m for m, _w in got["quick"]], "slow": [m for m, _w in got["slow"]],
               "uncacheable": got["uncacheable"], "observed_modules": len(faces)}
    lines = ["== 待跑集合（按改动选择）==",
             f"  改动 {len(changed)} 件 · 跑 {len(run)} · 跳 {len(got['skip'])} · "
             f"快车道 {len(got['quick'])} · 慢车道让位 {len(got['slow'])} · "
             f"常跑不可缓存 {len(got['uncacheable'])} {note}"]
    for mod, why in got["run"][:20]:
        lines.append(f"  [跑] {mod:<38} {why}")
    _emit("gate-select", payload, as_json, lines)
    return 0


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
    ap.add_argument("--observe", nargs="*", default=None, metavar="MOD",
                    help="观测测试模块读面（省略模块名即全量；可续跑）")
    ap.add_argument("--workers", type=int, default=5, help="观测/执行的并行度")
    ap.add_argument("--check", nargs="*", default=None, metavar="PATH",
                    help="按改动跑快车道 check（判定缓存 + 并行 + 慢车道让位）")
    ap.add_argument("--all", action="store_true", help="check 时含慢车道（定时/发布用）")
    ap.add_argument("--no-cache", action="store_true", help="check 时绕过判定缓存")
    ap.add_argument("--plan-only", action="store_true", help="check 只出计划不执行")
    ap.add_argument("--verdicts", nargs="*", default=None, metavar="PATH",
                    help="判定缓存 dry-run：按改动报出命中/真跑/不可缓存")
    ap.add_argument("--select", nargs="*", default=None, metavar="PATH",
                    help="按改动路径选「该跑的测试模块」（读面数据在缓存区，缺席即全跑）")
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
    if args.observe is not None:
        return _observe_all(args.observe, args.workers, args.json)
    if args.check is not None:
        return _check(args.check, args.workers, args.json, args.all, not args.no_cache,
                      args.plan_only)
    if args.verdicts is not None:
        return _verdicts(args.verdicts, args.json)
    if args.select is not None:
        return _select(args.select, args.json)
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
