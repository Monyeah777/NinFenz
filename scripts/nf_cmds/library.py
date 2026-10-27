"""CLI 处理器：library 族（自 scripts/nf.py 抽出；按子命令拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import ROOT, _machine_fail, _rel_out, _trust_line, _trust_note


def _library_ls(args):
    import json as _json
    from core import library as lib

    rows = lib.entries(ROOT)
    if getattr(args, "json", False):
        print(_json.dumps({"kind": "library-ls", **lib.to_manifest(ROOT)},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf library ls（%d 件）==" % len(rows))
        for e in rows:
            fm = e["fm"]
            print("  %-32s %-10s %-6s %s" % (
                e["id"], str(fm.get("status") or "active"),
                str(fm.get("license") or "-"), str(fm.get("title") or "")))
    return 0


def _library_show(args):
    import json as _json
    from core import library as lib

    want = args.entry.strip()
    hit = None
    for e in lib.entries(ROOT):
        if e["id"] == want or e["id"].lower() == want.lower():
            hit = e
            break
    if hit is None:
        return _machine_fail(
            args, "条目未找到：%s（修复指引：`nf library ls` 可枚举现有编号；"
                  "编号大小写拿不准时先全小写化再查 library/ALIAS.md 转译）" % args.entry, 1)
    if args.json:
        # frontmatter 的 title/description 也是投稿者文本 ⇒ 同 MCP 口径带信任标注
        note = _trust_note(hit["path"], str(hit.get("text") or ""))
        print(_json.dumps({"kind": "library-show", "id": hit["id"],
                           "path": hit["path"],
                           "frontmatter": hit["fm"], "_meta": note},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf library show %s ==" % hit["id"])
        print("  路径：%s" % hit["path"])
        line = _trust_line(_trust_note(hit["path"], str(hit.get("text") or "")))
        if line:
            print(line)
        for k in sorted(hit["fm"]):
            print("  %-14s %s" % (k + ":", hit["fm"][k]))
    return 0


def _library_reindex(args):
    import json as _json
    from core import library as lib

    out = lib.write_projection(ROOT)
    if args.json:
        print(_json.dumps({"kind": "library-reindex", **out},
                          ensure_ascii=False, indent=2))
    else:
        print("== nf library reindex ==")
        print("  重生成：%s" % ("、".join(out["changed"]) if out["changed"]
                                else "无变化（投影已是最新）"))
    return 0


def _library_verify(args):
    import json as _json
    from core import library as lib

    vkey = None
    if getattr(args, "key_file", ""):
        from core import attest as _att2
        vkey = _att2.read_key_file(_rel_out(args.key_file))
    issues, warns, stats = lib.verify(
        ROOT, key=vkey,
        ssh_allowed_signers=getattr(args, "ssh_allowed_signers", ""),
        ssh_identity=getattr(args, "ssh_identity", ""))
    proj = lib.check_projection(ROOT)
    if args.json:
        print(_json.dumps({"kind": "library-verify", "issues": issues,
                           "projection": proj, "warns": warns,
                           "stats": {k: v for k, v in stats.items()
                                     if k != "warns"}},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf library verify（图书馆门）==")
        print("  条目 %d · 在役 %d · WARN %d"
              % (stats["entries"], stats["active"], len(warns)))
        for i in list(issues) + list(proj):
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in warns:
            print("  [WARN] %s" % w)
        if not issues and not proj:
            print("  ✓ frontmatter 真源 + INDEX/ALIAS 投影一致")
    return 1 if (issues or proj) else 0


def _library_search(args):
    import json as _json
    from core import library as lib

    hits = lib.search(args.query, ROOT)
    if args.json:
        print(_json.dumps({"kind": "library-search", "query": args.query,
                           "count": len(hits), "hits": hits},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf library search「%s」（%d 命中）==" % (args.query, len(hits)))
        for h in hits:
            print("  %-32s %-6s %s" % (h["id"], h["score"], h["title"]))
            print("      %s" % h["path"])
    return 0


def _library_status_ops(args):
    import json as _json
    from core import library as lib

    sub = args.library_cmd
    try:
        if sub == "supersede":
            path = lib.set_status(ROOT, args.entry, "superseded", superseded_by=args.by)
            msg = "已取代：%s → %s" % (args.entry, args.by)
        else:
            new = "deprecated" if sub == "deprecate" else "active"
            path = lib.set_status(ROOT, args.entry, new)
            msg = "生命周期 → %s：%s" % (new, args.entry)
    except (ValueError, OSError) as exc:
        # 输入问题不得冒成「内部错误」（修复前：错编号 → 兜底 handler 报内部错误 +
        # 建议跑 NF_DEBUG 看堆栈，指向了错误的排查方向）。set_status 的 ValueError
        # 自带修复指引，这里原样透出即可。
        return _machine_fail(args, str(exc), 1)
    if args.json:
        print(_json.dumps({"kind": "library-status", "ok": True, "path": path,
                           "message": msg}, ensure_ascii=False, indent=2))
    else:
        print("  ✓ %s（投影已重建；%s）" % (msg, path))
    return 0


def _library_receipts(args):
    import json as _json
    from core import receipts as rc

    if args.entry:
        if not os.path.exists(os.path.join(ROOT, rc.RECEIPTS_REL)):
            print("  ✗ 缺回执文件（修复指引：nf library receipts --write）",
                  file=sys.stderr)
            return 1
        doc = rc.load(ROOT)
        want = args.entry.strip().lower()
        hit = next((e for e in doc.get("entries") or []
                    if str(e.get("id", "")).lower() == want), None)
        if hit is None:
            print("  ✗ 回执中没有该条目：%s（修复指引：nf library ls 列全量编号）"
                  % args.entry, file=sys.stderr)
            return 1
        folded = rc.fold_proof(str(hit["leaf"]), hit.get("proof") or [])
        ok = folded == str(doc.get("root"))
        if args.json:
            print(_json.dumps({"kind": "library-receipts", "id": hit["id"],
                               "ok": ok, "root": doc.get("root"),
                               "folded": folded, "path": hit.get("path"),
                               "leaf": hit.get("leaf"), "proof": hit.get("proof")},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf library receipts --entry %s ==" % hit["id"])
            print("  回执折叠：%s" % folded[:24])
            print("  全馆根　：%s" % str(doc.get("root"))[:24])
            print("  %s（拿到该条内容 + 本回执即可本地自验，无需全馆）"
                  % ("✓ 一致" if ok else "✗ 不一致"))
        return 0 if ok else 1
    if args.write:
        rel = rc.write(ROOT)
        doc = rc.build(ROOT)
        print("  ✓ 回执已写入：%s（根 %s · %d 条）"
              % (rel, doc["root"][:16], doc["count"]))
        return 0
    if not os.path.exists(os.path.join(ROOT, rc.RECEIPTS_REL)):
        print("  ✗ 缺回执文件（修复指引：nf library receipts --write）",
              file=sys.stderr)
        return 1
    issues, stats = rc.verify(rc.load(ROOT), ROOT)
    if args.json:
        print(_json.dumps({"kind": "library-receipts", "issues": issues,
                           "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf library receipts（%d 条 · root=%s）=="
              % (stats.get("entries", 0), str(stats.get("root"))[:16]))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 每条回执折叠到根，且根与实时重算一致")
    return 1 if issues else 0


def _library_attest(args):
    import json as _json
    from core import library as nflib2
    from core import attest as _att

    try:
        key = _att.read_key_file(_rel_out(args.key_file)) if args.key_file else None
        out = nflib2.set_attestation(
            ROOT, args.entry, key=key,
            ssh_key=getattr(args, "ssh_key", ""),
            ssh_identity=getattr(args, "ssh_identity", ""))
    except (OSError, ValueError) as exc:
        # 凭证类输入问题（私钥路径不存在等）不得冒成「内部错误」（文档示例真跑抓到）。
        return _machine_fail(args, str(exc), 1)
    if args.json:
        print(_json.dumps({"kind": "library-attest", **out},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf library attest %s ==" % out["id"])
        print("  信任级：%s%s" % (out["level"],
                                 "" if not out.get("key_id")
                                 else "（key_id %s）" % out["key_id"]))
        print("  attestation：%s" % out["attestation"])
        print("  已写入 frontmatter（attestation/attested_at%s），投影已重建"
              % ("/anchor_*" if out.get("key_id") else ""))
        if out.get("warn"):
            print("  ⚠ %s" % out["warn"])
    return 0


def _cmd_library(args):
    """nf library：云端图书馆机器面（真源 = 条目 frontmatter）。"""
    sub = getattr(args, "library_cmd", None) or "ls"
    if sub == "ls":
        return _library_ls(args)
    if sub == "show":
        return _library_show(args)
    if sub == "reindex":
        return _library_reindex(args)
    if sub == "verify":
        return _library_verify(args)
    if sub == "search":
        return _library_search(args)
    if sub in ("deprecate", "restore", "supersede"):
        return _library_status_ops(args)
    if sub == "receipts":
        return _library_receipts(args)
    if sub == "attest":
        return _library_attest(args)
    print("  ✗ 未知 library 子命令：%s" % sub, file=sys.stderr)
    return 2
