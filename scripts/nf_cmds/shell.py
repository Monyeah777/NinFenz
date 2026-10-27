"""CLI 处理器：shell/terminal（自 scripts/nf.py 抽出；按子模式拆小函数，行为逐字保留）。

`run()` 由 nf.py 的 `_cmd_shell` 注入两个调用方符号（避免包 → 入口的循环导入）：
`main`（命令 dispatcher）与 `collect_cli_tree` / `shell_command_index`（argparse 面派生）。
"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, _page_text, _portable_path,
                            _shell_baseline, _surface_module_on_disk)


def _shell_runner(main):
    def runner(argv):
        argv = list(argv)
        if argv and argv[0] in ("shell", "terminal"):
            print("  终端内不再开终端（避免递归会话）："
                  "请另开一个终端窗口运行 nf shell。", file=sys.stderr)
            return 2
        return main(argv)
    return runner


def _shell_setup(args, term, index):
    """解析会话/颜色/宽度/历史；返回 (rc, ctx)。rc 非 None 表示参数校验失败。"""
    # 会话状态（`--session`）：显式 CLI 参数 > 会话文件 > 缺省
    state, state_warn = term.load_session_state(args.session_path)
    _s = (state.get("settings") or {}) if state else {}
    color_mode = args.color or str(_s.get("color") or "auto")
    width = args.width or int(_s.get("width") or 0) or 0
    limit = args.limit if args.limit is not None else int(_s.get("limit") or 0)
    color_on = term.resolve_color(color_mode, sys.stdout)
    if state_warn:
        print("  [WARN] %s" % state_warn, file=sys.stderr)
    if args.session_path and not os.path.isabs(args.session_path):
        print("  ✗ --session 须给绝对路径（修复指引：用 <NF_HOME>/shell_session.json 之类的仓库外路"
              "径）",
              file=sys.stderr)
        return 2, None
    _sess_abs = os.path.abspath(args.session_path) if args.session_path else ""
    _scratch_prefix = os.path.abspath(os.path.join(ROOT, ".rivet")) + os.sep
    _inside_repo = bool(_sess_abs) and _sess_abs.startswith(os.path.abspath(ROOT))
    _in_scratch = bool(_sess_abs) and _sess_abs.startswith(_scratch_prefix)
    if args.session_path and _inside_repo and not _in_scratch:
        print("  ✗ --session 不得落在仓库内（修复指引：会话状态属本机用户态，请放到 NF_HOME 或临时"
              "目录——"
              "仓库内留件会被 git add -A 吞掉，2026-09-26 实测过）", file=sys.stderr)
        return 2, None
    # 历史落点（交互态；`--exec`/`--file` 一律不写，保确定性）
    history_path = None
    if not args.no_history:
        history_path = args.history or term.default_history_path()
    return None, {"index": index, "color_mode": color_mode, "width": width,
                  "limit": limit, "color_on": color_on, "history_path": history_path}


def _shell_forms(args, term, ctx):
    width = ctx["width"]
    color_on = ctx["color_on"]
    if args.form_id is not None and not args.form_id:
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "forms", "count": len(term.form_table()),
                               "rows": [{"id": f["id"], "title": f["title"],
                                         "summary": f["summary"],
                                         "steps": [dict(st) for st in f["steps"]],
                                         "argv": list(f["argv"])}
                                        for f in term.form_table()]},
                              ensure_ascii=False, indent=2))
            return 0
        print(term.render_forms("", width or None, color_on))
        return 0
    if args.form_id:
        form = term.form_by_id(args.form_id)
        if form is None:
            print("  ✗ 未识别的表单：%s（可用：%s；或 nf shell --form 列全部）"
                  % (args.form_id, "、".join(str(f["id"]) for f in term.form_table())),
                  file=sys.stderr)
            return 2
        answers = {}
        for pair in args.answer or []:
            k, _, v = str(pair).partition("=")
            answers[k.strip()] = v.strip()
        missing = term.form_missing(form, answers)
        if missing:
            print("  [FAIL] 表单 %s 还缺必填项：%s（修复指引：--answer %s=…）"
                  % (form["id"], "、".join(missing), missing[0]), file=sys.stderr)
            return 2
        argv = term.build_argv(form, answers)
        if args.json:
            import json as _json
            if not args.yes:
                print(_json.dumps({"kind": "form-plan", "id": form["id"],
                                   "argv": argv, "executed": False},
                                  ensure_ascii=False, indent=2))
                return 0
            code = ctx["runner"](argv)
            print(_json.dumps({"kind": "form-run", "id": form["id"], "argv": argv,
                               "executed": True, "exit": code},
                              ensure_ascii=False, indent=2))
            return code
        if not args.yes:
            print("== 表单 %s（%s）==" % (form["title"], form["id"]))
            print("  组装命令：nf %s" % " ".join(argv))
            print("  （dry-run：加 --yes 才执行；交互态用 /form %s 逐项追问）" % form["id"])
            return 0
        print("== 表单 %s（%s）· 执行 ==" % (form["title"], form["id"]))
        print("  nf %s" % " ".join(argv))
        return ctx["runner"](argv)
    return None


def _shell_surface_write(args, term, ctx, collect_cli_tree) -> int:
    tree = collect_cli_tree()
    payload = term.surface_payload(tree["commands"], tree["root_flags"])
    target = args.surface_write or term.SURFACE_MODULE_PATH
    try:
        from core import paths as _paths
        full = _paths.validate_path(ROOT, target)
    except Exception as exc:                         # noqa: BLE001 - 落点不合法即用法错误
        return _machine_fail(args, "生成件落点不合法：%s" % exc, 2)
    text = term.render_surface_module(payload)
    parent = os.path.dirname(full)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    from core import atomic_write
    atomic_write.write_text(full, text)
    rel = os.path.relpath(full, ROOT).replace("\\", "/")
    if args.json:
        import json as _json
        print(_json.dumps({"kind": "surface-write", "ok": True, "path": rel,
                           "digest": payload["digest"],
                           "lines": len(text.splitlines()),
                           "source": payload["source"]["module"]},
                          ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("  ✓ 终端面投影已刷新：%s（真源 %s · %s）"
          % (rel, payload["source"]["module"], payload["digest"][:19]))
    return 0


def _shell_surface(args, term, ctx, collect_cli_tree) -> int:
    tree = collect_cli_tree()
    payload = term.surface_payload(tree["commands"], tree["root_flags"])
    if args.json:
        import json as _json
        print(_json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(_page_text(term.render_surface(payload, ctx["width"] or None, ctx["color_on"]),
                     args.pager))
    return 0


def _shell_commands(args, term, ctx) -> int:
    index = ctx["index"]
    if args.json:
        import json as _json
        filt = (args.commands or "").lower()
        rows = [e for e in index
                if not filt or filt in str(e.get("path")).lower()
                or filt in str(e.get("summary") or "").lower()]
        print(_json.dumps({"kind": "commands", "filter": args.commands or "",
                           "count": len(rows), "rows": rows},
                          ensure_ascii=False, indent=2))
        return 0
    print(_page_text(term.render_commands(index, args.commands or "",
                                          limit=ctx["limit"], width=ctx["width"] or None,
                                          color=ctx["color_on"]), args.pager))
    return 0


def _shell_map(args, term, ctx) -> int:
    if args.json:
        import json as _json
        fams = term.families_for(args.family_map or "")
        print(_json.dumps({"kind": "map", "filter": args.family_map or "",
                           "count": len(fams),
                           "families": [{"id": f["id"], "name": f["name"],
                                         "summary": f["summary"],
                                         "commands": list(f["commands"])}
                                        for f in fams]},
                          ensure_ascii=False, indent=2))
        return 0
    print(_page_text(term.render_map(args.family_map or "", ctx["width"] or None,
                                     ctx["color_on"]), args.pager))
    return 0


def _shell_search(args, term, ctx) -> int:
    text, hits = term.render_search(ctx["index"], args.search, width=ctx["width"] or None,
                                    color=ctx["color_on"])
    print(_page_text(text, args.pager))
    return 0 if hits else 2


def _shell_baseline_cmd(args, term, ctx, main) -> int:
    import contextlib
    import io

    def _capture(argv, stdin_text=None):
        """证据行执行：捕获输出（基线表只判「输出里有没有/有没有违规片段」）。"""
        buf = io.StringIO()
        old_in = sys.stdin
        if stdin_text is not None:
            sys.stdin = io.StringIO(str(stdin_text))
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = main(list(argv))
        finally:
            sys.stdin = old_in
        return code, buf.getvalue()

    self_issues = term.baseline_argv_issues()
    results, stats = term.run_baseline(_capture)
    failed = [r for r in results if not r["ok"]]
    shown = term.portable_rows(results)     # 展示/机器面回 `{TMP}`（本机路径不回吐）
    if args.json:
        import json as _json
        print(_json.dumps({"kind": "shell-baseline",
                           "ok": not self_issues and not failed,
                           "self_issues": self_issues, "stats": stats,
                           "rows": shown}, ensure_ascii=False, indent=2))
        return 0 if (not self_issues and not failed) else 1
    print(term.render_baseline(shown, stats, ctx["width"] or None, ctx["color_on"]))
    for i in self_issues:
        print("  [FAIL] 基线自身不合规：%s" % i)
    for r in failed:
        why = ("耗时 %s ms > 预算 %s ms" % (r["ms"], r["max_ms"]) if r["content_ok"]
               else "期望含 %r 且不含 %r" % (r["expect"], r["forbid"]))
        print("  [FAIL] %s：退出码 %s（证据：nf %s；%s）"
              % (r["id"], r["exit"], " ".join(r["argv"]), why))
    return 0 if (not self_issues and not failed) else 1


def _shell_verify(args, term, ctx, collect_cli_tree, main) -> int:
    import shutil
    index = ctx["index"]
    tree = collect_cli_tree()
    if args.deep:
        import contextlib
        import io
        live_buf = io.StringIO()

        def _live(argv):
            """活体执行：**捕获**输出（机器面须纯 JSON）。逐条 `--help` 的扫描输出不留在
            `live_buf`——否则人读面会把最后一条 help 当成「活体输出」打印（实测踩过）。"""
            is_help_sweep = len(argv) >= 2 and str(argv[-1]) == "--help"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = main(list(argv))
            if not is_help_sweep:
                live_buf.truncate(0)
                live_buf.seek(0)
                live_buf.write(buf.getvalue())
            return code

        issues, stats = term.deep_check(
            index, tree["commands"], tree["root_flags"],
            live_runner=_live,
            history_path=ctx["history_path"], session_path=args.session_path or None,
            stream=sys.stdout,
            pager_ok=bool(shutil.which("less") or shutil.which("more")))
        stats["live_output"] = term.clip(live_buf.getvalue().strip(), 300)
    else:
        issues, stats = term.self_check(index, tree["commands"], tree["root_flags"])
    # 投影对账（与 check39 同源判据）：真源改了却没重生成 ⇒ 当场红
    issues = list(issues) + term.surface_sync_issues(
        _surface_module_on_disk(), tree["commands"], tree["root_flags"])
    if args.json:
        import json as _json
        print(_json.dumps({"kind": "shell-verify", "ok": not issues,
                           "deep": bool(args.deep), "issues": issues,
                           "stats": stats}, ensure_ascii=False, indent=2))
        return 0 if not issues else 1
    print("== nf shell --verify（终端自检 · 与 verify check39 同源判据%s）=="
          % (" · 活体档" if args.deep else ""))
    for i in issues:
        print("  [FAIL] %s" % i)
    print("  命令 %d · 能力族 %d · 索引条目 %d · 菜单示例 %d · 动作 %d → %s"
          % (stats["commands"], stats["families"], stats["index_entries"],
             stats["examples"], stats.get("actions", 0),
             "通过" if not issues else "FAIL %d" % len(issues)))
    if args.deep:
        print("  活体：%s 退出码 %s · 历史落点 %s · 会话落点 %s"
              % (stats.get("live_command", "-"), stats.get("live_code", "-"),
                 stats.get("历史落点", "-"), stats.get("会话落点", "-")))
        _failed = stats.get("help_sweep_failed") or []
        print("  全命令可调用：%d/%d（逐条 --help；失败：%s）"
              % ((stats.get("help_sweep_total", 0) - len(_failed)),
                 stats.get("help_sweep_total", 0),
                 "、".join(_failed[:5]) if _failed else "无"))
        print("  环境：TTY %s · readline %s · 分页器 %s"
              % ("是" if stats.get("tty") else "否",
                 "可用" if stats.get("readline") else "不可用",
                 stats.get("pager", "未探测")))
        for _ln in str(stats.get("live_output") or "").splitlines():
            print("  ── 活体输出：%s" % _ln)
    print("  补全：内建候选列表（/complete、行尾 Tab）+ %s"
          % ("readline 已接管" if term.readline_available()
             else "readline 不可用（本平台无该模块，走零依赖回退）"))
    print("  历史：%s"
          % _portable_path(args.history or term.default_history_path()))
    return 0 if not issues else 1


def _shell_script(args, term, ctx, sw, runner) -> int:
    # 形状闸门（2026-10-01）：`--file <目录>` 此前回 `[Errno 13] Permission denied: 'docs'`
    # 配「确认路径存在后重试」——对一个**确实存在**的目录说「不存在」，指引本身就错。
    _sf = args.script_file
    if not os.path.isfile(_sf):
        return _machine_fail(
            args, "脚本文件不是在场文件：%s（修复指引：`--file` 给**在场脚本文件**——每行一条 "
                  "nf 命令，`#` 注释与空行跳过；交互式逐条输入请用 `--exec \"a; b\"`）"
                  % _sf, 2)
    try:
        code, text, _records = sw.run_file(args.script_file, runner, ROOT,
                                           assume_yes=args.yes,
                                           as_json=args.json, index=ctx["index"])
    except OSError as exc:
        print("  ✗ 读不到脚本文件：%s（修复指引：确认路径存在后重试）" % exc,
              file=sys.stderr)
        return 2
    print(text)
    return code


def _shell_exec(args, ctx, sw, runner) -> int:
    code, text, _records = sw.run_script(args.exec_script, runner, ROOT,
                                         assume_yes=args.yes,
                                         as_json=args.json, index=ctx["index"])
    print(text)
    return code


def _shell_interactive(args, term, ctx, sw, runner) -> int:
    # 机器面防挂（2026-10-01）：`--json` 的帮助写明「配合 --exec」。若一路走到**交互兜底**还带着
    # `--json`，说明消费方期待 JSON，却会被送进交互会话——非 TTY（agent/CI/管道）下**永久阻塞**。
    # fail-closed 明确拒，并把可用的机读子模式列全。
    if args.json:
        return _machine_fail(
            args, "--json 需配合机读子模式（修复指引：`nf shell --exec \"<命令>\" --json`、"
                  "`--file <脚本> --json`、`--verify --json`、`--commands --json`、"
                  "`--map --json`、`--form [id] --json`、`--baseline --json`）；"
                  "裸 `nf shell` 是**交互终端**，非 TTY 下会阻塞，故不在此输出 JSON", 2)
    if term.install_readline(lambda text: [c["text"] for c in term.complete(text, ctx["index"])],
                             ctx["history_path"]):
        pass                                  # readline 接管 Tab 与历史（POSIX）
    print_banner = not args.no_banner
    return sw.run_session(runner, sys.stdin, sys.stdout, ROOT,
                          assume_yes=args.yes,
                          show_banner=print_banner,
                          baseline=_shell_baseline(), index=ctx["index"],
                          history_path=ctx["history_path"], color=ctx["color_on"],
                          width=ctx["width"] or None, limit=ctx["limit"],
                          color_mode=ctx["color_mode"], session_path=args.session_path)


def run(args, *, main, collect_cli_tree, shell_command_index) -> int:
    """nf shell（别名 nf terminal）：终端交互入口（端壳退役后的人机面）。"""
    from core import session_watch as _sw, terminal as term   # 会话缓存包装（见 core.session_watch）

    index = shell_command_index()
    runner = _shell_runner(main)
    rc, ctx = _shell_setup(args, term, index)
    if rc is not None:
        return rc
    ctx["runner"] = runner

    if args.form_id is not None:
        rc = _shell_forms(args, term, ctx)
        if rc is not None:
            return rc
    if args.surface_write is not None:
        return _shell_surface_write(args, term, ctx, collect_cli_tree)
    if args.surface:
        return _shell_surface(args, term, ctx, collect_cli_tree)
    if args.commands is not None:
        return _shell_commands(args, term, ctx)
    if args.family_map is not None:
        return _shell_map(args, term, ctx)
    if args.search:
        return _shell_search(args, term, ctx)
    if args.baseline:
        return _shell_baseline_cmd(args, term, ctx, main)
    if args.verify:
        return _shell_verify(args, term, ctx, collect_cli_tree, main)
    if args.complete_prefix:
        cands = term.complete(args.complete_prefix, index)
        print(term.render_completions(args.complete_prefix, cands))
        return 0 if cands else 2
    if args.script_file:
        return _shell_script(args, term, ctx, _sw, runner)
    if args.exec_script:
        return _shell_exec(args, ctx, _sw, runner)
    return _shell_interactive(args, term, ctx, _sw, runner)
