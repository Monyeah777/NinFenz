"""CLI 处理器：misc（自 scripts/nf.py 抽出；行为逐字保留，由 nf.py re-export）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, _rel_display, _rel_out, _rel_to_root, _policy_text)

def _cmd_sig(args):
    """nf sig：41 波C C1 —— 结构化签名（知识指纹）。"""
    from core import knowledge_sig as ks
    import json as _json
    try:
        if args.verify:
            issues, stats = ks.verify_reproducible(ROOT)
            print("== nf sig --verify（check25 同语义）==")
            print("  文档 %d · 可复现 %d" % (stats["docs"], stats["reproducible"]))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 01-36 全量签名两遍一致（知识指纹稳定）"); return 0
            return 1
        targets = list(args.target) if args.target else ks.discover_docs(ROOT)
        if not targets:
            print("  ✗ 未找到签名目标（缺省 = 根目录 01-36 编号方案文档）",
 file=sys.stderr); return 1
        out = []
        for t in targets:
            # 形状闸门（2026-09-30）：`nf sig <目录>` 此前落到读盘抛
            # `[Errno 13] Permission denied: '<机器绝对路径>'`，无指引 + 回吐机器路径。
            if not os.path.isfile(t if os.path.isabs(t) else os.path.join(ROOT, t)):
                return _machine_fail(
                    args, "签名目标不是文件：%s（修复指引：`nf sig` 收**文件**"
                          "（缺省 = 根目录 01-36 编号方案文档，`nf sig --verify` 做两遍"
                          "复现校验）；要签目录里的某一件，请指明具体文件名）" % t)
            rel = _rel_to_root(t)
            sig = ks.build_signature(rel, ROOT)
            out.append({"digest": ks.signature_digest(sig), "sig": sig})
        if args.json:
            print(_json.dumps({"kind": "sig", "count": len(out), "rows": out},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf sig（%d 文档）==" % len(out))
            for r in out:
                s = r["sig"]
                print("  %s  %-10s %-8s %s  refs=%d" %
                      (r["digest"][:12], s["path"], s["doc_id"],
                       s["title"][:28], len(s["refs"])))
        return 0
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))

def _cmd_attest(args):
    """nf attest：内容 attestation 生成/校验（三级信任；缺锚一律拒绝）。"""
    from core import attest
    import json as _json
    if getattr(args, "selfcheck", False):
        # 机制体检（2026-10-17）：check42 是门禁侧入口，这一面是**用户侧**入口——
        # 让「验签方 ≠ 签名方」这条结论随时可复跑，而不必等全量门禁。
        from core import provenance_external as pex
        issues, stats = pex.scan(ROOT)
        if args.json:
            print(_json.dumps({"kind": "attest-selfcheck", "ok": not issues,
                               "issues": issues, "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf attest --selfcheck（外部验签机制体检）==")
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 独立子进程验签通过 · 篡改必红 · 外锚=%s"
                      % ("在场" if stats.get("external_anchor") else "缺位（如实登记）"))
        return 1 if issues else 0
    try:
        if args.verify:
            # 形状闸门（2026-09-30）：`--verify <目录>` 此前落到 open(dir) 抛
            # `[Errno 13] Permission denied: '<机器绝对路径>'`，无指引 + 回吐机器路径。
            if not os.path.isfile(_rel_out(args.verify)):
                return _machine_fail(
                    args, "信封不是文件：%s（修复指引：`--verify` 收 `nf attest --out "
                          "<信封.json>` 写出的**信封 JSON**；先生成——`nf attest <文件> "
                          "--out <信封.json>`）" % args.verify)
            # 格式闸门（2026-10-01）：坏信封此前回吐裸解析错（与 `nf score --baseline` 同族）。
            try:
                # 用**绝对**落点打开：`_rel_to_root` 给的是仓相对路径，直接 `open` 会按进程
                # cwd 解析（实测从非仓根 cwd 跑 → `[Errno 2] ..\..\AppData\…`）。
                with open(os.path.join(ROOT, _rel_to_root(args.verify)),
                          encoding="utf-8") as fh:
                    payload = _json.load(fh)
            except ValueError as exc:
                return _machine_fail(
                    args, "信封不是合法 JSON：%s（%s）（修复指引：收 `nf attest --out "
                          "<信封.json>` 写出的信封；坏件请重新生成）" % (args.verify, exc), 1)
            items = (payload.get("attestations")
                     if isinstance(payload, dict) and "attestations" in payload
                     else [payload])
            key = attest.read_key_file(_rel_out(args.key_file)) if args.key_file else None
            results = []
            for att in items:
                ok, issues, level = attest.verify(att, ROOT, key=key)
                results.append({"subject": (att.get("subject") or {}).get("path"),
                                "ok": ok, "level": level, "issues": issues})
            all_ok = bool(results) and all(r["ok"] for r in results)
            if args.json:
                print(_json.dumps({"kind": "attest-verify", "ok": all_ok,
                                   "results": results},
                                  ensure_ascii=False, indent=2))
            else:
                print("== nf attest --verify（%d 件）==" % len(results))
                for r in results:
                    print("  %s %-34s 信任级：%s"
                          % ("✓" if r["ok"] else "✗", r["subject"], r["level"]))
                    for i in r["issues"]:
                        print("    [FAIL] %s" % i, file=sys.stderr)
            return 0 if all_ok else 1
        targets = [args.target] if args.target else list(attest.DEFAULT_SUBJECTS)
        key = attest.read_key_file(_rel_out(args.key_file)) if args.key_file else None
        items = []
        for t in targets:
            # 形状闸门（2026-09-30）：`nf attest <目录>` 此前落到读盘抛
            # `[Errno 13] Permission denied: '<机器绝对路径>'`，无指引 + 回吐机器路径。
            if not os.path.isfile(t if os.path.isabs(t) else os.path.join(ROOT, t)):
                return _machine_fail(
                    args, "目标不是文件：%s（修复指引：`nf attest` 只收**文件**"
                          "（缺省 = 出厂件清单）；目录请先 `ls` 定位具体件，"
                          "校验已签发信封用 `nf attest --verify <信封.json>`）" % t)
            att = attest.build(_rel_to_root(t), ROOT, issuer=args.issuer)
            if key:
                att = attest.sign_hmac(att, key)
            items.append(att)
        payload = (items[0] if len(items) == 1
                   else {"schema": "nf-attest-set/1", "attestations": items})
        if args.out:
            out_path = (args.out if os.path.isabs(args.out)
                        else os.path.join(ROOT, args.out))
            # 形状闸门（2026-09-30 二扫）：`--out <目录>` 此前落到 open 抛裸
            # `[Errno 13] Permission denied`（无指引）。
            if os.path.isdir(out_path):
                return _machine_fail(
                    args, "--out 落点是目录：%s（修复指引：给**文件**路径，如 "
                          "attest.json）" % args.out, 1)
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            from core import atomic_write      # 信封交付件：原子写
            atomic_write.write_text(out_path, _json.dumps(
                payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        if args.json:
            print(_json.dumps({"kind": "attest", **payload},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf attest（%d 件）==" % len(items))
            for att in items:
                sig = att.get("signature") or {}
                print("  %s  %-34s 级=%s  信封=%s"
                      % (att["subject"]["sha256"][:12], att["subject"]["path"],
                         sig.get("scheme") or "digest_only",
                         att["envelope_digest"][:12]))
            if args.out:
                print("  写入：%s" % _rel_display(out_path))
            if not key:
                print("  提示：未加 --key-file → digest_only 级（只证一致，"
                      "不证诚实性）；对外可验证需 hmac 密钥或 sigstore 外挂锚。",
                      file=sys.stderr)
        return 0
    except UnicodeDecodeError as exc:
        # 非 UTF-8 目标（2026-10-01 探针）：此前只回裸 `'utf-8' codec can't decode …`
        # ——**零指引**的输入问题。收口成带修复指引的用户错误（与 `nf import` 同口径）。
        return _machine_fail(
            args, "目标不是 UTF-8 文本：%s（修复指引：本命令只收 **UTF-8** 文本件"
                  "（md / json）；其它编码或二进制请先转成 UTF-8 再签）" % exc)
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))

def _cmd_receipts(args):
    """nf receipts：协议层回执单根（生成 / 校验 / 单条验证）。"""
    from core import receipts as rc
    import json as _json
    path = os.path.join(ROOT, rc.PROTOCOL_RECEIPTS_REL)
    if args.write:
        rel = rc.write_scope(ROOT, scope=args.scope)
        doc = rc.build_scope(ROOT, scope=args.scope)
        print("  ✓ 协议层回执已写入：%s（根 %s · %d 件）"
              % (rel, doc["root"][:16], doc["count"]))
        # 派生面联动刷新（真实事故驱动）：in-toto / SLSA / PROV / CID 等派生面与透明日志
        # 都绑定回执根——重签后不刷新，check31/check33 会红（本波实测踩到一次）。
        refreshed = []
        try:
            from core import transparency_log as _tl
            if os.path.isfile(os.path.join(ROOT, _tl.GENERATED_REL)):
                _tl.write(ROOT)
                refreshed.append(_tl.GENERATED_REL)
        except Exception as exc:            # 不静默：刷新失败要看得见
            print("  [warn] 透明日志未刷新：%s" % exc, file=sys.stderr)
        interop_dir = os.path.join(ROOT, "results", "interop")
        if os.path.isdir(interop_dir):
            try:
                from core import interop_export as _ie
                for kind in _ie.KINDS:
                    with open(os.path.join(interop_dir, "%s.json" % kind), "wb") as fh:
                        fh.write(_ie.render(kind, ROOT))
                refreshed.append("results/interop/*.json（%d 面）" % len(_ie.KINDS))
            except Exception as exc:
                print("  [warn] 互操作入仓面未刷新：%s" % exc, file=sys.stderr)
        if refreshed:
            print("  ↻ 派生面联动刷新：%s" % " · ".join(refreshed))
        return 0
    if not os.path.exists(path):
        print("  ✗ 缺协议层回执（修复指引：nf receipts --write）", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fh:
        doc = _json.load(fh)
    if args.entry:
        hit = next((e for e in doc.get("entries") or []
                    if e.get("id") == args.entry), None)
        if hit is None:
            return _machine_fail(args, "回执中没有该件：%s（修复指引：`nf receipts` 列全量；"
                                 "路径按仓库相对写法，如 protocol/CONFORMANCE.md）" % args.entry, 1)
        folded = rc.fold_proof(str(hit["leaf"]), hit.get("proof") or [])
        ok = folded == str(doc.get("root"))
        print("== nf receipts --entry %s ==" % hit["id"])
        print("  折叠 %s · 根 %s → %s"
              % (folded[:16], str(doc.get("root"))[:16], "✓ 一致" if ok else "✗ 不一致"))
        return 0 if ok else 1
    issues, stats = rc.verify_scope(doc, ROOT)
    if args.json:
        print(_json.dumps({"kind": "receipts", "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf receipts --scope %s（%d 件 · root=%s）=="
              % (args.scope, stats.get("entries", 0), str(stats.get("root"))[:16]))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 每条回执折叠到根，且根与实时重算一致")
    return 1 if issues else 0

def _cmd_telemetry(args):
    """nf telemetry：trace 记录 → OTel GenAI semconv 属性 / OTLP 形状。"""
    from core import telemetry_semconv as ts
    import json as _json
    tp = args.trace if os.path.isabs(args.trace) else os.path.join(ROOT, args.trace)
    if not os.path.isfile(tp):
        print("  ✗ 目标不存在：%s（修复指引：给出在场 trace JSON 路径——单条记录或 "
              "{records:[...]}；`nf telemetry --help` 有形状说明）" % args.trace, file=sys.stderr)
        return 1
    try:
        records = ts.load_trace(args.trace)
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))
    if not records:
        print("  ✗ trace 为空或格式不识别（支持单条记录或 {records:[...]}）",
              file=sys.stderr)
        return 1
    if args.otlp:
        print(_json.dumps({"kind": "telemetry-otlp",
                           **ts.to_export(records)}, ensure_ascii=False,
                          indent=2, sort_keys=False))
        return 0
    print("== nf telemetry（%d 记录 → semconv 属性）==" % len(records))
    for r in records:
        print("  %s" % ts.tool_name_of(r))
        for k, v in sorted(ts.attributes_for(r).items()):
            print("    %-28s %s" % (k, _json.dumps(v, ensure_ascii=False)))
    return 0

def _cmd_diff(args):
    """nf diff：41 波C C2 —— 结构化差异 + 兼容判定。"""
    from core import knowledge_sig as ks
    import json as _json
    try:
        # 形状闸门（2026-09-30）：`nf diff <目录> <目录>` 此前落到读盘抛
        # `[Errno 13] Permission denied: '<作者机绝对路径>'`，无指引（`_rel_to_root` 只判在场）。
        for side, val in (("a", args.a), ("b", args.b)):
            sp = val if os.path.isabs(val) else os.path.join(ROOT, val)
            if not os.path.isfile(sp):
                return _machine_fail(
                    args, "签名目标不是文件：%s=%s（修复指引：`nf diff a b` 各收**一份文件**"
                          "（01-36 文档 / 管线 / 模块 md，已挂签名的件）；缺省签名面用 "
                          "`nf sig`）" % (side, val))
        ra = _rel_to_root(args.a)
        rb = _rel_to_root(args.b)
        diff = ks.diff_signatures(ks.build_signature(ra, ROOT),
                                 ks.build_signature(rb, ROOT))
        if args.json:
            print(_json.dumps({"kind": "diff", **diff},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf diff ==")
            print("  %s  →  %s" % (diff["from"], diff["to"]))
            if not diff["changes"]:
                print("  无字段差异（两份签名一致）")
            for c in diff["changes"]:
                print("  [%s] %s  %r → %r" % (c["kind"], c["field"], c["from"], c["to"]))
            print("  判定：%s" % diff["verdict"])
            impact = diff.get("impact", "editorial")
            label = {"bump": "结构性（须 bump + 迁移记录）",
                     "additive": "字段级新增（V1 只增不删）",
                     "editorial": "措辞/编辑（无契约影响）"}.get(impact, impact)
            print("  影响度：%s（%s）" % (impact, label))
        return 0
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))

def _cmd_layers(args) -> int:
    """nf layers：抽象阶梯（真源 protocol/LAYERS.json 的投影 + 体检）。"""
    import json

    from core import layer_model as lm

    if args.write:
        try:
            rel = lm.write_region(ROOT)
        except ValueError as exc:
            return _machine_fail(args, str(exc), 1)
        if args.json:
            print(json.dumps({"kind": "layers-write", "ok": True, "refreshed": rel,
                              "note": "生成区真源 protocol/LAYERS.json"},
                             ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print("  ✓ 生成区已刷新：%s（真源 protocol/LAYERS.json）" % rel)
        return 0

    doc = lm.load(ROOT)
    issues, stats = lm.scan(ROOT)

    if args.verify:
        if args.json:
            print(json.dumps({"kind": "layers-verify", "ok": not issues, "issues": issues,
                              "stats": stats}, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if not issues else 1
        print("== nf layers --verify（阶梯体检 · 与 verify check27 R7 同源）==")
        for i in issues:
            print("  [FAIL] %s" % i)
        ok = not issues
        print("  阶 %d · 资产子级 %d · 入口面 %d · 纵切件 %d · 规则 %d → %s"
              % (stats["tiers"], stats["asset_levels"], stats["surfaces"],
                 stats.get("crosscut", 0), stats["rules"],
                 "通过" if ok else "FAIL %d" % len(issues)))
        return 0 if ok else 1

    if args.json:
        print(json.dumps({
            "kind": "layers", "schema": doc.get("schema"),
            "rules": doc.get("rules"), "tiers": doc.get("tiers"),
            "asset_levels": doc.get("asset_levels"),
            "surfaces": doc.get("surfaces"), "crosscut": doc.get("crosscut"),
            "derived": doc.get("derived"), "retirement": doc.get("retirement"),
            "issues": issues, "stats": stats,
        }, ensure_ascii=False, indent=2))
        return 0 if not issues else 1

    print("== nf layers（NF 抽象阶梯 · 两轴 + 纵切）==")
    for t in doc.get("tiers") or []:
        print("[%s] %s（%s · 变更档 %s）"
              % (t.get("order"), t.get("name"), t.get("status"), t.get("change_tier")))
        print("    真源面：%s" % "、".join((t.get("source") or {}).get("globs") or []))
        print("    接口面：%s" % "、".join((t.get("interface") or {}).get("globs") or []))
        print("    实现面：%s" % (t.get("implementation") or {}).get("note", ""))
        print("    判据：%s" % "、".join(t.get("judged_by") or []))
    print("  资产阶五子级：%s"
          % " → ".join(str(lv.get("name")) for lv in doc.get("asset_levels") or []))
    print("  入口面（不作为真源）：%s"
          % "、".join(str(sf.get("name")) for sf in doc.get("surfaces") or []))
    print("  验证纵切：%s"
          % "、".join(str(c.get("id"))
                      for c in (doc.get("crosscut") or {}).get("components") or []))
    print("  体检：nf layers --verify（改真源后跑 --write 刷新 docs/layers.md 生成区）")
    return 0

def _cmd_changelog(args):
    """nf changelog：从变更条目 + 约定式提交生成版本节（默认预览；--write 落盘并归档）。"""
    import json as _json
    from core import changelog_gen as cg
    from core import release_gate as rg

    version = getattr(args, "version", None) or rg.release_line(ROOT)
    date = getattr(args, "date", None) or ""
    use_commits = not getattr(args, "no_commits", False)
    if getattr(args, "write", False):
        if not date:
            print("  ✗ --write 需要 --date YYYY-MM-DD（日期不臆造）", file=sys.stderr)
            return 2
        res = cg.write(ROOT, version=version, date=date, use_commits=use_commits)
        if not res.get("ok"):
            print("  ✗ %s" % "；".join(res.get("issues") or []), file=sys.stderr)
            return 2
        print("  ✓ 已写入 CHANGELOG [%s] 并归档 %d 条变更条目到 changes/%s/"
              % (res["version"], len(res["archived"]), res["version"]))
        return 0
    text = cg.render(ROOT, version=version, date=date, use_commits=use_commits)
    if getattr(args, "json", False):
        issues, stats = cg.check(ROOT)
        print(_json.dumps({"schema": "nf-changelog/1", "version": version, "date": date,
                           "section": text, "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if issues else 0
    print(text, end="")
    return 0

def _cmd_runtime(args):
    """nf runtime：参考运行时（确定性 harness + record/replay）。

    判据与文件读写都在 `core.runtime` 内——本层只做命令面转发（不在此写盘：写面纪律由
    `_PATH_FLAG_DESTS` / 编码闸 + core.runtime 的 fail-closed 校验共同守住）。
    """
    from core import runtime as rt

    if getattr(args, "rt_cmd", "") != "run":
        print("  ✗ 缺子命令（修复指引：nf runtime run --plan <plan.json> "
              "--trace <trace.json>）", file=sys.stderr)
        return 2
    return rt.cli_run(plan=args.plan, trace=args.trace, state=args.state,
                      record=args.record, replay=args.replay, as_json=args.json)

def _cmd_agent(args) -> int:
    """nf agent：多 agent 协作契约（T10.3；只读、不跑真实模型）。"""
    import json as _json
    from core import agent_contracts as ac

    sub = str(getattr(args, "agent_cmd", "") or "")
    if sub == "plan":
        domain = str(getattr(args, "domain", "") or "techdoc")
        try:
            doc = ac.plan(ROOT, domain)
        except ValueError as exc:
            print("  ✗ %s" % exc, file=sys.stderr)
            return 2
        if getattr(args, "json", False):
            print(_json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print("== nf agent plan（域 %s · 管线 %s · 域包 %s）=="
              % (doc["domain"], doc["pipeline"], doc["pack"]))
        for step in doc["chain"]:
            print("  %d. %-12s 门=%-24s 模块=%s"
                  % (step["step"], step["layer"], step["gate"],
                     ",".join(step["module"])))
            print("       in=%s → out=%s · 失败策略=%s"
                  % (",".join(step["inputs"]), ",".join(step["outputs"]),
                     _policy_text(step["failure_policy"])))
        for edge in doc["edges"]:
            print("  交接：%s → %s（%s）" % (edge["from"], edge["to"], edge["event"]))
        hook = doc["runtime_hook"]
        print("  runtime 衔接：%s.%s（client=%s；trace=%s）"
              % (hook["module"], hook["entry"], hook["client_interface"],
                 hook["trace_schema"]))
        return 0
    if sub == "check":
        issues, stats = ac.validate(root=ROOT)
        if getattr(args, "json", False):
            print(_json.dumps({"kind": "agent-check", "schema": ac.CHECK_SCHEMA,
                               "ok": not issues, "issues": issues, "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf agent check（角色=模块 / 交接=事件 / 验收=门）==")
            for issue in issues:
                print("  [FAIL] %s" % issue)
            print("  角色 %d · 域 %d · 模块 %d · 事件 %d · 门 %d → %s"
                  % (stats["roles"], stats["domains"], stats["modules"],
                     stats["events"], stats["profiles"],
                     "PASS" if not issues else "FAIL"))
        return 0 if not issues else 1
    print("  ✗ 需要子命令：`nf agent plan --domain techdoc|regulatory [--json]`"
          " / `nf agent check [--json]`（修复指引：见 nf agent --help）", file=sys.stderr)
    return 2
