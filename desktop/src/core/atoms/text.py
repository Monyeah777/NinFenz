"""文本原子：跨文件关键词对齐（哪一侧缺哪个词）/ 正则命中清单。只回数据。"""
from __future__ import annotations

import re
from collections.abc import Iterable

from . import _wake


def keyword_both_ways(text_a: str, text_b: str, keywords: Iterable[str]) -> list[tuple[str, str]]:
    """→ [(缺词的一侧, 关键词)]；两侧都有或两侧都无 → 不报。

    「两侧都无」不报是有意为之：对齐判据问的是**两份文本是否互相呼应**，不是「这个词该不该存在」。
    「该存在」由声明清单（能力层的输入面）判，原子不做第二遍。
    顺序 = 关键词的传入顺序；同一关键词只可能缺在一侧，所以顺序天然稳定。
    """
    _wake("text.keyword_both_ways")
    out: list[tuple[str, str]] = []
    for keyword in keywords:
        in_a = keyword in text_a
        in_b = keyword in text_b
        if in_a and not in_b:
            out.append(("b", keyword))
        elif in_b and not in_a:
            out.append(("a", keyword))
    return out


def regex_absent(text: str, pattern: str) -> list[tuple[int, str]]:
    """→ [(行号, 该行正文)]，覆盖 pattern 的每一处命中；无命中 → []。

    命名沿用设计文档（regex_absent）：判据是「不许命中」，但返回值必须是**命中了什么**，
    否则失败文案只能写「有命中」，修复指引无处落脚（ADR-0002 不许注水）。
    """
    _wake("text.regex_absent")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(
            f"正则无法编译：{exc}"
            "（修复指引：检查 pattern 的括号/量词/转义，先单独跑一遍）") from exc
    return [(number, line) for number, line in enumerate(text.splitlines(), 1)
            if compiled.search(line)]
