"""terminal · _ui（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import os
from functools import lru_cache

from ._const import (
    _RESET,
    _STYLES,
    _WIDE_RANGES,
)


@lru_cache(maxsize=4096)
def char_width(ch: str) -> int:
    """单字符显示宽度（CJK/全角/emoji = 2，其余 = 1，控制字符 = 0）。

    带缓存：列表渲染每个字符都要问一次宽度，`--commands`（135 行）这类场景下是热路径；
    字符集有限，4096 项缓存足够覆盖任意一次渲染。
    """
    cp = ord(ch)
    if cp < 32 or cp == 0x7F:
        return 0
    for lo, hi in _WIDE_RANGES:
        if lo <= cp <= hi:
            return 2
    return 1




def display_width(text: str) -> int:
    """字符串显示宽度（列对齐用；纯函数、确定性）。"""
    return sum(char_width(ch) for ch in str(text or ""))




def pad_to(text: str, width: int) -> str:
    """右补空格到指定**显示宽度**（CJK 不歪列）。"""
    text = str(text or "")
    gap = int(width) - display_width(text)
    return text + (" " * gap if gap > 0 else "")




def clip(text: str, width: int) -> str:
    """单行截断到指定显示宽度（超宽加省略号）。"""
    text = str(text or "")
    if display_width(text) <= width:
        return text
    out, used = [], 0
    for ch in text:
        cw = char_width(ch)
        if used + cw > max(0, int(width) - 1):
            break
        out.append(ch)
        used += cw
    return "".join(out) + "…"




def style(text, kind: str, on: bool = False) -> str:
    """按语义着色（on=False 原样返回——非 TTY 默认，保逐字节确定）。"""
    body = str(text)
    if not on or kind not in _STYLES:
        return body
    return "%s%s%s" % (_STYLES[kind], body, _RESET)




def resolve_color(mode: str = "auto", stream=None) -> bool:
    """颜色模式 → 布尔：always / never / auto（auto = 真 TTY 且未设 NO_COLOR）。

    额外尊重 `CLICOLOR_FORCE`（非 "0" 即强制开启 auto 档）——与 `NO_COLOR` 同为业界惯例；
    两者冲突时 `NO_COLOR` 优先（关比开安全）。
    """
    m = str(mode or "auto").strip().lower()
    if m == "always":
        return True
    if m == "never":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if str(os.environ.get("CLICOLOR_FORCE") or "").strip() not in ("", "0"):
        return True
    try:
        return bool(stream is not None and stream.isatty())
    except Exception:      # 尽力而为：判定不了就按无色（安全侧）
        return False




def highlight(text, needle, on: bool = False) -> str:
    """把命中词包成高亮（**仅着色时**；大小写不敏感，只标第一处，避免满屏噪声）。

    必须在**截断/补位之后**调用：ANSI 转义也算字符宽度，先着色会让列对齐失真。
    """
    body = str(text or "")
    key = str(needle or "")
    if not on or not key:
        return body
    idx = body.lower().find(key.lower())
    if idx < 0:
        return body
    return (body[:idx] + style(body[idx:idx + len(key)], "warn", True)
            + body[idx + len(key):])




def term_width(width=None, env=None, default: int = 100) -> int:
    """渲染宽度：显式 width > 环境 COLUMNS（≥40 才认）> default。"""
    if width:
        try:
            return max(40, int(width))
        except (TypeError, ValueError):
            return default
    e = env if env is not None else os.environ
    try:
        cols = int(e.get("COLUMNS") or 0)
    except (TypeError, ValueError, AttributeError):
        cols = 0
    return cols if cols >= 40 else default




def _row(left: str, right: str, width: int, color: bool = False,
         hl: str = "") -> str:
    """两列行：左列固定宽度（按显示宽度补），右列按剩余宽度截断（可带命中高亮）。"""
    left_col = 28
    left_txt = pad_to("  " + left, left_col)
    remain = max(20, int(width) - left_col)
    return (style(left_txt, "cmd", color)
            + highlight(clip(right, remain), hl, color))
