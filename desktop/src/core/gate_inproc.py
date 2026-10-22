#!/usr/bin/env python3
"""把 verify.sh 里 checkN 的 `$PY3 - <<'PYEOF' … PYEOF` 段**在当前进程内**执行（L-A 的核心）。

为什么这么做
------------
实测：全量门禁 1462 s 中 check12 占 1408 s，其余 39 条合计 54 s；而这 54 s 里有相当比例是
**解释器启动税**——`verify.sh` 一共起 42 次 `$PY3`。这些 heredoc 里的判据本体（合计 1607 行）
本来就是纯 Python，完全可以同进程跑掉。

**本模块不做的事（关键纪律）**
- **不改写判据**：heredoc 的源码**逐字照抄**过来执行，绝不「顺手优化」或重写逻辑；
- **不猜结论**：退出码仍由 heredoc 自己的 `sys.exit(1 if … else 0)` 决定。

怎么处理 `sys.exit`
-------------------
heredoc 普遍以 `sys.exit(1 if problems else 0)` 收尾。若直接 exec，它会**杀掉调用进程**
（门禁引擎自己）。故执行时把名字 `sys` 绑定到一个**只替换 `exit` 的 shim**，让
`sys.exit(n)` 抛一个可捕获的内部异常；`sys.path` 等其余属性原样转发。

stdout 也会被捕获：verify.sh 把这些输出重定向到 `$NFL_TMP/nf_checkN.log`，门禁只在失败时
回显它的尾部；本模块同样回传，供 `no "…$(tail -3 …)"` 的等价实现使用。
"""
from __future__ import annotations

#: 显式拿 builtins 模块：`__builtins__` 在「模块 vs dict」两种形态间摇摆（实测踩过
#: `TypeError: vars() argument must have __dict__ attribute`），不用它。
import builtins as _builtins
import contextlib
import io
import os
import re
import runpy
import sys
import tempfile
from pathlib import Path
from typing import Any

from core import repo_trust  # H1 信任门（叶子件：只做 origin 判定，无反向依赖）

#: heredoc 起始行：`    if "$PY3" - <<'PYEOF' >"$NFL_TMP"/nf_checkNN.log 2>&1`
#:
#: **不要写成 `^\s*.*"…"`**（2026-10-15 实测被本仓 redos_scan 判红）：`\s*` 与 `.*` 匹配的
#: 字符集重叠，不命中时会在两者之间指数级重分配起点，65536 字符输入实测 **1598 ms**
#: （预算 1500 ms）。`.*` 本就能吃掉前导空白，故去掉 `\s*`；只找标记，故去掉尾部 `.*$`。
_HEREDOC_START = re.compile(r'^.*"\$PY3"\s+-\s+<<\'(\w+)\'')
_HEREDOC_LOG = re.compile(r'>>?\s*"\$NFL_TMP"/(\S+?)\s')


class _Exit(Exception):
    """`sys.exit(n)` 的进程内替身（不杀调用进程）。"""

    def __init__(self, code: Any = 0) -> None:
        super().__init__(code)
        self.code = code if isinstance(code, int) else (0 if code is None else 1)


class _SysShim:
    """转发除 `exit` 之外的一切到真 sys；`exit` 换成抛 `_Exit`。"""

    def __init__(self, real: Any) -> None:
        self._real = real

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def exit(self, code: Any = 0) -> None:
        raise _Exit(code)


def extract_heredoc(text: str, num: int) -> tuple[str, str] | None:
    """取出 checkN 的 heredoc 源码 → (源码, 日志文件名)；没有则 None。

    切法：从 `<<'PYEOF'` 那行之后，到**顶格**的结束标记那行为止，逐字保留。
    """
    lines = text.splitlines()
    head = "check%d(){" % num
    i = next((k for k, ln in enumerate(lines) if ln == head), None)
    if i is None:
        return None
    end = next((k for k in range(i + 1, len(lines)) if lines[k] == "}"), len(lines))
    body = lines[i:end]
    for k, line in enumerate(body):
        m = _HEREDOC_START.match(line)
        if not m:
            continue
        marker = m.group(1)
        logm = _HEREDOC_LOG.search(line)
        logname = logm.group(1) if logm else "nf_check%d.log" % num
        for j in range(k + 1, len(body)):
            if body[j].strip() == marker:
                return "\n".join(body[k + 1:j]) + "\n", logname
    return None


