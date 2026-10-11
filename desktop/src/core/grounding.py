"""锚点回验（06 §4④ 的机读实现）：输出事实点必须能在裁剪包/来源里找到锚。

机制借鉴 ai-engineering-lab grounding.py:33-53：**标点/空白归一 + token 重叠阈值**
容忍转述（同一事实换个说法也算命中），**未溯源只标注、不丢件**。

NF 现状（内部差距，非外部反推）：06_Agent执行协议.md §4④ 已声明「正文中每个事实点
必须能在裁剪包中找到锚点」为强制，但 verify.sh 的 check4 只 grep 字符串、
quality_gate 的锚点判据是结构性的（P00/P80 在场）——真实现空白。
本模块把该判据做成可复用纯函数；接线（quality_gate R3 / check17 / check32）属重构波次。

纪律：纯标准库；无副作用；不联网；不丢件（返回未锚定清单，由调用方决定处置）。
"""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple

#: 非词字符（标点/空白/全角空格一律去除）——只做「同义写法收敛」，不做语义改写
_NON_WORD = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")
#: token 切分：ASCII 词 / 数字 / 单个汉字（汉字逐字切，抗分词差异）
_TOKEN = re.compile(r"[0-9A-Za-z_]+|[\u4e00-\u9fff]")

#: 默认容忍阈值：转述（改标点、换语序、增删虚词）仍须 ≥0.8 token 命中
DEFAULT_THRESHOLD = 0.8


def normalize(text: str) -> str:
    """去掉非词字符并小写——用于「整串包含」这一抗分词兜底。"""
    return _NON_WORD.sub("", text or "").lower()


def tokens(text: str) -> List[str]:
    """词/数字/单汉字 token 列表（小写）。"""
    return _TOKEN.findall((text or "").lower())


def overlap(needle: str, haystack: str) -> float:
    """needle 的 token 在 haystack 中的命中比例（0..1）。

    双形态：归一化整串包含 → 1.0（抗分词差异）；否则按 token 交集比例。
    """
    n = normalize(needle)
    if n and n in normalize(haystack):
        return 1.0
    nt = tokens(needle)
    if not nt:
        return 0.0
    hs = set(tokens(haystack))
    return sum(1 for t in nt if t in hs) / len(nt)


def verify_anchors(facts: Iterable[str], sources: Iterable[str],
                   threshold: float = DEFAULT_THRESHOLD) -> Tuple[bool, List[dict]]:
    """逐条事实点在来源集合里找锚 → (全锚定?, 未锚定清单)。

    未锚定项带 best 分与 reason，**不丢件**——调用方按需标注/回填，不静默丢弃。
    """
    src = [s for s in sources if isinstance(s, str) and s.strip()]
    unanchored: List[dict] = []
    for f in facts:
        if not isinstance(f, str) or not f.strip():
            continue
        best = max((overlap(f, s) for s in src), default=0.0)
        if best < threshold:
            unanchored.append({"fact": f, "best": round(best, 3),
                               "reason": "任何来源的 token 重叠都低于阈值 %s" % threshold})
    return (not unanchored, unanchored)
