#!/usr/bin/env python3
"""NF 终端（`nf shell`）——端壳退役后的人机交互入口（纯 stdlib · 确定性 · 可注入）。

定位（对齐 `docs/L3_FROZEN.md`「能力入口一律落 CLI」）：
桌面 GUI 端壳与打包线已于 2026-09-09 永久退役，公开面收敛为「协议 + core 库 + CLI」，
人机交互面随之真空。本模块补的**不是**第二套命令面，而是把**既有** CLI 命令面按能力菜单
组织成可交互会话：读一行 → 解析 → 闸门 → 分派 → 打印。命令真源仍是 `scripts/nf.py`
的 argparse 面——`ZONES` 的每条示例命令都由 verify check39 解析断言，菜单指向死命令即红。

三条硬约束（与仓库红线同源）：
1. **零第三方依赖**：只用 stdlib。刻意不用 curses（Windows 无该模块）与 PySide6 等
   GUI 工具包（PySide6 只服务 CCV3 卡面写入，与终端无关）。
2. **确定性**：同一输入两次运行逐字节一致——`nf shell --exec` 是回归面，也是 check39 的判据。
3. **安全闸门**：写入类命令默认拒跑，须显式确认（交互输入 yes，或调用方显式 `--yes`）。
   终端不替使用者拍板；`serve`（长驻服务）与 `shell`（递归会话）在会话内给指引而非执行。

分层：本模块只做「解析 / 菜单 / 渲染 / 闸门 / 会话状态机」，**不 import scripts/nf.py**——
执行由调用方以 `runner(argv) -> int` 注入，故 core 层保持零 CLI 反向依赖，单测可完全离线。
"""
from __future__ import annotations

from dataclasses import dataclass

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
from typing import Any

# 依赖面：实现在 _terminal 子包；本行履约原模块对 core 的 import 边（勿删）。
# 终端纪律：默认无色（NO_COLOR 一票否决），非 TTY 逐字节确定（硬契约）。
# 规范 JSON 编码单源：surface_digest 在 _terminal._surface 走 attest.canonical（审计 Z1）。
# 读点：会话状态落盘/读回在 _terminal._session_io，仍走 json_doc.loads / json_doc.load（N11）。
from core import atomic_write, attest, json_doc, storage

from ._terminal._baseline import (
    TERMINAL_BASELINE,
    _expect_hits,
    baseline_argv_issues,
    baseline_table,
    baseline_tmp_dir,
    portable_rows,
    render_baseline,
    run_baseline,
    writable_dir_probe,
)
from ._terminal._catalog import (
    families_for,
    families_without_zone,
    family_of,
    family_table,
    zone_by_key,
    zone_table,
    zones_of_family,
)
from ._terminal._completion import (
    _restore_msys_partial,
    complete,
    install_readline,
    readline_available,
    render_completions,
)
from ._terminal._const import (
    _RESET,
    _STYLES,
    _WIDE_RANGES,
    BASELINE_DEEP_MAX_MS,
    BASELINE_DEFAULT_MAX_MS,
    BASELINE_FORBIDDEN_FLAGS,
    BASELINE_TMP,
    BLOCKED_IN_SHELL,
    CONFIRM_FLAG_PAIRS,
    CONFIRM_FLAGS,
    CONFIRM_VERBS,
    PROMPT,
    QUIT_WORDS,
    SESSION_SCHEMA,
    SHELL_VERSION,
    SLASH_HELP,
    SLASH_WORDS,
    SURFACE_MODULE_HEAD,
    SURFACE_MODULE_PATH,
    SURFACE_SCHEMA,
    SURFACE_SOURCE,
    YES_WORDS,
    Intent,
)
from ._terminal._forms import (
    build_argv,
    form_action_dict,
    form_by_id,
    form_missing,
    form_pending,
    form_table,
    render_form,
    render_forms,
    zone_action_dicts,
)
from ._terminal._history import (
    append_history,
    default_history_path,
    load_history,
)
from ._terminal._parse import (
    _lev,
    _slash_intent,
    _strip_comment,
    _strip_nf,
    did_you_mean,
    example_resolves,
    needs_confirm,
    parse,
    search,
    split_args,
)
from ._terminal._render import (
    banner,
    menu,
    render_commands,
    render_map,
    render_search,
    zone_detail,
)
from ._terminal._script import (
    _statements,
    run_file,
    run_lines,
    run_script,
)
from ._terminal._session import Session, SessionOptions
from ._terminal._session_io import (
    load_session_state,
    save_session_state,
)
from ._terminal._session_run import RunOptions, run_session
from ._terminal._surface import (
    _surface_params,
    render_surface,
    render_surface_module,
    surface_digest,
    surface_module_text,
    surface_payload,
    surface_sync_issues,
)
from ._terminal._tables import (
    FAMILIES,
    FORM_EXEMPT,
    FORMS,
    ZONES,
)
from ._terminal._ui import (
    _row,
    char_width,
    clip,
    display_width,
    highlight,
    pad_to,
    resolve_color,
    style,
    term_width,
)