def run_inproc(src: str, root: Path, name: str) -> tuple[int, str]:
    """在当前进程内跑一段 heredoc 源码 → (退出码, 捕获的输出)。

    **必须在仓库根下执行**：verify.sh 的 heredoc 大量使用相对路径
    （`scripts/nf.py`、`desktop/src/core/...`、`04_模块库/...`）。bash 跑门禁时 cwd 就是
    仓库根，而引擎可能被从任意目录调起（例如 `cd desktop && python -m unittest`），
    不切 cwd 就会 `FileNotFoundError: desktop/scripts/nf.py`（实测踩过）。
    故这里显式切到 root，结束后还原（保留调用方原 cwd）。
    """
    # H1 纵深防御（2026-10-22）：本函数会 exec 目标仓库的源码，任何直接调用也算跨信任边界。
    # 引擎侧已有失败面文案（gate_engine._trust_gate）；这里拒绝**执行**本身（抛，不返回码）。
    repo_trust.assert_trusted(str(root))
    src_dir = str(root / "desktop" / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    shim = _SysShim(sys)
    glb: dict[str, Any] = {
        "__name__": "_nf_inproc_{}".format(name),
        "__builtins__": __builtins__,
        "sys": shim,
    }
    buf = io.StringIO()
    code = 0
    old_cwd = os.getcwd()
    try:
        os.chdir(str(root))
    except OSError as exc:       # 尽力而为：切不进去就按当前 cwd 跑，理由落诊断面
        _CHDIR_FAILURES.append(str(exc))
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(src, "<verify.sh:{}>".format(name), "exec"), glb)
    except _Exit as e:
        code = int(e.code)
    except SystemExit as e:                     # 万一 heredoc 直接用 SystemExit
        code = int(e.code or 0)
    except BaseException:
        import traceback
        buf.write(traceback.format_exc())
        code = 1
    finally:
        try:
            os.chdir(old_cwd)
        except OSError as exc:   # 还原失败只记诊断，不覆盖已得出的判定
            _CHDIR_FAILURES.append(str(exc))
    return code, buf.getvalue()


def run_script(path: Any, root: Path, name: str) -> tuple[int, str]:
    """在进程内跑一个**独立脚本**（本仓只有 check37 用这条），→ (退出码, 输出)。

    与 `run_check_inproc` 同一纪律：不重写脚本判据，只省掉一层 bash 与一次解释器启动。
    脚本自己调 `sys.exit(n)` 时由 `_sys_shim` 收成返回值，**不杀门禁进程**。
    """
    repo_trust.assert_trusted(str(root))       # H1 纵深防御：见 run_inproc 同款注释
    src_dir = str(root / "desktop" / "src")
    for p in (src_dir, str(root)):
        if p not in sys.path:
            sys.path.insert(0, p)
    buf = io.StringIO()
    code = 0
    old_cwd = os.getcwd()
    try:
        os.chdir(str(root))
    except OSError as exc:       # 尽力而为：切不进去就按当前 cwd 跑，理由落诊断面
        _CHDIR_FAILURES.append(str(exc))
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            runpy.run_path(str(path), run_name="__main__")
    except SystemExit as e:
        code = int(e.code or 0)
    except BaseException:
        import traceback
        buf.write(traceback.format_exc())
        code = 1
    finally:
        try:
            os.chdir(old_cwd)
        except OSError as exc:   # 还原失败只记诊断，不覆盖已得出的判定
            _CHDIR_FAILURES.append(str(exc))
    return code, buf.getvalue()


#: 切 cwd 失败的原因（诊断面；空 = 都切成功）。
_CHDIR_FAILURES: list[str] = []


