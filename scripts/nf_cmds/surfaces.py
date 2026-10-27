"""CLI 处理器：surfaces（自 scripts/nf.py 抽出；行为逐字保留，由 nf.py re-export）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, _no_machine_paths, _rel_display,
                            _rel_out, _print_ops_report)

def _cmd_registry(args) -> int:
    """契约注册表内容寻址（T8.2）：CID 索引生成/校验（实现在 core/registry_index.py）。"""
    import json as _json          # 本文件按需局部导入（见其余 _cmd_* 的同一习惯）
    from core import registry_index as ri

    sub = str(getattr(args, "registry_cmd", "") or "")
    if sub != "index":
        print("  ✗ registry 子命令缺失（当前支持：index；例：nf registry index --write）",
              file=sys.stderr)
        return 2
    if getattr(args, "write", False):
        issues, doc = ri.write(ROOT)
    else:
        issues, doc = ri.check(ROOT)
    if getattr(args, "json", False):
        print(_json.dumps({"kind": "registry-index", "schema": ri.SCHEMA,
                           "issues": issues, "index": doc},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf registry index（内容寻址 · 真源 %s）==" % ri.INDEX_REL)
        print("  包 %d · root %s · 算法 %s"
              % (len(doc.get("entries") or []), str(doc.get("root", ""))[:16],
                 (doc.get("algorithm") or {}).get("cid", "?")))
        signed = str((doc.get("signature") or {}).get("scheme") or "")
        print("  签名：%s" % ("已声明 %s" % signed if signed
                             else "未签名（sig 留空；本版只做内容寻址与篡改检测）"))
        print("  模式：%s" % ("write（已重写索引）" if getattr(args, "write", False)
                             else "check（只校验）"))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0

def _cmd_glossary(args) -> int:
    """nf glossary：英文术语层（T12.2）——check 校验 / render 人读件（同源生成）。"""
    from core import glossary as glg

    sub = getattr(args, "glossary_cmd", "") or ""
    if sub == "check":
        return glg.run(as_json=bool(getattr(args, "json", False)), root=ROOT)
    if sub == "render":
        doc = glg.load(ROOT)
        out = str(getattr(args, "out", "") or "docs/protocol/glossary.en.md")
        target = out if os.path.isabs(out) else _rel_out(out)
        try:
            glg.write_markdown(doc, target)
        except OSError as exc:
            print("  ✗ 渲染落盘失败：%s（修复指引：给可写路径；相对路径按仓库根解析）"
                  % exc, file=sys.stderr)
            return 2
        print("== nf glossary render ==")
        print("  ✓ 已写入：%s（entries %d · 同源确定性）"
              % (_rel_display(target), len(doc.get("entries") or [])))
        return 0
    print("  ✗ 缺子命令（用法：`nf glossary check [--json]` ｜ "
          "`nf glossary render [--out docs/protocol/glossary.en.md]`）", file=sys.stderr)
    return 2

def _cmd_spec(args) -> int:
    """nf spec：ls｜check（契约语义三规则）｜canonical（规范形）｜modelcheck（相位图模型检查）。"""
    action = getattr(args, "action", None) or "ls"
    if action == "modelcheck":
        from core import model_check as mc
        limit = getattr(args, "max_states", None)
        return mc.run(ROOT, max_states=int(limit) if limit else mc.DEFAULT_MAX_STATES,
                      as_json=bool(getattr(args, "json", False)))
    if action == "check":
        from core import contract_semantics as cs
        return cs.run_check(ROOT, core_only=bool(getattr(args, "core", False)),
                            as_json=bool(getattr(args, "json", False)))
    if action == "canonical":
        from core import contract_semantics as cs
        return cs.run_canonical(ROOT, as_json=bool(getattr(args, "json", False)))
    from core.registry_loader import load_registry

    reg_path = args.registry or os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    reg = load_registry(reg_path)
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "kind": "spec-registry",
            "registry_schema_version": reg.registry_schema_version,
            "modules": len(reg.modules),
            "protocols": [{"id": p.get("id"), "schema_version": p.get("schema_version"),
                           "version": p.get("version") or "1.0.0",
                           "modules": len(p.get("module_ids") or [])}
                          for p in reg.protocols or []],
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("== nf spec ls ==")
    print(f"  registry_schema_version: {reg.registry_schema_version}")
    print(f"  官方核心模块: {len(reg.modules)} 件")
    for p in reg.protocols or []:
        print(f"  {p.get('id')}: schema v{p.get('schema_version')}"
              f" · version {p.get('version') or '1.0.0'}"
              f" · {len(p.get('module_ids') or [])} 模块")
    return 0

def _cmd_conformance(args):
    """nf conformance：一致性报告工件（全部契约 → Merkle 根 + verdict）。"""
    from core import conformance_report as cr
    import json as _json
    if args.write:
        doc = cr.run(ROOT)
        rel = cr.write(ROOT, doc=doc)
        print("== nf conformance --write ==")
        print("  报告已写入：%s" % rel)
        print("  verdict：%s（%d/%d 契约通过）· root=%s"
              % (doc["verdict"], doc["passed"], doc["total"], doc["root"][:16]))
        return 0 if doc["verdict"] == "conformant" else 1
    # 全套契约只跑一遍：实时结果既用于与在盘报告比对，也用于打印（过去跑两遍，纯重复）
    doc = cr.run(ROOT)
    issues, stats = cr.verify_committed(ROOT, live=doc)
    if args.json:
        print(_json.dumps({"kind": "conformance", "report": doc, "issues": issues},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf conformance（一致性报告）==")
        print("  %s · %d/%d 契约 · root=%s"
              % (doc["verdict"], doc["passed"], doc["total"], doc["root"][:16]))
        for c in doc["contracts"]:
            print("  %s %-30s %s" % ("✓" if c["ok"] else "✗", c["id"], c["detail"][:60]))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if (issues or doc["verdict"] != "conformant") else 0

def _cmd_endpoint(args):
    """nf endpoint：服务端点契约自检（proposed）。"""
    from core import endpoint
    import json as _json
    issues, warns, stats = endpoint.scan(ROOT)
    doc = endpoint.load(ROOT)
    if args.json:
        print(_json.dumps({"kind": "endpoint", "contract": doc, "issues": issues,
                           "warns": warns, "stats": stats},
                          ensure_ascii=False, indent=2,
                          sort_keys=True))
    else:
        print("== nf endpoint（服务端点契约 · %s）==" % stats.get("status", "?"))
        for ep in doc.get("endpoints") or []:
            print("  %-8s %-22s %-9s %s"
                  % (ep.get("method"), ep.get("path"),
                     "SSE" if ep.get("streaming") else "单发", ep.get("maps_to")))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in warns:
            print("  [note] %s" % w)
        if not issues:
            print("  ✓ 每个端点都映射到现存 CLI 子命令或 MCP 工具（契约不指向空气）")
    return 1 if issues else 0

def _cmd_ir(args) -> int:
    """nf ir：内容 IR（T7.2）——节点级检查（parse→render 规范形 + 悬空 + IR 文本规则）。"""
    from core import content_ir as cir
    import json as _json

    if getattr(args, "ir_cmd", "") != "check":
        print("  ✗ 缺子命令（用法：nf ir check <file> [--json]；"
              "内容 IR 节点图另见 core.content_ir）", file=sys.stderr)
        return 2
    target = args.file if os.path.isabs(args.file) else os.path.join(ROOT, args.file)
    if not os.path.isfile(target):
        return _machine_fail(
            args, "目标不存在：%s（修复指引：给出在场 markdown 产物路径——相对仓库根或绝对皆可；"
                  "典型输入 = `nf assemble \"…\" --build --dest out` 的产物）" % args.file)
    try:
        rep = cir.check_file(target, root=ROOT)
    except OSError as exc:
        return _machine_fail(args, "读取产物失败：%s（修复指引：确认文件可读且为 UTF-8）" % exc)
    rep["path"] = args.file
    if args.json:
        print(_json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=False))
    else:
        print(cir.format_report(rep))
    return 0 if rep.get("ok") else 1

def _cmd_model(args):
    """nf model：内容建模三件（词表 / 规范说明件 / 数据契约）。"""
    from core import modeling as M
    import json as _json
    part = getattr(args, "part", "") or ""
    fns = {"vocab": M.verify_vocabularies,
           "normative": M.verify_normative,
           "contracts": M.verify_contracts}
    picked = [k for k in fns if not part or k == part]
    issues, warns, stats = [], [], {}
    for k in picked:
        i, w, s = fns[k](ROOT)
        issues += i
        warns += w
        stats[k] = s
    if args.json:
        print(_json.dumps({"kind": "model", "issues": issues, "warns": warns,
                           "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf model（内容建模三件%s）==" % (" · " + part if part else ""))
        for k in picked:
            print("  %-10s %s" % (k, stats.get(k, {})))
        for w in warns:
            print("  [WARN] %s" % w)
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 词表与真源一致 · 规范件皆有主 · 说明件未被当规范 · 契约 quality_rule 全部解"
                "析")
    return 1 if issues else 0

def _cmd_assertions(args):
    """nf assertions：跑数据化断言表（封闭 kind 集，不引第三方）。"""
    from core import assertions as at
    import json as _json
    results, issues = at.run(ROOT)
    cap_stats = at.capability_report(ROOT)[1]
    if args.json:
        print(_json.dumps({"kind": "assertions", "results": results,
                           "capabilities": cap_stats, "issues": issues},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf assertions（%d 条 · kind 封闭集 %s）=="
              % (len(results), "/".join(at.KINDS)))
        if cap_stats.get("declared"):
            print("  能力面：%d 个能力 · 覆盖 check %d/%d · 挂账断言 %d/%d%s"
                  % (cap_stats["capabilities"], cap_stats["covered"], cap_stats["checks"],
                     cap_stats["mapped_assertions"], cap_stats["assertions"],
                     (" · 聚合独占：%s" % ",".join(str(n) for n in cap_stats["aggregate_only"]))
                     if cap_stats.get("aggregate_only") else ""))
        for r in results:
            print("  [%s] %-38s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"]))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 断言表全绿（新增规则 = 加一行数据，不必改 check 代码）")
    return 1 if issues else 0

def _cmd_license(args):
    """nf license：图书馆许可证门（登记行 + 内联声明双源）。"""
    from core import license_gate as lg
    import json as _json
    issues, stats = lg.scan(ROOT)
    if args.json:
        print(_json.dumps({"kind": "license", "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf license（图书馆许可证门）==")
        print("  登记 %d 件 · 已声明 %d · 未声明 %d · 无内联 %d · 双源不一致 %d"
              % (stats["entries"], stats["declared"], len(stats["undeclared"]),
                 len(stats["no_inline"]), len(stats["mismatched"])))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in stats["warnings"]:
            print("  [WARN] %s" % w)
        if not issues:
            print("  ✓ 许可面无 FAIL（WARN 为待投稿人回填项，不阻断入库）")
    return 1 if issues else 0

def _cmd_lsp(args):
    """nf lsp：LSP 服务器（stdio）／客户端配置生成。"""
    from core import lsp as lsp_mod
    root = args.root or ROOT
    if args.print_config:
        # 编辑器装配面：唯一真相 = lsp_client.render_client_config（docs/lsp.md 的示例由它产出）。
        print("# 目标编辑器：%s；仓库根：%s" % (args.print_config, root))
        from core import lsp_client as _lsp_client
        print(_lsp_client.render_client_config(args.print_config, root), end="")
        return 0
    return lsp_mod.LspServer(root=root, explicit_root=bool(args.root)).serve()

def _cmd_stats(args) -> int:
    """自述数字实算（出口自动化 · check38 子扫描 1）。"""
    import json as _json          # 本文件按需局部导入（见其余 _cmd_* 的同一习惯）
    from core import repo_stats as rs

    if args.write:
        issues, stats = rs.write(ROOT)
    else:
        issues, stats = rs.check(ROOT)
    if args.json:
        print(_json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf stats（自述数字实算 · 真源 protocol/repo_stats.json）==")
        print("  官方核心：模块 %d · 管线 %s"
              % (stats["core_modules"], " / ".join(stats.get("core_pipelines") or [])))
        print("  社区规模：登记包 %d · 资产档 %d · 概念图 %d · 域包 %d/%d 细分"
              % (stats["registered_packs"], stats["pack_assets"], stats["concept_graphs"],
                 stats["domain_packs"], stats["subdivisions_total"]))
        print("  标准目录：%d 条（可达 %d / 不可达 %d · 机构 %d · %d 边） · 绑定 %d 条"
              % (stats["standards_total"],
 stats["standards_reachable"],
 stats["standards_unreachable"],
                 stats["standards_bodies"], stats["standards_edges"], stats["standard_bindings"]))
        print("  质量凭证：verify check1-%d 常驻（脚本 v%s） · 馆藏 %d 件"
              % (stats["verify_checks"], stats["verify_version"], stats["library_items"]))
        print("  模式：%s" % ("write（已重写生成区）" if args.write else "check（只校验）"))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0

def _cmd_facts(args) -> int:
    """事实真源（SSOT）：protocol/facts.json 的生成/校验（实现在 scripts/nf_facts.py）。"""
    import importlib.util
    path = os.path.join(ROOT, "scripts", "nf_facts.py")
    spec = importlib.util.spec_from_file_location("nf_facts", path)
    if spec is None or spec.loader is None:
        print("  ✗ 读不到 scripts/nf_facts.py（事实真源模块缺失）", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run(write_mode=bool(args.write), json_out=bool(args.json), root=ROOT)

def _cmd_ops(args) -> int:
    """nf ops：内容 SRE（真实产物 → SLI/SLO；缺源 fail-closed，已知无数据如实 UNKNOWN）。"""
    import json as _json
    from core import content_ops as co

    sub = str(getattr(args, "ops_cmd", "") or "")
    live = not bool(getattr(args, "no_live", False))
    want_json = bool(getattr(args, "json", False))
    if sub == "report":
        report = co.collect(ROOT, live=live)
        if want_json:
            print(_json.dumps({"kind": "ops-report", **report}, ensure_ascii=False,
                              indent=2, sort_keys=True))
        else:
            _print_ops_report(report)
        return 0
    if sub == "check":
        issues, report = co.check(ROOT, live=live)
        if want_json:
            print(_json.dumps({"kind": "ops-check", "issues": issues, "report": report},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            _print_ops_report(report)
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
        return 1 if issues else 0
    print("  ✗ ops 需要子命令：report / check（例：nf ops report --json）", file=sys.stderr)
    return 2

def _cmd_security(args) -> int:
    """nf security：内容供应链安全扫描族（T8.3；只读、离线、不执行被扫内容）。

    退出码 = 报告里的 `exit`（0 干净 / 1 有 critical / 2 不可判定），与 `--json` 的
    `exit` 字段同源——脚本消费方读一个口径就够。
    """
    import json as _json
    from core import content_security as cs
    if str(getattr(args, "security_cmd", "") or "") != "scan":
        print("  ✗ 需要子命令：`nf security scan [PATH...] [--json]`", file=sys.stderr)
        return 2
    try:
        report = cs.scan(getattr(args, "paths", None) or None,
                         root=getattr(args, "root", ROOT) or ROOT)
    except OSError as exc:                        # 盘/权限：框成可修正的用户问题
        return _machine_fail(args, "扫描失败：%s（修复指引：确认 --root 与路径可读）"
                             % _no_machine_paths(str(exc)), 2)
    # 机器面纪律：错误原因里可能带 OSError 的绝对路径——统一过 `_no_machine_paths`。
    for item in report.get("errors") or []:
        item["reason"] = _no_machine_paths(str(item.get("reason") or ""))
    if getattr(args, "json", False):
        print(_json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(cs.render_text(report))
    return int(report.get("exit") or 0)

def _cmd_privacy(args) -> int:
    """nf privacy：隐私与 air-gap 静态审计族（T11.2；只读、离线、不执行被扫内容）。

    两个子命令：
    - `scan`：内容面 PII / 本机路径 / 凭据（凭据单源复用 content_security）；
    - `check`：AST 静态审计 core/ 与 scripts/ 的网络站点（白名单逐条理由，陈旧即红）。
    退出码 = 报告里的 `exit`（0 干净 / 1 有 critical / 2 不可判定），与 `--json` 同源。
    """
    import json as _json
    from core import privacy_scan as ps
    sub = str(getattr(args, "privacy_cmd", "") or "")
    try:
        if sub == "scan":
            report = ps.scan(getattr(args, "paths", None) or None,
                             root=getattr(args, "root", ROOT) or ROOT)
            render = ps.render_scan_text
        elif sub == "check":
            report = ps.audit_network(root=getattr(args, "root", ROOT) or ROOT)
            render = ps.render_check_text
        else:
            print("  ✗ 需要子命令：`nf privacy scan [PATH...] [--json]` 或 `nf privacy check "
                  "[--json]`", file=sys.stderr)
            return 2
    except OSError as exc:                        # 盘/权限：框成可修正的用户问题
        return _machine_fail(args, "审计失败：%s（修复指引：确认 --root 与路径可读）"
                             % _no_machine_paths(str(exc)), 2)
    # 机器面纪律：错误原因里可能带 OSError 的绝对路径——统一过 `_no_machine_paths`。
    for item in report.get("errors") or []:
        item["reason"] = _no_machine_paths(str(item.get("reason") or ""))
    if getattr(args, "json", False):
        print(_json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(report))
    return int(report.get("exit") or 0)
