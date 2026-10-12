#!/usr/bin/env python3
"""canonical JSON 面（P-C1）：--rule nf（仓库口径）/ --rule jcs（RFC 8785 JCS）。

**两条不同规范，刻意用规则名分开**（D-10 裁定）：

  - 'nf'  = 仓库内部口径 nf-canonical/1：键按 **Python 码点序**；整数浮点保留 '.0'。
    本体在 'core/attest.py'（唯一实现），此处只做 CLI 包装，**不复制**该逻辑。
  - 'jcs' = RFC 8785：键按 **UTF-16 码元序**（§3.2.3）；数字走 ECMAScript Number::toString
    （§3.2.2.3）；字符串最小转义（§3.2.2.2）。本体在本文件（canonical_jcs）。

为什么 'jcs' 必须**独立**实现（不复用 attest.canonical）：跨语言契约对拍的价值来自「各语言
按同一规范各自实现」。若 Python 侧复用内部口径，对拍只能证明「同一个口径没变」，Rust / C#
两份 JCS 实现就失去了对照物。D-10 已裁定内部口径**不得**对外当 RFC 8785 承诺——规则名就是
这条边界的载体；两口径的分歧本身由 'desktop/tests/test_jcs_spec_gap.py' 钉死。

退出码（与 Rust 'engine/rust/canonical'、C# 'engine/dotnet/tools/nf-canonical' 逐条一致，
否则对拍器无法用 rc 统一判「拒绝」）：0 成功；1 输入不是合法 JSON/UTF-8；2 用法或读不到文件。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import (  # noqa: E402 - 必须先插入 desktop/src 才能 import core
    attest,
    json_doc,
)

# ------------------------------------------------------------------ RFC 8785

_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _utf16_key(s):
    """RFC 8785 §3.2.3 的排序键：UTF-16 **码元**序列（不是码点序列）。"""
    try:
        return s.encode("utf-16-be")
    except UnicodeEncodeError as exc:  # 未配对代理：UTF-16 都编不出来 ⇒ I-JSON 不合法
        raise ValueError(f"键含未配对代理（I-JSON 不许）：{exc}"
                         "（修复指引：改用成对代理，或直接写 UTF-8 字符）") from exc


def _es_number(v):
    """ECMAScript Number::toString(x)（RFC 8785 §3.2.2.3）。

    记值 = 0.<digits> × 10**n（digits 为最短往返的有效数字、无前导/尾随零），k = len(digits)：
      k <= n <= 21  → digits 后补 (n-k) 个 0（定点）
      0 < n <= 21   → 小数点落在 digits 中间
      -6 < n <= 0   → 0. 后补 (-n) 个 0
      其余          → 科学计数法，指数带显式符号
    """
    if isinstance(v, bool):  # bool 是 int 的子类，先挡掉
        raise ValueError("布尔不是数字（修复指引：JCS 只接受 JSON 数字，布尔按 true/false 处理）")
    if isinstance(v, int):
        try:
            v = float(v)
        except OverflowError as exc:
            raise ValueError("整数字面量超出 binary64 范围"
                             "（修复指引：改用可被 IEEE-754 表示的量级，或写成字符串）") from exc
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("数字非有限（I-JSON 不许）"
                         "（修复指引：JSON 不含 NaN/Infinity，请用 null 或字符串）")
    if v == 0.0:            # 覆盖 -0.0：IEEE 下 -0.0 == 0.0
        return "0"
    neg = v < 0.0
    text = repr(abs(v))     # CPython 3.1+ 的 repr 即最短往返
    mant, sep, exp_s = text.partition("e")
    exp = int(exp_s) if sep else 0
    int_part, _dot, frac = mant.partition(".")
    all_digits = int_part + frac
    lead = len(all_digits) - len(all_digits.lstrip("0"))
    digits = all_digits[lead:].rstrip("0") or "0"
    n = exp + len(int_part) - lead
    k = len(digits)
    out = "-" if neg else ""
    if k <= n <= 21:
        return out + digits + "0" * (n - k)
    if 0 < n <= 21:
        return out + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return out + "0." + "0" * (-n) + digits
    m = n - 1
    head = digits[0] + ("." + digits[1:] if k > 1 else "")
    return out + head + "e" + ("+" if m >= 0 else "-") + str(abs(m))


def _escape(s):
    """最小转义（JCS §3.2.2.2）：仅引号、反斜杠与 C0 控制字符；未配对代理 fail-closed。"""
    parts = ['"']
    for ch in s:
        if ch in _ESCAPES:
            parts.append(_ESCAPES[ch])
        elif ord(ch) < 0x20:
            parts.append(f"\\u{ord(ch):04x}")
        elif 0xD800 <= ord(ch) <= 0xDFFF:
            raise ValueError("字符串含未配对代理（I-JSON 不许）"
                             "（修复指引：改用成对代理，或直接写 UTF-8 字符）")
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def _emit(v, out):
    if v is None:
        out.append("null")
    elif v is True:
        out.append("true")
    elif v is False:
        out.append("false")
    elif isinstance(v, str):
        out.append(_escape(v))
    elif isinstance(v, (int, float)):
        out.append(_es_number(v))
    elif isinstance(v, list):
        out.append("[")
        for i, item in enumerate(v):
            if i:
                out.append(",")
            _emit(item, out)
        out.append("]")
    elif isinstance(v, dict):
        out.append("{")
        for i, key in enumerate(sorted(v, key=_utf16_key)):
            if i:
                out.append(",")
            out.append(_escape(key))
            out.append(":")
            _emit(v[key], out)
        out.append("}")
    else:
        raise ValueError(f"不支持的 JSON 值类型：{type(v).__name__}"
                         "（修复指引：入参须来自 loads_strict 的 JSON 值）")


def canonical_jcs(doc):
    """RFC 8785 规范化字节（无尾换行）。"""
    out = []
    _emit(doc, out)
    return "".join(out).encode("utf-8")


def _reject_constant(name):
    raise ValueError(f"非有限数（I-JSON 不许）：{name}"
                     "（修复指引：JSON 不含 NaN/Infinity，请用 null 或字符串）")


def _pairs_hook(pairs):
    seen = set()
    out = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"重复键（I-JSON 不许）：{key}"
                             "（修复指引：合并为一键，或把多个值改成数组）")
        seen.add(key)
        out[key] = value
    return out


def loads_strict(text):
    """严格 JSON 读入（重复键 / NaN / Infinity 一律拒，不静默降级）。"""
    return json.loads(text, object_pairs_hook=_pairs_hook, parse_constant=_reject_constant)


def main() -> int:
    ap = argparse.ArgumentParser(description="canonical JSON（--rule nf=仓库口径 / jcs=RFC 8785）")
    ap.add_argument("--file", required=True, help="输入 JSON 文件")
    ap.add_argument("--rule", default="nf", choices=("nf", "jcs"),
                    help="nf=仓库内部口径（默认）；jcs=RFC 8785")
    args = ap.parse_args()
    try:
        raw = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"读不到 {args.file}：{exc}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print("输入不是合法 UTF-8", file=sys.stderr)
        return 1
    try:
        if args.rule == "jcs":
            body = canonical_jcs(loads_strict(raw))
        else:
            body = attest.canonical(json_doc.loads(raw, None, what="输入 JSON"))
    except ValueError as exc:
        print(f"输入不是合法 JSON：{exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(body)
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