def tail(text: str, n: int = 3) -> str:
    """verify.sh 的 `tail -n … | tr '\\n' ' '` 等价：取末 n 行拼成一行。"""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return " ".join(lines[-n:]) if lines else ""


#: 跑整个 check 体时用来替换 banner 的哨兵：既保留「banner 被执行一次」的形状，
#: 又能观测到 bash 是否真的走到了那一行。
BANNER_MARK = "\x00nf-banner\x00"

_BANNER_IN_BODY = re.compile(r"^\s*echo\s+'== \[[^']*'\s*$", re.M)


def run_check_inproc(body: str, root: Path, name: str) -> tuple[int, list[str], str]:
    """在进程内跑**整个 check 体**（含 bash 分支）→ (退出码, PASS 文案列表, 输出)。

    与只跑单个 heredoc 的 `run_inproc` 的分工：`run_inproc` 对**多 heredoc** 的 check
    （check 8 / 16 / 35）与「`then` 分支是 `:`」的形态会给出与 bash 不一致的结论；
    本函数把整段 check 体交给 Python 执行，于是 bash 的 `if/then/else`、`err=1` 累积、
    多条 heredoc 的顺序**都真实发生**——分支结构不必被解析器理解。

    做法要点：
      - `echo` 必须被替换掉，否则整段 check 的 banner 会混进「输出」（判据只看 `ok/no/wn`）；
      - banner 那行替换成哨兵打印，用来观测「执行到哪一步」（bash 分支语义的锚点）；
      - `ok/no/wn` 按 verify.sh 的同名函数语义收集文案，故 PASS 文案就是**真执行到的那些**。
    """
    repo_trust.assert_trusted(str(root))       # H1 纵深防御：exec 前拒绝不可信仓库
    for p in (str(root / "desktop" / "src"), str(root)):
        if p not in sys.path:
            sys.path.insert(0, p)

    text = body
    m = _BANNER_IN_BODY.search(text)
    if m:
        text = text[:m.start()] + "print({!r})\n".format(BANNER_MARK) + text[m.end():]

    out_lines: list[str] = []
    passes: list[str] = []

    def _ok(msg: str) -> None:
        passes.append(str(msg))
        out_lines.append("  [PASS] {}".format(msg))

    def _no(msg: str) -> None:
        out_lines.append("  [FAIL] {}".format(msg))

    def _wn(msg: str) -> None:
        out_lines.append("  [WARN] {}".format(msg))

    def _echo(*a: Any) -> None:
        out_lines.append(" ".join(str(x) for x in a))

    class _Print:
        """只认哨兵；其余 print 一律吞掉（check 体自己不会 print）。"""

        def __call__(self, *a: Any, **_k: Any) -> None:
            for x in a:
                if x == BANNER_MARK:
                    out_lines.append("  [BANNER]")

    shim = _SysShim(sys)
    glb: dict[str, Any] = {
        "__name__": "_nf_check_{}".format(name),
        "__builtins__": {**vars(_builtins), "print": _Print()},
        "sys": shim,
        "ok": _ok, "no": _no, "wn": _wn, "echo": _echo,
        "NFL_TMP": os.environ.get("NFL_TMP", tempfile.gettempdir()),
        "PY3": sys.executable,
    }
    code = 0
    old_cwd = os.getcwd()
    try:
        os.chdir(str(root))
    except OSError as exc:       # 尽力而为：切不进去就按当前 cwd 跑，理由落诊断面
        _CHDIR_FAILURES.append(str(exc))
    try:
        exec(compile(text, "<verify.sh:{}>".format(name), "exec"), glb)
    except _Exit as e:
        code = int(e.code)
    except SystemExit as e:
        code = int(e.code or 0)
    except BaseException:
        import traceback
        out_lines.append(traceback.format_exc())
        code = 1
    finally:
        try:
            os.chdir(old_cwd)
        except OSError as exc:   # 还原失败只记诊断，不覆盖已得出的判定
            _CHDIR_FAILURES.append(str(exc))
    return code, passes, "\n".join(out_lines)
