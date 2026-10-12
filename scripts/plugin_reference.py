#!/usr/bin/env python3
"""微内核插件的 Python **参考实现**（回退面 + 字节等价的对照物）。

§18.3 / §18.5：插件缺失、崩溃、超时、fuel 耗尽 → 一律回退到本实现，并**记录降级**（不许静默）。
§18.7：参考实现**恒在**——插件只做加速，绝不进正确性关键路径。

形态与插件逐条对齐（同一份清单声明的 io）：

    argv    --method <name>
    stdin   原始字节（唯一输入通道）
    stdout  小写十六进制 + LF
    stderr  报因；退出码 2 = 用法/未知方法
"""
import argparse
import hashlib
import sys

#: 方法名 → 实现。与 engine/wasm/manifests/sha256.json 的 methods 一一对应。
METHODS = {
    "sha256": lambda data: hashlib.sha256(data).hexdigest(),
}


def contract():
    """本参考实现对外承诺的 I/O 契约（供宿主与判据对账，避免两处各写一份）。"""
    return {"stdout": "hex-lowercase+LF", "exit_ok": 0, "exit_usage": 2,
            "methods": sorted(METHODS)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="微内核插件 Python 参考实现（只读）")
    ap.add_argument("--method", default="sha256")
    args = ap.parse_args(argv)
    fn = METHODS.get(args.method)
    if fn is None:
        print(f"未知方法：{args.method}（在册：{' | '.join(sorted(METHODS))}）",
              file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read()
    sys.stdout.write(fn(data) + "\n")
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
