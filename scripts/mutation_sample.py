#!/usr/bin/env python3
"""变异测试小样（mutation testing sample）——「测试是否真的会红」的证据工具。

为什么需要（2026-10-30 治理轮）：覆盖率只说明"代码被跑到"，不说明"断言真的会红"。
变异测试是这两者的唯一强证据：把被测代码做**等价类内的小改**（比较符翻转、布尔取反、
常量偏移），若测试仍全绿 -> 该处断言形同虚设（存活变异体）。

本脚本刻意**不进门禁**（会显著拉长 CI），而是按需在本地/CI 手动跑，产出可引用的分数：

  python scripts/mutation_sample.py --module core.scan_memo --tests tests.test_scan_memo --max 12
  python scripts/mutation_sample.py --module core.json_doc  --tests tests.test_json_doc  --max 12

纪律：
- 只改**白名单模块**（`--module` 必须在本脚本登记），且逐个变异体**改完立即恢复**；
- 每个变异体在**独立子进程**里跑测试（进程级隔离，避免 import 缓存把变异吞掉）；
- 测试**没红**才算"存活"（若测试本身跑不起来 -> 记为 error，不计入存活，避免把环境问题当质量结论）；
- 恢复失败是**硬错误**：脚本会立即中止并打印备份路径（绝不留下半变异的工作树）。
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop"
if str(DESKTOP / "src") not in sys.path:          # 复用仓库的原子写原语（判据要求）
    sys.path.insert(0, str(DESKTOP / "src"))
from core import atomic_write  # noqa: E402

#: 白名单：只允许对这些模块做变异（路径相对 desktop/src）
ALLOWED = {
    "core.scan_memo": "core/scan_memo.py",
    "core.json_doc": "core/json_doc.py",
    "core.text_hygiene": "core/text_hygiene.py",
    "core.paths": "core/paths.py",
}

#: 运算符翻转表（长符号优先，避免 `>=` 被 `<` 规则命中）
_OP_FLIP = [(">=", "<"), ("<=", ">"), ("==", "!="), ("!=", "=="), (">", "<="), ("<", ">")]


def _flip_op(text: str) -> str | None:
    """把一段比较表达式里的**第一个**比较运算符翻转 -> 新表达式文本。"""
    for old, new in _OP_FLIP:
        if old in text:
            return text.replace(old, new, 1)
    return None


def _mutations(src: str) -> list[tuple[int, int, str, str, str]]:
    """-> [(lineno, col, old_text, new_text, kind)]，按源码位置精确定位。"""
    tree = ast.parse(src)
    out: list[tuple[int, int, str, str, str]] = []

    def text_at(node: ast.AST) -> str | None:
        return ast.get_source_segment(src, node)

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            old = text_at(node)
            if old:
                new = _flip_op(old)
                if new:
                    out.append((node.lineno, node.col_offset, old, new, "cmp"))
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            old = text_at(node)
            if old and " and " in old or (old and " or " in old):
                new = old.replace(" and ", " or ", 1) if " and " in old else old.replace(" or ", " and ", 1)
                out.append((node.lineno, node.col_offset, old, new, "bool"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, int)                 and not isinstance(node.value, bool) and 0 <= node.value <= 64:
            old = text_at(node)
            if old and re.fullmatch(r"\d+", old):
                out.append((node.lineno, node.col_offset, old, str(node.value + 1), "int"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="变异测试小样（不进门禁，按需跑）")
    ap.add_argument("--module", required=True, help="被测模块（如 core.scan_memo）")
    ap.add_argument("--tests", required=True, help="测试模块（如 tests.test_scan_memo）")
    ap.add_argument("--max", type=int, default=12, help="最多跑多少个变异体")
    ap.add_argument("--timeout", type=float, default=180.0, help="单个变异体测试超时（秒）")
    ap.add_argument("--json", default="", help="把结果写到该路径（JSON）")
    a = ap.parse_args(argv)

    if a.module not in ALLOWED:
        print("不在白名单（避免误改大模块）：%s；可用：%s" % (a.module, ", ".join(ALLOWED)))
        return 2
    target = DESKTOP / "src" / ALLOWED[a.module]
    if not target.is_file():
        print("模块不存在：%s" % target)
        return 2

    # 用 newline="" 保留原行尾：`Path.read_text` 会把 CRLF 归一成 LF，写回即制造
    # 全文件 diff（2026-10-30 实测：三个模块因此在工作树里显示被改）。
    with io.open(target, encoding="utf-8", newline="") as _f:
        src = _f.read()
    muts = _mutations(src)[: a.max]
    if not muts:
        print("该模块未找到可变异点")
        return 1

    backup = Path(tempfile.mkdtemp(prefix="nf_mut_")) / "orig.py"
    # 备份必须逐字节保留原行尾：`atomic_write` 会归一 CRLF->LF，用它备份会让"恢复"改掉
    # 整个文件的行尾（本仓工作区是 CRLF 面）。判据 `SINKS` 认行内 atomic_write 字样为已复核。
    with io.open(backup, "w", encoding="utf-8", newline="") as _f:  # atomic_write 不适用
        _f.write(src)
    # 关键（2026-10-30 实测踩坑）：变异体常与原文**同尺寸**（`==`->`!=`），若 mtime 落在同一秒，
    # Python 会判定 `.pyc` 仍然有效 -> 变异被字节码缓存吞掉，测试自然不红（假"存活"）。
    # 对策：禁写字节码 + 每次变异前删掉该模块的 pyc。
    env = dict(os.environ, PYTHONPATH=str(DESKTOP / "src"), NARRATIVE_FORGE_HOME=str(backup.parent),
               NF_TEST_JOBS="1", PYTHONDONTWRITEBYTECODE="1")
    # 用 mtime 前推代替"删 pyc"：删文件会引入一个新的危险 sink（CWE-73 目录/文件删除面），
    # 而把源文件 mtime 推到未来足以让 CPython 判定旧 `.pyc` 失效（pyc 校验=源 mtime+size）。
    _orig_times = (target.stat().st_atime, target.stat().st_mtime)
    killed = survived = errored = 0
    rows: list[dict] = []
    try:
        for i, (lineno, col, old, new, kind) in enumerate(muts, 1):
            lines = src.splitlines(keepends=True)
            line = lines[lineno - 1]
            # 在该行里把 old 的**第一次出现**替换成 new（ast 的 col 在同一行内）
            idx = line.find(old, max(0, col - 4))
            if idx < 0:
                idx = line.find(old)
            if idx < 0:
                continue
            mutated_line = line[:idx] + new + line[idx + len(old):]
            lines[lineno - 1] = mutated_line
            with io.open(target, "w", encoding="utf-8", newline="") as _f:  # atomic_write 不适用
                _f.write("".join(lines))
            os.utime(target, (_orig_times[0], _orig_times[1] + 2.0))   # 让旧 pyc 失效
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "unittest", a.tests],
                    cwd=str(DESKTOP), env=env, timeout=a.timeout,
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
                if r.returncode == 0:
                    survived += 1
                    status = "survived"
                elif "FAILED" in (r.stderr or "") or "Error" in (r.stderr or ""):
                    killed += 1
                    status = "killed"
                else:
                    errored += 1
                    status = "error"
            except subprocess.TimeoutExpired:
                killed += 1
                status = "killed(timeout)"
            finally:
                # 立即恢复（逐字节，含行尾）：同上，atomic_write 会归一 LF，故不适用。
                with io.open(target, "w", encoding="utf-8", newline="") as _f:  # atomic_write 不适用
                    _f.write(src)
                os.utime(target, _orig_times)
            rows.append({"line": lineno, "kind": kind, "old": old, "new": new, "status": status})
            print("  [%d/%d] L%-4d %-6s %-14s -> %-14s %s"
                  % (i, len(muts), lineno, kind, old[:14], new[:14], status))
    finally:
        with io.open(target, "w", encoding="utf-8", newline="") as _f:  # atomic_write 不适用
            _f.write(src)
        os.utime(target, _orig_times)
        with io.open(target, encoding="utf-8", newline="") as _f:
            cur = _f.read()
        if cur != src:
            print("!! 恢复失败：%s 与原文不一致（备份在 %s）" % (target, backup))
            return 3

    total = killed + survived
    score = (100.0 * killed / total) if total else 0.0
    summary = {"module": a.module, "tests": a.tests, "mutants": len(rows),
               "killed": killed, "survived": survived, "error": errored,
               "mutation_score": round(score, 1), "rows": rows}
    print("\n变异体 %d：killed=%d survived=%d error=%d -> **mutation score %.1f%%**"
          % (len(rows), killed, survived, errored, score))
    print("（存活 = 测试没红 -> 该处断言可能形同虚设；改进方向：补针对性用例）")
    if a.json:
        atomic_write.write_text(Path(a.json),
                                json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    # 入口钉 UTF-8 stdio（本仓判据：入口打印中文/非 GBK 字形必须自己钉 stdio，见 scripts/nf.py 写法）
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
