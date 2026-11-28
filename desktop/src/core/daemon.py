#!/usr/bin/env python3
"""NF 执行层常驻守护 —— 把「每条命令一次解释器启动」换成「一次启动、长期热跑」。

**为什么要它（本机实测，2026-09-28）**：裸解释器启动 **146 ms**、`nf --version` **401 ms**
（导入 + argparse ≈ 255 ms）——即**每条命令有 ~400 ms 的固定成本，与命令内容无关**；而同一
命令在热进程里只要 1–5 ms（命令面缓存 v12、内容键缓存 v14–v16 都已就位）。所以「执行层
毫秒级」= 把重活留在常驻进程里，客户端只做一次套接字往返。

**机制借鉴**（工业界的同一范式：`dmypy` / `emacsclient` / `nvim --server` / 语言服务器）：

- **服务端**：只绑 `127.0.0.1` 的 TCP 套接字；回环**不是**信任边界，故另发一次性令牌，
  请求必须带令牌才算数。**单线程串行**处理：不并发跑仓库命令（确定性优先）。
- **协议**（版本化、极简、**纯 bash 可当客户端**）：
    请求 = 一行 JSON：`{"proto":1,"token":"…","cwd":"…","argv":["stats","--check"]}`
    响应 = 三行明文头 + 原始载荷：`<exit>` + `<out_len>` + `<err_len>` + stdout 字节 + stderr 字节
  响应不用 JSON 的原因：客户端常是 shell——`read` 三行 + `head -c` 两个长度即可原样转发，
  不需要 JSON 解码器（也就没有 jq 依赖）。
- **状态**：`<NF_HOME>/daemon.json`（pid/port/token/root/started/proto），`NF_HOME` 复用
  `core.storage.default_home()` 单源；令牌不进日志。
- **新鲜度（关键纪律）**：每次请求前清空**按路径/根键**的进程缓存（`pack_combo` 画像、
  `registry_loader` 注册表），**保留内容键缓存**（围栏 YAML、引用度普查——键即内容，天然
  不陈旧）。于是「热进程」与「新起进程」结果一致：等价性由 `test_daemon` 逐命令比对守住。
- **拒绝面**：长驻/嵌套命令（`serve` / `shell` / `daemon`）在守护内一律拒跑（退出码 2）——
  与终端里「递归长驻拦截」同一条纪律。

边界：本模块**只加速、不改语义**；不写仓库文件（状态只落 NF_HOME）；杀掉守护进程即回到
原来的「每命令一次启动」路径（`scripts/nf` 会静默回退）。
"""

# 读点：请求体解析在 _daemon._proto 里仍走 json_doc.loads（N11）。

from __future__ import annotations

import contextlib
import hmac
import io
import json
import os
import sys

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys as _sys
import types as _types
from pathlib import Path

from core import (
    asset_contract,
    atomic_write,
    disk_cache,
    json_doc,
    pack_combo,
    registry_loader,
    storage,
)
from core import (
    conformance_scan as _csc,
)
from core import (
    conformance_scan as _csc_new,
)
from core import (
    conformance_scan as _csc_old,
)
from core import (
    conformance_scan as csc,
)
from core import (
    disk_cache as _dc,
)
from core import (
    import_graph as _igr,
)

#: 响应缓存（**只在守护进程内、只在树没变时**复用整条命令的 stdout/stderr/退出码）。
#: 判据与账本在 `core.response_cache`（会话 `session_watch` 与守护共用同一套 ⇒ 只有一种说法）。
from core import (
    response_cache as _rc,
)
from core import (
    watch as _watch,
)

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade

# 依赖面：逐字保留原模块 import 面（含函数内 core import 的边）——
# 耦合图/纯度面按模块级 import 计算，勿删（见 re-export 说明）。
#: bash 快路模板（`nf daemon shell-init bash` 原样输出，供 `eval "$(…)"` 装进交互 shell）。
#: 关键点：**全部用 bash 内建**（/dev/tcp + printf + read -N），因此 `nf …` 是当前 shell 里的
#: 一次函数调用 + 一次套接字往返——没有子进程、没有解释器启动，这才是真正的毫秒级客户端。
#: 长驻/自指命令（见 `REFUSED_COMMANDS`）与「无参」一律直落 python 入口（与守护拒绝面一致）。
# 兼容转发面：CLI 与测试读 dm.SHELL_INIT_BASH（模板真源已迁 core.daemon_shell，见其 docstring）。
from core.daemon_shell import SHELL_INIT_BASH  # noqa: E402,F401

