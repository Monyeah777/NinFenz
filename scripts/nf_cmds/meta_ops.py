"""CLI 处理器：元/运维面剩余命令（release/completion/worldmodel/cli/serve/score/explain/help/nfal；自 nf.py 抽出）。

需要入口私有的符号（parser 面 / 命令树 / 版本 / CHECK_GUIDE）由 nf.py 的 shim 注入，避免包 → 入口循环导入。
"""
from __future__ import annotations

import argparse
import os
import sys

from nf_cmds.common import (ROOT, _existing_nonfile_issue, _machine_fail, _rel_display, _rel_out, _release_freeze)

def _cmd_release(args):
    """nf release：发布前体检；--plan 出计划；--freeze [--apply] 按序走冻结链。"""
    from core import release_gate as rg

    if getattr(args, "plan", False):
        import json as _json
        if getattr(args, "json", False):
            print(_json.dumps({"schema": "nf-release-plan/1", "steps": rg.plan(ROOT)},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(rg.render_plan(ROOT))
        return 0
    if getattr(args, "freeze", False):
        return _release_freeze(args)
    if getattr(args, "json", False) and not getattr(args, "fast", False):
        # 机读发布面：确定性摘要（计划 + 前置 + golden 快照），供 CI/发布人留档；只读、不跑 verify。
        import json as _json
        man = rg.manifest(ROOT)
        print(_json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if man["issues"] else 0
    import subprocess  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
    from core import posix_shell as psh
    from core import quality_baseline as qb

    issues, stats = qb.scan(ROOT)
    print("== nf release check（发布前体检）==")
    print("  verify 版本 %s · check 数 %d（基线自描述一致：%s）"
          % (stats["verify_version"], stats["checks"],
             "OK" if not issues else "FAIL"))
    for i in issues:
        print("  [FAIL] %s" % i, file=sys.stderr)
    if args.fast:
        print("  --fast：跳过 verify.sh 全量（发布前请跑完整 nf release）")
        return 1 if issues else 0
    # P3（2026-10-18）：发布前必须走 **full 档**（默认档是 quick：静态 + 受影响测试，
    # 只给开发回路用）；--no-cache 保证发布体检是**真跑**而不是回放旧判定。
    argv = [psh.posix_shell(), "verify.sh", "--full", "--no-cache"]  # nosec B404/B603/B607
    rc = subprocess.run(argv, cwd=ROOT).returncode
    gate_fail = bool(issues) or rc != 0
    if not gate_fail:
        from core import asset_ledger_projection as alp
        from core import instruction_step_audit as isa
        from core import payload_registry as pr
        for name, fn in (("资产 ledger", alp.verify),
                         ("指令审计", isa.scan),
                         ("载荷注册表", pr.scan)):
            f_issues, _ = fn(ROOT)
            if f_issues:
                gate_fail = True
                print("  [FAIL] %s：%s" % (name, "；".join(f_issues[:3])),
                      file=sys.stderr)
            else:
                print("  ✓ %s 一致" % name)
        cov = subprocess.run([psh.posix_shell(), "scripts/per_module_coverage.sh", "30"],  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
                             cwd=ROOT).returncode
        if cov != 0:
            gate_fail = True
            print("  [FAIL] 逐模块覆盖率 < min30", file=sys.stderr)
        else:
            print("  ✓ 逐模块覆盖率 ≥ min30")
        # 静态检查（软依赖）：lint 此前只在 GitHub CI 跑，本地 pre-push（本命令）不含它，
        # 于是「未定义名」一类硬错会在本地积压、只在推送后才红（实测：core/disk_cache.py
        # 曾带 4 处 F821 进树）。这里按仓库软依赖纪律接入：ruff 不在场就跳过并明示，
        # 在场则以**仓库 ruff.toml 同口径**判死。
        lint = subprocess.run([sys.executable, "-m", "ruff", "check",
                               "desktop/src", "scripts"], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        lint_out = (lint.stdout or "") + (lint.stderr or "")
        if lint.returncode == 127 or "No module named" in lint_out:
            print("  [WARN] 缺 ruff（跳过静态检查；修复指引：pip install ruff）")
        elif lint.returncode != 0:
            gate_fail = True
            print("  [FAIL] ruff 静态检查未过（修复指引：python -m ruff check desktop/src scripts）",
                  file=sys.stderr)
        else:
            print("  ✓ ruff 静态检查零告警（仓库 ruff.toml 口径）")
        # 端到端（动态可执行面）：发布前体检必须覆盖「真链路跑通」，不能只看静态门禁。
        # 此前 e2e 只在 e2e-desktop.yml 独立跑，release-gate 不含它——发布前的绿灯
        # 因此不保证端到端可用（顶层化目标：e2e 纳入 release-gate）。
        e2e = subprocess.run([sys.executable, os.path.join("scripts", "e2e_desktop_headless.py")],
                             cwd=ROOT)
        if e2e.returncode != 0:
            gate_fail = True
            print("  [FAIL] 端到端冒烟未过（修复指引：python scripts/e2e_desktop_headless.py）",
                  file=sys.stderr)
        else:
            print("  ✓ 端到端冒烟通过（官方 13 件 + M91/M92 + P04 → 装配 → 生成 → 断言）")
        # 机器可读报告新鲜度（静态可核验面）：已提交的 protocol/verification_report.json
        # 必须等于实时重算——否则门禁的「机器面结论」是过期的。
        vrpt = subprocess.run([sys.executable,
 os.path.join("scripts",
 "verify_report.py"),
 "--fresh"],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        if vrpt.returncode != 0:
            gate_fail = True
            tail = [l for l in ((vrpt.stderr or "") + (vrpt.stdout or "")).splitlines() if l.strip()][-2:]
            print("  [FAIL] 门禁机器可读报告过期或判据未过（修复指引：python scripts/verify_report."
                "py "
                  "--write）%s" % ("；" + " / ".join(tail) if tail else ""), file=sys.stderr)
        else:
            print("  ✓ 门禁机器可读报告新鲜（protocol/verification_report.json == 实时重算）")
    if gate_fail:
        print("  ✗ 发布体检未过（基线/verify）——禁止发布", file=sys.stderr)
        return 1
    print("  ✓ 发布体检通过：verify 全绿 + 基线自描述一致（可打 tag）")
    return 0

def _cmd_worldmodel(args):
    """nf worldmodel：浏览确定性抽象状态契约（machine_contract.world_model）。"""
    import json as _json
    from pathlib import Path

    from core import conformance_scan as csc
    from core import world_model as wm

    concrete = None
    if getattr(args, "state_path", None):
        # 形状 + 格式闸门（2026-10-01）：此前直接读盘 → 缺件时抛裸
        # `[Errno 2] No such file or directory: 'state.json'` 冒成「内部错误 + 机器路径」
        # （文档示例 `nf worldmodel --run --state state.json` 真跑即复现）。
        # 口径统一（2026-10-01）：相对路径按**仓库根**（与 `_rel_out` / `_rel_to_root` 同；此前
        # 直接 `Path(args.state_path)` ⇒ 按进程 cwd，而本命令的错误消息自己写着「相对仓库根或
        # 绝对皆可」——**消息与行为不一致**，从仓外 cwd 跑必然误判「状态件不存在」）。
        sp = Path(_rel_out(args.state_path))
        if not sp.is_file():
            return _machine_fail(
                args, "状态件不存在：%s（修复指引：`--state` 给**在场**具体状态 JSON 文件"
                      "（相对仓库根或绝对皆可）；只想看抽象状态契约就跑 `nf worldmodel --walk`，"
                      "不带 `--state` 即按契约内建初值重放）" % args.state_path, 1)
        try:
            concrete = _json.loads(sp.read_text(encoding="utf-8"))
        except ValueError as exc:
            return _machine_fail(
                args, "状态件不是合法 JSON：%s（修复指引：`--state` 收状态 JSON 对象，"
                      "键名须与该模型契约的 world_slots 对应；对照 `nf worldmodel --walk`）"
                      % exc, 1)

    def _load(model):
        text = Path(ROOT, model["source"]).read_text(encoding="utf-8")
        parsed = csc._fence_yaml(text, "machine_contract")
        return parsed.get("machine_contract", {}).get("world_model")

    def _run_one(model):
        contract = _load(model)
        if not isinstance(contract, dict):
            return None
        runtime = wm.WorldModelRuntime(contract)
        return runtime.replay_concrete(concrete) if concrete is not None else runtime.replay()

    issues, stats = wm.scan(ROOT)
    if args.json and args.run:
        runs = []
        for m in stats["models"]:
            result = _run_one(m)
            if result is not None:
                runs.append({
                    "module": m["module"],
                    "source": m["source"],
                    "result": result,
                })
        print(_json.dumps({"kind": "worldmodel-run", "issues": issues, "runs": runs},
                          ensure_ascii=False, indent=2, sort_keys=True))
    elif args.json:
        print(_json.dumps({"kind": "worldmodel", "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf worldmodel（JEPA-inspired 确定性抽象状态契约 · check32 硬门）==")
        print("  模块 %d · 变量 %d · 相位 %d · 不变式 %d · checks %d · slots %d/%d"
              % (stats["modules"], stats["variables"],
                 stats["phases"], stats["invariants"],
                 stats.get("checks", 0), stats.get("slots", 0),
                 stats.get("slot_registry", 0)))
        for m in stats["models"]:
            print("  · %s（%s · initial=%s · %d phases · %d invariants · %d checks）"
                  % (m["module"], m["source"], m["initial_phase"],
                     m["phases"], m["invariants"], m.get("checks", 0)))
        if args.walk:
            for m in stats["models"]:
                contract = _load(m)
                if not isinstance(contract, dict):
                    continue
                seq, reason, repeat = wm.phase_sequence(contract)
                print("  → %s 重放：%s（终止=%s%s）"
                      % (m["module"], " → ".join(seq), reason,
                         " · 重复=" + str(repeat) if repeat else ""))
        if args.run:
            for m in stats["models"]:
                result = _run_one(m)
                if result is None:
                    continue
                print("  → %s 运行：%d steps（%s%s · digest=%s）"
                      % (m["module"], len(result["steps"]), result["reason"],
                         " · 重复=" + str(result["repeat"]) if result["repeat"] else "",
                         result.get("digest", "")[:12]))
                for step in result["steps"]:
                    print("    %d. %s → %s（guard=%s）"
                          % (step["step"], step["phase_from"], step["phase_to"],
                             step["guard"]))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0

def _cmd_score(args):
    """nf score：基线相对回归评分（绝对门之上的 no-silent-worsening 面）。"""
    from core import regression_score as rs
    from datetime import datetime, timezone
    import json as _json
    try:
        cur = rs.evaluate(ROOT)
        # 形状闸门（2026-09-30 同族扫）：`--baseline <目录>` 此前落到 load_baseline 抛裸
        # Errno；**不在场**仍允许（按空基线起手，`--write-baseline` 可落新基线）。
        _bi = _existing_nonfile_issue(
            args.baseline, "--baseline",
            "修复指引：给基线 JSON 的**文件**路径（缺省 = protocol/score_baseline.json；"
            "不存在时会按空基线起手）")
        if _bi:
            return _machine_fail(args, _bi, 1)
        base_rel = args.baseline or rs.DEFAULT_BASELINE
        base_path = (base_rel if os.path.isabs(base_rel)
                     else os.path.join(ROOT, base_rel))
        if os.path.exists(base_path):
            # 格式闸门（2026-10-01）：坏基线此前落到外层的 `_machine_fail(str(exc))`，
            # 回吐裸解析错（`Expecting property name…`）——与本命令 `--exceptions` 的门
            # 口径不一致（那边有「形如 …」的指引）。同一命令两个相邻旗标，判据必须同款。
            try:
                baseline = rs.load_baseline(base_path)
            except ValueError as exc:
                return _machine_fail(
                    args, "基线不是合法 JSON：%s（%s）（修复指引：给 `nf score "
                          "--write-baseline` 产的基线件；缺省位 %s）" % (base_rel, exc,
                                                                    rs.DEFAULT_BASELINE), 1)
        else:
            baseline = {"schema": rs.SCHEMA}
        exceptions = []
        if args.exceptions:
            exc_path = (args.exceptions if os.path.isabs(args.exceptions)
                        else os.path.join(ROOT, args.exceptions))
            # 形状 + 格式闸门（2026-10-01）：`--exceptions <目录/缺失件>` 此前抛裸
            # `[Errno 13]/[Errno 2]`（零指引），与 `--baseline` 同类。
            if not os.path.isfile(exc_path):
                return _machine_fail(
                    args, "例外表不存在：%s（修复指引：`--exceptions` 给**在场 JSON 文件**，"
                          "形如 `[{\"signal\": \"…\", \"reason\": \"…\"}]`（例外只标注理由、"
                          "不隐藏回归）；不给即按零例外判）" % args.exceptions, 1)
            try:
                with open(exc_path, encoding="utf-8") as fh:
                    exceptions = _json.load(fh)
            except ValueError as exc:
                return _machine_fail(
                    args, "例外表不是合法 JSON：%s（修复指引：形如 "
                          "`[{\"signal\": \"…\", \"reason\": \"…\"}]`）" % exc, 1)
        out = rs.compare(cur, baseline, tolerance=args.tolerance,
                         exceptions=exceptions)
        if args.write_baseline:
            rs.save_baseline(base_path, cur,
                             recorded_at=datetime.now(timezone.utc)
                             .strftime("%Y-%m-%dT%H:%M:%SZ"),
                             note="nf score --write-baseline")
        if args.json:
            print(_json.dumps({"kind": "score", "current": cur, "compare": out},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf score（基线相对回归评分）==")
            print("  当前 %.2f · 基线 %.2f · delta %+.2f · 容差 %.2f"
                  % (out["current_score"], out["baseline_score"],
                     out["delta"], args.tolerance))
            print("  %s" % out["verdict"])
            for s in cur["signals"]:
                print("  · %-18s w=%.2f v=%.2f" % (s["name"], s["weight"], s["value"]))
            for r in out["regressed"]:
                print("    [REGRESS] %s %.4f → %.4f（%.4f）"
                      % (r["signal"], r["from"], r["to"], r["drop"]),
                      file=sys.stderr)
            if args.write_baseline:
                print("  基线已写入：%s" % _rel_display(base_path))
        return 0 if out["ok"] else 1
    except (OSError, ValueError, _json.JSONDecodeError) as exc:
        return _machine_fail(args, str(exc), 1)

def _cmd_nfal(args) -> int:
    """nf nfal：透传到 core.nfal_cli（guard 表达式的解析/检查/编译/求值）。"""
    from core import nfal_cli
    return nfal_cli.main(list(getattr(args, "nfal_args", []) or []))

def run_cli(args, build_parser):
    """nf cli：CLI 信息架构机读层（T11.3；只读消费 argparse + terminal.FAMILIES）。"""
    import json as _json
    from core import cli_catalog as cc

    sub = str(getattr(args, "cli_cmd", "") or "")
    if sub != "map":
        print("  ✗ 需要子命令：`nf cli map [--write|--check] [--json]`"
              "（修复指引：见 nf cli --help）", file=sys.stderr)
        return 2
    try:
        parser = build_parser()
    except Exception as exc:  # noqa: BLE001 - 命令面坏件 → 可修正的用户问题
        print("  ✗ 构建命令面失败：%s（修复指引：修复 argparse 面后重跑）" % exc,
              file=sys.stderr)
        return 2
    want_json = bool(getattr(args, "json", False))
    if getattr(args, "write", False):
        paths, doc = cc.write(ROOT, parser)
        issues = cc.coverage_issues(doc)
        if want_json:
            print(_json.dumps({"kind": "cli-map-check", "schema": "nf-cli-map-check/1",
                               "ok": not issues, "issues": issues, "written": paths,
                               "coverage": doc["coverage"]},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for rel in paths:
                print("  ✓ 已生成 %s" % rel)
            print("  命令 %d · 族 %d · 已归族 %d"
                  % (doc["coverage"]["commands"], doc["coverage"]["families"],
                     doc["coverage"]["covered"]))
        return 0 if not issues else 1
    if getattr(args, "check", False):
        issues, diffs, doc = cc.check(ROOT, parser)
        if want_json:
            print(_json.dumps({"kind": "cli-map-check", "schema": "nf-cli-map-check/1",
                               "ok": not issues, "issues": issues, "diffs": diffs,
                               "coverage": doc["coverage"]},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf cli map --check（生成件 vs 实时重算）==")
            for issue in issues:
                print("  [FAIL] %s" % issue)
            print("  → %s" % ("PASS" if not issues else "FAIL"))
        return 0 if not issues else 1
    doc = cc.build(parser, root=ROOT)
    issues = cc.coverage_issues(doc)
    if want_json:
        print(_json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not issues else 1
    cov = doc["coverage"]
    print("== nf cli map（命令面 IA · 只读）==")
    print("  顶层命令 %d · 能力族 %d · 已归族 %d · JSON 面 %d"
          % (cov["commands"], cov["families"], cov["covered"],
             sum(1 for c in doc["commands"] if c["has_json"])))
    for fam in doc["families"]:
        print("  %-10s %s（%d 条）"
              % (fam["id"], fam["name"], len(fam["commands"])))
    for issue in issues:
        print("  [FAIL] %s" % issue)
    print("  → %s" % ("PASS" if not issues else "FAIL"))
    return 0 if not issues else 1

def run_help(args, build_parser):
    """nf help [COMMAND]：显示 nf 总帮助或指定子命令帮助。"""
    root = build_parser()
    command = getattr(args, "command", None)
    if command:
        for action in root._actions:
            if isinstance(action, argparse._SubParsersAction):
                choice = action.choices.get(command)
                if choice is not None:
                    choice.print_help()
                    return 0
        print("  ✗ 未知子命令：%s（nf --help 看全量）" % command, file=sys.stderr)
        return 2
    root.print_help()
    return 0

def run_completion(args, collect_cli_tree):
    """nf completion <bash|zsh|fish>：从 argparse 命令面生成 shell 补全脚本。"""
    data = collect_cli_tree()
    cmds = data["commands"]
    root_flags = data["root_flags"]
    tree = data["tree"]
    words = lambda xs: " ".join(xs)  # noqa: E731

    def var(cmd):
        return cmd.replace("-", "_")

    if args.shell == "bash":
        lines = [
            "# nf bash completion（自动生成 · 追加到 ~/.bashrc 后 source）",
            "_nf_cmds=\"%s\"" % words(cmds),
            "_nf_root_flags=\"%s\"" % words(root_flags),
        ]
        for c in cmds:
            lines.append("_nf_flags_%s=\"%s\"" % (var(c), words(tree[c]["flags"])))
            if tree[c]["nested"]:
                lines.append("_nf_nested_%s=\"%s\""
                             % (var(c), words(sorted(tree[c]["nested"]))))
        lines += [
            "_nf_completions(){",
            "  local cur cmd",
            "  cur=\"${COMP_WORDS[COMP_CWORD]}\"",
            "  if [ \"$COMP_CWORD\" -eq 1 ]; then",
            "    COMPREPLY=( $(compgen -W \"$_nf_cmds $_nf_root_flags\" -- \"$cur\") )",
            "    return",
            "  fi",
            "  cmd=\"${COMP_WORDS[1]}\"",
            "  case \"$cmd\" in",
        ]
        for c in cmds:
            if tree[c]["nested"]:
                lines.append(
                    "    %s) if [ \"$COMP_CWORD\" -eq 2 ]; then"
                    " eval nest=\"$_nf_nested_%s\";"
                    " COMPREPLY=( $(compgen -W \"$nest\" -- \"$cur\") ); return; fi ;;" % (c,
 var(c)))
        lines += [
            "  esac",
            "  eval fl=\"$_nf_flags_${cmd//-/_}\"; fl=\"${fl:-}\"",
            "  if [[ \"$cur\" == -* ]]; then COMPREPLY=( $(compgen -W \"$fl\" -- \"$cur\") ); retur"
                "n; fi",
            "  COMPREPLY=( $(compgen -W \"$fl\" -- \"$cur\") $(compgen -f -- \"$cur\") )",
            "}",
            "complete -F _nf_completions nf",
            "",
        ]
        print("\n".join(lines))
        return 0

    if args.shell == "zsh":
        all_flags = sorted(set(data["root_flags"]))
        for c in cmds:
            all_flags += tree[c]["flags"]
            for sub in tree[c]["nested"].values():
                all_flags += sub
        all_flags = sorted(set(all_flags))
        lines = [
            "#compdef nf",
            "# nf zsh completion（自动生成）",
            "_nf_cmds=(%s)" % " ".join(cmds),
            "_nf_all_flags=(%s)" % " ".join(all_flags),
            "_nf() {",
            "  local -a cmds",
            "  cmds=(%s)" % " ".join(cmds),
            "  if (( CURRENT == 2 )); then",
            "    _describe -t commands 'nf command' cmds",
            "  else",
            "    if [[ $PREFIX == -* ]]; then compadd -- $_nf_all_flags; else _files; fi",
            "  fi",
            "}",
            "compdef _nf nf",
            "",
        ]
        print("\n".join(lines))
        return 0

    # fish
    lines = [
        "# nf fish completion（自动生成 · nf completion fish | source）",
        "complete -c nf -f",
        "complete -c nf -n '__fish_use_subcommand' -a '%s'" % " ".join(cmds),
    ]
    for c in cmds:
        for f in tree[c]["flags"]:
            if f.startswith("--"):
                lines.append("complete -c nf -n '__fish_seen_subcommand_from %s' -l %s"
                             % (c, f[2:]))
            elif f.startswith("-") and len(f) == 2:
                lines.append("complete -c nf -n '__fish_seen_subcommand_from %s' -s %s"
                             % (c, f[1:]))
        for n2 in tree[c]["nested"]:
            lines.append("complete -c nf -n '__fish_seen_subcommand_from %s' -a '%s'"
                         % (c, n2))
            for f in tree[c]["nested"][n2]:
                cond = "__fish_seen_subcommand_from %s; and __fish_seen_subcommand_from %s" % (c,
 n2)
                if f.startswith("--"):
                    lines.append("complete -c nf -n '%s' -l %s" % (cond, f[2:]))
                elif f.startswith("-") and len(f) == 2:
                    lines.append("complete -c nf -n '%s' -s %s" % (cond, f[1:]))
    print("\n".join(lines))
    return 0

def run_serve(args, version):
    """nf serve [mcp.json]：stdio JSON-RPC 服务（C1，MCP client 拉起）。

    默认路径（无参）= **实时仓库面**：不要求先产快照——直接起只读 resources/tools/prompts
    面（数据源 = 仓库只读扫描），适合 agent 密集重复调用（免掉「先 run 再 serve」两跳）。
    给快照路径时行为不变（烧快照面）。

    transport 纪律：stdout 只写 MCP 消息（换行分隔 JSON-RPC）——初始化说明走 stderr。
    """
    from core.mcp_runtime import load_snapshot, McpRuntime

    if args.snapshot:
        label = os.path.basename(args.snapshot)
        try:
            snapshot = load_snapshot(args.snapshot)
        except OSError as exc:
            print("  ✗ 快照不可读：%s（修复指引：确认路径；或直接 `nf serve` 走实时仓库面，无需快照"
                "）"
                  % exc, file=sys.stderr)
            return 2
        except ValueError as exc:
            print("  ✗ 快照形状不合规：%s" % exc, file=sys.stderr)
            return 2
    else:
        label = "live（实时仓库面，无需快照）"
        snapshot = {"mcp": {"name": "nf-repo-live", "version": version,
                            "resources": []}}
    print(f"== nf serve {label} =="
          f"（stdio JSON-RPC，Ctrl+C 退出）", file=sys.stderr)
    # 参数 ⇄ inputSchema 校验器**在此注入**（依赖倒置：mcp_runtime 是稳定侧，不反向依赖
    # 校验器；见其 __init__ docstring）——上架通道因此逐条执行 tools/list 里那份声明。
    from core import json_schema
    return McpRuntime(snapshot, schema_check=json_schema.json_schema_check).serve_stdio()

def run_explain(args, guide):
    """nf explain：41 波C C5 —— check 修复指引（缺什么/补什么/示例）。"""
    key = args.check.strip().lower()
    if key in ("all", ""):
        print("== nf explain all（check 修复指引全量）==")
        for k in sorted(guide):
            print("  check%s：%s" % (k, guide[k]))
        return 0
    if key.startswith("check"):
        key = key[5:]
    guide = guide.get(key)
    if not guide:
        print("  ✗ 未知 check：%s（可用 all 看全量）" % args.check, file=sys.stderr); return 2
    print("== nf explain check%s ==" % key)
    print("  %s" % guide); return 0
