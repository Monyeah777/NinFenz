"""terminal · _session_run（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from dataclasses import dataclass

from ._completion import (
    complete,
    render_completions,
)
from ._const import (
    PROMPT,
    YES_WORDS,
)
from ._history import (
    append_history,
)
from ._parse import (
    _strip_comment,
    needs_confirm,
    parse,
)
from ._render import (
    banner,
)
from ._session import Session, SessionOptions
from ._session_io import (
    load_session_state,
    save_session_state,
)


@dataclass(frozen=True)
class RunOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    assume_yes: bool = False
    show_banner: bool = True
    baseline: str = ''
    index: object = None
    history_path: object = None
    color: object = False
    width: object = None
    limit: object = 0
    color_mode: object = 'never'
    session_path: object = None


def run_session(runner, stdin, stdout, opts: RunOptions | None = None) -> int:
    r"""交互会话主循环：读一行 → 分派 → 打印 → 直到 quit / EOF。

    写入类命令在交互态**就地追问**（读到 yes 才放行本次）；非交互态仍须 `--yes`。
    返回 0（正常结束）或非 0（会话中有命令失败）——供 CI/脚本判红。

    健壮性（对标顶尖 CLI 终端）：Ctrl-C 只取消当前行、不杀会话；行尾 `\` 续行（多行命令）；
    行尾 Tab = 补全候选；`history_path` 启用跨会话历史（`--exec`/`--file` 不写，保确定性）。
    """
    opts = opts if opts is not None else RunOptions()
    session, warn = _open_session(opts, runner, stdout)
    if opts.show_banner:
        _print_banner(stdout, opts.baseline, opts.color, warn)
    worst = 0
    while not session.quit:
        line = _read_command(stdin, stdout, session)
        if line is None:                      # EOF（管道/重定向结束）
            break
        if line == "":
            continue
        worst = _handle_line(line, session, stdin, stdout, worst)
    if session.session_path:
        save_session_state(session.session_path, session)
    return worst


def _open_session(opts: RunOptions, runner, stdout):
    """会话对象 + 会话状态载入的 warning。"""
    state, warn = load_session_state(opts.session_path)
    session = Session(
        runner,
        opts=SessionOptions(
            assume_yes=opts.assume_yes,
            index=opts.index,
            history_path=opts.history_path,
            color=opts.color,
            width=opts.width,
            limit=opts.limit,
            color_mode=opts.color_mode,
            stream=stdout,
            session_path=opts.session_path,
        ),
    )
    session.last_zone = str(state.get("last_zone") or "")
    return session, warn


def _print_banner(stdout, baseline, color, warn: str) -> None:
    """开场横幅（可带会话状态 warning）。"""
    stdout.write(banner(baseline, color) + "\n")
    if warn:
        stdout.write("  [WARN] %s\n" % warn)
    stdout.flush()


def _read_command(stdin, stdout, session):
    r"""读一行命令（含 Tab 补全与 `\` 续行）→ 行文本；None=EOF；空串=本行无操作。"""
    stdout.write(PROMPT)
    stdout.flush()
    try:
        line = stdin.readline()
    except KeyboardInterrupt:      # Ctrl-C 取消当前输入，会话继续（不是退出码 130）
        stdout.write("\n  （已取消当前输入——会话继续；quit 退出）\n")
        stdout.flush()
        return ""
    if line == "":
        stdout.write("\n")
        return None
    # 行尾 Tab = 补全（零依赖的「Tab 体感」：任何平台都能用；readline 可用时另有接管）
    if line.rstrip("\n").endswith("\t"):
        partial = _strip_comment(line).rstrip("\n").rstrip("\t")
        stdout.write(render_completions(partial, complete(partial, session.index)) + "\n")
        stdout.flush()
        return ""
    # 行尾 `\` 续行：长命令/多行输入（续行提示符为 `… `）
    while line.rstrip("\n").endswith("\\"):
        line = line.rstrip("\n")[:-1] + " "
        stdout.write("... ")
        stdout.flush()
        try:
            nxt = stdin.readline()
        except KeyboardInterrupt:
            nxt = ""
        if nxt == "":
            break
        line += nxt
    return line


def _handle_line(line: str, session, stdin, stdout, worst: int) -> int:
    """处理一行：写盘闸门追问 → 派发 → 记账（返回新的 worst）。"""
    intent = parse(line)
    need = _needs_confirm(intent, session) if intent.kind in ("run", "replay") else False
    if need and not session.assume_yes:
        if not _ask_confirm(intent, stdin, stdout):
            _record_blocked(intent, session, stdout)
            return max(worst, 2)
        return _dispatch_line(line, session, stdout, worst, True)
    return _dispatch_line(line, session, stdout, worst, False)


def _needs_confirm(intent, session) -> bool:
    """写盘闸门：run 直判；replay 先解析出真正要跑的那条再判（fail-closed 不变）。"""
    need = needs_confirm(intent.payload) if intent.kind == "run" else False
    if intent.kind != "replay" or not intent.payload:
        return need
    ok, resolved = session.resolve_replay(intent.payload)
    if ok and parse(resolved).kind == "run":
        return needs_confirm(parse(resolved).payload)
    return need


def _ask_confirm(intent, stdin, stdout) -> bool:
    """交互态就地追问是否执行。"""
    stdout.write("  该命令会写盘：%s\n  确认执行？(yes/no) " % intent.raw)
    stdout.flush()
    return stdin.readline().strip().lower() in YES_WORDS


def _record_blocked(intent, session, stdout) -> None:
    """取消的写盘命令入 history（exit=2）。"""
    stdout.write("  已取消（未执行）。\n")
    stdout.flush()
    session.history.append({"line": intent.raw, "kind": "blocked",
                            "exit": 2, "argv": list(intent.payload),
                            "out": "", "err": "", "note": ""})


def _dispatch_line(line: str, session, stdout, worst: int, confirmed: bool) -> int:
    """派发一行并打印/记账。"""
    rec = session.dispatch(line, confirmed=confirmed)
    text = (rec["out"] + rec["err"] + rec["note"]).rstrip("\n")
    if text:
        stdout.write(text + "\n")
    stdout.flush()
    worst = max(worst, rec["exit"])
    # 只记「真执行过的东西」：空行不入，quit/exit 也不入（否则每条会话都多一行噪音）
    if session.history_path and rec["kind"] not in ("empty", "quit"):
        append_history(session.history_path, rec["line"])
    return worst