#: 观测计数由 `response_cache.STATS` 提供（上面 `_CACHE_STATS` 即同一个字典对象）。
# 兼容转发面：测试读 dm.CACHEABLE_COMMANDS / dm._WRITE_FLAG_PREFIXES；cacheable 本模块自用。
# 真源已迁 core.response_cache（准入表 + 闸门旗标前缀），此处只做对外再导出。
from core.response_cache import _WRITE_FLAG_PREFIXES, CACHEABLE_COMMANDS, cacheable

from ._daemon import _cache, _server
from ._daemon._cache import (
    _CACHE_STATS,
    _CLI_CACHE,
    _WATCH_LOCK,
    _load_cli,
    _sync_resident,
    _watch_generation,
    cache_stats,
    reset_process_caches,
    reset_response_cache,
    set_watcher,
)
from ._daemon._cli import (
    _cli_module,
)
from ._daemon._const import (
    BIND_HOST,
    HANDSHAKE_TIMEOUT,
    MAX_ARGV_CHARS,
    MAX_ARGV_TOTAL,
    MAX_CWD_CHARS,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    PROTO,
    REFUSED_COMMANDS,
    RESIDENT_ENV_OFF,
    SOCKET_TIMEOUT,
    STATE_NAME,
)
from ._daemon._proto import (
    _BoundedBytesIO,
    _check_argv_size,
    _check_json_nesting,
    _configure_server_socket,
    _decode_frame,
    _LineReader,
    _parse_json_request,
    _parse_request,
    _strict_json_object,
    _validated_cwd,
    read_framed,
    run_request,
    send_framed,
)
from ._daemon._server import (
    _internal_error_frame,
    _reap_child,
    _serve_conn,
    main,
    ping,
    query_stats,
    serve_forever,
    start,
    stop,
)
from ._daemon._state import (
    _STATE_WRITE_LOCK,
    _harden_perms,
    clear_state,
    read_state,
    state_path,
    write_state,
)

_install_live_facade(__name__, {
    "_WATCHER": _cache,
    "_CHILD": _server,
})



def _code_fingerprint(root: Path) -> Tuple:
    """`core/*.py` + `scripts/*.py` 的 (相对路径, mtime_ns, size) 指纹（用 scandir，不做 walk）。

    只用一次 `scandir` 就拿到 mtime/size（Windows 上也是单次目录读），实测 ~1–3 ms；
    换来的是「改了源码，下一条命令就用新代码」——否则守护会拿旧逻辑回话，比慢更糟。
    """
    rows = []
    for rel in ("desktop/src/core", "scripts"):
        try:
            with os.scandir(Path(root) / rel) as it:
                for ent in it:
                    if not ent.name.endswith(".py"):
                        continue
                    st = ent.stat()
                    rows.append((rel + "/" + ent.name, st.st_mtime_ns, st.st_size))
        except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
            continue
    rows.sort()
    return tuple(rows)


def _reset_code_fingerprint(root: Path) -> None:
    """清代码面指纹与导入闭包指纹；清不掉不影响重载。"""
    try:
        from core import disk_cache
        disk_cache.reset_code_fingerprint(str(root))
        # 导入图/闭包指纹也要跟着清：代码一变，各派生「自己的代码闭包」可能换了成员
        # （新增 import、换依赖），不清就会拿旧闭包当键。
        from core import import_graph as _igr
        _igr.reset_code_scope(str(root))
    except Exception:                                    # noqa: BLE001 - 清不掉不影响重载
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）


def _save_resident():
    """取常驻语料层（跨代码换版保住）；失败/未激活 → None。"""
    saved = None
    try:
        from core import conformance_scan as _csc_old
        if _csc_old.resident_active():
            saved = _csc_old.take_resident()
    except Exception:                                    # noqa: BLE001
        saved = None
    return saved


def _adopt_resident(saved) -> None:
    """把常驻语料层搬回新模块；搬不回去就下次重读。"""
    if saved is None:
        return
    try:
        from core import conformance_scan as _csc_new  # 重新导入 → 新模块对象
        _csc_new.adopt_resident(saved)
    except Exception:                                    # noqa: BLE001 - 搬不回去就下次重读
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）


