#!/usr/bin/env python3
"""PyO3 原语包装（core.rust_pyext）的常驻回归。

为什么（2026-10-22）：engine/rust/pyo3 把 `sha256` / `float_repr` 两个**逐字节对账过**的纯函数
暴露成 CPython 扩展；本判据钉住「包装层永远可用 + 与 stdlib 逐字节一致」：

① sha256 与 `hashlib.sha256().digest()` 一致（空 / abc / 0..255 / 中文）；
② float_repr 与 `repr()` 一致（边界值 + 伪随机位模式）；
③ 扩展缺席时回退 stdlib（本判据不依赖 .pyd 在场——它永远要绿）。

扩展在场（`nf_pyengine` 可 import）时，上面的对账同时覆盖「Rust 实现」那条真路径；
缺席时覆盖「回退」那条路径——两条路径都吃同一份判据，不假装用过扩展。
"""
from __future__ import annotations

import hashlib
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import rust_pyext as re  # noqa: E402


class RustPyExtTest(unittest.TestCase):
    def test_sha256_matches_hashlib(self) -> None:
        for data in (b"", b"abc", bytes(range(256)), "中文".encode("utf-8")):
            self.assertEqual(re.sha256(data), hashlib.sha256(data).digest())

    def test_float_repr_matches_python(self) -> None:
        vals = [0.0, -0.0, 1e-4, 1e-5, 1e15, 1e16, 100.0, 0.1,
                float("inf"), float("-inf"), float("nan"), 5e-324,
                153838026194641.125]
        for v in vals:
            self.assertEqual(re.float_repr(v), repr(v))
        rnd = random.Random(42)
        for _ in range(20000):
            bits = rnd.getrandbits(64)
            v = struct.unpack("d", struct.pack("Q", bits))[0]
            self.assertEqual(re.float_repr(v), repr(v))

    def test_engine_is_optional(self) -> None:
        # 包装层必须在扩展缺席时也能用（回退 stdlib）；这里只断言调用不抛、结果正确。
        self.assertEqual(re.sha256(b"x"), hashlib.sha256(b"x").digest())
        self.assertEqual(re.float_repr(1.0), "1.0")


if __name__ == "__main__":
    unittest.main()
