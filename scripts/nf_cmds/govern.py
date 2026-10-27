"""CLI 处理器：govern（自 scripts/nf.py 抽出；行为逐字保留，由 nf.py re-export）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, _rel_out)

def _cmd_design_audit(args) -> int:
    """nf design audit：M_AUDIT 协议设计审计（决策过程质量）。

    audit init <question> --target T --mode {steelman,blindspot,full}
    audit --check <file>    # schema/verdict/清单边界；缺文件提示非红
    audit ls [--root]       # 审计记录索引
    """
    from pathlib import Path
    from core.audit import init_audit, check_audit, scan_audit

    if args.check_file:
        p = Path(args.check_file)
        warns = check_audit(p)
        if not warns:
            print(f"  ✓ 审计结构自检通过: {p}")
            return 0
        print(f"== nf design audit --check {p} ==")
        for w in warns:
            print(f"  ⚠ {w}")
        return 1
    if args.action == "init":
        if not args.question:
            print('  ✗ init 需要审计问题: nf design audit init "<问题>" --target T')
            return 2
        if not args.target:
            print('  ✗ init 需要 --target（被审计对象）: 如 --target "38 方案"')
            return 2
        out = Path(args.out) if args.out else Path.cwd() / "audit.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        init_audit(args.question, target=args.target, mode=args.mode,
                   context=args.context, path=out)
        print(f"== nf design audit init（mode={args.mode}）==")
        print(f"  ✓ audit.md 已生成: {out}")
        print("    按引导问卷完成各节回填，然后 --check 自检")
        return 0
    # ls
    root = Path(args.root)
    if not root.is_dir():
        print(f"  ✗ 目录不存在: {root}")
        return 1
    hits = scan_audit(root)
    print("== nf design audit ls ==")
    if not hits:
        print("  （无 audit.md——nf design audit init 生成第一份）")
        return 0
    print(f"  审计记录 {len(hits)} 份:")
    for h in hits:
        print(f"  · {h}")
    return 0

def _cmd_review(args):
    """nf review：缺口逐行审查（模型判 + 证据复核）。"""
    from core import gap_review as gr
    import json as _json
    scope = tuple(s for s in (args.scope or "").split(",") if s)
    # 拼错的 --scope **不许静默成空表**（那读起来像「这一类没缺口」）：fail-closed + 可枚举面。
    bad = gr.unknown_classes(scope)
    if bad:
        print("  ✗ 未知 --scope：%s（可枚举：%s）"
              "（修复指引：--scope 只收这些类别，逗号分隔；不带 --scope 即全类）"
              % ("、".join(bad), " / ".join(gr.CLASSES)), file=sys.stderr)
        return 2
    doc = gr.review(ROOT, adapter=args.adapter, endpoint=args.endpoint,
                    limit=args.limit, batch=max(1, args.batch), timeout=args.timeout,
                    classes=scope)
    if args.json:
        print(_json.dumps({"kind": "review", **doc},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf review（逐行缺口审查 · 适配器 %s）==" % args.adapter)
        print("  %s" % gr.summary(doc))
        # 缺件 ⇒ 某类候选**无从判定**：如实报出并判非零（不许把「判不了」当成「没缺口」）
        for i in doc.get("issues") or []:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for r in doc["fixable"][:40]:
            print("  [可修] %-22s %s:%s  p=%s sev=%s | %s"
                  % (r["class"], r["file"], r["line"],
                     ("%.2f" % r["model_gap_p"]) if r["model_gap_p"] is not None else "-",
                     ("%.2f" % r["model_severity"]) if r["model_severity"] is not None else "-",
                     r["evidence"][:88]))
        if doc["suspected"]:
            print("  —— 模型怀疑但**无证据**（不修，只挂账）%d 条" % len(doc["suspected"]))
    if args.write:
        if args.write.replace("\\", "/").startswith("protocol/"):
            print("  ✗ 报告不得写入协议层 protocol/（修复指引：写 results/ 或 .rivet/）",
                  file=sys.stderr)
            return 2
        dest = os.path.join(ROOT, args.write)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        from core import atomic_write          # 审查报告：原子写
        atomic_write.write_text(dest, _json.dumps(
            doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        print("  报告已写入：%s" % args.write)
    return 2 if (doc.get("issues") or []) else 0

def _cmd_workloop(args):
    """nf workloop：决策模型挑活 → 工单（只落内部档案）→ 收口记档。"""
    from core import workloop as wl
    import json as _json
    if args.close:
        rel = wl.close(ROOT, args.close, args.outcome or "landed", args.gate or "unknown",
                       args.note)
        print("  ✓ 已收口：%s（结果 %s · 门禁 %s）"
              % (rel, args.outcome or "landed", args.gate or "unknown"))
        return 0
    if args.list:
        rows = wl.items(ROOT, limit=max(1, args.top), source=args.source)
        if args.json:
            print(_json.dumps({"kind": "workloop-ls", "count": len(rows),
                               "rows": rows},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for it in rows:
                print("  %-28s %-16s %s" % (it["id"], it["kind"], it["title"]))
            print("  （共 %d 项在册%s；这是决策层的候选面）"
                  % (len(wl.items(ROOT, source=args.source)),
                     "（来源限定 %s）" % args.source if args.source else ""))
        return 0
    doc = wl.plan(ROOT, adapter=args.adapter, top=max(1, args.top),
                  endpoint=args.endpoint, timeout=args.timeout, source=args.source)
    if args.json:
        print(_json.dumps({"kind": "workloop", **doc},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(wl.render_brief(doc))
    if args.write and doc.get("status") == "ok":
        rel = wl.write_order(ROOT, doc)
        if not args.json:
            print("\n  工单已落内部档案：%s（计划类产品内部消化，不入公开仓）" % rel)
    return 0 if doc.get("status") == "ok" else 1

def _cmd_decide(args):
    """nf decide：决策层统一入口（stub 走门禁口径；外部适配器为非门禁任务）。"""
    from core import decision_layer as dl
    import json as _json
    # 形状闸门（2026-09-30 同族扫）：`--state <目录>` / `--questions <非 JSON>` 此前直接落
    # `open`/`json.load` 抛异常 ⇒ 冒到 CLI 兜底报「内部错误 + [Errno 13]」或裸解析错（无指引）。
    if args.state:
        sp = args.state if os.path.isabs(args.state) else os.path.join(ROOT, args.state)
        if not os.path.isfile(sp):
            return _machine_fail(
                args, "--state 不是文件：%s（修复指引：给**文件**路径——决策状态文本；"
                      "也可改用 `--state-text \"…\"` 直接内联）" % args.state, 1)
    qp = args.questions if os.path.isabs(args.questions) else os.path.join(ROOT, args.questions)
    if not os.path.isfile(qp):
        return _machine_fail(
            args, "--questions 不是文件：%s（修复指引：给**JSON 文件**——候选集/问题上报表，"
                  "形状见 docs/decision-layer.md；`nf decide --dry-run` 可先做决策层体检）"
                  % args.questions, 1)
    if args.state:
        with open(args.state, encoding="utf-8") as fh:
            state = fh.read()
    else:
        state = args.state_text
    try:
        with open(args.questions, encoding="utf-8") as fh:
            questions = _json.load(fh)
    except ValueError as exc:   # 在场但不是合法 JSON ⇒ 干净错误 + 指引
        return _machine_fail(
            args, "--questions 不是合法 JSON：%s（修复指引：形状见 "
                  "docs/decision-layer.md；`nf decide --dry-run` 可先做决策层体检）" % exc, 1)
    req = {"state": state, "questions": questions}
    if args.dry_run:
        issues, stats = dl.scan(ROOT)
        if args.json:
            print(_json.dumps({"kind": "decide-dryrun", "issues": issues,
                               "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 决策层面体检通过（%s）" % dl.summary(stats))
        return 1 if issues else 0
    out = dl.decide(req, adapter=args.adapter, endpoint=args.endpoint,
                    model=args.model, timeout=args.timeout, root=ROOT)
    if args.json:
        print(_json.dumps({"kind": "decide", **out},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        if out.get("status") == "abstained":
            print("  ⚠ abstained：%s" % out.get("reason"))
        else:
            for name, ans in (out.get("answers") or {}).items():
                if ans.get("type") == "choice":
                    print("  %-14s choice → %s（p=%.3f）"
                          % (name, ans.get("argmax"),
                             (ans.get("probs") or [0])[list(ans.get("options") or [])
                              .index(ans.get("argmax"))] if ans.get("options") else 0.0))
                elif ans.get("type") == "score":
                    print("  %-14s score → 期望值 %.2f（%s）"
                          % (name, ans.get("value", 0.0),
                             " ".join("%.2f" % p for p in ans.get("probs") or [])))
                else:
                    print("  %-14s noul → p(true)=%.3f" % (name, ans.get("p", 0.0)))
            meta = out.get("meta") or {}
            print("  （适配器 %s · calibrated=%s · 决策层不出现在门禁路径）"
                  % (meta.get("adapter"), meta.get("calibrated")))
    return 0 if out.get("status") == "ok" else 1

def _cmd_audit(args):
    """nf audit：审计/验收（列表 / 单件机检 / 全量机检）。"""
    from core import audit as au
    import json as _json
    sub = getattr(args, "audit_cmd", None) or "ls"
    want_json = bool(getattr(args, "json", False))
    if sub == "rebind":
        issues, st = au.rebind(ROOT, note=args.note, dry_run=bool(args.dry_run))
        if want_json:
            print(_json.dumps({"kind": "audit-rebind", "issues": issues, "stats": st},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf audit rebind%s ==" % ("（dry-run）" if args.dry_run else ""))
            print("  %s" % st.get("note"))
            print("  审计件 %d · 重绑 %d 件 / %d 条摘要 · 跳过（legacy）%d 件"
                  % (st.get("records", 0), st.get("rechained", 0), st.get("subjects", 0),
                     st.get("skipped", 0)))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
        return 1 if issues else 0
    if sub == "check":
        # 形状闸门（2026-10-01）：`nf audit check <目录>` 此前只吐一行「审计件不存在：docs」
        # 的 [FAIL]（**零指引**）——先判形状，给可执行口径（与 `nf postmortem check` 同规）。
        ap_path = args.path if os.path.isabs(args.path) else os.path.join(ROOT, args.path)
        if not os.path.isfile(ap_path):
            return _machine_fail(
                args, "审计件不存在：%s（修复指引：给**在场**审计件 md 路径（相对仓库根或"
                      "绝对皆可）；`nf audit` 可枚举既有审计件）" % args.path, 1)
        issues, st = au.check_doc(ROOT, args.path)
        if want_json:
            print(_json.dumps({"kind": "audit-check", "path": args.path,
                               "issues": issues, "stats": st},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf audit check %s%s ==" % (
                args.path, "（legacy：无审计头，按 WARN 挂账）" if st.get("legacy") else ""))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues and not st.get("legacy"):
                print("  ✓ 必填齐 · verdict 在册 · 结论绑定对象 digest · 签收双要素")
        return 1 if issues else 0
    if sub == "verify":
        issues, warns, stats = au.scan(ROOT)
        if want_json:
            print(_json.dumps({"kind": "audit-verify", "issues": issues,
                               "warns": warns, "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf audit verify（%d 件 · 带审计头 %d · legacy %d）=="
                  % (stats.get("audits", 0), stats.get("with_header", 0), stats.get("legacy", 0)))
            for w in warns:
                print("  [WARN] %s" % w)
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 声明与全部审计件一致（legacy 只挂账不判死）")
        return 1 if issues else 0
    rows = au.entries(ROOT)
    if want_json:
        print(_json.dumps({"kind": "audit-ls", "count": len(rows),
                           "rows": [{k: e["fm"].get(k) for k in
                                     ("id", "date", "scope", "verdict", "auditor")}
                                    for e in rows]},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf audit（%d 件）==" % len(rows))
        for e in rows:
            fm = e["fm"]
            print("  %-11s %-6s %-11s %s" % (fm.get("id") or "(legacy)",
                                             fm.get("verdict") or "-",
                                             fm.get("date") or "-", e["file"]))
    return 0

def _cmd_postmortem(args):
    """nf postmortem：复盘（列表 / 单件机检 / 全量机检）。"""
    from core import postmortem as pm
    import json as _json
    sub = getattr(args, "postmortem_cmd", None) or "ls"
    want_json = bool(getattr(args, "json", False))
    if sub == "check":
        # 通配**由程序自行展开**（文档示例写 `postmortems/PO-0001-*.md`，而 cmd 不展开
        # ⇒ 原实现把字面通配当路径查，报「复盘件不存在」；与 `nf bench` 同类，2026-09-30 修）。
        import glob as _glob
        # 形状闸门（2026-09-30）：glob 到**目录**（如 `nf postmortem check docs`）此前会把
        # 目录当复盘件查，正文报「复盘件不存在：docs」（`[FAIL]` 行）——**无指引**且框定错误。
        matched = [f for f in sorted(_glob.glob(_rel_out(args.path))) if os.path.isfile(f)]
        if not matched:
            return _machine_fail(
                args, "未匹配到复盘件**文件**：%s（修复指引：`nf postmortem ls` 可枚举既有"
                      "复盘件；通配由本命令自行展开，无需依赖 shell；目录不会被展开为文件）"
                      % args.path, 1)
        issues, actions = [], 0
        for one in matched:
            rel = os.path.relpath(one, ROOT).replace(os.sep, "/")
            i_one, st_one = pm.check_doc(ROOT, rel)
            issues += ["%s：%s" % (rel, i) for i in i_one]
            actions += int((st_one or {}).get("actions", 0) or 0)
        st = {"files": len(matched), "actions": actions}
        if want_json:
            print(_json.dumps({"kind": "postmortem-check", "path": args.path,
                               "issues": issues, "stats": st},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf postmortem check %s（行动项 %d 条）==" % (args.path, st.get("actions", 0)))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 四段齐 · 无指责 · 根因指向机制 · 行动项带负责人与判据")
        return 1 if issues else 0
    if sub == "verify":
        issues, warns, stats = pm.scan(ROOT)
        if want_json:
            print(_json.dumps({"kind": "postmortem-verify", "issues": issues,
                               "warns": warns, "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf postmortem verify（%d 件 · 行动项 %d 条）=="
                  % (stats.get("postmortems", 0), stats.get("actions", 0)))
            for w in warns:
                print("  [WARN] %s" % w)
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 声明与全部复盘件一致")
        return 1 if issues else 0
    rows = pm.entries(ROOT)
    if want_json:
        print(_json.dumps({"kind": "postmortem-ls", "count": len(rows),
                           "rows": [{k: e["fm"].get(k) for k in
                                     ("id", "title", "status", "date", "trigger")}
                                    for e in rows]},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf postmortem（%d 件）==" % len(rows))
        for e in rows:
            fm = e["fm"]
            print("  %-9s %-7s %-10s %s" % (fm.get("id"), fm.get("status"),
                                            fm.get("date"), fm.get("title")))
    return 0

def _cmd_handover(args):
    """nf handover：接力协议（列表 / 单件机检 / 全量机检）。"""
    from core import handover as ho
    import json as _json
    sub = getattr(args, "handover_cmd", None) or "ls"
    want_json = bool(getattr(args, "json", False))
    if sub == "check":
        # 形状闸门（2026-10-01）：同 `nf audit check`——此前只吐一行「交接件不存在：docs」。
        ho_path = args.path if os.path.isabs(args.path) else os.path.join(ROOT, args.path)
        if not os.path.isfile(ho_path):
            return _machine_fail(
                args, "交接件不存在：%s（修复指引：给**在场**接力件 md 路径（相对仓库根或"
                      "绝对皆可）；`nf handover` 可枚举既有接力件）" % args.path, 1)
        issues, st = ho.check_doc(ROOT, args.path)
        if want_json:
            print(_json.dumps({"kind": "handover-check", "path": args.path,
                               "issues": issues, "stats": st},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf handover check %s（未决 %d 条）==" % (args.path, st.get("pending", 0)))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 五段齐 · 未决非空且每条带判据 · refs 可解析")
        return 1 if issues else 0
    if sub == "verify":
        issues, warns, stats = ho.scan(ROOT)
        if want_json:
            print(_json.dumps({"kind": "handover-verify", "issues": issues,
                               "warns": warns, "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf handover verify（%d 件 · 未决 %d 条）=="
                  % (stats.get("handovers", 0), stats.get("pending", 0)))
            for w in warns:
                print("  [WARN] %s" % w)
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 声明与全部交接件一致")
        return 1 if issues else 0
    rows = ho.entries(ROOT)
    if want_json:
        print(_json.dumps({"kind": "handover-ls", "count": len(rows),
                           "rows": [{k: e["fm"].get(k) for k in
                                     ("id", "title", "status", "date", "from", "to")}
                                    for e in rows]},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf handover（%d 件）==" % len(rows))
        for e in rows:
            fm = e["fm"]
            print("  %-9s %-7s %-10s %s → %s" % (fm.get("id"), fm.get("status"),
                                                 fm.get("date"), fm.get("from"), fm.get("to")))
    return 0

def _cmd_decisions(args):
    """nf decisions：决策记录（列表 / 单条 / 机检 / 投影重建）。"""
    from core import decisions as dc
    import json as _json
    sub = getattr(args, "decisions_cmd", None) or "ls"
    want_json = bool(getattr(args, "json", False))
    if sub == "reindex":
        out = dc.write_projection(ROOT)
        if want_json:
            # 机器面（2026-10-01 修）：同 `patterns reindex`——声明了 `--json` 却打散文。
            print(_json.dumps({"kind": "decisions-reindex", "ok": True,
                               "changed": out["changed"],
                               "note": "decisions/INDEX 投影已重建（真源 = 各 ADR 头）"},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  ✓ decisions/INDEX 投影已重建：%s"
                  % ("有变化" if out["changed"] else "无变化"))
        return 0
    if sub == "show":
        want = args.id.strip().upper()
        hit = next((e for e in dc.entries(ROOT)
                    if str(e["fm"].get("id")) == want), None)
        if hit is None:
            return _machine_fail(args, "未找到：%s（修复指引：nf decisions 可枚举）" % args.id, 1)
        if want_json:
            print(_json.dumps({"kind": "decisions-show", "id": want,
                               "path": hit["path"], "frontmatter": hit["fm"]},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf decisions show %s ==" % want)
            for k in sorted(hit["fm"]):
                print("  %-14s %s" % (k + ":", hit["fm"][k]))
            print()
            print(hit["body"].strip()[:1200])
        return 0
    issues, warns, stats = dc.scan(ROOT)
    proj = dc.check_projection(ROOT)
    if sub == "verify":
        if want_json:
            print(_json.dumps({"kind": "decisions-verify", "issues": issues,
                               "warns": warns, "projection": proj,
                               "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf decisions verify（%d 条 · accepted %d）=="
                  % (stats.get("decisions", 0), stats.get("accepted", 0)))
            for i in list(issues) + list(proj):
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues and not proj:
                print("  ✓ 编号/状态/取代链/证据可解析/三段齐/回执锚定 全部一致")
        return 1 if (issues or proj) else 0
    rows = dc.entries(ROOT)
    if want_json:
        print(_json.dumps({"kind": "decisions-ls", "count": len(rows),
                           "rows": [{k: e["fm"].get(k) for k in
                                     ("id", "title", "status", "date", "superseded_by")}
                                    for e in rows]},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf decisions（%d 条）==" % len(rows))
        for e in rows:
            fm = e["fm"]
            print("  %-9s %-11s %-10s %s" % (fm.get("id"), fm.get("status"),
                                             fm.get("date"), fm.get("title")))
    return 0

def _cmd_approve(args):
    """nf approve：内容绑定批准记录（生成 / 校验）。"""
    from core import approval
    import json as _json
    if args.list:
        rows = approval.list_records(ROOT)
        if args.json:
            print(_json.dumps({"kind": "approve-ls", "count": len(rows),
                               "rows": rows},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf approve --list（%d 条）==" % len(rows))
            for r in rows:
                print("  %s %-42s by %-12s %s%s"
                      % ("✗失效" if r["stale"] else "✓有效", r["subject"],
                         r["approved_by"] or "-", r["approved_at"],
                         ("　· " + r["note"][:30]) if r["note"] else ""))
            if not rows:
                print("  （暂无记录）")
        return 0
    if args.verify:
        issues, stats = approval.verify(ROOT)
        if args.json:
            print(_json.dumps({"kind": "approve-verify", "issues": issues,
                               "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf approve --verify（%d 条）==" % stats.get("records", 0))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 全部批准记录有效（内容绑定未失效）")
        return 1 if issues else 0
    if not args.subject:
        print("  ✗ 需要被批准对象路径（或 --verify）（修复指引：nf approve <path> --by <人>）",
              file=sys.stderr)
        return 2
    try:
        rel = approval.approve(ROOT, args.subject, args.by, args.note)
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))
    if args.json:
        print(_json.dumps({"kind": "approve", "ok": True, "record": rel},
                          ensure_ascii=False, indent=2))
    else:
        print("  ✓ 批准记录已写入：%s（对象改动即自动失效）" % rel)
    return 0