def _sync_code(root: Path) -> None:
    """源码变了就整块重载（丢弃 `core.*` 与 CLI 模块）：保证守护不跑旧代码。"""
    fp = _code_fingerprint(root)
    if _CLI_CACHE.get("fp") == fp:
        return
    # 代码换版必须**同时**清掉「代码面指纹」的记忆：否则持久缓存的键还停在旧代码上，
    # 会拿旧算法算出来的账当新账（见 core.disk_cache.code_fingerprint 的说明）。
    _reset_code_fingerprint(root)
    # 常驻语料层跨代码换版**保住**：它装的是仓库事实（正文/目录/逐件摘要），与代码无关；
    # 而 `core.*` 被整块摘掉重载时，新模块会是个**空层**——不搬回来，改一行代码就得让下一条
    # 重命令把整棵语料重读一遍（实测 ~2 s）。
    saved = _save_resident()
    for name in [m for m in list(sys.modules) if m == "core" or m.startswith("core.")]:
        if name != "core.daemon":           # 守护自身模块留着（改它需重启，见模块 docstring）
            sys.modules.pop(name, None)
    _CLI_CACHE.clear()
    _CLI_CACHE["fp"] = fp
    _adopt_resident(saved)


def _run_cli(nf, argv: List[str]) -> int:
    """在重定向环境下跑 guarded_main → 退出码（SystemExit 也收下）。

    **必须走 guarded_main**（2026-10-10 审计 X0，P0）：`main()` 的异常兜底只在
    `cli()` 里，守护直接调 `main()` 会让任何未捕获异常穿出去、**杀死常驻进程**。
    实测触发门槛极低：`protocol/` 下任一 JSON 被截断（18/18）⇒ json.JSONDecodeError
    ⇒ 守护退出、客户端 rc=1 + 零输出。guarded_main 是 CLI 与本守护**共用的同一条
    错误面**（scripts/nf.py 单一实现），故两条路径的错误帧逐字一致。
    """
    try:
        return int(nf.guarded_main(list(argv)))
    except SystemExit as exc:                      # argparse --help 等
        return int(exc.code or 0)


def _reset_after_request() -> None:
    """请求结束清一次：写命令改了仓库，缓存不留残影。"""
    reset_process_caches()
    try:
        from core import conformance_scan as _csc
        _csc.clear_changes()          # 确知变更面**只在当次请求内有效**（否则它单调增长、
    except Exception:                 #  # 几条命令之后会让键层复用退化成全量重算——实测踩过）
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）


def execute(argv: List[str], root: Path, cwd: Optional[str] = None
            ) -> Tuple[int, bytes, bytes]:
    """在**本进程内**执行一条 nf 命令，并把 stdout/stderr 原样抓成字节。"""
    if argv and str(argv[0]) in REFUSED_COMMANDS:
        msg = ("守护进程内拒跑长驻/嵌套命令 `nf %s`"
               "（修复指引：在普通终端里直接跑；守护只承载一次性命令）\n" % argv[0])
        return 2, b"", msg.encode("utf-8")
    if cwd is not None:
        cwd = _validated_cwd(root, cwd)
    _sync_resident(root)          # 常驻层按监听变更集失效（说不清就整批作废）——必须在任何读之前
    # 响应缓存：**只在「树没变」有可证信号时**才可能命中（判据与账本在 core.response_cache）。
    gen, allowed = _watch_generation(), bool(cacheable(argv))
    hit = _rc.lookup(argv, gen, allowed, cwd)
    if hit is not None:
        return hit
    _sync_code(root)          # 源码变了就先重载（否则会用旧逻辑回话）
    reset_process_caches()
    nf = _load_cli(root)
    out_buf = _BoundedBytesIO(MAX_RESPONSE_BYTES)
    err_buf = _BoundedBytesIO(MAX_RESPONSE_BYTES)
    out_txt = io.TextIOWrapper(out_buf, encoding="utf-8", write_through=True)
    err_txt = io.TextIOWrapper(err_buf, encoding="utf-8", write_through=True)
    old_cwd = os.getcwd()
    old_argv, old_stdin = sys.argv, sys.stdin
    code = 0
    try:
        if cwd and os.path.isdir(cwd):
            os.chdir(cwd)
        sys.argv = ["nf"] + [str(a) for a in argv]
        sys.stdin = io.StringIO("")       # 一次性命令不读交互输入（长驻命令已被拒）
        with contextlib.redirect_stdout(out_txt), contextlib.redirect_stderr(err_txt):
            code = _run_cli(nf, argv)
    finally:
        out_txt.flush()
        err_txt.flush()
        sys.argv, sys.stdin = old_argv, old_stdin
        os.chdir(old_cwd)
        _reset_after_request()
    code, out, err = int(code), out_buf.getvalue(), err_buf.getvalue()
    _rc.store(argv, gen, allowed, opts=_rc.Response(code=code, out=out, err=err, cwd=cwd))
    # **非准入命令 = 无法证明只读**（可能写仓库）⇒ 立刻整批作废，不等监听线程异步察觉（写在
    # `note_uncacheable` 里：脚本里 `nf conformance --write; nf score` 连跑曾吃到写之前的旧响应）。
    _rc.note_uncacheable(allowed, code, gen)
    return code, out, err


