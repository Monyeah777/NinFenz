type: fix
surface: runtime-security
note: 守护进程 cwd 经 realpath 后必须位于受信仓库根内，越界请求 fail-closed
