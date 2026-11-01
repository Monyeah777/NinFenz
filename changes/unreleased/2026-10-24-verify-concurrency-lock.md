type: fix
surface: ci
note: 同仓 verify 门禁增加进程级排他锁；并发运行明确等待或超时拒绝，避免共享 npm payload 中间态造成假红