def _handle_conn(conn: socket.socket, token: str, root: Path) -> bool:
    """处理一条连接 → 是否请求关闭守护。

    **单条请求的异常不得外溢**（2026-10-10 审计 X0，P0）：`execute()` 之外的常驻层/缓存/
    重载异常在这里归一成结构化错误帧；连接仍在场时把帧发回去，让客户端拿到「这次失败了」
    而不是「守护没了」。
    """
    try:
        req = _parse_request(_LineReader(conn))
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        send_framed(conn, 2, b"", ("请求不可读：%s\n" % exc).encode("utf-8"))
        return False
    conn.settimeout(SOCKET_TIMEOUT)
    if req.get("proto") != PROTO:
        send_framed(conn, 2, b"", "proto 不符\n".encode())
        return False
    # D1（2026-10-22 安全审计）：令牌是**唯一信任边界**，比较必须常量时间。
    # 同时拒绝非字符串形态（旧实现里 `!=` 对 dict/list 只是"不相等"，语义上等于合法比较，
    # 但会把"类型错"混进"令牌错"，诊断面就分不清）。
    got_token = req.get("token")
    if not isinstance(got_token, str) or not hmac.compare_digest(got_token, token):
        # 回环不是信任边界：无令牌（或令牌不符）一律拒绝执行
        send_framed(conn, 2, b"", "令牌缺失或不符：拒绝执行"
                                  "（修复指引：用 scripts/nf 启动器，或 nf daemon status）\n"
                                  .encode("utf-8"))
        return False
    op = req.get("op")
    if op is not None:
        if not isinstance(op, str):
            send_framed(conn, 2, b"", "op 必须是字符串\n".encode())
            return False
        if op == "shutdown":
            send_framed(conn, 0, b"", b"")
            return True
        if op == "stats":
            # 观测面必须**在守护进程内**取：缓存与监听件都是守护的进程状态，客户端看不到。
            payload = json.dumps(cache_stats(), ensure_ascii=False).encode("utf-8")
            send_framed(conn, 0, payload, b"")
            return False
        send_framed(conn, 2, b"", "未知 op（允许 shutdown / stats）\n".encode())
        return False
    argv = req.get("argv")
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        send_framed(conn, 2, b"", "argv 必须是字符串列表\n".encode("utf-8"))
        return False
    try:
        cwd = _validated_cwd(root, req.get("cwd"))
    except ValueError as exc:
        send_framed(conn, 2, b"", f"请求不可读：{exc}\n".encode())
        return False
    from core import disk_cache as _dc
    _dc.defer_begin()                # 请求期间：派生结果的写盘只入队
    try:
        code, out, err = execute(argv, root, cwd=cwd)
    except SystemExit as exc:        # 请求级：裸 SystemExit 也归一（不得因它杀死守护）
        _dc.defer_drop()
        code, out, err = int(exc.code or 0), b"", b""
    except Exception as exc:         # noqa: BLE001 - 单条请求失败不得杀死守护（见 _internal_error_frame）
        _dc.defer_drop()             # 异常路径：丢队列（缓存不是事实，丢了只是下次重算）
        code, out, err = 1, b"", _internal_error_frame(exc)
    send_framed(conn, code, out, err)
    # **回包之后再落盘**：写盘是纯写、只供别的进程（冷进程 / 守护重启）用，不该占客户端关键路径
    # （实测：一次新内容状态的落盘在守护口径下值 20–80 ms）。落盘失败也只是丢缓存。
    try:
        _dc.defer_flush()
    except Exception:                                    # noqa: BLE001 - 落盘尽力而为
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）
    return False

if __name__ == "__main__":                                # pragma: no cover - 进程入口
    raise SystemExit(main())
