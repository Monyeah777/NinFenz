"""CLI 处理器：asset 族（自 scripts/nf.py 抽出；按子命令拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import _machine_fail


def _asset_baseline(args):
    from core import asset_line_baseline as alb

    if args.write:
        path = alb.write(args.root)
        print("== nf asset baseline --write ==")
        print("  [OK] 资产行数基线已重签：%s" % os.path.relpath(path, args.root))
        print("    下一步：`bash verify.sh` 由 check8 自证外形一致")
        return 0
    issues, warns, stats = alb.verify(args.root)
    print("== nf asset baseline（在册 %d 包 · 基线 %d 包）=="
          % (stats.get("packages", 0), stats.get("baseline", 0)))
    for w in warns:
        print("  [WARN] %s" % w)
    for i in issues:
        print("  [FAIL] %s" % i)
    if not issues:
        print("  [OK] 社区包资产外形与基线一致（改外形须显式重签）")
    return 1 if issues else 0


def _asset_add(args):
    from core import asset_ledger as al

    if not args.root:
        print("  ✗ add 需要 --root（台账所在资产根目录，如 05_资产库）", file=sys.stderr)
        return 2
    entry = al.add_asset(args.root, args.file, args.key, args.source,
                         module=args.module, version=args.version,
                         status=args.status, tier=args.tier,
                         package=args.package)
    print("== nf asset add ==")
    print("  ✓ 已入库：%s（key=%s · version=%s · status=%s）"
          % (entry["file"], entry["key"], entry["version"], entry["status"]))
    print("    台账：%s" % al.default_ledger_path(args.root))
    print("    下一步：`bash verify.sh` 由 check23 自证供应链闭合")
    return 0


def _asset_verify(args):
    from core import asset_ledger as al

    issues, stats = al.verify_root(args.root)
    print("== nf asset verify（扫描根：%s）==" % args.root)
    print("  台账 %d · 托管资产 %d · 存量未托管 %d · 孤儿头 %d"
          % (stats["ledgers"], stats["assets"],
             stats["untracked"], stats["orphans"]))
    for i in issues:
        print("  [FAIL] %s" % i)
    if issues:
        print("  ✗ 供应链台账存在缺口——修复后重跑（verify.sh check23 同语义）",
              file=sys.stderr)
        return 1
    print("  ✓ 台账闭合：每资产可溯源 / 可发现 / 键无孤儿")
    return 0


def _asset_inventory(args):
    import json as _json
    from core import asset_ledger as al

    rows = al.inventory_root(args.root)
    if args.json:
        print(_json.dumps({"kind": "asset-inventory", "rows": rows},
                          ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("== nf asset inventory（扫描根：%s）==" % args.root)
    if not rows:
        print("  （无 provenance.json 台账——nf asset add 建档首个资产集）")
        return 0
    for r in rows:
        err = ("（读取失败：%s）" % r["error"]) if r.get("error") else ""
        print("  · %-28s pkg=%-10s tier=%-12s 在册=%d 未托管=%d 孤儿=%d%s"
              % (r["dir"], r["package"], r["tier"],
                 r["assets"], r["untracked"], r["orphans"], err))
    return 0


def _asset_ls(args):
    import json as _json
    from core import asset_ledger as al

    rows = al.filter_rows(al.iter_assets(args.root),
                          pkg=args.pkg, tier=args.tier, status=args.status)
    if args.json:
        print(_json.dumps({"kind": "asset-ls", "rows": rows},
                          ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("== nf asset ls%s%s%s ==" % (
        "（pkg=" + args.pkg + "）" if args.pkg else "",
        "（tier=" + args.tier + "）" if args.tier else "",
        "（status=" + args.status + "）" if args.status else ""))
    if not rows:
        print("  （货架为空——nf asset add 入库首批资产）")
        return 0
    for r in rows:
        print("  · %-8s %-14s v%-6s %-10s %s -> %s"
              % (r["tier"], r["key"], r["version"], r["status"],
                 r["file"], r["source"]))
    return 0


def _asset_density(args):
    import json as _json
    from core import asset_density as ad

    issues, stats = ad.scan(args.root)
    if args.json:
        print(_json.dumps({"kind": "asset-density",
                           "ok": not issues, "issues": issues,
                           "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf asset density（45 资产键语义密度）==")
        print("  资产文件 %d · 键 %d · 平均 %.2f 键/档"
              % (stats["files"], stats["keys"],
                 stats["avg_keys_per_file"]))
        print("  无键档（中文名/附机制，合法计数）%d · 短档(<200字) %d"
              % (stats["unkeyed"], stats["tiny"]))
        for i in issues:
            print("  [FAIL] %s" % i)
        if not issues:
            print("  ✓ 密度体检通过：无空档/不可读资产档")
    return 1 if issues else 0


def _asset_usage(args):
    import json as _json
    from core import asset_density as ad

    issues, stats = ad.usage_scan(args.root)
    if args.json:
        print(_json.dumps({"kind": "asset-usage",
                           "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf asset usage（45 资产引用度）==")
        print("  资产键 %d · 有引用 %d · 零引用 %d · 引用总次数 %d"
              % (stats["assets"], stats["used"], stats["zero_usage"],
                 stats["total_refs"]))
        if stats["zero_keys"]:
            print("  零引用键（低信息候选，不自动删）：%s"
                  % "、".join(stats["zero_keys"][:20]))
    return 1 if (issues or (args.strict and stats["zero_usage"] > 0)) else 0


def _asset_thickness(args):
    import json as _json
    from core import asset_density as ad

    issues, stats = ad.thickness_scan(args.root)
    if args.json:
        print(_json.dumps({"kind": "asset-thickness",
                           "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf asset thickness（45 资产语义厚度）==")
        print("  资产档 %d · 平均 %d 字符/档 · 平均 %d 小节/档"
              % (stats["files"], stats["avg_chars"],
                 stats["avg_sections"]))
        print("  低信息候选 %d（只报告不删）" % stats["low_info"])
        for f in stats["low_files"][:20]:
            print("  · %s" % f)
    return 1 if issues else 0


def _asset_ledger(args):
    import json as _json
    from core import asset_ledger_projection as alp

    if args.refresh:
        issues, stats = alp.refresh(args.root)
    else:
        issues, stats = alp.verify(args.root)
    if args.json:
        print(_json.dumps({"kind": "asset-ledger",
                           "refresh": bool(args.refresh),
                           "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf asset ledger（资产键表机读投影）==")
        if args.refresh:
            print("  ✓ ledger 已重生成（%d 条）" % stats.get("entries", 0))
        else:
            print("  校验：条目 %d · 一致 %s"
                  % (stats.get("entries", 0),
                     "是" if not issues else "否（refresh）"))
        for i in issues:
            print("  [FAIL] %s" % i)
    return 1 if issues else 0


def _asset_contract(args) -> int:
    """nf asset contract：数字资产契约三面（数据/代码/脚本）——与 verify check40 同源。"""
    import json as _json
    from core import asset_contract as ac
    if args.export:
        n = ac.write_export(args.root)
        print("== nf asset contract --export ==")
        print("  已写出 %s（资源 %d 条）" % (ac.EXPORT_REL, n))
        return 0
    if args.freeze:
        issues, stats = ac.freeze(args.root)
    elif args.run_tests:
        issues, stats = ac.run_tests(args.root)
    else:
        issues, _warns, stats = ac.scan(
            args.root, faces=([args.face] if args.face else ()))
    if args.json:
        print(_json.dumps({"kind": "asset-contract", "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    elif args.freeze:
        print("== nf asset contract --freeze ==")
        print("  已重冻摘要 %d 条（真源 protocol/asset_contracts.json）" % stats.get("frozen", 0))
    elif args.run_tests:
        print("== nf asset contract --run-tests ==")
        print("  测试件 %d · 用例 %d" % (stats.get("files", 0), stats.get("tests", 0)))
    else:
        print("== nf asset contract（数字资产契约四面：数据/代码/脚本/包清单）==")
        print("  面：data %d · code %d · script %d · index %d · 链 %d · 件 %d"
              % (stats.get("data", 0), stats.get("code", 0), stats.get("script", 0),
                 stats.get("index", 0), stats.get("chains", 0), stats.get("files", 0)))
    for i in issues:
        print("  [FAIL] %s" % i, file=sys.stderr)
    if not issues and not args.json:
        print("  ✓ 通过（真源 protocol/asset_contracts.json）")
    return 1 if issues else 0


def _asset_status_ops(args):
    """rm / deprecate / restore：写操作，需显式 --ledger + --key。"""
    from core import asset_ledger as al

    ledger_path = args.ledger
    assets_root = os.path.dirname(os.path.abspath(ledger_path))
    if args.asset_cmd == "rm":
        removed = al.remove_entry(assets_root, args.key, ledger_path=ledger_path)
        print("== nf asset rm ==")
        print("  ✓ 已从台账摘除：%s（%s）" % (removed["key"], removed["file"]))
        print("    资产文件保留；若残留文件头，verify check23 将报孤儿——确认不再使用后手动清理"
            "旧头")
        return 0
    status = "deprecated" if args.asset_cmd == "deprecate" else "active"
    updated = al.set_status(assets_root, args.key, status, ledger_path=ledger_path)
    print("== nf asset %s ==" % args.asset_cmd)
    print("  ✓ 状态流转：%s -> %s（文件头已同步）"
          % (updated["key"], updated["status"]))
    return 0


def _cmd_asset(args) -> int:
    """nf asset：资产供应链台账族（40 总纲 S2）。纯信息命令缺省只读，写操作显式子命令。"""
    from core import asset_ledger as al

    try:
        sub = args.asset_cmd
        if sub == "baseline":
            return _asset_baseline(args)
        if sub == "add":
            return _asset_add(args)
        if sub == "verify":
            return _asset_verify(args)
        if sub == "inventory":
            return _asset_inventory(args)
        if sub == "ls":
            return _asset_ls(args)
        if sub == "density":
            return _asset_density(args)
        if sub == "usage":
            return _asset_usage(args)
        if sub == "thickness":
            return _asset_thickness(args)
        if sub == "ledger":
            return _asset_ledger(args)
        if sub == "contract":
            return _asset_contract(args)
        return _asset_status_ops(args)
    except al.AssetLedgerError as exc:
        return _machine_fail(args, str(exc), 1)
