"""terminal · _baseline（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
import tempfile
import time
from typing import Any

from ._const import (
    BASELINE_DEEP_MAX_MS,
    BASELINE_DEFAULT_MAX_MS,
    BASELINE_FORBIDDEN_FLAGS,
    BASELINE_TMP,
)
from ._ui import (
    pad_to,
    style,
)


def baseline_tmp_dir() -> str:
    """基线探针目录：`<系统临时目录>/nf_baseline_<pid>`（按进程唯一；仓库之外）。"""
    path = os.path.join(tempfile.gettempdir(), "nf_baseline_%d" % os.getpid())
    os.makedirs(path, exist_ok=True)
    return path




TERMINAL_BASELINE: tuple[dict[str, Any], ...] = (
    {"id": "discover-commands", "name": "命令面可达（列出全部命令）",
     "argv": ("shell", "--commands", "--no-banner"), "expect": "nf 命令面"},
    {"id": "discover-search", "name": "关键词检索（按用途找命令）",
     "argv": ("shell", "--search", "装配", "--no-banner"), "expect": "命令检索"},
    {"id": "discover-map", "name": "能力地图（全命令按族策展）",
     "argv": ("shell", "--map", "--no-banner"), "expect": "能力地图"},
    {"id": "typo-suggest", "name": "拼错建议（不甩 usage）",
     "argv": ("shell", "--exec", "nf statss", "--no-banner"), "expect": "你是不是想找",
     "expect_exit": 2},
    {"id": "write-gate", "name": "写盘闸门（非交互默认拒跑）",
     "argv": ("shell", "--exec", "nf stats --write", "--no-banner"),
     "expect": "确认", "expect_exit": 2},
    # 2026-09-30 补：**无标记写盘动词**与**命令+旗标**配对的闸门（此前只拦 `--write` 一族）
    {"id": "write-gate-verb", "name": "写盘闸门（无标记动词：library 生命周期）",
     "argv": ("shell", "--exec", "nf library deprecate NF-ZZZ", "--no-banner"),
     "expect": "确认", "expect_exit": 2},
    {"id": "write-gate-reindex", "name": "写盘闸门（投影重建）",
     "argv": ("shell", "--exec", "nf decisions reindex", "--no-banner"),
     "expect": "确认", "expect_exit": 2},
    {"id": "write-gate-pair", "name": "写盘闸门（interop --all 落盘）",
     "argv": ("shell", "--exec", "nf interop --all", "--no-banner"),
     "expect": "确认", "expect_exit": 2},
    {"id": "nested-shell-guard", "name": "递归/长驻拦截（serve/shell）",
     "argv": ("shell", "--exec", "nf shell", "--no-banner"),
     "expect": "另开", "expect_exit": 2},
    {"id": "complete", "name": "补全（命令 / 子命令 / 旗标）",
     "argv": ("shell", "--complete", "nf lay", "--no-banner"), "expect": "nf layers"},
    {"id": "limit-hint-and-no-ansi", "name": "限长提示 + 非 TTY 无色（一行双断言）",
     "argv": ("shell", "--commands", "asset", "--limit", "3", "--no-banner"),
     "expect": ("还有",), "forbid": "\x1b"},
    {"id": "script-face", "name": "脚本面（--exec 逐条执行）",
     "argv": ("shell", "--exec", "/zone 0", "--no-banner"), "expect": "环境自检"},
    {"id": "history-replay", "name": "历史重放（!! / !n / !前缀）",
     # 本行主题是「重放机制」，用最轻的真实命令（--version）——避免把 `layers --verify`
     # 那类全仓扫描（~1.5 s/次）的成本记在效率证据上（时间预算是判**机制开销**的）。
     "argv": ("shell", "--exec", "nf --version; !!", "--no-banner"), "expect": "重放"},
    {"id": "history-persist", "name": "历史落盘（交互态写文件）",
     "argv": ("shell", "--history", BASELINE_TMP + "/shell_history", "--no-banner"),
     "stdin": "nf --version\nquit\n",
     "expect": "nf 1.0.5", "expect_file": BASELINE_TMP + "/shell_history"},
    {"id": "session-persist", "name": "会话状态持久化（--session）",
     "argv": ("shell", "--session", BASELINE_TMP + "/shell_session.json",
              "--no-history", "--no-banner"),
     "stdin": "/set width=120\nquit\n",
     "expect": "width = 120", "expect_file": BASELINE_TMP + "/shell_session.json"},
    {"id": "menu-family-crosslink", "name": "菜单↔能力族互标",
     "argv": ("shell", "--exec", "/menu", "--no-banner"), "expect": "未在此列的族"},
    {"id": "form-dry-run", "name": "写盘表单（dry-run 只组装不执行）",
     "argv": ("shell", "--form", "stats-write", "--json", "--no-banner"),
     "expect": '"executed": false'},
    {"id": "machine-face", "name": "机器面（--verify --json 纯 JSON）",
     "argv": ("shell", "--verify", "--json", "--no-banner"),
     "expect": '"kind": "shell-verify"'},
    {"id": "live-selfcheck", "name": "活体自检（真跑一条只读命令）",
     # 同一行承载两条断言：活体档在场 + 全 64 命令逐条 --help 均可调用（只跑一次）
     "argv": ("shell", "--verify", "--deep", "--no-banner"),
     "expect": ("活体", "全命令可调用："), "max_ms": BASELINE_DEEP_MAX_MS},
)




def baseline_table() -> tuple:
    """顶尖 CLI 基线真源（`nf shell --baseline`、check39、测试共用同一份）。"""
    return TERMINAL_BASELINE




def _baseline_identity_issues(row: dict, argv: list, seen: set,
                               seen_argv: dict) -> list:
    """基线行的身份面：id 唯一、argv 唯一、入口是 shell、有判据。"""
    issues = []
    rid = str(row.get("id"))
    if not rid or rid in seen:
        issues.append("基线行 id 缺失或重复：%s" % rid)
    seen.add(rid)
    key = tuple(argv)
    if key in seen_argv:
        issues.append("基线行 %s 与 %s 的 argv 相同——合并断言，勿重复执行" % (rid, key))
    seen_argv[key] = rid
    if not argv or argv[0] != "shell":
        issues.append("基线行 %s 的入口不是 shell：%s" % (rid, argv[:1]))
    if not row.get("expect") and not row.get("forbid"):
        issues.append("基线行 %s 既没 expect 也没 forbid（判不出对错）" % rid)
    return issues


def _baseline_argv_checks(row: dict, argv: list) -> list:
    """基线行的 argv/退出码面：只读、临时占位绝对路径、expect_exit 只许 0/2。"""
    issues = []
    rid = str(row.get("id"))
    for tok in argv:
        if tok in BASELINE_FORBIDDEN_FLAGS:
            issues.append("基线行 %s 带写盘旗标 %s（证据必须只读）" % (rid, tok))
    for tok in argv:
        if BASELINE_TMP in tok and not os.path.isabs(
                tok.replace(BASELINE_TMP, baseline_tmp_dir())):
            issues.append("基线行 %s 的临时占位展开后不是绝对路径：%s" % (rid, tok))
    expect_exit = int(row.get("expect_exit", 0))
    if expect_exit not in (0, 2):
        issues.append("基线行 %s 的 expect_exit 只许 0 或 2（0 = 该成功，2 = 该被拒）" % rid)
    if expect_exit != 0 and not row.get("expect"):
        issues.append("基线行 %s 声明了非零 expect_exit，须给 expect 说明拒跑理由" % rid)
    return issues


def baseline_argv_issues() -> list:
    """自洽判据：id 唯一、**argv 唯一**、只走 shell、且证据行只读；只报 issue、不删行。
    2026-10-14：同一 argv 跑两遍纯属冗余（差异只可能在断言里 → 合并为一行双断言）。"""
    issues = []
    seen = set()
    seen_argv: dict = {}
    for row in TERMINAL_BASELINE:
        argv = [str(a) for a in row.get("argv") or []]
        issues.extend(_baseline_identity_issues(row, argv, seen, seen_argv))
        issues.extend(_baseline_argv_checks(row, argv))
    return issues




def _expect_hits(text: str, expect) -> bool:
    """`expect` 支持单条或多条：多条要求**全部出现**（同一行证据可承载多条断言）。"""
    if not expect:
        return True
    items = expect if isinstance(expect, (list, tuple)) else [expect]
    return all(str(x) in text for x in items)




# 注意：**只**对含 {TMP} 的项做 normpath——否则 Windows 上会把 /zone 0 规整成
# \zone 0，直接打坏斜杠命令（实测踩到：脚本面与菜单行双双判红）。
def _baseline_argv_norm(row: dict) -> list:
    """基线行 argv → 展开本机临时目录后的形态（仅含占位符的项做 normpath）。"""
    argv = []
    for a in row.get("argv") or []:
        item = str(a)
        argv.append(os.path.normpath(item.replace(BASELINE_TMP, baseline_tmp_dir()))
                    if BASELINE_TMP in item else item)
    return argv


def _baseline_expect_file(row: dict) -> str:
    """expect_file 占位符展开（未声明 → 空串）。"""
    _exp_raw = str(row.get("expect_file") or "")
    return (os.path.normpath(_exp_raw.replace(BASELINE_TMP, baseline_tmp_dir()))
            if _exp_raw else "")


def _baseline_content_ok(row: dict, code: int, text: str, exp_file: str) -> bool:
    """单次执行的断言：退出码 + expect 全中 + forbid 缺席 + expect_file 真落盘。"""
    return (code == int(row.get("expect_exit", 0))
            and _expect_hits(text, row.get("expect"))
            and (not row.get("forbid") or row["forbid"] not in text)
            and (not exp_file or os.path.isfile(exp_file)))


def _baseline_retry(row: dict, runner, argv: list, budget: float,
                    exp_file: str) -> tuple[float, bool, int]:
    """有界重试：只超预算才继续，取最小样本 → (ms, content_ok, code)。"""
    ms, content_ok, code = float("inf"), False, 0
    for _ in range(3):
        t0 = time.perf_counter()
        code, out = runner(argv, row.get("stdin"))
        ms = min(ms, (time.perf_counter() - t0) * 1000.0)
        text = str(out or "")
        content_ok = _baseline_content_ok(row, code, text, exp_file)
        if not content_ok or ms <= budget:
            break
    return ms, content_ok, code


def _run_baseline_row(row: dict, runner) -> dict:
    """跑一行基线证据 → 结果行。"""
    argv = _baseline_argv_norm(row)
    budget = float(row.get("max_ms", BASELINE_DEFAULT_MAX_MS))
    exp_file = _baseline_expect_file(row)
    ms, content_ok, code = _baseline_retry(row, runner, argv, budget, exp_file)
    ok = content_ok and ms <= budget
    return {"id": row["id"], "name": row["name"],
            "argv": argv,
            "exit": code, "expect_exit": int(row.get("expect_exit", 0)),
            "ms": round(ms, 1),
            "max_ms": budget, "content_ok": content_ok,
            "ok": bool(ok),
            "expect": row.get("expect") or "",
            "forbid": row.get("forbid") or "",
            "expect_file": exp_file}


def run_baseline(runner, rows=None) -> tuple:
    """逐行跑证据命令 → (results, stats)。

    `runner(argv, stdin_text=None) -> (exit_code, 合并输出)`：`stdin` 供交互态证据喂输入，
    `expect_file` 断言某文件**真的落盘**；超预算的行**再测两次取最小**（见 BASELINE_DEEP_MAX_MS）。
    """
    results = [_run_baseline_row(row, runner) for row in (rows or TERMINAL_BASELINE)]
    stats = {"rows": len(results),
             "passed": sum(1 for r in results if r["ok"]),
             "slowest_ms": max([r["ms"] for r in results] or [0.0]),
             "total_ms": round(sum(r["ms"] for r in results), 1)}
    return results, stats




def portable_rows(results) -> list:
    """把基线结果里的**本机临时路径**还原成 `{TMP}` 占位符（仅供展示/机器面）。

    为什么（2026-10-01 取证）：`run_baseline` 为了让证据命令真跑，把 `{TMP}` 展开成了本机
    临时目录；那份**原始结果**要留着（单测断言展开值、排障要看真实路径），但直接进人读面/
    `--json` 就是**机器绝对路径回吐**（实测 `nf shell --baseline` 与 `--baseline --json` 都在
    打印 `C:\\Users\\<user>\\…`）。故拆开：执行/诊断用原值，**展示用本函数**。
    """
    tmp_now = baseline_tmp_dir()
    out = []
    for r in results or []:
        row = dict(r)
        row["argv"] = [str(a).replace(tmp_now, BASELINE_TMP) for a in r.get("argv") or []]
        f = str(r.get("expect_file") or "")
        row["expect_file"] = f.replace(tmp_now, BASELINE_TMP) if f else ""
        out.append(row)
    return out




def render_baseline(results, stats, width=None, color: bool = False) -> str:  # noqa: ARG001 - 调用契约：nf.py/test 按 width= 传入
    """渲染基线逐行结果（人读）：一行一项能力 + 判定 + 证据命令。"""
    lines = [style("== 顶尖 CLI 基线（%d 项 · 逐条可复跑）==" % stats["rows"], "head", color),
             "  通过 %d/%d · 总耗时 %s ms · 最慢 %s ms（每行有延迟预算，超时即判效率退化）"
             % (stats["passed"], stats["rows"], stats.get("total_ms", "-"),
                stats.get("slowest_ms", "-"))]
    for r in results:
        flag = style("✔" if r["ok"] else "✘", "ok" if r["ok"] else "fail", color)
        lines.append("%s %s %8s ms  nf %s"
                     % (flag, pad_to(r["name"], 30), r.get("ms", "-"),
                        " ".join(r["argv"])))
    lines.append("  单行复跑：直接执行该行的 `nf …`（全部只读，不改仓库）")
    return "\n".join(lines)




def writable_dir_probe(path: str) -> tuple:
    """→ (ok, 说明)：**不落件**地判断某文件落点是否可写（沿祖先上溯到存在的目录再看权限）。

    不用「写一个探针再删」：本环境删目录受限，且探针本身就会留件——「不留件」比「测得准一点点」重要。
    """
    if not path:
        return True, "未启用"
    cur = os.path.dirname(os.path.abspath(path)) or "."
    while cur and not os.path.isdir(cur):
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    if os.path.isdir(cur) and os.access(cur, os.W_OK):
        return True, "可写（%s）" % cur
    return False, "不可写（%s）" % cur
