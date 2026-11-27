"""core._session 私有实现分片 2/2（对外只经 core._session 门面导入）：Session"""

from __future__ import annotations

from core._terminal._const import YES_WORDS
from core._terminal._forms import build_argv, form_missing, form_pending, render_form
from core._terminal._session_io import save_session_state
from core._terminal._ui import resolve_color

from ._part1 import _SessionPart1


class Session(_SessionPart1):
    """终端会话状态机：解析 → 闸门 → 分派，I/O 全部由调用方注入（可离线单测）。

    `runner(argv) -> int` 为命令执行回调（CLI 侧传 `main`）；本类只负责
    「该不该跑 / 跑完怎么记」——保证 core 层不依赖 scripts/nf.py。
    """

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
