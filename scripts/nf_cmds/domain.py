"""CLI 处理器：domain 族（自 scripts/nf.py 抽出；按子命令拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import ROOT, _machine_fail


def _domain_specs(args):
    import glob as _glob
    import json as _json

    from core import domain_pack as dp

    spec_dir = os.path.join(ROOT, dp.SPEC_DIR)
    codes = sorted(os.path.splitext(os.path.basename(p))[0]
                   for p in _glob.glob(os.path.join(spec_dir, "*.json")))
    reg = {}
    try:
        with open(os.path.join(ROOT, dp.REGISTRY_REL), encoding="utf-8") as fh:
            reg = {p.get("id"): p for p in _json.load(fh).get("protocols") or []}
    except (OSError, ValueError) as exc:
        # registry 读不到/不可解析时**不能**静默当空表：那会让每条规格都显示「未建」——
        # 用户看到的是「一个都没建」这种**错的事实**（2026-09-30 收口）。
        return _machine_fail(args, "registry 不可读：%s（修复指引：确认 %s 在场且为合法 "
                             "JSON；`nf doctor` 可体检）" % (exc, dp.REGISTRY_REL), 1)
    rows = []
    for c in codes:
        spec = dp.load_spec(ROOT, c)
        rows.append({"code": c, "name": spec["name"], "pack": spec["pack_name"],
                     "category": spec["category"], "family": spec["metric_family"],
                     "built": spec["pack_name"] in reg,
                     "pipeline": (reg.get(spec["pack_name"]) or {}).get("pipeline", "")})
    if args.json:
        print(_json.dumps({"kind": "domain-specs", "count": len(rows),
                           "rows": rows},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("  %-5s %-22s %-22s %-18s %s" % ("域码", "名称", "包名", "度量族", "状态"))
        for r in rows:
            print("  %-5s %-22s %-22s %-18s %s"
                  % (r["code"], r["name"], r["pack"], r["family"],
                     ("已建 " + r["pipeline"]) if r["built"] else "未建"))
        print("  —— 规格 %d 条（已建 %d）" % (len(rows), sum(1 for r in rows if r["built"])))
    return 0


def _domain_shells(args):
    import json as _json

    from core import shell_ledger as sl

    issues, s = sl.ratchet(ROOT)
    if args.json:
        print(_json.dumps({"kind": "domain-shells", "issues": issues,
                           "survey": s, "baseline": sl.BASELINE},
                          ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if issues else 0
    print("== nf domain shells（派生空壳台账 · 域口径表）==")
    print("  域包 %d（已填 %d · 带空壳 %d）· 空壳条目 **%d** 处"
          % (s["packs_total"], s["packs_filled"], s["packs_with_shell"], s["hits"]))
    print("  冻结基线：带空壳包 ≤ %d · 空壳 ≤ %d 处（**只减不增**，见 core/shell_ledger.BASELIN"
        "E）"
          % (sl.BASELINE["packs_with_shell"], sl.BASELINE["hits"]))
    for pkg, n in sorted(s["per_package"].items())[:5]:
        print("   · %-28s %d 处" % (pkg, n))
    if len(s["per_package"]) > 5:
        print("   · …其余 %d 包同型（每包 %d 处 = 12 条细分 × 3 处占位）"
              % (len(s["per_package"]) - 5, sl.BASELINE["per_shell_pack"]))
    print("  → 补全口径：领域判据须由作者/领域专家落笔（不代写）；补完请下调 BASELINE")
    print("  档位对账：人读声明 ⇄ 机读 `content_tier` ⇄ 正文占位 %s（不一致 %d 件）"
          % ("三处同真" if not s["tier_mismatches"] else "**已分叉**",
             len(s["tier_mismatches"])))
    for i in issues:
        print("  ✗ %s" % i, file=sys.stderr)
    if not issues:
        print("  ✓ 未超基线（缺口只减不增）")
    return 1 if issues else 0


def _domain_build(args):
    import json as _json

    from core import domain_pack as dp

    spec_code = str(args.spec or "").strip()   # 域码是标识符：裁空白（同 who-refers 口径）
    try:
        spec = dp.load_spec(ROOT, spec_code)
    except (ValueError, OSError) as exc:
        # 输入问题不得冒成「内部错误」（修复前：错代码 → 兜底 handler 报内部错误 +
        # 建议跑 NF_DEBUG 看堆栈，指向了错误的排查方向）。load_spec 的 ValueError
        # 自带修复指引，这里原样透出即可（与 library 生命周期命令同一口径）。
        return _machine_fail(args, str(exc), 1)
    from core import output_forms as of           # 渲染器由调用方注入（工厂不再反向依赖产出面）
    out = dp.build(ROOT, spec, write=args.write, render=not args.no_render,
                   renderer=of.render_outputs)
    if args.json:
        print(_json.dumps({"kind": "domain-build", **out},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("  域 %s · 包 %s · 管线 %s · 模块 %s"
              % (out["spec"], spec["pack_name"], out["pipeline"],
                 "、".join(out["module_ids"])))
        print("  计划 %d 件，%s %d 件%s"
              % (out["files"],
                 "已落盘" if args.write else "待落盘（--write 才写）",
                 out["written"] if args.write else out["changed"],
                 "" if args.write else "（差异件）"))
        if args.write:
            print("  登记：02 §8 %s · verify.sh DOMAIN %s · registry protocols[] %s · "
                  "产出面渲染 %d 件"
                  % (out["registry"]["section02"], out["registry"]["domain_list"],
                     out["registry"].get("protocols", "—"),
                     len(out["registry"].get("render") or [])))
            for i in (out["registry"].get("render_issues") or []):
                print("  [FAIL] %s" % i, file=sys.stderr)
    return 0


def _domain_verify(args):
    import glob as _glob
    import json as _json

    from core import domain_pack as dp

    spec_dir = os.path.join(ROOT, dp.SPEC_DIR)
    codes = sorted(os.path.splitext(os.path.basename(p))[0]
                   for p in _glob.glob(os.path.join(spec_dir, "*.json")))
    targets = [str(args.spec).strip()] if args.spec else codes
    issues_all = []
    rows = []
    for c in targets:
        try:
            spec = dp.load_spec(ROOT, c)
        except (ValueError, OSError) as exc:
            return _machine_fail(args, str(exc), 1)
        issues, stats = dp.verify(ROOT, spec)
        issues_all += ["%s: %s" % (c, i) for i in issues]
        rows.append({"code": c, "stats": stats})
    if args.json:
        print(_json.dumps({"kind": "domain-verify", "issues": issues_all,
                           "rows": rows},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for i in issues_all:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues_all:
            print("  ✓ 域包工厂自检通过：%d 个域包与生成器逐字节一致，登记三处到位" % len(targets))
    return 1 if issues_all else 0


def _cmd_domain(args):
    """nf domain：域包工厂（build / verify / specs / shells）+ 成熟度分级（maturity）。"""
    sub = getattr(args, "domain_cmd", "") or "specs"
    if sub == "record":
        from core import exec_record as er
        return er.run(ROOT, check=getattr(args, "check", None),
                      write=getattr(args, "write", None),
                      as_json=bool(getattr(args, "json", False)))
    if sub == "maturity":
        from core import domain_maturity as dmx
        return dmx.run(ROOT, as_json=bool(getattr(args, "json", False)),
                       write=bool(getattr(args, "write", False)))
    if sub == "specs":
        return _domain_specs(args)
    if sub == "shells":
        return _domain_shells(args)
    if sub == "build":
        return _domain_build(args)
    return _domain_verify(args)
