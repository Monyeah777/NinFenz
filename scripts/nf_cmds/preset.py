"""CLI 处理器：preset 族（自 scripts/nf.py 抽出；按子命令拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os

from nf_cmds.common import _machine_fail, _open_store, _portable_path, _rel_out


def _preset_find(store, name):
    want = str(name or "").strip()
    return next((p for p in store.list_presets() if p.name == want), None)


def _preset_ls(args, store, home_txt, want_json):
    import json as _json

    rows = [p.to_json() for p in store.list_presets()]
    if want_json:
        print(_json.dumps({"kind": "preset-ls", "home": home_txt,
                           "count": len(rows), "rows": rows},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf preset ls（%d 条 · 预设库 %s）==" % (len(rows), home_txt))
        for r in rows:
            print("  %-22s %-6s 模块 %-3d 资产包 %s"
                  % (r.get("name"), r.get("pipeline"),
                     len(r.get("modules") or []), r.get("asset_pack") or "-"))
        if not rows:
            print("  （空；`nf preset save <名> --pipeline P04 --modules 通用类:M00` 建一条）")
    return 0


def _preset_show(args, store, home_txt, want_json):
    import json as _json

    p = _preset_find(store, args.name)
    if p is None:
        return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举本机预设）"
                             % args.name, 1)
    if want_json:
        print(_json.dumps({"kind": "preset-show", "home": home_txt,
                           "preset": p.to_json()},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf preset show %s ==" % p.name)
        print("  管线：%s" % p.pipeline)
        print("  模块：%s" % ("、".join(p.modules) or "（空）"))
        print("  资产包：%s" % (p.asset_pack or "（空）"))
        print("  建档：%s" % (p.created_at or "-"))
    return 0


def _preset_apply(args, store, want_json):
    import json as _json
    from core import preset_manager as pm

    p = _preset_find(store, args.name)
    if p is None:
        return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举本机预设）"
                             % args.name, 1)
    res = pm.apply_preset(store, p)
    modules = [m.full_id for m in res["modules"]]
    if want_json:
        print(_json.dumps({"kind": "preset-apply", "name": p.name,
                           "pipeline": res["pipeline"], "modules": modules,
                           "asset_pack": res["asset_pack"],
                           "warnings": res["warnings"]},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf preset apply %s ==" % p.name)
        print("  管线：%s · 模块 %d 件：%s"
              % (res["pipeline"], len(modules), "、".join(modules) or "（空）"))
        print("  资产包：%s" % (res["asset_pack"] or "（空）"))
        for w in res["warnings"]:
            print("  [WARN] %s" % w)
        if not res["warnings"]:
            print("  ✓ 装配清单已解析（本机模块齐备）；真生产：nf run --pipeline %s "
                  "--modules %s --store <store>" % (res["pipeline"], ",".join(modules)))
    return 0


def _preset_save(args, store, want_json):
    import json as _json
    from core.models import Preset

    if _preset_find(store, args.name) is not None and not args.force:
        return _machine_fail(
            args, "同名预设已存在：%s（修复指引：换名，或加 --force 覆盖；"
                  "`nf preset show %s` 先看现状）" % (args.name, args.name), 1)
    p = Preset(name=args.name.strip(), pipeline=(args.pipeline or "P01").strip(),
               modules=[m.strip() for m in (args.modules or "").split(",") if m.strip()],
               asset_pack=(args.assets or "").strip())
    path = store.save_preset(p)
    if want_json:
        print(_json.dumps({"kind": "preset-save", "ok": True, "name": p.name,
                           "path": _portable_path(path), "preset": p.to_json()},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("  ✓ 预设已保存：%s（%s）" % (p.name, _portable_path(path)))
    return 0


def _preset_rm(args, store, want_json):
    import json as _json

    if not store.remove_preset(args.name):
        return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举）"
                             % args.name, 1)
    if want_json:
        print(_json.dumps({"kind": "preset-rm", "ok": True, "name": args.name},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("  ✓ 已删除预设：%s" % args.name)
    return 0


def _preset_export(args, store, want_json):
    import json as _json
    from core import preset_manager as pm

    p = _preset_find(store, args.name)
    if p is None:
        return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举）"
                             % args.name, 1)
    if os.path.isdir(_rel_out(args.out)):
        return _machine_fail(args, "--out 落点是目录：%s（修复指引：给**文件**路径，"
                             "如 my.preset.json）" % args.out, 1)
    if not pm.export_preset_file(p, args.out):
        return _machine_fail(args, "写导出件失败：%s（修复指引：给可写文件路径）" % args.out, 1)
    if want_json:
        print(_json.dumps({"kind": "preset-export", "ok": True, "name": p.name,
                           "out": args.out}, ensure_ascii=False, indent=2,
                          sort_keys=True))
    else:
        print("  ✓ 预设已导出：%s → %s" % (p.name, args.out))
    return 0


def _preset_import(args, store, home_txt, want_json):
    import json as _json
    from core import preset_manager as pm
    from core.models import Preset

    p = pm.import_preset_file(store, args.file)
    if p is None:
        return _machine_fail(
            args, "预设不可用：%s（修复指引：收 `nf preset export` 产的 JSON（含 name 与 "
                  "pipeline 两个必需字段）；文件须在场且可读）" % args.file, 1)
    if (args.name or "").strip():
        p = Preset(name=args.name.strip(), pipeline=p.pipeline, modules=list(p.modules),
                   asset_pack=p.asset_pack, created_at=p.created_at)
        store.save_preset(p)
    if want_json:
        print(_json.dumps({"kind": "preset-import", "ok": True, "name": p.name,
                           "home": home_txt, "preset": p.to_json()},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("  ✓ 预设已导入本机：%s（%s）" % (p.name, home_txt))
    return 0


def run(args):
    """nf preset：预设配置（一份存档 = 管线 + 模块 + 资产包 的**一次组装**）。

    落点 = **NF_HOME**（用户态预设库），不写仓库；`apply` 只做**解析**（管线 + 模块 + 资产包
    + 本地缺失提示），真生产仍走 `nf run`。
    """
    sub = getattr(args, "preset_cmd", None) or "ls"
    store, err = _open_store(args, getattr(args, "store", ""))   # 同上：干净拒绝
    if err is not None:
        return err
    want_json = bool(getattr(args, "json", False))
    home_txt = _portable_path(store.presets_root)
    if sub == "ls":
        return _preset_ls(args, store, home_txt, want_json)
    if sub == "show":
        return _preset_show(args, store, home_txt, want_json)
    if sub == "apply":
        return _preset_apply(args, store, want_json)
    if sub == "save":
        return _preset_save(args, store, want_json)
    if sub == "rm":
        return _preset_rm(args, store, want_json)
    if sub == "export":
        return _preset_export(args, store, want_json)
    return _preset_import(args, store, home_txt, want_json)
