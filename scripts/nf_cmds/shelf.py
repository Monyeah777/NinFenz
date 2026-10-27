"""CLI 处理器：shelf 族（自 scripts/nf.py 抽出；行为逐字保留，由 nf.py re-export）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, json_doc)

def _cmd_market(args) -> int:
    """nf market：依赖闭包 + 挂载冲突预检（B4 CLI 先行；信息查询，冲突不阻断）。"""
    import json
    from core.market_analyzer import (conflicts, dependencies, grades_of_package,
                                      list_market)
    from core.registry_sync import check_registerable
    from core.registry_loader import load_registry

    reg_path = args.registry or os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    doc_path = os.path.join(ROOT, "02_联动注册表.md")

    # ---- list 目录视图（v2.5.0 Wave3）----
    if args.list:
        reg = load_registry(reg_path)
        items = list_market(reg, tier=args.tier)
        if args.json:
            import json as _json
            print(_json.dumps({
                "kind": "market-list",
                "tier": args.tier,
                "items": items,
            }, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print(f"== nf market list{'（tier=' + args.tier + '）' if args.tier else ''} ==")
        _badge = {"official": "🏛官方", "community": "🌐社区", "experimental": "🧪实验"}
        for it in items:
            if it["kind"] == "module":
                print(f"  [{_badge[it['grade']]}] 模块 {it['id']} · {it['name']}")
            else:
                print(f"  [{_badge[it['grade']]}] 包 {it['id']} v{it['version']}"
                      f"（{it['modules']} 模块）")
        return 0

    if not args.pkg_dir:
        print("✗ 缺 pkg_dir（或加 --list 列目录）", file=sys.stderr)
        return 2
    pkg_id = os.path.basename(args.pkg_dir.rstrip("/\\"))

    with open(reg_path, encoding="utf-8") as f:
        reg = json_doc.loads(f.read(), dict, what=reg_path)
    prots = {p["id"]: p for p in reg.get("protocols", [])}
    with open(doc_path, encoding="utf-8") as f:
        doc = f.read()

    # 登记状态（复用 registry_sync 三要件校验；issue 即未就绪提示，不阻断查询）
    reg_issues = check_registerable(args.pkg_dir, doc)
    if pkg_id not in prots:
        if args.json:
            print(json.dumps({
                "kind": "market-package",
                "pkg_id": pkg_id,
                "registered": False,
                "issues": reg_issues,
            }, ensure_ascii=False, indent=2, sort_keys=True))
            return 1 if reg_issues else 0
        print("  ✗ 包 %s 不在 registry protocols[]——无 references 可查"
              "（修复指引：核对包名（`nf market --list` 可枚举已登记包）；若是新包，"
              "先按 02 §8.3 登记三要件完成登记）" % pkg_id)
        return 1 if reg_issues else 0

    # 加载各包 protocol.yaml 内容（data 供 dependencies/conflicts 用）
    import glob
    from core import lazy_yaml as _ly
    _yaml = _ly.module()
    if _yaml is None:
        # 审计 Y6（P1）：缺 PyYAML 不裸崩成「内部错误」，给可执行指引（降级靠 lazy_yaml 出声）。
        return _machine_fail(args, "缺 PyYAML：无法读各包 protocol.yaml 的声明"
                                   "（修复指引：pip install pyyaml）", 1)
    data = {}
    for pf in sorted(glob.glob(os.path.join(ROOT, "community", "*", "protocol.yaml"))):
        try:
            with open(pf, encoding="utf-8") as f:
                raw = _yaml.safe_load(f)
            data[raw["package"]["id"]] = raw
        except Exception:  # 尽力而为：跳过不可读/不可解析项（该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出）  # nosec B112 —— 尽力而为：跳过不可读/不可解析项（对应门禁另报；见 AUD-0016）
            continue

    seen, dep_issues = dependencies(pkg_id, prots, data)
    cfl = conflicts(pkg_id, prots, data)
    # A6 质量分级徽章（v2.4.0）：官方核心/社区/实验
    grades = grades_of_package(prots, pkg_id)
    if args.json:
        print(json.dumps({
            "kind": "market-package",
            "pkg_id": pkg_id,
            "registered": True,
            "issues": reg_issues,
            "dependencies": sorted(seen),
            "dependency_issues": dep_issues,
            "conflicts": cfl,
            "grades": grades,
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"== nf market {pkg_id} ==")
    print("  登记状态: %s" % ("在册（02 §8 + registry protocols[]）"
                              if not reg_issues else "; ".join(reg_issues)))
    if grades:
        _badge = {"official": "🏛官方", "community": "🌐社区", "experimental": "🧪实验"}
        badge_line = ", ".join(f"{m}({_badge[g]})" for m, g in grades.items())
        print(f"  分级徽章: {badge_line}")
    print("  依赖闭包: %s" % (", ".join(sorted(seen)) if seen else "无跨包引用"))
    for i in dep_issues:
        print(f"  [依赖] {i}")
    if cfl:
        for i in cfl:
            print(f"  [冲突] {i}")
    else:
        print("  挂载冲突: 无")
    return 0

def _cmd_combine(args):
    """nf combine：域包自由组合（plan / breadth / verify / materialize）。"""
    import json as _json

    from core import pack_combo as pc

    sub = getattr(args, "combine_cmd", "") or "plan"
    if sub == "breadth":
        stats = pc.breadth(ROOT, triple_sample=args.triples, quad_sample=args.quads,
                           quint_sample=args.quints, sext_sample=args.sexts)
        if args.json:
            print(_json.dumps({"kind": "combine-breadth", **stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  参与包 %d · 两两 %d/%d 合法 · 三元 %d/%d · 四元 %d/%d · 五元 %d/%d · "
                  "六元 %d/%d · 全合法=%s"
                  % (stats["packs"], stats["pairs_legal"], stats["pairs"],
                     stats["triples_legal"], stats["triples"],
                     stats["quads_legal"], stats["quads"],
                     stats["quints_legal"], stats["quints"],
                     stats["sexts_legal"], stats["sexts"], stats["all_legal"]))
            for f in stats["failures"][:5]:
                print("  [FAIL] %s" % f)
        return 0 if stats["all_legal"] else 1
    if sub == "verify":
        doc = pc.declared(ROOT)
        bad = 0
        rows = []
        for cert in doc.get("certificates") or []:
            issues, st = pc.verify_certificate(ROOT, cert)
            label = cert.get("label") or "+".join(cert.get("packs") or [])
            rows.append({"label": label, "legal": st.get("legal"),
                         "modules": st.get("modules"), "issues": issues})
            bad += 1 if issues else 0
        if args.json:
            print(_json.dumps({"kind": "combine-verify", "certificates": len(rows),
                               "failed": bad, "rows": rows},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for r in rows:
                print("  %s %-34s 模块 %-4s %s"
                      % ("✓" if not r["issues"] else "✗", r["label"], r["modules"],
                         "" if not r["issues"] else r["issues"][:1]))
            print("  —— 证书 %d 条，失败 %d" % (len(rows), bad))
        return 1 if bad else 0
    if sub == "materialize":
        out = pc.materialize(ROOT, packs=[x.strip() for x in args.packs.split(",") if x.strip()],
                             combo_id=args.id, category=args.category, write=args.write)
        if not out.get("ok"):
            print("  ✗ %s" % out.get("reason"), file=sys.stderr)
            if args.json:
                import json as _j
                print(_j.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
            return 1
        reg = {"02": False, "dom": False, "protocols": ""}
        if args.write:
            r = pc.combo_register(ROOT, out["package"], out["category"], out["pipeline"],
                                  [x.strip() for x in args.packs.split(",") if x.strip()],
                                  out["references"], out["certificate"])
            reg = {"02": r["section02"], "dom": r["domain_list"],
                   "protocols": r["protocols"]}
        if args.json:
            import json as _j
            print(_j.dumps({"kind": "combine-materialize", **out, "registry": reg},
                           ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  组合包 %s（管线 %s · 类别 %s）" % (out["package"], out["pipeline"],
                                                    out["category"]))
            print("  借阅模块 %d · references %d · 层栈 %s"
                  % (out["modules"], out["references"],
                     {k: v for k, v in out["layers"].items()}))
            print("  文件 %d 件，%s %d 件%s"
                  % (out["files"], "已落盘" if args.write else "待落盘（--write 才写）",
                     out["written"] if args.write else out["changed"],
                     "" if args.write else "（差异件）"))
            if args.write:
                print("  登记：02 %s · DOMAIN %s · registry %s"
                      % (reg["02"], reg["dom"], reg["protocols"]))
        return 0
    packs = [x.strip() for x in args.packs.split(",") if x.strip()]
    mods = [x.strip() for x in getattr(args, "modules", "").split(",") if x.strip()]
    assets = [x.strip() for x in getattr(args, "assets", "").split(",") if x.strip()]
    if not packs and not mods:
        print("  需给 --packs 或 --modules（也可 `nf combine breadth`）", file=sys.stderr)
        return 2
    cert = pc.combine(ROOT, packs=packs, extra_modules=mods, extra_assets=assets)
    if getattr(args, "certify", False):
        cert = pc.certify(ROOT, packs=packs, label=args.label, note=args.note,
                          extra_modules=mods, write=True)
    if args.json:
        print(_json.dumps({"kind": "combine", **cert},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("  组合：%s%s" % ("、".join(cert["packs"]) or "（组件级）",
                              ("＋" + "、".join(cert["extra_modules"])) if cert["extra_modules"] else ""))
        print("  合法=%s · 模块 %d · 层栈 %s"
              % (cert["legal"], cert["module_count"],
                 {r["layer"]: len(r["modules"]) for r in cert["layer_stacks"]}))
        print("  依赖悬挂 %d · 未桥事件 %d · 资产借阅 %d · 摘要 %s"
              % (len(cert["dependency_closure"]["dangling"]),
                 len(cert["event_closure"]["unbridged"]),
                 len(cert["assets_borrowed"]), cert["digest"]))
        # 不在册的包必须**点名**（2026-10-01 全量恶意值扫取证）：此前人读面只给
        # 「合法=False」，读者**分不清**「包名打错了」与「真冲突」——机读面 `unknown_packs`
        # 一直是有的，缺的是人读面把这条决定性事实说出来（与 who-refers/related/impact 同款）。
        if cert.get("unknown_packs"):
            print("  [FAIL] 不在册的包：%s（修复指引：`nf market --list` 可枚举已登记包；"
                  "组件级取用改给 --modules <模块 id>）" % "、".join(cert["unknown_packs"]),
                  file=sys.stderr)
        if getattr(args, "certify", False):
            print("  ✓ 证书已写入 %s" % pc.CERT_REL)
    return 0 if cert["legal"] else 1

def _cmd_output(args):
    """nf output：产出形态面（清单 / 判件 / 全量机检 / 渲染 / 机验率）。"""
    import json as _json

    from core import output_forms as of

    sub = getattr(args, "output_cmd", "") or "verify"
    if sub == "list":
        reg = of.load_registry(ROOT)
        rows = []
        for f in reg.get("forms") or []:
            if args.status and f.get("status") != args.status:
                continue
            if args.category and f.get("category") != args.category:
                continue
            if args.tier and f.get("tier") != args.tier:
                continue
            rows.append(f)
        if args.json:
            print(_json.dumps({"kind": "output-list", "count": len(rows),
                               "rows": rows},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  %-28s %-14s %-4s %-12s %s"
                  % ("形态", "类别", "档位", "状态", "规范入口/备注"))
            for f in rows:
                print("  %-28s %-14s %-4s %-12s %s"
                      % (f.get("id"), f.get("category"), f.get("tier"),
                         f.get("status"), (f.get("spec") or {}).get("uri", "")))
            cov = reg.get("coverage") or {}
            print("  —— 共 %d 条（可达 %s / 不可达 %s）；状态 %s；档位 %s"
                  % (cov.get("forms", 0), cov.get("reachable"),
                     cov.get("unreachable"), cov.get("by_status"), cov.get("by_tier")))
        return 0
    if sub == "check":
        blob = []
        bad = 0
        for p in args.paths:
            rel = p
            if os.path.isabs(p):
                rel = os.path.relpath(p, os.path.abspath(ROOT)).replace(os.sep, "/")
            if not os.path.isfile(os.path.join(ROOT, rel.replace("/", os.sep))):
                blob.append({"path": rel, "error": "文件不存在"}); bad += 1; continue
            form, tier = of.detect(ROOT, rel)
            issues = of._FORM_CHECK.get(form, lambda r, x: [])(ROOT, rel)
            blob.append({"path": rel, "form": form, "max_tier": tier,
                         "issues": issues})
            bad += 1 if issues else 0
        if args.json:
            print(_json.dumps({"kind": "output-check", "count": len(blob),
                               "rows": blob},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for r in blob:
                if r.get("error"):
                    print("  [FAIL] %s %s" % (r["path"], r["error"])); continue
                mark = "✗" if r["issues"] else "✓"
                print("  %s %-46s 形态=%-14s 上限档位=%s"
                      % (mark, r["path"], r["form"], r["max_tier"]))
                for i in r["issues"]:
                    print("      - %s" % i)
            if bad:
                # 失败即给可执行口径（2026-10-01）：此前只吐「文件不存在」这一行，读者
                # 不知道去哪儿找正确路径。
                print("  修复指引：`--paths` 给**在场文件**路径（相对仓库根或绝对皆可）；"
                      "`nf output list` 可枚举产出形态与规范入口。", file=sys.stderr)
        return 1 if bad else 0
    if sub == "render":
        issues, rows = of.render_outputs(ROOT, package=args.package, write=args.write)
        if args.json:
            print(_json.dumps({"kind": "output-render", "issues": issues,
                               "rows": rows},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for r in rows:
                print("  %s %-52s 生成器=%-24s %s"
                      % ("改" if r["changed"] else "同", r["path"], r["generator"],
                         "已落盘" if r["written"] else "未落盘（--write 才写）"))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
        return 1 if issues else 0
    if sub == "meter":
        if args.write:
            doc = of.write_baseline(ROOT)
            if not args.json:
                print("  已重签 %s" % of.BASELINE_REL)
                _st = doc
        _, _st = of.meter(ROOT)
        if args.json:
            print(_json.dumps({"kind": "output-meter", **_st},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  %-18s %-8s %-8s %-10s %s"
                  % ("包", "机验面", "功能面", "散文资产", "机验率"))
            for pkg, s in (_st.get("packages") or {}).items():
                print("  %-18s %-8s %-8s %-10s %s"
                      % (pkg, s["machine_verifiable"], s["functional"],
                         s["prose_assets"], s["machine_verifiable_ratio"]))
            print("  合计：%s" % _st.get("totals"))
        return 0
    issues, stats = of.scan(ROOT)
    if args.json:
        print(_json.dumps({"kind": "output-verify", "issues": issues,
                           "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            reg = stats.get("registry") or {}
            print("  ✓ 产出形态面一致：形态 %s 条（可达 %s）；包级产出 %s 件；机验率 %s"
                  % (reg.get("forms"), reg.get("forms", 0) - reg.get("unreachable", 0),
                     (stats.get("index") or {}).get("outputs"),
                     {k: v["machine_verifiable_ratio"]
                      for k, v in (stats.get("meter") or {}).items()}))
    return 1 if issues else 0
