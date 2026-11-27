"""daemon 私有子模块 _const：协议/体量上限常量与守护拒跑命令集。

门面 core.daemon 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations


PROTO = 1

#: 监听地址：**只允许回环**（与 scripts/serve_decision_model.py 同一条纪律；本模块不提供
#: 「显式放行外网」的开关——守护进程能执行任意 nf 命令，绝不能出回环）。
BIND_HOST = "127.0.0.1"

#: 请求体上限（1 MiB）：一条命令的 argv 远小于此；设上限防「自称超长」的无界读。
MAX_REQUEST_BYTES = 1 << 20

#: 单次响应载荷上限（16 MiB，与 Rust worker 同口径）：防止客户端按伪造/失控长度分配内存。
MAX_RESPONSE_BYTES = 16 << 20

#: 单条 argv 上限（字符）：参数是「命令 + 选项 + 标识符」，不是正文载荷。
MAX_ARGV_CHARS = 8192

#: argv 合计上限（字符）：防「一条 1 MB 请求 → CLI 回吐 200 KB 用法」这类放大。
MAX_ARGV_TOTAL = 65536

#: 工作目录上限（字符）；cwd 只是定位参数，不应成为超长内存/路径解析载荷。
MAX_CWD_CHARS = 32768

#: 守护内**拒跑**的命令：长驻（`serve` / `shell` / `terminal` / `lsp`）与自指（`daemon`）。
#:
# : 为什么是这五个（2026-10-01 修）：此前只有 `serve` / `shell` / `daemon`，于是**别名与常驻面漏网**
# ——
#: `nf terminal`（`shell` 的 argparse 别名）与 `nf lsp`（常驻 stdio 服务）会进守护在进程内执行，
#: 而守护把 stdin 设成空串 ⇒ `lsp` 立刻读到 EOF 后**以 0 退出且零输出**，调用方（编辑器 / agent）
#: 把「静默无事发生」当成成功，直跑却会真的起服务：**同一条命令两条路径两种结果**。
#: 口径：凡是会占住前台的命令，守护一律拒跑（集合与 `core.terminal.BLOCKED_IN_SHELL` 相等，
#: 由 `desktop/tests/test_daemon_parity.py` 的集合判据钉住；别名闭合同件）。
REFUSED_COMMANDS = ("serve", "shell", "terminal", "lsp", "daemon")

#: 连接读写超时（秒）：客户端卡住不得拖死守护。
SOCKET_TIMEOUT = 30.0

#: 帧接收超时（秒）：未认证连接最多占住串行 accept 这么久，随后即断开。
HANDSHAKE_TIMEOUT = 5.0

STATE_NAME = "daemon.json"

#: 关闭「常驻语料层」的开关（诊断/对照用）：设了就整批作废且不再收录，退回每次重读。
RESIDENT_ENV_OFF = "NF_NO_RESIDENT"
