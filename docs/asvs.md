# OWASP ASVS 5.0.0 Level 2 作用域评估

> 标准版本：OWASP Application Security Verification Standard 5.0.0（提交
> `5cf9b032440be53ce345ab3c130fda46ba1ce7a2`）。这是内部、按风险裁剪的证据评估，
> **不是第三方 ASVS 认证**。

## 作用范围

本评估覆盖 NinFenz 本地运行时的真实攻击面：CLI、daemon IPC、MCP stdio、plugin host、
文件与路径处理、配置、密钥使用、日志和错误处理。

纳入章节：

- V1 Encoding and Sanitization
- V2 Validation and Business Logic
- V4 API and Web Service
- V5 File Handling
- V6 Authentication
- V7 Session Management
- V8 Authorization
- V11 Cryptography
- V12 Secure Communication
- V13 Configuration
- V14 Data Protection
- V15 Secure Coding and Architecture
- V16 Security Logging and Error Handling

V3、V9、V10、V17 因没有浏览器前端、自包含用户令牌、OAuth/OIDC 服务端或 WebRTC 面而排除。
V4、V6、V12 虽纳入适用性审查，但逐项结论可以是 `not-applicable`；例如本项目没有 HTTP、
GraphQL、WebSocket、密码/MFA 登录或远程网络监听面。daemon 的短期令牌属于本地会话与授权，
在 V7、V8 中评估。

## 判定口径

- `enforced`：仓内有实现、边界测试或机读证据，且当前评估未发现必需缺口。
- `partial`：控制存在，但覆盖不完整、缺少专门验证，或仍依赖人工判断。
- `not-applicable`：当前运行时没有该控制对应的攻击面；必须记录具体理由。

`partial` 与 `not-applicable` 都必须带 gap。矩阵不会把“写了文档”自动等同于“控制已执行”。

当前结果：

- 需求：191 条
- `enforced`：82 条
- `partial`：0 条
- `not-applicable`：109 条

输入规则、数据分类、密码算法、通信路径、授权、资源上限、生产默认值和发布约束由
`packaging/security/application-security-controls.json` 统一登记，并由
`desktop/src/core/security_controls.py` 对照代码常量与负例测试校验。人读说明见
[security-controls.md](security-controls.md)。

## 重点控制

- daemon 只监听回环地址，并要求每次进程启动生成的 256 位 CSPRNG 令牌。
- 令牌比较使用 `hmac.compare_digest`；状态文件在 POSIX 上收紧为 `0600`。
- daemon 同时执行空闲超时与绝对最大寿命；默认绝对寿命为 24 小时，可用
  `NF_DAEMON_MAX_LIFETIME` 调整，`0` 表示显式关闭。
- MCP 入站、快照、资源正文、出站消息均有硬上限；工具参数通过封闭 schema 校验。
- plugin host 使用 wasmtime fuel、墙钟超时、有界 stdin/stdout/stderr，且默认不授予
  filesystem、network 或 environment 能力。
- 文件路径先做跨平台词法拒绝，再做 realpath 包含性校验。
- 所有准入的本地文件类型都必须通过扩展名与内容一致性校验；仓库读取边界在返回正文前执行。
- 密码原语通过版本化 suite registry 选择，当前提供 `v1`（SHA-256）与 `v2-sha512`，
  禁止未知 suite。
- 安全事件使用 UTC 时间、结构化字段、单行转义和常见凭据形态遮蔽。
- 后台 daemon 的 stderr 追加到 `<NF_HOME>/daemon.log`；安全事件同时写入哈希链审计文件，
  并转发到 Windows Event Log 或 POSIX syslog 的逻辑独立日志面。

### 安全日志清单

| 通道 | 事件 | 格式 | 落点 | 保护 |
|---|---|---|---|---|
| daemon 前台/后台 | 启动、停止、请求拒绝、授权失败、内部错误、连接错误 | `UTC + JSON object` 单行 | stderr；`daemon start` 时追加到 `<NF_HOME>/daemon.log`；链式 `security-audit.jsonl` | 凭据形态遮蔽、控制字符转义；POSIX 日志文件 `0600` |
| 宿主独立日志 | 与本地安全事件相同 | JSON 记录与链摘要 | Windows Event Log Application / POSIX syslog AUTH | 宿主日志 ACL 与保留策略；NF 进程外留存 |
| CLI 结果面 | 用户请求的正常输出 | 命令自身协议 | stdout | `NF_DEBUG=1` 才展示额外异常 |
| MCP 协议面 | JSON-RPC 正常与错误响应 | 单行 JSON-RPC 2.0 | stdout | 对外内部错误统一为 `Internal error` |

- daemon 内部异常对客户端只返回通用错误；异常类型进入安全事件，不回传路径、traceback 或令牌。

## 运行判据

```bash
python scripts/asvs_policy.py
python scripts/asvs_policy.py --json
python scripts/generate_asvs_matrix.py --write
```

更新 ASVS 固定提交或生成器策略时才运行 `generate_asvs_matrix.py --write`；CI 只校验已提交矩阵，
不依赖网络。

## 边界

- 没有外部评估员的独立访谈、渗透测试和证据抽样，因此不能表述为“ASVS Level 2 认证通过”。
- 当前作用域内没有 `partial`；策略门禁把任何控制退回 `partial` 视为基线回归。
- V6/V12 的逐项 N/A 取决于当前产品边界。若以后新增远程 HTTP transport、用户账号或 OAuth，
  必须重新纳入适用性评估。