@dataclass(frozen=True)
class DeepCheckOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    root_flags: object = ()
    live_runner: object = None
    history_path: object = None
    session_path: object = None
    stream: object = None
    pager_ok: object = None


def deep_check(index, commands, opts: DeepCheckOptions | None = None) -> tuple:
    """活体自检 → (issues, stats)：静态面之上再核**本机环境**与**真跑一条只读命令**。

    `nf shell --verify`（静态）与 `--verify --deep`（活体）共用本函数；调用方注入
    `live_runner(argv) -> int`（真实执行一条只读命令）与 `pager_ok`（分页器是否在场）。
    判据只读、不落件：可写性用祖先目录探测，不写探针文件。
    """

    opts = opts if opts is not None else DeepCheckOptions()
    root_flags = opts.root_flags
    live_runner = opts.live_runner
    history_path = opts.history_path
    session_path = opts.session_path
    stream = opts.stream
    pager_ok = opts.pager_ok
    issues, stats = self_check(index, commands, root_flags)
    # 说明：`live_runner` 可能内部走 argparse 的 --help（SystemExit(0)）——统一在此归一，
    # 否则一次 help 就把整个深检打断（实测踩过）。
    def _live(argv):
        if live_runner is None:
            return -1
        try:
            code = live_runner(list(argv))
            return code if isinstance(code, int) else 0
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else 0
        except Exception:
            return 1

    # 活体 ①：真跑一条只读命令（覆盖「命令面真的能跑通」而不是「索引里查得到」）
    if live_runner is not None:
        code = _live(["layers", "--verify"])
        stats["live_command"] = "nf layers --verify"
        stats["live_code"] = code
        if code != 0:
            issues.append("活体自检失败：nf layers --verify 退出码 %s"
                          "（修复指引：直接跑该命令看细分；阶梯件或索引可能已漂移）" % code)
        # 活体 ①b：「最全功能」的可执行层证据——**逐条**跑 `nf <cmd> --help`（只读）
        failed = []
        for cmd in sorted({str(c) for c in (commands or [])}):
            if _live([cmd, "--help"]) != 0:
                failed.append(cmd)
        stats["help_sweep_total"] = len(set(commands or []))
        stats["help_sweep_failed"] = failed
        if failed:
            issues.append("全命令可调用性失败：%s（修复指引：逐条跑 nf <cmd> --help 定位；"
                          "命令面与实况脱钩即「最全」失守）" % "、".join(failed[:6]))
    # 活体 ②：历史 / 会话落点可写（只探测，不落件）
    for label, path in (("历史", history_path), ("会话", session_path)):
        ok, why = writable_dir_probe(path)
        stats["%s落点" % label] = why
        if not ok:
            issues.append("%s落点不可写：%s（修复指引：--history / --session 指向可写目录）"
                          % (label, why))
    # 活体 ③：环境事实（TTY / readline / 分页器）——如实报告，不当判据
    try:
        stats["tty"] = bool(stream is not None and stream.isatty())
    except Exception:      # 尽力而为：判不了就记 False（事实陈述，不影响结论）
        stats["tty"] = False
    stats["readline"] = readline_available()
    stats["pager"] = "在场" if pager_ok else ("不在场" if pager_ok is False else "未探测")
    return issues, stats




