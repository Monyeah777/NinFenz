"""terminal · _session（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from ._completion import (
    complete,
    render_completions,
)
from ._const import (
    BLOCKED_IN_SHELL,
    YES_WORDS,
)
from ._forms import (
    build_argv,
    form_by_id,
    form_missing,
    form_pending,
    render_form,
    render_forms,
)
from ._history import (
    load_history,
)
from ._parse import (
    _strip_comment,
    did_you_mean,
    needs_confirm,
    parse,
)
from ._render import (
    menu,
    render_commands,
    render_map,
    render_search,
    zone_detail,
)
from ._session_io import (
    save_session_state,
)
from ._tables import (
    FORMS,
)
from ._ui import (
    resolve_color,
)


class Session:
    """终端会话状态机：解析 → 闸门 → 分派，I/O 全部由调用方注入（可离线单测）。

    `runner(argv) -> int` 为命令执行回调（CLI 侧传 `main`）；本类只负责
    「该不该跑 / 跑完怎么记」——保证 core 层不依赖 scripts/nf.py。
    """

    def __init__(self, runner, assume_yes: bool = False, index=None,
                 history_path=None, color=False, width=None, limit=0,
                 color_mode="never", stream=None, session_path=None):
        if not callable(runner):
            raise ValueError("Session 需要可调用的 runner(argv) -> int；"
                             "请传入 scripts/nf.py 的 main（终端不自己执行命令）")
        self._runner = runner
        self.assume_yes = bool(assume_yes)
        self.history: list[dict[str, Any]] = []   # 逐条记录 dict（line/kind/exit/argv/out/err/note）
        self.last_zone = ""
        self.quit = False
        # 命令面索引（由 CLI 侧从 argparse 面派生）：用于检索 / 列命令 / 拼错建议。
        # 缺省 None = 不启用预检（core 单测可完全离线，不依赖 CLI 面）。
        self.index = list(index or [])
        self._tops = {str(e.get("path")).split(" ")[0] for e in self.index}
        # 历史文件（交互态用；None = 不记录）。`--exec` / `--file` 一律不写，保持确定性。
        self.history_path = str(history_path) if history_path else None
        # 视图设置（`/set` 可改）：颜色 / 宽度 / 列表限长。默认无色——非 TTY 逐字节确定。
        self.color = bool(color)
        self.color_mode = str(color_mode or "never")
        self.width = width
        self.limit = int(limit or 0)
        self.stream = stream
        # 会话状态（`--session <file>`）：视图设置 + 上次分区；None = 不持久化
        self.session_path = str(session_path) if session_path else None
        self.active_form: dict[str, Any] | None = None   # {"form": …, "answers": {…}} —— 写盘表单进行中
        # 会话内命令记录（供 `!!` / `!n` / `!前缀` 重放；不含 replay 自身，避免自指）
        self.commands: list[Any] = []   # [(原始行, …)] 只记「能重放」的类别

    def invoke(self, argv: list) -> tuple:
        """执行一条命令 → (exit_code, stdout, stderr)；捕获输出以便落档与比对。

        三类非返回式退出都在此归一，保证会话不被打断：
        `SystemExit`（argparse 用法错误 / --version / help 动作）、`KeyboardInterrupt`（130）、
        未预期异常（与 CLI 顶层同口径：一句错误 + 退出 1，NF_DEBUG=1 时透出堆栈）。
        """
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with redirect_stdout(out), redirect_stderr(err):
            try:
                result = self._runner(list(argv))
                if isinstance(result, int):
                    code = result
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
            except KeyboardInterrupt:
                code = 130
            except Exception as exc:  # 与 CLI 顶层同口径：一句错误 + 退出 1
                print("  ✗ 内部错误：%s（重跑 NF_DEBUG=1 看堆栈）" % exc, file=sys.stderr)
                code = 1
        return code, out.getvalue(), err.getvalue()

    #: 只读视图类意图（不执行外部命令，只渲染）
    _VIEW_KINDS = ("menu", "zone", "search", "commands", "map", "complete", "replay-list")

    def dispatch(self, line: str, confirmed: bool = False) -> dict:
        """处理一行 → 记录 dict（line/kind/exit/argv/out/err/note）。

        `confirmed=True` 表示调用方已就该行取得使用者放行（交互追问拿到 yes）——写入类
        命令据此放行；`assume_yes`（CLI 的 --yes）是整场会话的显式放行开关。
        """
        early = self._form_preempt(line)
        if early is not None:
            return early
        intent = parse(line)
        rec = {"line": intent.raw, "kind": intent.kind, "exit": 0,
               "argv": [], "out": "", "err": "", "note": ""}
        self._handlers().get(intent.kind, self._run)(intent, rec, confirmed)
        self._record(intent, rec)
        return rec

    def _form_preempt(self, line: str):
        """表单进行中：除 `/cancel` 与 quit 外，输入一律当作**回答**（`k=v` 或按顺序填）。"""
        if self.active_form is None:
            return None
        early = self._handle_form_line(_strip_comment(str(line)).strip())
        if early is not None:
            self.history.append(early)
        return early

    def _record(self, intent, rec: dict) -> None:
        """落历史；能重放的类别记入 `commands`（供 `!!`/`!n`/`!前缀`）。"""
        self.history.append(rec)
        if rec["kind"] in self.REPLAYABLE_KINDS and str(intent.raw).strip():
            self.commands.append(str(intent.raw).strip())

    def _handlers(self) -> dict:
        """意图 → 处理器（**查表**替代 if/elif 链：新增意图只加一行，不改控制流）。"""
        view = self._view
        return {
            "empty": self._h_empty, "quit": self._h_quit, "help": self._h_help,
            "set": self._set_cmd,
            "menu": view, "zone": view, "search": view, "commands": view,
            "map": view, "complete": view, "replay-list": view,
            "form": self._form_cmd, "cancel": self._form_cmd,
            "replay": self._replay, "history": self._history_cmd,
            "unknown": self._unknown,
        }

    def _h_empty(self, intent, rec: dict, confirmed: bool) -> None:
        pass

    def _h_quit(self, intent, rec: dict, confirmed: bool) -> None:
        self.quit = True

    def _h_help(self, intent, rec: dict, confirmed: bool) -> None:
        code, out, err = self.invoke(["help"] + ([intent.payload] if intent.payload else []))
        rec.update(exit=code, out=out, err=err)

    def _view(self, intent, rec: dict, confirmed: bool = False) -> None:
        """只读视图：菜单/分区/检索/命令表/地图/补全/重放清单（不触外部执行）。"""
        kind = intent.kind
        if kind == "menu":
            rec["note"] = menu(self.width, self.color)
        elif kind == "zone":
            self.last_zone = intent.payload
            rec["note"] = zone_detail(intent.payload, self.color)
        elif kind == "search":
            text, hits = render_search(self.index, intent.payload,
                                       width=self.width, color=self.color)
            rec["note"] = text
            rec["exit"] = 0 if hits else 2
        elif kind == "commands":
            rec["note"] = render_commands(self.index, intent.payload, limit=self.limit,
                                          width=self.width, color=self.color)
        elif kind == "map":
            rec["note"] = render_map(intent.payload, self.width, self.color)
        elif kind == "complete":
            cands = complete(intent.payload, self.index)
            rec["note"] = render_completions(intent.payload, cands,
                                             width=self.width, color=self.color)
            rec["exit"] = 0 if cands else 2
        else:  # replay-list
            rec["note"] = self.render_replay_list()

    def _form_cmd(self, intent, rec: dict, confirmed: bool = False) -> None:
        if intent.kind == "cancel":
            self._cancel_form(rec)
        elif not intent.payload:
            rec["note"] = render_forms("", self.width, self.color)
        else:
            self._open_form(intent.payload, rec)

    def _open_form(self, fid: str, rec: dict) -> None:
        form = form_by_id(fid)
        if form is None:
            rec.update(exit=2, note="未识别的表单：%s（可用：%s；/form 列全部）"
                       % (fid, "、".join(str(f["id"]) for f in FORMS)))
            return
        self.active_form = {"form": form, "answers": {}}
        rec["note"] = render_form(form, {}, self.color)

    def _cancel_form(self, rec: dict) -> None:
        if self.active_form:
            fid = self.active_form["form"]["id"]
            self.active_form = None
            rec["note"] = "已中止表单 %s（未执行任何写盘动作）" % fid
        else:
            rec.update(exit=2, note="当前没有进行中的表单（/form 列全部表单）")

    def _replay(self, intent, rec: dict, confirmed: bool) -> None:
        ok, payload = self.resolve_replay(intent.payload)
        if not ok:
            rec.update(exit=2, note=str(payload))
            return
        inner = self.dispatch(payload, confirmed=confirmed)
        rec.update(kind="replay", argv=inner["argv"], exit=inner["exit"],
                   out=inner["out"], err=inner["err"])
        rec["note"] = "重放：%s%s" % (payload, ("\n" + inner["note"])
                                     if inner["note"] else "")

    def _history_cmd(self, intent, rec: dict, confirmed: bool = False) -> None:
        rows = load_history(self.history_path, limit=200) if self.history_path else []
        n = int(str(intent.payload).strip()) if str(intent.payload).strip().isdigit() else 0
        shown = rows[-n:] if n else rows
        head = ("== 历史（%d 条%s）==" % (len(rows), "（最近 %d 条）" % n if n else ""))
        if not self.history_path:
            rec["note"] = ("未启用历史记录（交互态加 --history <文件> 或去掉 --no-history；"
                           "`--exec`/`--file` 不写历史以保持确定性）")
            rec["exit"] = 2
        elif not shown:
            rec["note"] = head + "\n  （暂无记录）"
        else:
            rec["note"] = "\n".join([head] + ["  %3d  %s" % (i + 1, ln)
                                              for i, ln in enumerate(shown)])

    def _unknown(self, intent, rec: dict, confirmed: bool = False) -> None:
        rec.update(exit=2, note=("未识别：%s（可用：数字 0-7 看菜单 · /menu · "
                                 "/map · /find <词> · /commands · /help · quit · "
                                 "或直接输入 nf 命令）" % intent.raw))

    def _set_cmd(self, intent, rec: dict, confirmed: bool = False) -> None:
        text, ok = self._apply_settings(intent.payload)
        rec["note"] = text
        rec["exit"] = 0 if ok else 2

    def _auto_complete(self, argv: list) -> list:
        """效率：**唯一前缀**自动补全（`nf stat` → `nf stats`）——只在恰好一个候选时生效，
        有歧义一律不猜（照旧走未知命令分支给候选）。"""
        if not (argv and self._tops and argv[0] not in self._tops
                and not str(argv[0]).startswith("-")):
            return argv
        cands = sorted(c for c in self._tops if c.startswith(argv[0]))
        return [cands[0]] + argv[1:] if len(cands) == 1 else argv

    def _run_block(self, argv: list, confirmed: bool) -> str:
        """run 分支的拦截面 → 空串表示放行；否则为拒跑说明。"""
        if not argv:
            return ""
        blocked = BLOCKED_IN_SHELL.get(argv[0])
        unknown = (self._tops and argv[0] not in self._tops
                   and argv[0] not in ("help", "--version", "--help", "-h"))
        if unknown:
            near = did_you_mean(argv[0], sorted(self._tops))
            return ("未知命令：%s%s（修复指引：/find <词> 检索命令面，或 /commands 列全部；"
                    "直接跑 `nf --help` 看总览）"
                    % (argv[0], "；你是不是想找：%s" % "、".join(near) if near else ""))
        if blocked:
            return blocked
        if needs_confirm(argv) and not (self.assume_yes or confirmed):
            return ("%s 属于写入/不可逆面——须显式确认：交互会话里输入 yes 放行，"
                    "非交互跑时加 --yes（终端不替使用者拍板）。" % " ".join(argv))
        return ""

    def _run(self, intent, rec: dict, confirmed: bool) -> None:
        argv = list(intent.payload)
        rec["argv"] = argv
        completed = self._auto_complete(argv)
        if completed != argv:
            rec["note"] = "唯一前缀补全：%s → %s" % (argv[0], completed[0])
            argv = completed
            rec["argv"] = argv
        note = self._run_block(argv, confirmed)
        if note:
            rec.update(exit=2, note=note)
            return
        code, out, err = self.invoke(argv)
        rec.update(exit=code, out=out, err=err)

    def _apply_settings(self, payload: str):
        """`/set [k=v …]` → (文本, ok)：改视图设置；成功且开了会话文件时顺手落盘。"""
        text, ok = self._set_impl(payload)
        if ok and self.session_path:
            save_session_state(self.session_path, self)
        return text, ok

    #: 可重放的输入类别（表单追问的中间回答不算——重放它没有意义）
    REPLAYABLE_KINDS = ("run", "set", "commands", "search", "map", "complete", "history")

    def resolve_replay(self, spec: str):
        """解析重放说明 → `(ok, 命令行 | 给用户的说明)`。

        形态：`!!`（上一条）、`!n`（第 n 条，1 起）、`!前缀`（最近一条以该前缀开头）。
        """
        spec = str(spec or "").strip()
        if not self.commands:
            return False, "本次会话还没有可重放的命令（先跑一条；/replay 看清单）"
        if not spec:
            return True, self.commands[-1]
        if spec.isdigit():
            n = int(spec)
            if 1 <= n <= len(self.commands):
                return True, self.commands[n - 1]
            return False, ("重放序号越界：!%s（本次会话共 %d 条；/replay 看清单）"
                           % (spec, len(self.commands)))
        for line in reversed(self.commands):
            if line.startswith(spec):
                return True, line
        return False, ("没有以「%s」开头的历史命令（/replay 看清单；或直接输入该命令）" % spec)

    def render_replay_list(self) -> str:
        """列出可重放命令（编号与 `!n` 一致）。"""
        if not self.commands:
            return "（本次会话还没有可重放的命令）"
        lines = ["== 本次会话命令（%d 条 · 重放：!! / !n / !前缀）==" % len(self.commands)]
        lines += ["  %3d  %s" % (i + 1, ln) for i, ln in enumerate(self.commands)]
        return "\n".join(lines)

    def _handle_form_line(self, text: str):
        """表单进行中的一行输入 → 记录 dict（除 `/cancel`/quit 外都算回答）。"""
        active = self.active_form
        form = active["form"] if active else {}
        answers = active["answers"] if active else {}
        low = text.lower()
        rec = {"line": text, "kind": "form", "exit": 0, "argv": [], "out": "",
               "err": "", "note": ""}
        if text.startswith("/cancel") or low in ("cancel", "取消"):
            self.active_form = None
            rec["note"] = "已中止表单 %s（未执行任何写盘动作）" % form["id"]
            return rec
        if text.startswith("/") and not text.startswith("/form"):
            return None                    # 其它斜杠命令照常走 parse（表单保持挂起）
        if not form_pending(form, answers) and not form_missing(form, answers):
            if low in YES_WORDS:
                try:
                    argv = build_argv(form, answers)
                except ValueError as exc:
                    rec.update(exit=2, note=str(exc))
                    return rec
                self.active_form = None
                code, out, err = self.invoke(argv)
                rec.update(kind="run", argv=argv, exit=code, out=out, err=err)
                return rec
            self.active_form = None
            rec["note"] = ("已取消（未执行）：表单 %s 未提交（重新 /form %s 可再填）"
                           % (form["id"], form["id"]))
            return rec
        return self._answer_form(text)

    def _answer_form(self, text: str):
        """把一行记进表单：`k=v` 指定键，否则按 steps 顺序填下一个未 settle 项。

        空行 = **明确跳过**当前项（记空串），于是可选项也会被逐项问到、而不是被静默略过。
        """
        active = self.active_form
        form = active["form"] if active else {}
        answers = active["answers"] if active else {}
        steps = list(form.get("steps") or [])
        key, _, val = text.partition("=")
        key = key.strip()
        if val and any(st["key"] == key for st in steps):
            answers[key] = val.strip()
        else:
            pend = [st for st in steps if st["key"] not in answers]
            if not pend:
                return {"line": text, "kind": "form", "exit": 0, "argv": [],
                        "out": "", "err": "",
                        "note": "表单已填完：回答 yes 执行 / no 取消"}
            answers[pend[0]["key"]] = str(text or "").strip()
        return {"line": text, "kind": "form", "exit": 0, "argv": [], "out": "",
                "err": "", "note": render_form(form, answers, self.color)}

    def _set_impl(self, payload: str):
        """`/set` 的实现（无副作用；落盘由 `_apply_settings` 负责）。"""
        bad = []
        for pair in str(payload or "").split():
            key, _, value = pair.partition("=")
            key, value = key.strip().lower(), value.strip()
            if key == "color":
                if value not in ("auto", "always", "never"):
                    bad.append(pair)
                    continue
                self.color_mode = value
                self.color = resolve_color(value, self.stream)
            elif key == "width":
                try:
                    self.width = max(40, int(value)) if value else None
                except ValueError:
                    bad.append(pair)
            elif key == "limit":
                try:
                    self.limit = max(0, int(value))
                except ValueError:
                    bad.append(pair)
            elif value == "":
                pass
            else:
                bad.append(pair)
        lines = ["== 终端设置 ==",
                 "  color = %s（实际着色：%s；`NO_COLOR` 一票否决 auto）"
                 % (self.color_mode, "开" if self.color else "关"),
                 "  width = %s（默认取 COLUMNS，否则 100）" % (self.width or "auto"),
                 "  limit = %s（列表限长；0 = 全部）" % self.limit,
                 "  历史 = %s" % (self.history_path or "关闭"),
                 "  会话 = %s" % (self.session_path or "未持久化（--session <文件> 开启）"),
                 "  用法：/set color=never width=120 limit=40（可只给其中几项）"]
        if bad:
            lines.append("  [FAIL] 无法识别：%s（可用键：color / width / limit）" % "、".join(bad))
        return "\n".join(lines), not bad

    def handle(self, line: str) -> tuple:
        """薄封装：处理一行 → (kind, exit_code, 要打印的文本)。"""
        rec = self.dispatch(line)
        return (rec["kind"], rec["exit"],
                (rec["out"] + rec["err"] + rec["note"]).rstrip("\n"))
