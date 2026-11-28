"""terminal · _completion（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

from ._const import (
    SLASH_HELP,
    SLASH_WORDS,
)
from ._tables import (
    FAMILIES,
    ZONES,
)
from ._ui import (
    _row,
    style,
    term_width,
)


def _restore_msys_partial(text: str) -> str:
    """MSYS/Git-Bash 兼容（**补全面**）：以 `/` 开头的参数会被通行层改写成 `C:/…/ma`。

    与 `parse()` 的还原同判据，但**允许前缀**——补全本来就是打一半：末段若是任一斜杠词的
    前缀就还原成 `/<段>`。只影响补全候选，不改变任何执行语义。
    """
    if "/" not in text and "\\" not in text:
        return text
    head, _, tail = text.partition(" ")
    seg = head.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if seg and any(str(w).startswith(seg) for w in SLASH_WORDS):
        return "/" + seg + ((" " + tail) if tail else "")
    return text




def complete(partial: str, index, limit: int = 20) -> list:
    """补全候选（纯函数，确定性）→ [{"text": …, "note": …}]。

    支持四类前缀：`/`（斜杠命令）、`/map <族>`、`/zone <键>`、`nf <命令>[ <子命令>][ -]`。
    命令/子命令/旗标都从 CLI 的 argparse 索引派生——补全面与命令面永远同源。
    """
    text = str(partial or "")
    stripped = _restore_msys_partial(text.strip())
    entries = list(index or [])
    if stripped.startswith("/"):
        return _slash_completions(stripped, limit)
    return _nf_completions(stripped, entries, limit)


def _slash_completions(stripped: str, limit: int) -> list:
    """斜杠命令族补全。"""
    body = stripped[1:]
    head, _, tail = body.partition(" ")
    if head in ("map", "族", "地图") and " " in body:
        return _map_completions(tail, limit)
    if head in ("zone", "z", "区") and " " in body:
        return _zone_completions(tail, limit)
    return _slash_word_completions(head, limit)


def _map_completions(tail: str, limit: int) -> list:
    """`/map <族>` 的族名补全。"""
    out = []
    for fam in FAMILIES:
        key = str(fam["id"])
        if tail and not (key.startswith(tail) or tail in str(fam["name"])):
            continue
        out.append({"text": "/map %s" % key, "note": str(fam["name"])})
    return out[:limit]


def _zone_completions(tail: str, limit: int) -> list:
    """`/zone <键>` 的区键补全。"""
    out = []
    for z in ZONES:
        if tail and not str(z["key"]).startswith(tail):
            continue
        out.append({"text": "/zone %s" % z["key"], "note": str(z["title"])})
    return out[:limit]


def _slash_word_completions(head: str, limit: int) -> list:
    """斜杠帮助词补全。"""
    out = []
    for word, note in SLASH_HELP:
        if word.startswith(head):
            out.append({"text": "/" + word, "note": note})
    return out[:limit]


def _nf_completions(stripped: str, entries, limit: int) -> list:
    """`nf` 命令面补全（命令/子命令/旗标）。"""
    has_nf = stripped == "nf" or stripped.startswith("nf ")
    body = stripped[3:].strip() if stripped.startswith("nf ") else stripped
    tokens = body.split()
    base = " ".join(tokens[:-1]) if len(tokens) > 1 else ""
    prefix = tokens[-1] if tokens else ""
    out = []
    if prefix.startswith("-"):
        return _flag_completions(entries, base, prefix, has_nf, limit)
    return _path_completions(entries, base, prefix, has_nf, limit)


def _flag_completions(entries, base: str, prefix: str, has_nf: bool, limit: int) -> list:
    """已解析命令的旗标补全。"""
    out = []
    for e in entries:
        if str(e.get("path")) == base:
            for flag in e.get("flags") or []:
                if str(flag).startswith(prefix):
                    out.append({"text": ("nf " if has_nf else "") + base + " " + flag,
                                "note": "旗标"})
            break
    return out[:limit]


def _path_completions(entries, base: str, prefix: str, has_nf: bool, limit: int) -> list:
    """命令/子命令路径补全。"""
    out = []
    for e in entries:
        path = str(e.get("path"))
        if base:
            if not path.startswith(base + " "):
                continue
            if " " in path[len(base) + 1:]:
                continue
        elif " " in path:
            continue
        if prefix and not path.startswith(prefix):
            continue
        out.append({"text": ("nf " + path) if has_nf else path,
                    "note": str(e.get("summary") or "")})
    return out[:limit]




def render_completions(partial: str, cands, width=None, color: bool = False) -> str:
    """渲染补全候选（人读）：一行一条，带用途；未命中给下一步指引。"""
    if not cands:
        return ("无补全候选：「%s」（用 /commands 列全部命令、/map 看能力族，"
                "或 /find <词> 检索）" % partial)
    w = term_width(width)
    lines = [style("== 补全：「%s」（%d 条）==" % (partial, len(cands)), "head", color)]
    for c in cands:
        lines.append(_row(str(c.get("text")), str(c.get("note") or ""), w, color))
    return "\n".join(lines)




def install_readline(completer_text, history_path=None):
    """可用时接上 readline（POSIX）：Tab 补全 + 历史文件；不可用返回 False（Windows 常态）。

    这是**可选增强**而非依赖：补全判据本身在 `complete()` 里，任何平台都能用。
    """
    try:
        import readline  # (stdlib；Windows 无该模块)
    except ImportError:
        return False
    try:
        if history_path:
            try:
                readline.read_history_file(history_path)
            except OSError:  # 历史文件读不到（首次运行/权限）⇒ 从空历史开始
                pass
            readline.set_history_length(200)

        def _completer(text, state):
            options = completer_text(text) or []
            if state < len(options):
                return options[state]
            return None

        readline.set_completer(_completer)
        readline.parse_and_bind("tab: complete")
        return True
    except Exception:      # 尽力而为：readline 行为异常时不拖垮终端（缺口由补全命令另报）
        return False




def readline_available() -> bool:
    """只探测 readline 是否可用（不产生副作用——`--verify` 用它报事实，不改当前进程行为）。"""
    try:
        import readline  # noqa: F401
        return True
    except ImportError:
        return False
