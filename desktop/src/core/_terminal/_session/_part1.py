"""core._session 私有实现分片 1/2（对外只经 core._session 门面导入）：SessionOptions 等"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any

from core._terminal._completion import complete, render_completions
from core._terminal._const import BLOCKED_IN_SHELL
from core._terminal._forms import form_by_id, render_form, render_forms
from core._terminal._history import load_history
from core._terminal._parse import _strip_comment, did_you_mean, needs_confirm, parse
from core._terminal._render import menu, render_commands, render_map, render_search, zone_detail
from core._terminal._tables import FORMS


@dataclass(frozen=True)
class SessionOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    assume_yes: bool = False
    index: object = None
    history_path: object = None
    color: object = False
    width: object = None
    limit: object = 0
    color_mode: object = 'never'
    stream: object = None
    session_path: object = None


class _SessionPart1:

    def __init__(self, runner, opts: SessionOptions | None = None):
        opts = opts if opts is not None else SessionOptions()
        assume_yes = opts.assume_yes
        index = opts.index
        history_path = opts.history_path
        color = opts.color
        width = opts.width
        limit = opts.limit
        color_mode = opts.color_mode
        stream = opts.stream
        session_path = opts.session_path
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
