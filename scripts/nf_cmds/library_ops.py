"""CLI 处理器：library_ops（自 scripts/nf.py 抽出；行为逐字保留，由 nf.py re-export）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, _trust_line, _trust_note)

def _cmd_who_refers(args) -> int:
    """nf who-refers <module_id>：谁在 references 中引用了该模块（A2 反查）。"""
    from core.retriever import referenced_by
    from core.registry_loader import load_registry
    from core.impact_check import impact_of_change

    # 口径统一（2026-10-01）：**标识符**输入一律 `strip()`（粘贴时常带看不见的尾随空格）。
    # 实测：`nf who-refers "M90 "` / `nf related "M90 "` / `nf impact "M90 "` 此前判「不在册」
    # ——那是假事实（id 本来就是对的）；而 `library show` / `decisions show` / `patterns show`
    # 早就裁了。**路径类入参不裁**（POSIX 下尾随空格是合法文件名）。
    mid = str(args.module_id).strip()
    reg_path = args.registry or os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    # 口径统一（2026-09-30）：目标不在册时**不得**报「无（无人引用）」——那是**错的事实**
    # （用户会把「查错了名字」读成「没人引用它」）。与 `nf impact`（同族反查）同一判据、
    # 同一指引：先问 `impact_of_change` 目标是否在册，miss 即拒。
    probe = impact_of_change(load_registry(reg_path), mid)
    if probe.get("error"):
        return _machine_fail(
            args, "%s（修复指引：目标须是 registry 在册的 module / protocol id"
                  "（如 M00 / 通用:M10）；`nf market --list` 与 `nf module ls` 可枚举）"
                  % probe["error"], 1)
    refs = referenced_by(mid, path=reg_path)
    print(f"== 谁引用了 {mid} ==")
    if not refs:
        print("  无（registry protocols[].references 中无引用）")
        return 0
    for r in refs:
        ro = "只读" if r.get("asset_readonly") else ""
        print(f"  {r['referrer']} → {r['source_package']}.{r['module_id']} {ro}")
    return 0

def _cmd_impact(args) -> int:
    """nf impact <target>：拟删除目标（module/protocol）的破坏性影响预检（A4 前置）。

    --check 门禁模式：破坏性变更（module 被引用/官方在册，或整包删除有引用方）
    exit 1——镜像 verify 铁律，供变更前门禁接线。
    """
    from core.impact_check import impact_of_change
    from core.registry_loader import load_registry

    target = str(args.target).strip()          # 标识符入参裁空白（见 who-refers 同款注释）
    reg_path = args.registry or os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    reg = load_registry(reg_path)
    im = impact_of_change(reg, target)
    print(f"== 删除影响面预检: {target} ==")
    if im.get("error"):
        print(f"  [拒绝] {im['error']}（修复指引：目标须是 registry 在册的 module / protocol id"
              f"（如 M00 / 通用:M10 / 校园情感领域包）；`nf market --list` 与 `nf module ls` 可枚举"
                  f"）")
        return 1

    if "module_id" in im:                     # module 级
        refs = im["referenced_by"]
        print(f"  类型: module（官方在册 {im['in_official_core'] or '无'} · "
              f"属包 {im['in_packages'] or '无'}）")
        if not refs and not im["in_official_core"]:
            print("  无破坏性影响（无引用方且非官方核心——可安全移除）")
            return 0
        for r in refs:
            ro = "只读" if r.get("asset_readonly") else ""
            print(f"  破坏性: 被 {r['protocol']} 引用（引用声明源 {r['source_package']}"
                  f"，asset_readonly {ro or 'false'}）")
        if im["in_official_core"]:
            print(f"  破坏性: 官方核心在册 {im['in_official_core']}（删官方核心 = 协议事故）")
        return 1 if args.mode == "check" else 0
    # protocol 级（整包删除）
    refs = im["referenced_by_packages"]
    print(f"  类型: protocol 整包（module_ids {im['module_ids'] or '无'}）")
    if not refs:
        print("  无破坏性影响（无其它包引用本包模块——可安全移除，自身 references 随之消失）")
        return 0
    for r in refs:
        print(f"  破坏性: 被 {r['protocol']} 引用（引用声明源 {r['source_package']}）")
    return 1 if args.mode == "check" else 0

def _cmd_rename(args) -> int:
    """nf rename <old> <new>：模块改名引用重链（A5 变更助手）。

    --check（缺省）只列受影响引用；--apply 批量重链 references[].module_id 后
    合并写 registry protocols[]（只改引用目标，不动其它字段，V1 只增不删语义）。
    """
    from core.impact_check import rename_module_plan
    from core.registry_loader import load_registry

    reg_path = args.registry or os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    reg = load_registry(reg_path)
    plan = rename_module_plan(reg, args.old_id, args.new_id)
    print(f"== 改名引用重链: {args.old_id} → {args.new_id} ==")
    if not plan["affected"]:
        print("  无引用方（registry references 中无引用该模块——安全改名，无需重链）")
        return 0
    for a in plan["affected"]:
        print(f"  重链: {a['protocol']} references {a['old_module_id']} → "
              f"{a['new_module_id']}（源 {a['source_package']}）")

    if args.mode != "apply":
        print(f"  [{args.mode or 'check'}] 未写盘（--apply 才合并写 registry protocols[]）")
        return 0

    import json as _json
    # 原子写 + LF（2026-09-30）：与 `nf register --apply` 同一对象（registry.json）；
    # 这处此前还是**裸写 + 平台默认行尾**（Windows 会落 CRLF，撞 check33 编码卫生）。
    # 读-改-写串行化（2026-10-01）：锁内**重读并重跑改名计划**（按 old→new 幂等）——
    # 否则两个并发 `--apply`（改名 × 登记）会互相覆盖掉对方刚写的 protocols[]。
    from core import atomic_write
    from core.registry_loader import load_registry as _load_registry
    with atomic_write.lock_file(reg_path, what="registry.json（nf rename --apply）"):
        _load_registry.cache_clear()        # 锁内必须拿**最新**盘面（该加载器带进程内缓存）
        plan2 = rename_module_plan(_load_registry(reg_path), args.old_id, args.new_id)
        with open(reg_path, encoding="utf-8") as f:
            raw = _json.load(f)
        raw["protocols"] = plan2["updated_protocols"]
        atomic_write.write_text(reg_path,
                                _json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    print(f"  ✓ 已重链 {len(plan['affected'])} 处引用并写盘 {reg_path}")
    print("  下一步：跑 `bash verify.sh` 由 check14 ⑦/check15 ① 元素级断言自证")
    return 0

def _cmd_rfc(args):
    """nf rfc：协议件 RFC 索引与 supersede 链自检。"""
    from core import rfc as rf
    from pathlib import Path
    import json as _json
    issues, warns, stats = rf.scan(ROOT)
    idx = rf.index(ROOT)
    if args.json:
        print(_json.dumps({"kind": "rfc", "index": idx, "issues": issues,
                           "warns": warns, "stats": stats},
                          ensure_ascii=False, indent=2,
                           sort_keys=True))
    else:
        print("== nf rfc（协议件版本史）==")
        for item in idx.get("docs") or []:
            head = rf.parse_head((Path(ROOT) / item["path"]).read_text(encoding="utf-8"))
            print("  %-9s %-34s %-16s %-9s %s"
                  % (item.get("rfc"), item.get("path"), head.get("cat", "-"),
                     head.get("status", "-"), head.get("date", "-")))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ %d 件 RFC 头齐备且链可解析" % stats.get("docs", 0))
    return 1 if issues else 0

def _cmd_patterns(args):
    """nf patterns：实践包（ls/show/for/verify/reindex）。"""
    from core import patterns as pt
    from pathlib import Path
    import json as _json
    sub = getattr(args, "patterns_cmd", None) or "ls"
    want_json = bool(getattr(args, "json", False))
    if sub == "ls":
        rows = pt.entries(ROOT)
        if want_json:
            print(_json.dumps({"kind": "patterns-ls", "count": len(rows),
                               "rows": [{"id": e["fm"].get("id"), "name": e["fm"].get("name"),
                                         "status": e["fm"].get("status"),
                                         "applies_to": e["fm"].get("applies_to")}
                                        for e in rows]},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf patterns ls（%d 条）==" % len(rows))
            for e in rows:
                fm = e["fm"]
                print("  %-28s %-10s %s" % (fm.get("id", e["dir"]),
                                            fm.get("status", ""), fm.get("name", "")))
        return 0
    if sub == "show":
        want = args.id.strip()
        hit = next((e for e in pt.entries(ROOT)
                    if str(e["fm"].get("id") or e["dir"]) == want), None)
        if hit is None:
            return _machine_fail(args, "pattern 未找到：%s（修复指引：nf patterns ls 可枚举）"
                                 % args.id, 1)
        text = (Path(ROOT) / hit["path"]).read_text(encoding="utf-8")
        note = _trust_note(hit["path"], text)      # 外来内容=数据（社区实践包）
        if want_json:
            print(_json.dumps({"kind": "patterns-show", "id": want, "path": hit["path"],
                               "frontmatter": hit["fm"], "_meta": note},
                              ensure_ascii=False,
                              indent=2, sort_keys=True))
        else:
            print("== nf patterns show %s ==" % want)
            if note:
                print(_trust_line(note))
            for k in sorted(hit["fm"]):
                print("  %-12s %s" % (k + ":", hit["fm"][k]))
            print()
            print(text.split("---", 2)[-1].strip()[:1200])
        return 0
    if sub == "for":
        hits = pt.for_path(ROOT, args.target)
        if want_json:
            print(_json.dumps({"kind": "patterns-for", "target": args.target,
                               "count": len(hits), "rows": hits},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf patterns for %s（%d 条适用）==" % (args.target, len(hits)))
            for h in hits:
                print("  %-28s %s（命中 %s）" % (h["id"], h["name"], h["matched"]))
        return 0
    if sub == "reindex":
        out = pt.write_projection(ROOT)
        if want_json:
            # 机器面（2026-10-01 修）：此前声明了 `--json` 却只打散文——按 JSON 解析的消费方
            # 会当场崩（全量复扫：`nf shell --commands --json` 列出的 93 条带 `--json` 命令里，
            # 只有 4 条不可解析，这是其中两条）。
            print(_json.dumps({"kind": "patterns-reindex", "ok": True,
                               "changed": out["changed"],
                               "note": "patterns/INDEX 投影已重建（真源 = 各 PATTERN.md 头）"},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  ✓ patterns/INDEX 投影已重建：%s"
                  % ("有变化" if out["changed"] else "无变化"))
        return 0
    issues, warns, stats = pt.scan(ROOT)
    proj = pt.check_projection(ROOT)
    if want_json:
        print(_json.dumps({"kind": "patterns-verify", "issues": issues,
                           "warns": warns, "projection": proj,
                           "stats": stats}, ensure_ascii=False, indent=2,
                          sort_keys=True))
    else:
        print("== nf patterns verify（%d 条）==" % stats.get("patterns", 0))
        for i in list(issues) + list(proj):
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in warns:
            print("  [WARN] %s" % w)
        if not issues and not proj:
            print("  ✓ 格式合规 + 适用面/证据可证 + INDEX 投影一致")
    return 1 if (issues or proj) else 0

def _cmd_cognition(args):
    """nf cognition：行话术语表 / 执行分档（认证 + 逐条逐字核对）。"""
    from core import cognition as cg
    import json as _json
    part = getattr(args, "part", "") or ""
    fns = {"glossary": cg.verify_glossary, "modes": cg.verify_modes}
    picked = [k for k in fns if not part or k == part]
    issues, warns, stats = [], [], {}
    for k in picked:
        i, w, s = fns[k](ROOT)
        issues += i
        warns += w
        stats[k] = s
    if args.json:
        print(_json.dumps({"kind": "cognition", "issues": issues,
                           "warns": warns, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        g, m = stats.get("glossary", {}), stats.get("modes", {})
        print("== nf cognition（术语 %d 条 · 使用面 %d · 执行档 %d · 合格实例 %d）=="
              % (g.get("terms", 0), g.get("uses", 0), m.get("modes", 0), m.get("instances_ok", 0)))
        for w in warns:
            print("  [WARN] %s" % w)
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 术语在真源与使用面逐字可核 · 每档实例含必备结构块")
    return 1 if issues else 0

def _cmd_related(args):
    """nf related：41 波C C4 —— 图书馆 See-Also 人读引用链（含模块级依赖图）。"""
    import json as _json
    import re as _re
    from core.market_analyzer import related_of
    from core import module_lifecycle as ml
    from core.impact_check import impact_of_change
    from core.registry_loader import load_registry
    reg_path = args.registry or os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    # 口径统一（2026-10-01）：目标不在册时**不得**回 rc=0「关联条目：—」——那是**错的事实**
    # （用户会把「名字查错了」读成「它没有关联」）。与同族反查 `nf impact` / `nf who-refers`
    # 用同一判据、同一指引。
    target = str(args.target).strip()          # 标识符入参裁空白（见 who-refers 同款注释）
    probe = impact_of_change(load_registry(reg_path), target)
    if probe.get("error"):
        return _machine_fail(
            args, "%s（修复指引：目标须是 registry 在册的 module / protocol id"
                  "（如 M00 / 通用:M10）；`nf market --list` 与 `nf module ls` 可枚举）"
                  % probe["error"], 1)
    try:
        with open(reg_path, encoding="utf-8") as fh:
            reg = _json.load(fh)
        prots = {p["id"]: p for p in reg.get("protocols", [])}
        owner = {}
        for pid in reg.get("protocols", []):
            for m in pid.get("module_ids") or []:
                owner.setdefault(m, pid.get("id"))
        for m in reg.get("modules", []):
            owner.setdefault(m.get("id"), "官方核心")
        fence_re = _re.compile(r"```yaml(.*?)```", _re.S)
        id_re = _re.compile(r"(?m)^\s*id:\s*(M\d+)")
        inp_re = _re.compile(r"(?ms)^\s*inputs:\s*\[(.*?)\]")
        graph = {}
        for rel in ml.iter_module_files(ROOT):
            txt = ml.read_text(ROOT, rel)
            for fence in fence_re.findall(txt):
                if "machine_contract:" not in fence:
                    continue
                im = id_re.search(fence)
                if not im:
                    continue
                iv = inp_re.search(fence)
                ins = set()
                if iv:
                    for x in _re.split(r"[,\s]+", iv.group(1).strip()):
                        if x and not x.startswith("#"):
                            ins.add(x)
                graph.setdefault(im.group(1), set()).update(ins)
        r = related_of(target, prots, module_graph=graph, owner_map=owner)
        if args.json:
            print(_json.dumps(r, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print("== nf related（See-Also · 相关条目 + 引用链）==")
        print("  目标：%s（%s）" % (r["target"], r["kind"]))
        print("  关联条目（引用了谁 / 依赖链）：%s" % ("、".join(r["refs"]) or "—"))
        print("  反向引用方（谁引用我）：%s" % ("、".join(r["referenced_by"]) or "—"))
        print("  相关模块互见：%s" % ("、".join(r["related_modules"]) or "—"))
        return 0
    except _json.JSONDecodeError as exc:
        # 在场但不是合法 registry JSON（形状不符）⇒ 给口径，不冒裸解析错（2026-09-30 同族扫）。
        return _machine_fail(
            args, "registry 不是合法 JSON：%s（修复指引：`--registry` 给 registry.json 的"
                  "**文件**路径（缺省 = desktop/src/core/registry.json）；`nf doctor` 可体检）"
                  % exc)
    except (OSError, ValueError, KeyError) as exc:
        return _machine_fail(args, str(exc))
