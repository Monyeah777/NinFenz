type: fix
surface: security
note: 原子替换后 fsync 父目录并保留既有 POSIX 权限；MCP 可缓存结果 TTL 固定一小时上限，保留字段不可被 payload 覆盖；守护 cwd 仅允许仓库根内目录
