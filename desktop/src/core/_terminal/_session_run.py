"""terminal · _session_run（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

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
from ._session import (
    Session,
)
from ._session_io import (
    load_session_state,
    save_session_state,
)


def run_session(runner, stdin, stdout, assume_yes: bool = False,
                show_banner: bool = True, baseline: str = "", index=None,
                history_path=None, color=False, width=None, limit=0,
                color_mode="never", session_path=None) -> int:
    r"""交互会话主循环：读一行 → 分派 → 打印 → 直到 quit / EOF。

    写入类命令在交互态**就地追问**（读到 yes 才放行本次）；非交互态仍须 `--yes`。
    返回 0（正常结束）或非 0（会话中有命令失败）——供 CI/脚本判红。

    健壮性（对标顶尖 CLI 终端）：Ctrl-C 只取消当前行、不杀会话；行尾 `\` 续行（多行命令）；
    行尾 Tab = 补全候选；`history_path` 启用跨会话历史（`--exec`/`--file` 不写，保确定性）。
    """
    state, warn = load_session_state(session_path)
    session = Session(runner, assume_yes=assume_yes, index=index,
                      history_path=history_path, color=color, width=width,
                      limit=limit, color_mode=color_mode, stream=stdout,
                      session_path=session_path)
    session.last_zone = str(state.get("last_zone") or "")
    if show_banner:
        stdout.write(banner(baseline, color) + "\n")
        if warn:
            stdout.write("  [WARN] %s\n" % warn)
        stdout.flush()
    worst = 0
    while not session.quit:
        stdout.write(PROMPT)
        stdout.flush()
        try:
            line = stdin.readline()
        except KeyboardInterrupt:      # Ctrl-C 取消当前输入，会话继续（不是退出码 130）
            stdout.write("\n  （已取消当前输入——会话继续；quit 退出）\n")
            stdout.flush()
            continue
        if line == "":                      # EOF（管道/重定向结束）
            stdout.write("\n")
            break
        # 行尾 Tab = 补全（零依赖的「Tab 体感」：任何平台都能用；readline 可用时另有接管）
        if line.rstrip("\n").endswith("\t"):
            partial = _strip_comment(line).rstrip("\n").rstrip("\t")
            stdout.write(render_completions(partial, complete(partial, session.index))
                         + "\n")
            stdout.flush()
            continue
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
        intent = parse(line)
        confirmed = False
        # 重放行要先解析出目标，写盘闸门才对**真正要跑的那条**生效（fail-closed 不变）
        _need = needs_confirm(intent.payload) if intent.kind == "run" else False
        if intent.kind == "replay" and intent.payload:
            _ok, _resolved = session.resolve_replay(intent.payload)
            if _ok:
                _target = parse(_resolved)
                if _target.kind == "run":
                    _need = needs_confirm(_target.payload)
        if _need and not session.assume_yes:
            stdout.write("  该命令会写盘：%s\n  确认执行？(yes/no) " % intent.raw)
            stdout.flush()
            confirmed = stdin.readline().strip().lower() in YES_WORDS
            if not confirmed:
                stdout.write("  已取消（未执行）。\n")
                stdout.flush()
                session.history.append({"line": intent.raw, "kind": "blocked",
                                        "exit": 2, "argv": list(intent.payload),
                                        "out": "", "err": "", "note": ""})
                worst = max(worst, 2)
                continue
        rec = session.dispatch(line, confirmed=confirmed)
        text = (rec["out"] + rec["err"] + rec["note"]).rstrip("\n")
        if text:
            stdout.write(text + "\n")
        stdout.flush()
        worst = max(worst, rec["exit"])
        # 只记「真执行过的东西」：空行不入，quit/exit 也不入（否则每条会话都多一行噪音）
        if session.history_path and rec["kind"] not in ("empty", "quit"):
            append_history(session.history_path, rec["line"])
    if session.session_path:
        save_session_state(session.session_path, session)
    return worst
