"""M15 Property/Differential Testing 参考：对 canonical 生成性质做确定性检查。"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[2] / "cli"
if str(CLI) not in sys.path:
    sys.path.insert(0, str(CLI))

from nf_app.canonical import CanonicalError, canonical_bytes  # noqa: E402


def _value(rng: random.Random, depth: int = 0):
    kinds = ["str", "int", "bool", "none"]
    if depth < 3:
        kinds += ["list", "dict"]
    kind = rng.choice(kinds)
    if kind == "str":
        return rng.choice(["a", "中文", "e\u0301", "\u00e9", "x y", ""])
    if kind == "int":
        return rng.randint(-1000, 1000)
    if kind == "bool":
        return rng.choice([True, False])
    if kind == "none":
        return None
    if kind == "list":
        return [_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    return {
        "k" + str(rng.randint(0, 5)): _value(rng, depth + 1)
        for _ in range(rng.randint(0, 4))
    }


def check_canonical(seed: int = 42, count: int = 100) -> list[str]:
    rng = random.Random(seed)
    failures: list[str] = []
    for i in range(count):
        value = _value(rng)
        try:
            first = canonical_bytes(value)
            second = canonical_bytes(value)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"case {i}: canonical raised {exc}")
            continue
        if first != second:
            failures.append(f"case {i}: canonical 不稳定")
        try:
            decoded = json.loads(first.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"case {i}: 输出非法 JSON {exc}")
            continue
        if decoded != value:
            failures.append(f"case {i}: roundtrip 不等")
    return failures


def check_float_rejected() -> bool:
    try:
        canonical_bytes({"x": 1.5})
    except CanonicalError:
        return True
    return False


def check_key_order_ignored() -> bool:
    a = canonical_bytes({"b": 1, "a": 2})
    b = canonical_bytes({"a": 2, "b": 1})
    return a == b


def check_unicode_preserved() -> bool:
    composed = "\u00e9"
    decomposed = "e\u0301"
    return canonical_bytes(composed) != canonical_bytes(decomposed)
