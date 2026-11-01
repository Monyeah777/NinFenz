# 应用安全控制基线

> 机读真源：`packaging/security/application-security-controls.json`。
> 校验入口：`python scripts/asvs_policy.py` 与
> `desktop/tests/test_security_controls.py`。本文只解释控制边界，不替代代码或测试。

本基线覆盖本地 CLI、daemon IPC、MCP stdio、WASM 插件宿主、文件解析、日志、配置和发布。
没有部署远程 HTTP 服务、用户账号系统或数据库。适用范围与 OWASP ASVS 的裁剪依据见
[asvs.md](asvs.md)。

## 输入校验

所有输入面采用封闭 schema 或带界解析器，默认拒绝未知形状：

- CLI 与 daemon JSON 只解码一次 UTF-8，再按 RFC 8259 严格解析；`NaN`、`Infinity` 和
  非标准常量拒绝。
- MCP 工具只接受声明过的 `inputSchema`，未知工具、未知方法和越界参数拒绝；
  单条入站消息、快照、资源正文和出站消息都有硬上限。
- WASM 插件输入作为有界字节载荷交给 wasmtime；宿主不把插件内容当作 Python 或 shell 执行。
- 文件路径先做词法拒绝，再做 realpath 包含性校验；越界、符号链接逃逸和超长 URI 拒绝。
- 类型检查先于值域检查；组合字段检查 schema、引用闭包、角色关系和运行时可寻址性。
- 原子读改写使用同目录替换和跨进程锁；失败时保留旧状态，不暴露半写入文件。

动态代码执行只存在于 `nf verify` 对目标仓库门禁脚本的兼容路径。外部仓库默认拒绝，
安装根以外仓库必须通过 `--trust-repo` 或显式 owner opt-in，且拒绝路径无执行副作用。

## 文件处理

运行时没有文件上传服务，也不解压用户提供的归档。处理的本地内容类型包括 JSON、JSONL、
CSV、Markdown、YAML、TOML、GraphML 和 WASM。JSON/schema 面、路径包含性和 WASM
运行时验证在准入时执行；恶意或损坏文件以有界错误拒绝，不转成宿主代码执行。

当前不声称对所有本地文本格式做 magic-byte 内容识别。这是 ASVS V5.2.2 的保留缺口；
新增文件上传或归档摄取前必须先补类型嗅探、压缩前后大小和成员数上限。

## 授权

授权默认拒绝：

- daemon 命令执行要求当前进程启动时生成的 256 位令牌；
- MCP 只暴露显式登记过的只读工具和资源，写工具不存在；
- WASM 插件默认无 filesystem、network 和 environment 能力，只有 manifest 显式授予才开放；
- 目标仓库代码默认不可执行，必须由调用者显式承担信任风险。

## 密码算法清单

机读清单固定当前允许的算法和密钥来源：

| 用途 | 算法/机制 | 密钥来源 | 生命周期 |
|---|---|---|---|
| daemon 会话认证 | `secrets.token_hex(32)` | 操作系统 CSPRNG | 每次启动重生成，关闭时清除 |
| 内容与回执完整性 | SHA-256 | 无密钥摘要 | 随内容版本 |
| 令牌/MAC 比较 | `hmac.compare_digest` | 无密钥机制 | 每次比较 |

算法清单变更必须经过发布审查，同步更新测试、兼容性分析和本文件。当前算法不由运行时协商，
因此 ASVS V11.2.2 保持 `partial`：升级需要受审查的版本发布，而不是在线替换。

## 通信清单

运行时只有三条本地通信路径：

| 路径 | 传输 | 鉴权 | 最小权限 |
|---|---|---|---|
| NF CLI → daemon | `127.0.0.1` TCP | 进程令牌 | 当前 OS 用户 |
| MCP 客户端 → NF | stdio JSON-RPC | 父进程管道所有权 | 只读工具/资源白名单 |
| 插件宿主 → WASM | 有界子进程 + wasmtime | 本地子进程 | manifest 能力默认拒绝 |

运行时不发起业务网络请求，也不接受用户提供的外部连接地址。发布构建访问的依赖源另行由
`packaging/supply-chain/package-sources.json` 的 HTTPS allowlist 约束。

## 数据分类

| 类别 | 机密性 | 完整性 | 日志与保留 |
|---|---|---|---|
| 公开协议/回执/发布元数据 | 公开 | SHA-256、提交历史和 checksums | 可记录；随仓库与发布保留 |
| 本地配置 | 当前 OS 用户 | 原子写和跨进程锁 | 只记元数据；用户删除为止 |
| daemon 会话密钥 | POSIX `0600`；Windows 继承用户 ACL | 常量时间比较 | 禁止记录；进程结束清除 |
| 安全事件 | 属主本地日志 | 单行追加记录 | 清洗后记录；按宿主策略保留 |
| 插件载荷 | 仅调用内存 | WASM 验证和有界缓冲 | 只记元数据；调用结束释放 |

敏感数据的保护要求与实际实现由机读清单逐类绑定；新增数据类别时必须同时定义访问、完整性、
日志和保留策略。

## 资源上限

耗时或占内存的功能都有显式预算：

- daemon 请求 1 MiB、响应 16 MiB；默认空闲寿命 1 小时、绝对寿命 24 小时。
- MCP 单消息 8 MiB、快照 32 MiB、资源正文 8 MiB、出站消息 16 MiB。
- WASM 插件输入和输出各 8 MiB；默认墙钟 30 秒，并有 fuel 与宿主超时双保险。
- daemon argv、cwd、URI、查询条数和回包字段数都有上限。

文档入口、传输上限和实现常量不一致时，ASVS 校验器失败。

## 日志保护

安全事件使用 UTC、单行 JSON、控制字符转义和凭据形态遮蔽。daemon 后台日志追加到
`<NF_HOME>/daemon.log`；POSIX 文件权限为 `0600`，Windows 继承当前用户目录 ACL。

当前日志不是不可变 WORM 存储，也没有自动发送到逻辑隔离的日志分析系统。因此：

- V16.4.2 保持 `partial`：本地属主可修改日志，缺少外部不可变锚；
- V16.4.3 保持 `partial`：没有独立日志汇聚、检测、告警和升级基础设施。

## 生产环境

调试模式默认关闭。只有显式设置 `NF_DEBUG` 才在本地 stderr 展示额外异常；daemon 对客户端
始终返回通用内部错误，不返回 traceback、令牌或目标路径。npm payload 通过 allowlist 排除测试、
开发和 VCS 文件，并由发布自检再次核验。

## 发布与依赖

Critical 漏洞停止发布；High 阻断合并与 tag，除非有可达性证据或显式风险处置；Medium 进入下一
维护窗口。依赖源、供应商、许可证、VEX 和 SBOM 分别由供应链清单校验。

发布构建连续构建两次并逐字节比较，产出 CycloneDX 1.6、SPDX 3.0.1、OpenVEX、checksums
和 release metadata。GitHub OIDC 生成 build provenance 与 VSA。当前声明仅限
`SLSA_BUILD_LEVEL_2`；共享 GitHub runner 仍是 L3 readiness 的 trusted-builder blocker，
不得因签名存在而虚标 Build L3。

## 判据

```bash
python scripts/asvs_policy.py
python -m pytest desktop/tests/test_security_controls.py -q
python scripts/slsa_l3_readiness.py
```

控制清单、代码常量、人读文档或负例测试任一漂移都会失败。
