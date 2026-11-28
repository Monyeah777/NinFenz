"""终端自检判据（静态策展 + 活体环境）——从 terminal 门面拆出的实现面。

拆分动机（C-001 文件 >400 行）：terminal.py 只保留门面 re-export；自检判据的具体实现
（索引/策展/菜单/活体命令/可写性/TTY 事实）落到本私有模块，公开 API 与判据语义不变。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._baseline import writable_dir_probe
from ._catalog import families_without_zone
from ._completion import readline_available
from ._forms import zone_action_dicts
from ._parse import example_resolves

@dataclass(frozen=True)
class DeepCheckOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    root_flags: object = ()
    live_runner: object = None
    history_path: object = None
    session_path: object = None
    stream: object = None
    pager_ok: object = None


def _facade():
    """门面模块（tests 会按 core.terminal 打补丁，故运行时动态取）。"""
    from core import terminal
    return terminal


def _families():
    """能力族表（运行时从门面取，保持 tests 的 patch 语义）。"""
    return _facade().FAMILIES


def _zones():
    """菜单区表（运行时从门面取，保持 tests 的 patch 语义）。"""
    return _facade().ZONES


def deep_check(index, commands, opts: DeepCheckOptions | None = None) -> tuple:
    """活体自检 → (issues, stats)：静态面之上再核**本机环境**与**真跑一条只读命令**。

    本函数是 `nf shell --verify`（静态）与 `--verify --deep`（活体）共用入口；调用方注入
    `live_runner(argv) -> int`（真实执行一条只读命令）与 `pager_ok`（分页器是否在场）。
    判据只读、不落件：可写性用祖先目录探测，不写探针文件。
    """
    opts = opts if opts is not None else DeepCheckOptions()
    root_flags = opts.root_flags
    history_path = opts.history_path
    session_path = opts.session_path
    stream = opts.stream
    pager_ok = opts.pager_ok
    issues, stats = self_check(index, commands, root_flags)
    # 说明：`live_runner` 可能内部走 argparse 的 --help（SystemExit(0)）——统一在 _make_live
    # 里归一，否则一次 help 就把整个深检打断（实测踩过）。
    if opts.live_runner is not None:
        _live_checks(_make_live(opts.live_runner), commands, issues, stats)
    # 活体 ②：历史 / 会话落点可写（只探测，不落件）
    issues += _probe_issues(history_path, session_path, stats)
    # 活体 ③：环境事实（TTY / readline / 分页器）——如实报告，不当判据
    stats["tty"] = _tty(stream)
    stats["readline"] = readline_available()
    stats["pager"] = "在场" if pager_ok else ("不在场" if pager_ok is False else "未探测")
    return issues, stats


def _make_live(live_runner):
    """把注入的 live_runner 归一成 `_live(argv) -> int`（SystemExit/异常不外溢）。"""
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
    return _live


def _live_checks(_live, commands, issues: list, stats: dict) -> None:
    """活体 ①：真跑一条只读命令 + 逐条 `--help` 可调用性。"""
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


def _probe_issues(history_path, session_path, stats: dict) -> list:
    """历史 / 会话落点可写性探测 → issue（判据只读，不落件）。"""
    issues = []
    for label, path in (("历史", history_path), ("会话", session_path)):
        ok, why = writable_dir_probe(path)
        stats["%s落点" % label] = why
        if not ok:
            issues.append("%s落点不可写：%s（修复指引：--history / --session 指向可写目录）"
                          % (label, why))
    return issues


def _tty(stream) -> bool:
    """TTY 事实（判不了记 False，不做判据）。"""
    try:
        return bool(stream is not None and stream.isatty())
    except Exception:      # 尽力而为：判不了就记 False（事实陈述，不影响结论）
        return False




def self_check(index, commands, root_flags=(), _examples=None) -> tuple:
    """终端自检 → (issues, stats)：策展完备性 + 索引覆盖 + 菜单示例可达。

    这是**单源判据**：`nf shell --verify`（给人跑）与 verify check39（给门禁跑）调用同一函数，
    于是「终端自己说没问题」与「门禁说没问题」永远同一套语义。
    """
    commands = {str(c) for c in commands or []}
    index_paths, index_tops = _index_sets(index)
    issues = _index_issues(commands, index_paths, index_tops)
    curation_issues, _seen = _curation_issues(commands)
    issues += curation_issues
    flags = {str(x) for x in root_flags or []}
    menu_issues, ex_total, act_total = _menu_issues(commands, flags)
    issues += menu_issues
    issues += _zone_key_issues() + _zone_family_issues()
    stats = {"commands": len(commands), "families": len(_families()),
             "index_entries": len(index_paths), "examples": ex_total,
             "actions": act_total,
             "families_without_zone": families_without_zone()}
    return issues, stats


def _index_sets(index) -> tuple:
    """索引路径集与顶层命令集。"""
    index_paths = {str(e.get("path")) for e in list(index or [])}
    index_tops = {p.split(" ")[0] for p in index_paths}
    return index_paths, index_tops


def _index_issues(commands: set, index_paths: set, index_tops: set) -> list:
    """① 索引：覆盖全部顶层命令 + 含二级 + 指向真命令。"""
    issues = []
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
    return issues


def _curation_issues(commands: set) -> tuple:
    """② 策展：能力族必须恰好分区命令集（不缺 / 不重 / 不虚）。"""
    seen: dict[str, Any] = {}
    issues = []
    for fam in _families():
        issues += _family_field_issues(fam)
        issues += _family_cmd_issues(fam, commands, seen)
    uncurated = sorted(commands - set(seen))
    if uncurated:
        issues.append("未被能力地图策展的命令：%s（修复指引：登记进 _families()——"
                      "「最全功能」= 每个命令都有归属）" % "、".join(uncurated[:8]))
    return issues, seen


def _family_field_issues(fam: dict) -> list:
    """能力族的 name/summary/commands 必填。"""
    if not fam.get("name") or not fam.get("summary") or not fam.get("commands"):
        return ["能力族 %s 缺 name/summary/commands（修复指引：补齐策展字段）"
                % fam.get("id")]
    return []


def _family_cmd_issues(fam: dict, commands: set, seen: dict) -> list:
    """单个能力族的命令归属判定。"""
    issues = []
    for cmd in fam.get("commands") or []:
        if cmd in seen:
            issues.append("命令 %s 同时归入 %s 与 %s（修复指引：一命令只归一族）"
                          % (cmd, seen[cmd], fam.get("id")))
        seen[cmd] = fam.get("id")
        if commands and cmd not in commands:
            issues.append("能力族 %s 含不存在的命令：%s（修复指引：改成真实命令）"
                          % (fam.get("id"), cmd))
    return issues


def _menu_issues(commands: set, flags: set) -> tuple:
    """③ 菜单：每条示例与每个动作必须指向真实命令。"""
    issues = []
    ex_total = 0
    act_total = 0
    for item in _zones():
        ex_issues, n_ex = _zone_example_issues(item, commands, flags)
        act_issues, n_act = _zone_action_issues(item, commands)
        issues += ex_issues + act_issues
        ex_total += n_ex
        act_total += n_act
        if not zone_action_dicts(item):
            issues.append("菜单区缺可执行动作：%s（修复指引：全屏视图的动作面板由 "
                          "zone_action_dicts 物化——显式登记 actions，或标 `forms: True` "
                          "让本区投影写盘表单）" % item.get("id"))
    return issues, ex_total, act_total


def _zone_example_issues(item: dict, commands: set, flags: set) -> tuple:
    """单区的示例命令可达性。"""
    issues = []
    examples = item.get("examples") or ()
    for ex in examples:
        if not example_resolves(ex, commands, flags):
            issues.append("菜单指向死命令：%s（区 %s）" % (ex, item["id"]))
    return issues, len(examples)


def _zone_action_issues(item: dict, commands: set) -> tuple:
    """单区的动作命令/key 判定。"""
    issues = []
    acts = zone_action_dicts(item)
    for act in acts:
        first = str((act.get("argv") or [""])[0])
        if first.startswith("-"):
            continue                    # 根级旗标（如 `nf --help`）按设计放行
        if commands and first not in commands:
            issues.append("菜单动作指向死命令：nf %s（动作 %s / 区 %s）"
                          "（修复指引：动作 argv 只许用真实 CLI 动词）"
                          % (first, act.get("key"), item.get("id")))
        if not str(act.get("key") or "").strip():
            issues.append("菜单动作缺稳定 key（区 %s）" % item.get("id"))
    return issues, len(acts)


def _zone_key_issues() -> list:
    """菜单键须从 0 连续。"""
    issues = []
    keys = [z["key"] for z in _zones()]
    if keys != [str(i) for i in range(len(keys))]:
        issues.append("菜单键不连续：%s（修复指引：从 0 起连续编号）" % keys)
    return issues


def _zone_family_issues() -> list:
    """菜单区的 family 必须在能力族名单。"""
    issues = []
    fam_ids = {str(f["id"]) for f in _families()}
    for z in _zones():
        if str(z.get("family") or "") not in fam_ids:
            issues.append("菜单区 %s 的 family 不在能力族名单：%s"
                          "（修复指引：填 start/forge/shelf/verify/library/govern/integrate/meta）"
                          % (z["id"], z.get("family")))
    return issues
