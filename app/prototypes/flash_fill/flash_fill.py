"""M1 Flash Fill 参考原型：从输入→输出例子合成白名单变换。

边界：只做前缀/后缀/去前缀/去后缀/替换/截断；不执行任意代码、不生成正则。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class InferError(ValueError):
    pass


@dataclass(frozen=True)
class Transform:
    kind: str
    a: str = ""
    b: str = ""

    def describe(self) -> str:
        return {
            "prefix": f"加前缀「{self.a}」",
            "suffix": f"加后缀「{self.a}」",
            "strip_prefix": f"去前缀「{self.a}」",
            "strip_suffix": f"去后缀「{self.a}」",
            "replace": f"把「{self.a}」替换为「{self.b}」",
            "truncate": f"截断到 {self.a} 字",
        }.get(self.kind, self.kind)

    def apply(self, text: str) -> str:
        if self.kind == "prefix":
            return self.a + text
        if self.kind == "suffix":
            return text + self.a
        if self.kind == "strip_prefix":
            return text[len(self.a):] if text.startswith(self.a) else text
        if self.kind == "strip_suffix":
            return text[: -len(self.a)] if self.a and text.endswith(self.a) else text
        if self.kind == "replace":
            return text.replace(self.a, self.b) if self.a else text
        if self.kind == "truncate":
            return text[: int(self.a)] if self.a.isdigit() else text
        raise InferError("未知变换：" + self.kind)


def _common_prefix(values: list[str]) -> str:
    if not values:
        return ""
    out = values[0]
    for value in values[1:]:
        while not value.startswith(out):
            out = out[:-1]
    return out


def _common_suffix(values: list[str]) -> str:
    if not values:
        return ""
    out = values[0]
    for value in values[1:]:
        while not value.endswith(out):
            out = out[:-1]
    return out


def _replace_candidate(a: str, b: str) -> tuple[str, str] | None:
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    m = 0
    while m < min(len(a), len(b)) - n and a[len(a) - 1 - m] == b[len(b) - 1 - m]:
        m += 1
    old = a[n: len(a) - m] if m else a[n:]
    new = b[n: len(b) - m] if m else b[n:]
    if old and len(old) >= 2 and a.replace(old, new) == b:
        return old, new
    return None


def infer(examples: Iterable[tuple[str, str]]) -> Transform:
    pairs = list(examples)
    if not pairs:
        raise InferError("至少需要一个例子")
    if all(a == b for a, b in pairs):
        raise InferError("输入与输出完全相同")

    # 统一加后缀：b = a + s
    if all(b.startswith(a) and len(b) >= len(a) for a, b in pairs):
        s = _common_suffix([b[len(a):] for a, b in pairs])
        if s:
            return Transform("suffix", s)

    # 统一加前缀：b = p + a
    if all(b.endswith(a) and len(b) >= len(a) for a, b in pairs):
        p = _common_prefix([b[: len(b) - len(a)] for a, b in pairs])
        if p:
            return Transform("prefix", p)

    # 去前缀：b = a[len(p):]
    if all(a.endswith(b) and len(a) > len(b) for a, b in pairs):
        p = _common_prefix([a[: len(a) - len(b)] for a, b in pairs])
        if p:
            return Transform("strip_prefix", p)

    # 去后缀：b = a[:-len(s)]
    if all(a.startswith(b) and len(a) > len(b) for a, b in pairs):
        s = _common_suffix([a[len(b):] for a, b in pairs])
        if s:
            return Transform("strip_suffix", s)

    # 截断：b = a[:n]，所有输出等长
    if all(a.startswith(b) for a, b in pairs):
        n = max(len(b) for _, b in pairs)
        if n and all(len(b) == n for _, b in pairs):
            return Transform("truncate", str(n))

    # 替换：同一 old/new 在所有例子上成立
    candidates = [_replace_candidate(a, b) for a, b in pairs]
    if candidates and all(c is not None for c in candidates):
        first = candidates[0]
        assert first is not None
        if all(c == first for c in candidates) and all(a.replace(first[0], first[1]) == b for a, b in pairs):
            return Transform("replace", first[0], first[1])

    raise InferError("无法从例子合成白名单变换")


def apply_all(transform: Transform, texts: Iterable[str]) -> list[str]:
    return [transform.apply(t) for t in texts]