def self_check(index, commands, root_flags=(), _examples=None) -> tuple:
    """终端自检 → (issues, stats)：策展完备性 + 索引覆盖 + 菜单示例可达。

    这是**单源判据**：`nf shell --verify`（给人跑）与 verify check39（给门禁跑）调用同一函数，
    于是「终端自己说没问题」与「门禁说没问题」永远同一套语义。
    """
    issues = []
    commands = {str(c) for c in commands or []}
    index = list(index or [])
    index_paths = {str(e.get("path")) for e in index}
    index_tops = {p.split(" ")[0] for p in index_paths}

    # ① 索引：覆盖全部顶层命令 + 含二级 + 指向真命令
    missing = sorted(commands - index_tops)
    if missing:
        issues.append("索引漏命令：%s（修复指引：索引须由 argparse 面派生）"
                      % "、".join(missing[:5]))
    stray = sorted(index_tops - commands)
    if stray:
        issues.append("索引含不存在的命令：%s（修复指引：核对 _shell_command_index）"
                      % "、".join(stray[:5]))
    if len(index_paths) < 2 * max(len(commands), 1):
        issues.append("索引疑未含二级子命令：%d 条 / 顶层 %d（修复指引：索引须含 `cmd sub`）"
                      % (len(index_paths), len(commands)))
    for path in sorted(index_paths):
        if not str(path).strip():
            issues.append("索引存在空路径条目（修复指引：核对索引派生）")

    # ② 策展：能力族必须恰好分区命令集（不缺 / 不重 / 不虚）
    seen: dict[str, Any] = {}
    for fam in FAMILIES:
        if not fam.get("name") or not fam.get("summary") or not fam.get("commands"):
            issues.append("能力族 %s 缺 name/summary/commands（修复指引：补齐策展字段）"
                          % fam.get("id"))
        for cmd in fam.get("commands") or []:
            if cmd in seen:
                issues.append("命令 %s 同时归入 %s 与 %s（修复指引：一命令只归一族）"
                              % (cmd, seen[cmd], fam.get("id")))
            seen[cmd] = fam.get("id")
            if commands and cmd not in commands:
                issues.append("能力族 %s 含不存在的命令：%s（修复指引：改成真实命令）"
                              % (fam.get("id"), cmd))
    uncurated = sorted(commands - set(seen))
    if uncurated:
        issues.append("未被能力地图策展的命令：%s（修复指引：登记进 FAMILIES——"
                      "「最全功能」= 每个命令都有归属）" % "、".join(uncurated[:8]))

    # ③ 菜单：每条示例与每个动作必须指向真实命令；键须从 0 连续
    flags = {str(x) for x in root_flags or []}
    ex_total = 0
    act_total = 0
    for item in ZONES:
        for ex in item.get("examples") or ():
            ex_total += 1
            if not example_resolves(ex, commands, flags):
                issues.append("菜单指向死命令：%s（区 %s）" % (ex, item["id"]))
        for act in zone_action_dicts(item):
            act_total += 1
            first = str((act.get("argv") or [""])[0])
            if first.startswith("-"):
                continue                    # 根级旗标（如 `nf --help`）按设计放行
            if commands and first not in commands:
                issues.append("菜单动作指向死命令：nf %s（动作 %s / 区 %s）"
                              "（修复指引：动作 argv 只许用真实 CLI 动词）"
                              % (first, act.get("key"), item.get("id")))
            if not str(act.get("key") or "").strip():
                issues.append("菜单动作缺稳定 key（区 %s）" % item.get("id"))
        if not zone_action_dicts(item):
            issues.append("菜单区缺可执行动作：%s（修复指引：全屏视图的动作面板由 "
                          "zone_action_dicts 物化——显式登记 actions，或标 `forms: True` "
                          "让本区投影写盘表单）" % item.get("id"))
    keys = [z["key"] for z in ZONES]
    if keys != [str(i) for i in range(len(keys))]:
        issues.append("菜单键不连续：%s（修复指引：从 0 起连续编号）" % keys)
    fam_ids = {str(f["id"]) for f in FAMILIES}
    for z in ZONES:
        if str(z.get("family") or "") not in fam_ids:
            issues.append("菜单区 %s 的 family 不在能力族名单：%s"
                          "（修复指引：填 start/forge/shelf/verify/library/govern/integrate/meta）"
                          % (z["id"], z.get("family")))

    stats = {"commands": len(commands), "families": len(FAMILIES),
             "index_entries": len(index_paths), "examples": ex_total,
             "actions": act_total,
             "families_without_zone": families_without_zone()}
    return issues, stats
