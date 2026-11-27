"""terminal · _script（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import json

from ._const import (
    SHELL_VERSION,
)
from ._session import Session, SessionOptions


def _statements(lines) -> list:
    """把脚本/`--exec` 文本切成语句：`;` 与换行都是分隔；`#` 开头为注释。"""
    out = []
    for raw in lines:
        for piece in str(raw).split(";"):
            stmt = piece.strip()
            if stmt and not stmt.startswith("#"):
                out.append(stmt)
    return out




def run_lines(lines, runner, assume_yes: bool = False, as_json: bool = False,
              index=None) -> tuple:
    """逐条执行语句序列 → (exit_code, 文本, 记录)（`--exec` 与脚本文件共用同一条链）。

    记录逐条含 line/kind/exit/argv/out/err —— 既是 CI 判据也是机器面（`--json`）。
    """
    session = Session(runner, opts=SessionOptions(assume_yes=assume_yes, index=index))
    records = []
    worst = 0
    for raw in _statements(lines):
        rec = session.dispatch(raw)
        records.append(rec)
        worst = max(worst, rec["exit"])
        if rec["kind"] == "quit":
            break
    if as_json:
        return (worst,
                json.dumps({"kind": "nf-shell", "shell_version": SHELL_VERSION,
                            "records": records}, ensure_ascii=False, indent=2),
                records)
    out_lines = []
    for rec in records:
        out_lines.append("[nf shell] > %s" % rec["line"])
        body = (rec["out"] + rec["err"] + rec["note"]).rstrip("\n")
        if body:
            out_lines += ["  " + ln for ln in body.splitlines()]
        out_lines.append("  结果：%s（exit=%d）" % (rec["kind"], rec["exit"]))
    return worst, "\n".join(out_lines), records




def run_script(script: str, runner, assume_yes: bool = False,
               as_json: bool = False, index=None) -> tuple:
    """非交互模式：`--exec "命令1; 命令2"` 逐条执行 → (exit_code, 文本, 记录)。

    `;` 与换行都是分隔符；`#` 开头为注释（NF 命令面本身不用分号/井号，故不产生歧义）。
    """
    return run_lines(str(script).splitlines() or [str(script)], runner,
                     assume_yes=assume_yes, as_json=as_json, index=index)




def run_file(path: str, runner, assume_yes: bool = False, as_json: bool = False,
             index=None) -> tuple:
    """脚本文件模式（`nf shell --file tour.nf`）：逐行执行，`#` 注释与空行跳过。

    与 `--exec` 共用同一条执行链（同一 Session / 索引 / 闸门），差别只在语句来源——
    于是「终端里能敲的」与「脚本里能跑的」永远是同一套语义。
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    return run_lines(lines, runner, assume_yes=assume_yes, as_json=as_json, index=index)
