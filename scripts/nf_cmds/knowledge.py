"""CLI 处理器：knowledge 族（自 scripts/nf.py 抽出；按子命令拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import ROOT, _machine_fail


def _knowledge_graph(args) -> int:
    """资产本体索引（T10.2）：CONCEPT_GRAPH 合并 → protocol/concept_graph_index.json。"""
    import json as _json
    from core import concept_index as ci

    want_json = bool(getattr(args, "json", False))
    write_mode = bool(getattr(args, "write", False))
    if write_mode:
        issues, doc = ci.write(ROOT)
    else:
        issues, doc = ci.check(ROOT)
    stats = doc.get("stats") or {}
    sources = doc.get("sources") or {}
    if want_json:
        print(_json.dumps({"kind": "concept-index", "schema": ci.SCHEMA,
                           "issues": issues, "index": doc},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge graph（资产本体索引 · 真源 %s）==" % ci.INDEX_REL)
        print("  覆盖：md %d/%d · graphml 回退 %d · 跳过 %d"
              % (sources.get("md_parsed", 0), sources.get("md_total", 0),
                 sources.get("graphml_used", 0), len(sources.get("skipped") or [])))
        print("  规模：域 %d · 概念 %d（出现 %d，同名合并 %d）· 边 %d（出现 %d，重复合并 %d）"
              % (stats.get("domains", 0), stats.get("nodes", 0),
                 stats.get("node_occurrences", 0), stats.get("merged_same_name", 0),
                 stats.get("edges", 0), stats.get("edge_occurrences", 0),
                 stats.get("duplicate_edges_merged", 0)))
        print("  质量：孤儿 %d · 悬空边 %d · 类别冲突 %d · warnings %d"
              % (stats.get("orphan_nodes", 0), stats.get("dangling_edges", 0),
                 stats.get("category_conflicts", 0), stats.get("warnings", 0)))
        print("  root：%s…" % str(doc.get("root", ""))[:24])
        print("  模式：%s" % ("write（已重写索引）" if write_mode else "check（只校验）"))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0


def _knowledge_order(args):
    import json as _json
    from core import knowledge as kn

    want_json = bool(getattr(args, "json", False))
    clearance = str(getattr(args, "clearance", "") or "")
    rows = kn.resolve_order(ROOT, clearance=clearance)
    if want_json:
        print(_json.dumps({"kind": "knowledge-order",
                           "clearance": clearance or "不裁剪",
                           "query_order": rows},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge order（查询有序：合同级 → 参考级%s）=="
              % ("· 裁剪至 " + clearance if clearance else ""))
        for i, r in enumerate(rows, 1):
            print("  %d. %-22s %-9s %-18s %s"
                  % (i, r["id"], r["authority"], r["kind"], r["locator"]))
    return 0


def _knowledge_visible(args):
    import json as _json
    from core import knowledge as kn

    want_json = bool(getattr(args, "json", False))
    clearance = str(getattr(args, "clearance", "public") or "public")
    allowed = kn.visible_ids(ROOT, clearance)
    rows = [{"id": str(s.get("id")), "visibility": str(s.get("visibility")),
             "visible": str(s.get("id")) in allowed} for s in kn.sources(ROOT)]
    if want_json:
        print(_json.dumps({"kind": "knowledge-visible",
                           "clearance": clearance, "sources": rows},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge visible --as %s ==" % clearance)
        for r in rows:
            print("  %-22s %-11s %s" % (r["id"], r["visibility"],
                                        "可见" if r["visible"] else "裁剪"))
    return 0


def _knowledge_frequency(args):
    import json as _json
    from core import knowledge as kn

    want_json = bool(getattr(args, "json", False))
    # 形状闸门（2026-09-30）：`--trace <目录>` 此前落到读盘抛
    # `[Errno 13] Permission denied: '…'`，无指引（与 attest/sig/diff 同类）。
    tp = args.trace if os.path.isabs(args.trace) else os.path.join(ROOT, args.trace)
    if not os.path.isfile(tp):
        return _machine_fail(
            args, "trace 件不存在：%s（修复指引：`--trace` 收 `nf assemble --check "
                  "<成品.md> --trace <trace.json>` 落盘的**文件**；目录不会被展开）"
                  % args.trace, 1)
    try:
        counts = kn.harvest_frequency(args.trace)
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc), 1)
    if args.write:
        kn.write_usage(ROOT, counts)
    issues, _warns, stats = kn.verify_usage(ROOT)
    if want_json:
        print(_json.dumps({"kind": "knowledge-frequency", "counts": counts,
                           "written": bool(args.write),
                           "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge frequency（%d 源有事件 · 共 %d 次）=="
              % (len(counts), sum(counts.values())))
        for k, v in counts.items():
            print("  %-22s %d" % (k, v))
        if not counts:
            print("  （trace 中无 knowledge_source 事件）")
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if args.write and not issues:
            print("  ✓ 频率台账已写入 %s（频次可复算）" % kn.USAGE_REL)
        elif not args.write:
            print("  （未写台账；加 --write 落盘）")
    return 1 if issues else 0


def _knowledge_lint(args):
    import json as _json
    from core import knowledge as kn

    want_json = bool(getattr(args, "json", False))
    issues, warns, stats = kn.lint(ROOT)
    if want_json:
        print(_json.dumps({"kind": "knowledge-lint", "issues": issues,
                           "warns": warns, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge lint（知识层巡检）==")
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in warns:
            print("  [WARN] %s" % w)
        if not issues:
            print("  ✓ 声明/顺序/溯源/悬空/孤儿 全绿（时效缺失 %d 件已记 WARN）"
                  % stats.get("no_stale_after", 0))
    return 1 if issues else 0


def _knowledge_transform_apply(args, tcmd):
    import datetime as _dt
    import json as _json
    from core import knowledge as kn

    want_json = bool(getattr(args, "json", False))
    src = args.src.strip()
    dst = args.dst.strip().replace("\\", "/")
    at = args.at.strip() or _dt.date.today().isoformat()  # noqa: DTZ011 - 本地日历日期是有意语义（UTC 会在跨零点给出错误「今天」）
    if not os.path.isfile(os.path.join(ROOT, dst)):
        print("  ✗ 产物不存在：%s（记录的 to 必须是仓库内真实件）" % dst,
              file=sys.stderr)
        return 1
    if src not in kn.reference_ids(ROOT):
        print("  ✗ from 必须是已声明的参考级源：%s（修复指引：nf knowledge 列全部源）"
              % src, file=sys.stderr)
        return 1
    digest = kn.sha256_file(os.path.join(ROOT, dst))
    entries = [dict(e) for e in (kn.load_log(ROOT).get("entries") or [])]
    cur = next((e for e in entries
                if e.get("from") == src and e.get("to") == dst), None)
    if cur is None:
        cur = {"from": src, "to": dst, "digest": digest, "reviewed_by": "",
               "reviewed_at": "", "evidence": [], "promoted": False}
        entries.append(cur)
    cur["digest"] = digest
    if args.by.strip():
        cur["reviewed_by"] = args.by.strip()
    cur["reviewed_at"] = at
    if tcmd == "promote":
        ev = [x.strip() for x in (args.evidence or "").split(",") if x.strip()]
        missing = [t for t in kn.TIERS if t not in ev]
        if missing:
            print("  ✗ 转正须齐三档证据，缺：%s（修复指引：--evidence %s）"
                  % ("/".join(missing), ",".join(kn.TIERS)), file=sys.stderr)
            return 1
        if not cur.get("reviewed_by"):
            print("  ✗ 转正须复核双签：缺 --by", file=sys.stderr)
            return 1
        cur["evidence"] = list(ev)
        cur["promoted"] = True
    kn.write_log(ROOT, entries)
    issues, _w, stats = kn.verify_transform(ROOT)
    if want_json:
        print(_json.dumps({"kind": "knowledge-transform", "entry": cur,
                           "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge transform %s ==" % tcmd)
        print("  %s → %s（digest %s）转正=%s 复核=%s@%s"
              % (src, dst, digest[:12], cur.get("promoted"),
                 cur.get("reviewed_by") or "-", cur.get("reviewed_at") or "-"))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 记录已落盘，且与产物摘要一致（产物一改记录即失效）")
    return 1 if issues else 0


def _knowledge_transform(args):
    import json as _json
    from core import knowledge as kn

    want_json = bool(getattr(args, "json", False))
    tcmd = getattr(args, "transform_cmd", None)
    if tcmd in ("add", "promote"):
        return _knowledge_transform_apply(args, tcmd)
    issues, _warns, stats = kn.verify_transform(ROOT)
    log = kn.load_log(ROOT)
    if want_json:
        print(_json.dumps({"kind": "knowledge-transform", "issues": issues,
                           "stats": stats,
                           "entries": log.get("entries") or []},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge transform（消化记录：%d 条）==" % stats.get("entries", 0))
        for e in log.get("entries") or []:
            print("  %-18s → %-28s 转正=%s" % (e.get("from"), e.get("to"),
                                                e.get("promoted")))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 记录与产物摘要一致（无记录 = 无转正，符合 stay-reference）")
    return 1 if issues else 0


def _knowledge_status(args):
    import json as _json
    from core import knowledge as kn

    want_json = bool(getattr(args, "json", False))
    issues, warns, stats = kn.scan(ROOT)
    decl = kn.load_decl(ROOT)
    if want_json:
        print(_json.dumps({"kind": "knowledge", "declaration": decl,
                           "issues": issues, "warns": warns, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf knowledge（双源知识层 · %d 源：合同 %d / 参考 %d）=="
              % (stats.get("sources", 0), stats.get("contract", 0), stats.get("reference", 0)))
        for s in kn.sources(ROOT):
            print("  %-22s %-9s %-18s %-10s %s"
                  % (s.get("id"), s.get("authority"), s.get("kind"),
                     s.get("visibility"), s.get("locator")))
        for w in warns:
            print("  [WARN] %s" % w)
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 权威分层/查询有序/时效/晋升/审核/认知裁剪 全部与判据一致")
    return 1 if issues else 0


def _cmd_knowledge(args):
    """nf knowledge：双源知识层（状态 / 顺序 / 巡检 / 消化记录 / 资产本体索引）。"""
    sub = getattr(args, "knowledge_cmd", None) or "status"
    if sub == "graph":
        return _knowledge_graph(args)
    if sub == "order":
        return _knowledge_order(args)
    if sub == "visible":
        return _knowledge_visible(args)
    if sub == "frequency":
        return _knowledge_frequency(args)
    if sub == "lint":
        return _knowledge_lint(args)
    if sub == "transform":
        return _knowledge_transform(args)
    return _knowledge_status(args)
