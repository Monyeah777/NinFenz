"""CLI 处理器：assemble 族（自 scripts/nf.py 抽出；按 phase 拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, _session_load, _session_write,
                            _write_trace_file)


def _assemble_check_trace(args) -> int:
    from core import trace_drill as tdl

    # 写→读回自证（2026-09-30 闭环）：`--trace` 落盘的遥测件此前**没有任何消费方**——
    # `core/trace_drill.analyze` 是设计好的消费端（重跑 round_drill、断言「重跑判定 ==
    # trace.ok」），却只被自己的单测引用，等于一条**不可达路径**。这里把它接成可跑入口。
    tp = (args.check_trace if os.path.isabs(args.check_trace)
          else os.path.join(ROOT, args.check_trace))
    if not os.path.isfile(tp):
        return _machine_fail(
            args, "trace 件不存在：%s（修复指引：本命令读 `nf assemble \"<需求>\" "
                  "--check <成品.md> --trace <trace.json>` 落盘的遥测件；"
                  "路径相对仓库根或绝对皆可）" % args.check_trace, 1)
    try:
        issues, stats = tdl.analyze(tp, ROOT)
    except (OSError, ValueError) as exc:
        return _machine_fail(
            args, "trace 件不可读：%s（修复指引：确认它是 `nf assemble --trace` 落盘的"
                  "JSON 对象，且含 source/requirement/ok 三键）" % exc, 1)
    if stats.get("verdict_scope") == "none":
        # fail-closed：trace 里没有回合级判定可核 ⇒ 明确说「没做」，不冒充「通过」
        # （与 `--check` 遇到无法解析的需求时 rc=2「未执行验收」同一口径）。
        return _machine_fail(
            args, "未执行漂移断言：该 trace 写时未加 `--rounds`（不含回合级判定）。"
                  "修复指引：重录——`nf assemble \"<需求>\" --check <成品.md> "
                  "--trace <trace.json> --rounds`，再跑本命令读回", 2)
    print("== nf assemble --check-trace（写→读回自证）==")
    print("  转录回合 %d · trace.ok=%s · 重跑判定=%s"
          % (stats["transcript_turns"], stats["expected_ok"], stats["actual_ok"]))
    for i in issues:
        print("  [FAIL] %s" % i, file=sys.stderr)
    if issues:
        return 1
    print("  ✓ 无漂移：重跑回合级 drill 与 trace 记录的判定一致")
    return 0


def _assemble_context(args):
    from core import assemble_plan as ap

    req_text = args.requirement
    answers = getattr(args, "answer", None) or []
    if args.session_path:
        prior = _session_load(args.session_path)
        answers = prior + [a for a in answers if a not in prior]
    if answers:
        req_text = req_text + "（" + "；".join(answers) + "）"
    funnel = ap.clarify(req_text, loose=bool(getattr(args, "loose", False)))
    plan_ = funnel.get("plan") or ap.plan(req_text, loose=bool(getattr(args, "loose", False)))
    return {"req_text": req_text, "answers": answers, "funnel": funnel, "plan_": plan_}


def _assemble_save(args, ctx):
    if not args.save_path:
        return None
    from core import assemble_plan as ap

    text = ap.dossier(ctx["req_text"], ctx["plan_"],
                      ctx["funnel"].get("questions") or [], ctx["answers"])
    # 形状闸门（2026-09-30 同族扫）：`--save <目录>` 此前落到 open 抛裸
    # `[Errno 13] Permission denied: 'docs'`（消息里带 OS 层裸错误）。
    if os.path.isdir(args.save_path):
        return _machine_fail(
            args, "--save 落点是目录：%s（修复指引：给**文件**路径，如 "
                  "需求档案.md）" % args.save_path, 1)
    try:
        parent = os.path.dirname(os.path.abspath(args.save_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        from core import atomic_write      # 需求档案：原子写
        atomic_write.write_text(args.save_path, text)
    except OSError as exc:
        return _machine_fail(args, "写需求档案失败：%s（修复指引：给可写文件路径）"
                             % exc, 1)
    print("  ✓ 需求档案已存：%s" % args.save_path)
    return None


def _assemble_clarify(args, ctx) -> int:
    funnel = ctx["funnel"]
    if args.session_path:
        _session_write(args.session_path, args.requirement, ctx["answers"])
    # 审计 N2（P1）：写失败必须让 rc≠0——此前 _write_trace_file 的返回值在 4 个调用点全被丢弃，
    # 于是「--trace 写不进去」照样返回 0（静默失败却报成功）。
    if args.trace_path and not _write_trace_file(args.trace_path, {
            "tool": "nf assemble", "phase": "clarify",
            "requirement": args.requirement,
            "questions": funnel.get("questions") or [],
    }):
        return 1
    print("== nf assemble（需求澄清）==")
    print("  你的需求信息还不够直接编排，先补三点（缺一不可）：")
    for q in funnel["questions"]:
        print("  · %s" % q)
    print("  补充后再跑：nf assemble \"交付物类型+受众+验收判据的一句话\" --check <out.md>")
    if args.check_md:
        # 2026-09-30 修：`--check` 是**验收动作**，此前会被含糊需求整段吞掉并返回 0——
        # 脚本里 `nf assemble "$REQ" --check out.md && 发布` 会把「没验收」读成「验收通过」。
        # `ap.check` 需要「允许集」而允许集来自需求解析，故这里只能明确拒（fail-closed）。
        return _machine_fail(
            args, "未执行验收：需求无法解析 ⇒ 定不出「允许集」，本次只做了需求澄清、"
                  "没有核对 %s（修复指引：把需求写成可编排的一句话，如 "
                  "`nf assemble \"西幻生存+生存+单世界\" --check <out.md>`）" % args.check_md,
             2)
    return 0


def _assemble_build(args, ctx) -> int:
    from core import assemble_build as ab
    from core import assemble_plan as ap

    plan_ = ctx["plan_"]
    dest = args.build_dest or "."
    guard = ab.check_dest(ROOT, dest)
    if guard and not getattr(args, "allow_protected_dest", False):
        print("  ✗ %s" % guard, file=sys.stderr)
        return 1
    # 形状闸门（2026-10-01）：`--dest <文件>` 此前落到 makedirs 抛裸
    # `[WinError 183] … '<机器路径>'`（有指引但框定不干净，且回吐机器路径）。
    if os.path.exists(dest) and not os.path.isdir(dest):
        return _machine_fail(
            args, "--dest 落点是文件：%s（修复指引：`--build --dest` 给**目录**；"
                  "产物写到 `<目录>/完整版_<包>.md`）" % dest, 2)
    try:
        os.makedirs(dest, exist_ok=True)
        text, bstats = ab.build(ROOT, ctx["req_text"], plan_)
        out_path = os.path.join(dest, "完整版_%s.md" % (plan_["package"] or "自定义世界"))
        from core import atomic_write      # 组装成品：原子写
        atomic_write.write_text(out_path, text)
    except OSError as exc:
        print("  ✗ 组装落盘失败：%s（修复指引：给可写目录）" % exc, file=sys.stderr)
        return 1
    issues, _bstats = ap.check(text, plan_)
    print("== nf assemble --build（需求 → 引用式完整版）==")
    print("  产物：%s（模块 %d 件 · 段 %d · 允许集 %d）"
          % (out_path, bstats["modules"], bstats["segments"],
             len(plan_.get("allowed_module_ids") or [])))
    for issue in issues:
        print("  [FAIL] %s" % issue, file=sys.stderr)
    if not issues:
        print("  ✓ 产物通过自组装机器验收（八段骨架 + 编号允许集 + 决策引用）")
    if args.trace_path and not _write_trace_file(args.trace_path, {
            "tool": "nf assemble", "phase": "build",
            "requirement": args.requirement, "output": out_path,
            "loose": bool(getattr(args, "loose", False)),
            "allowed_scope": plan_.get("allowed_scope"),
            "stats": bstats, "ok": not issues, "issues": issues,
    }):                       # 审计 N2：写失败 ⇒ rc≠0
        return 1
    return 1 if issues else 0


def _assemble_check(args, ctx) -> int:
    from core import assemble_plan as ap

    plan_ = ctx["plan_"]
    try:
        with open(args.check_md, encoding="utf-8") as fh:
            out_md = fh.read()
    except OSError as exc:
        print("  ✗ 读取成品失败：%s（修复指引：给出仓库内完整版 md 路径）" % exc,
              file=sys.stderr)
        return 1
    import re as _re
    has_segments = bool(_re.search(r"^##\s+[0-7]\.", out_md, _re.M))
    issues, stats = ap.check(out_md, plan_) if (
        has_segments or not args.rounds) else ([], {})
    if not stats:
        stats = {"segments": 0, "modules_mentioned": 0,
                 "allowed": len(plan_.get("allowed_module_ids") or [])}
    if args.rounds:
        from core import round_drill as rd
        r_issues, r_stats = rd.scan(out_md, plan_["allowed_module_ids"])
        for i in r_issues:
            issues.append("回合级[%s]" % i)
        if r_stats["warn_gaps"]:
            print("  [WARN] 回合跳号：%s" % r_stats["warn_gaps"])
    # 判定**口径分档**（2026-09-30）：`ok` 是命令总判定；只有加了 `--rounds` 才含回合级。
    # 逐字记下「本次是否做过回合级判定 + 其结果」，消费方（`--check-trace`/trace_drill）
    # 才不会把「没做回合级」误读成「回合级通过」（此前 `ok` 一个字段背两种口径）。
    rounds_scope = {"checked": bool(args.rounds),
                    "ok": (not r_issues) if args.rounds else None}
    print("== nf assemble --check（需求 → 成品机器验收）==")
    print("  需求：%s → %s/%s（模块提及 %d · 允许集 %d）"
          % (args.requirement, plan_["package"] or "？",
             plan_["pipeline"] or "？", stats["modules_mentioned"],
             stats["allowed"]))
    for issue in issues:
        print("  [FAIL] %s" % issue, file=sys.stderr)
    if not issues:
        print("  ✓ 成品通过自组装机器验收（八段骨架 + 编号允许集 + 决策引用）")
    if args.trace_path and not _write_trace_file(args.trace_path, {
            "tool": "nf assemble", "phase": "check",
            "requirement": args.requirement,
            "source": args.check_md,
            "loose": bool(getattr(args, "loose", False)),
            "allowed_scope": plan_.get("allowed_scope"),
            "matched": plan_.get("matched"),
            "package": plan_.get("package"),
            "pipeline": plan_.get("pipeline"),
            "ok": not issues,
            "rounds": rounds_scope,
            "issues": issues,
            "stats": stats,
    }):                       # 审计 N2：写失败 ⇒ rc≠0
        return 1
    return 1 if issues else 0


def _assemble_plan(args, ctx) -> int:
    plan_ = ctx["plan_"]
    print("== nf assemble（需求 → 装配计划）==")
    if plan_["matched"]:
        print("  匹配预设：%s · 管线 %s" % (plan_["package"], plan_["pipeline"]))
        print("  管线件：%s" % ("、".join(plan_["pipeline_files"]) or "—"))
        print("  取件模块：%s" % "、".join(plan_["fetch_modules"]))
        print("  装配允许集（%s）：%d"
              % ("--loose 全库" if plan_.get("loose")
                 else "官方核心 + 命中管线 default/allowed + references",
                 len(plan_["allowed_module_ids"])))
        print("  下一步：读 docs/agent/agent_组装指令包_v0.2.md → 取件 → 输出完整版 → "
              "nf assemble \"%s\" --check <out.md> 验收" % args.requirement)
    else:
        print("  未命中预设 → 用户自定义流（custom）")
        print("  可借用已登记包：%s"
              % ("、".join(plan_["known_packages"]) or "—"))
        print("  装配允许集（%s）：%d"
              % ("--loose 全库" if plan_.get("loose")
                 else "scoped = 官方核心 13；跨域/自定义件用 --loose",
                 len(plan_["allowed_module_ids"])))
        print("  自定义预留槽位：模块 M91-M99 或 <本包独占类别>:Mxx 类内段 · 资产 900+ 命名空间 · "
              "新管线 Pxx（避让层位 id P00-P80 与官方/既有管线，见 02 §8.3）")
        print("  建件：按 community/模板制作指令包.md 做自定义模块/资产 → "
              "protocol.yaml 登记（nf register）→ 成品里即可引用 → 验收")
        print("  验收：nf assemble \"%s\" --check <out.md>"
              % args.requirement)
    if args.session_path:
        _session_write(args.session_path, args.requirement, ctx["answers"])
    if args.trace_path and not _write_trace_file(args.trace_path, {
            "tool": "nf assemble", "phase": "plan",
            "requirement": args.requirement,
            "status": plan_.get("status"),
            "matched": plan_.get("matched"),
            "package": plan_.get("package"),
            "pipeline": plan_.get("pipeline"),
            "loose": bool(getattr(args, "loose", False)),
            "allowed_scope": plan_.get("allowed_scope"),
            "allowed_modules": len(plan_.get("allowed_module_ids") or []),
    }):                       # 审计 N2：写失败 ⇒ rc≠0
        return 1
    return 0


def _cmd_assemble(args):
    """nf assemble：需求 → 澄清漏斗 → 装配计划；--check 对成品完整版做机器验收。"""
    if getattr(args, "check_trace", None):
        return _assemble_check_trace(args)
    ctx = _assemble_context(args)
    rc = _assemble_save(args, ctx)
    if rc is not None:
        return rc
    if ctx["funnel"]["status"] == "clarify":
        return _assemble_clarify(args, ctx)
    if getattr(args, "build", False):
        return _assemble_build(args, ctx)
    if args.check_md:
        return _assemble_check(args, ctx)
    return _assemble_plan(args, ctx)
