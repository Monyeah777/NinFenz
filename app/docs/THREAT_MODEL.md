# NF APP 威胁模型（STRIDE + 六信任边界 + 解析面）

> ⛔ 操作指令：本件每条威胁必须绑定**信任边界**、**控制点**、**可复跑判据**与**状态词**。状态只有四值：`enforced`（有代码 + 可复跑判据）/ `partial`（部分在场，缺口指向具体位置）/ `planned`（未实现，**禁止写成已防**）/ `UNOBSERVABLE`（APP 无可观测面，须写理由与缓解）。改本件必须同步 `app/docs/ARCHITECTURE.md` §8 与 `app/docs/PRIVACY.md` 的对应条目。
> 状态：v1（2026-11-15）· 性质：威胁与边界声明（能防 / 不能防）· 取证时刻：2026-11-15 16:5x（本机实测：`pytest app/tests/test_security_negative.py` = **47 passed**；`pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py` = **87 passed / 1 failed**（`nf-project/minimal.json` 夹具与 schema 漂移）；`pytest app/tests` = **197 passed / 7 failed**；`cd app/core && cargo test --offline` = **编译失败 2 处**（E0658/E0605））。
> 依据：`app/docs/CONTRACT.md` §3/§6（解析硬化与安全纪律）、`app/docs/CLI.md`（op/FFI 面）、`app/schema/limits.json`（上限单一真源）、`app/schema/error_codes.json`（错误码单一真源）；上位：`SECURITY.md`（安全通道）、`docs/production/THREAT_MODEL.md`（仓库既有威胁模型范式，编号空间不重叠）。
> 边界口径：本件判 **APP 面**（控制面 + 共享核心 + 端壳契约）。仓库生产平面、Trust Fabric 面、CCOS 内部执行面各有自己的威胁模型，本件不替代、不越级声称。

## 0. 状态词与判定规则

| 状态 | 判定 | 本轮判据 |
|---|---|---|
| `enforced` | 控制点在代码里，且至少一条可复跑判据（测试/门禁）在场并通过 | 逐条在 §4 给路径与命令 |
| `partial` | 部分在场；必须写清缺哪一层（例如「控制面有、核心未落」「实现有、测试未落」） | 缺口写进 §5 OPEN |
| `planned` | 未实现；必须写落点/owner/下一步；报告与文档不得出现「已防」表述 | 进 §5 OPEN |
| `UNOBSERVABLE` | APP 侧没有可观测面；必须写 `reason` 与缓解 | 见 §2 两条例（NF-APP-TH-19、NF-APP-TH-20） |

**分层口径**（避免把「控制面挡了一次」误读为「全链已防」）：

- **最后一道防线** = Python 控制面 `app/cli/nf_app/security.py`（导入/解包/解析/脱敏在控制面先拒一次）。
- **最终权威** = Rust 核心 `app/core`（所有 op 语义的唯一实现；当前 `lib.rs` 为占位 → 核心侧控制点一律 `planned`，不因控制面有实现而升级为 enforced）。
- 因此同一威胁可能出现「控制面 enforced + 核心 planned」两格；这是如实登记，不是矛盾。

## 1. 六条信任边界（B-01…B-06）

| 编号 | 边界 | 边界两侧 | 主要威胁 | 当前控制（落点） | 状态 |
|---|---|---|---|---|---|
| B-01 | 用户输入 ↔ 解析器 | 文件/剪贴板/导入素材 ↔ APP | zip slip/bomb、symlink、YAML bomb、JSON 深度、路径穿越、超大文件 | `app/cli/nf_app/security.py`（`check_rel_path`:74、`inspect_zip_entries`、`extract_zip_safe`、`loads_yaml_secure`、`parse_json_secure`、`safe_join`）；`app/schema/limits.json`；`app/tests/test_security_negative.py` | enforced（控制面）/ planned（核心解析器） |
| B-02 | APP ↔ 外来内容包 | Pack/模板/社区包 ↔ APP | 篡改内容、同版本不同 digest、更新注入、旧版回滚、覆盖用户改动 | `pack-verify`（items/tree 摘要）、`NF-PCK-004`、`pack-diff/pack-merge` 备份+复验+回滚、overlay 冲突三类 | partial（`ops/pack.rs`/`ops/update.rs` 在场；核心编译未过） |
| B-03 | 端壳 ↔ 共享核心 | Kotlin/CMP 端壳 ↔ Rust `nf-app-core` | 未定义行为/panic、内存生命周期、ABI 版本错配、恶意大 JSON 输入 | C ABI 3 函数（`CLI.md` §5）、`nf_app_core_abi_version` 校验、`nf_app_core_free`、panic 兜底 + stderr 诊断 | partial（`ffi.rs` 111 行 + `bin/nf-app-core.rs` 89 行在场；核心编译未过） |
| B-04 | APP ↔ CCOS 执行面 | APP ↔ 外部执行面（持密钥） | 伪造结果、任务被改、密钥外泄、结果无证据 | `ccos-task/1`（`policy.secrets=ccos-only`）→ `ccos-result/1`（`task_digest` 回钉 + artifacts 摘要 + evidence）；`human_review.required` 恒 true；`NF-CCOS-002/003/004` | planned（语义冻结；实现未落） |
| B-05 | APP ↔ 平台 | APP ↔ Android intent/FileProvider/分享面板/剪贴板；Windows/macOS 文件关联/剪贴板 | 伪造深链、越权读取、分享外泄、URI 权限过宽、WebView 升权 | 组件 `exported=false`、路径限定、分享只读 URI + 临时缓存、脱敏前置、WebView（若用）JS/文件/网络全关 | planned（端壳未建 → OPEN-TOOLCHAIN） |
| B-06 | APP ↔ 真源与工具链 | APP ↔ 仓库真源（`protocol/**` 等）/ TUI / 依赖与构建 | 第二真源漂移、篡改真源、依赖注入、构建脚本外联、镜像重定向 | 只按 ID+digest 引用、不改 `protocol/**`、`Cargo.lock` 钉死、构建脚本不取网（`app/scripts/build_core.sh`）、门禁 check1–57 不占用 | partial（锁文件在场；镜像配置偏差 OPEN-SUPPLY-001） |

## 2. STRIDE 威胁矩阵（每类 ≥2 条）

> 编号空间 `NF-APP-TH-xx`；`判据` 列给可复跑命令或落点路径，`planned` 项在 §5 有 owner。

### S — Spoofing（伪造身份/来源）

| 编号 | 威胁 | 攻击面 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-APP-TH-01 | 用同 `id+version` 但内容不同的 Pack 冒充正版 | Pack 分发/导入 | `pack-verify` 逐 item sha256 + tree digest；同 id+version 不同 digest → `NF-PCK-004`（exit 3） | `app/schema/nf-pack.schema.json`（判定语义不变）；实现待 `app/core` 的 `pack-verify` | planned（核心未落） |
| NF-APP-TH-02 | 伪造 CCOS 结果（改 `task_digest`/替换 artifacts） | CCOS 回传文件/zip | `ccos-import-result` 回钉 `task_digest` + artifacts 摘要 + `NF-CCOS-002` | `app/schema/ccos-result.schema.json`；`app/docs/CONTRACT.md` §5.11 | planned |
| NF-APP-TH-03 | 伪造深链/分享 URI 冒充官方来源 | Android intent / 文件关联 | 端壳 `exported=false`、URI 参数校验、FileProvider 路径限定 | `app/docs/CONTRACT.md` §6；端壳 `app/android/**` 未建 | planned（OPEN-TOOLCHAIN） |

### T — Tampering（篡改）

| 编号 | 威胁 | 攻击面 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-APP-TH-04 | 改动 Pack 内文件但保留旧清单 | Pack 安装/使用 | `pack-verify`：manifest schema（L0）→ 逐 item sha256/size → tree digest → `requires`，不符 exit 1 | `app/docs/CLI.md`（`pack-verify` 行）；`app/schema/nf-pack.schema.json` | planned |
| NF-APP-TH-05 | 改项目引用/装配输入使产物与批准对象不一致 | 项目文件 | 引用 `{id,version,digest}` 双钉；digest 不符 → `NF-ASM-001`；评审 `subject_digest` 绑定 | `app/schema/nf-project.schema.json`（refs/review）；`app/schema/nf-assembly-plan.schema.json`（digest） | planned |
| NF-APP-TH-06 | 篡改备份/回滚注入旧版（供应链式降级） | 更新/回滚路径 | 备份 + 复验 + 旧版保留；摘要不符 → `NF-PCK-007`；`id+version` 冲突拒绝 | `app/docs/CONTRACT.md` §5.9；`app/schema/nf-pack-update.schema.json` | planned |

### R — Repudiation（抵赖）

| 编号 | 威胁 | 攻击面 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-APP-TH-07 | 声称「已评审/已批准」但对象已变 | 评审状态机 | `review.approved` 必须带 reviewer + note + `subject_digest`；改一处即失效 | `app/schema/nf-project.schema.json`（review 块）；`app/docs/CONTRACT.md` §5.10 | planned |
| NF-APP-TH-08 | CCOS 结果无证据/无来源（无法追责或复核） | CCOS 回传 | `ccos-result/1` 强制 `evidence` + `report` + `provenance`；人审 required | `app/schema/ccos-result.schema.json`；`app/docs/CLI.md`（`ccos-import-result`） | planned |

### I — Information disclosure（信息泄露）

| 编号 | 威胁 | 攻击面 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-APP-TH-09 | 分享/导出泄露绝对路径、家目录、用户名、邮箱、密钥形状 | 分享/导出（md/zip/json/剪贴板） | `sanitize_text`/`sanitize_obj` 掩码（邮箱、Windows 家目录、盘符路径、NIX 家目录/路径、AWS/OpenAI/GitHub/Slack/私钥/Bearer）；脱敏后仍命中 → `NF-E-002` 拒发 | `app/cli/nf_app/security.py:318-399`；`app/tests/test_security_negative.py`（`test_sanitize_*`、`test_assert_share_safe_*`） | enforced（控制面） |
| NF-APP-TH-10 | 诊断/日志把路径/内容带出设备 | 诊断目录/崩溃上报 | 诊断只落本地 `diagnostics/`、无出站、无崩溃上报（C-05） | 设计口径见 `app/docs/ARCHITECTURE.md` §8；端壳未建 | planned |
| NF-APP-TH-11 | 剪贴板回填把敏感内容静默带进项目 | 剪贴板 → 导入 | 回填走普通 `nf-import/1`（DraftProject，不覆盖）；解析硬化与上限同一套；预览 | `app/schema/nf-import.schema.json`；`security.py` 解析函数 | partial（解析侧 enforced；回填流未落） |
| NF-APP-TH-12 | 用户名单独出现（非家目录路径）未被脱敏 | 分享文本 | 当前仅覆盖「路径中的用户名」；裸用户名无检测 | `app/cli/nf_app/security.py:320-324`（正则集合）→ 缺口已登记 OPEN-PRIVACY-01 | partial |

### D — Denial of Service（拒绝服务/资源耗尽）

| 编号 | 威胁 | 攻击面 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-APP-TH-13 | zip bomb（高压缩比/超总量/超条目/深嵌套） | zip 解包 | `limits.zip`：条目 ≤5000、总量 ≤512 MiB、单文件 ≤64 MiB、压缩比 ≤100:1、嵌套 ≤1；超限 `NF-SEC-003` | `app/schema/limits.json`；`security.py`（`inspect_zip_entries`/`extract_zip_safe`）；负例 6 条（`test_zip_bomb_ratio_rejected` 等） | enforced（控制面） |
| NF-APP-TH-14 | YAML alias bomb / JSON 深度炸栈 | YAML/JSON 导入 | `limits.yaml`（别名展开 ≤1000、深度 ≤64）→ `NF-SEC-004`；`limits.json`（深度 ≤64、字节 ≤64 MiB）→ `NF-IMP-003` | `app/schema/limits.json`；`security.py`（`loads_yaml_secure`/`parse_json_secure`）；负例 `test_yaml_*`、`test_json_depth_rejected` | enforced（控制面） |
| NF-APP-TH-15 | 超大导入/装配把端壳卡死（无流式/无进度） | 端壳 UI | 上限（`limits.text.max_chars` 等）+ 端壳分块/取消（未实现） | 上限：`app/schema/limits.json`；端壳：未建 | partial（上限 enforced；UI 侧 planned） |

### E — Elevation of privilege（越权/提权）

| 编号 | 威胁 | 攻击面 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-APP-TH-16 | 解包路径穿越把文件写到 APP 私有目录之外（zip slip/symlink/junction/硬链） | zip/解包 | `check_rel_path`（禁绝对/盘符/UNC/`..`/反斜杠/控制字符/保留设备名）+ `extract_zip_safe` + symlink 拒绝 `NF-SEC-002`、slip `NF-SEC-001` | `app/cli/nf_app/security.py:74`、`:98`；`app/tests/test_security_negative.py` 9 条（含拒绝后不产生侧写 `test_extract_zip_safe_slip_writes_nothing_outside`） | enforced（控制面） |
| NF-APP-TH-17 | intent/FileProvider 被外部应用利用读取任意文件 | Android 组件 | `exported=false` 默认、只读 URI、路径限定、临时缓存清理 | `app/docs/CONTRACT.md` §6；端壳未建 | planned（OPEN-TOOLCHAIN） |
| NF-APP-TH-18 | WebView 本地预览被页面脚本升权/外联 | WebView（若启用） | 设计：JS 关闭、文件访问关闭、无网络、CSP；只用于本地只读预览 | `app/docs/CONTRACT.md` §6；当前端壳未建、未引入 WebView | planned（未启用；引入前须评审） |

### 不可观测项（必须写理由）

| 编号 | 项 | 为什么 UNOBSERVABLE | 缓解 |
|---|---|---|---|
| NF-APP-TH-19 | 内容交给第三方应用后的二次传播（分享出的 md/zip/json 被再转发/上传） | 分享动作完成后，APP 对接收方无任何观测面（无账号、无遥测、不追踪） | 脱敏前置 + 预览 + 拒发闸门（TH-09）；对用户明示「分享即离开本机」 |
| NF-APP-TH-20 | CCOS 内部是否按 task 执行（模型行为/越权使用输入） | CCOS 是外部执行面，APP 只能校验回传 digest 与 evidence 文件，无法观测执行过程 | 任务显式 `budget`/`policy`（`network=false`、`secrets=ccos-only`）；结果回钉 + 人审 required（TH-02/TH-08） |

## 3. 解析面逐项登记（攻击面 × 控制 × 状态）

| 解析面 | 攻击 | 当前控制 | 判据路径 | 状态 |
|---|---|---|---|---|
| zip slip（路径穿越） | `../`、绝对路径、盘符、反斜杠、重复条目 | `inspect_zip_entries`/`extract_zip_safe` + `check_rel_path`；`NF-SEC-001` | `app/cli/nf_app/security.py:74`；`app/tests/test_security_negative.py`（`test_zip_slip_rejected` 6 例参数化起） | enforced（控制面） |
| zip bomb（解压膨胀） | 压缩比/总量/条目/嵌套超限 | `limits.zip` 五维上限；`NF-SEC-003` | `app/schema/limits.json`；负例 `test_zip_bomb_ratio_rejected`、`test_zip_total_size_limit_override`、`test_zip_entry_count_limit_override` | enforced（控制面） |
| symlink/junction/硬链 | 通过链接写到目录外 | 拒绝 `NF-SEC-002`（`allow_symlink=false`） | `app/schema/limits.json`；负例 `test_zip_symlink_rejected` | enforced（控制面） |
| YAML bomb | alias 指数展开、深嵌套 | 别名展开 ≤1000、深度 ≤64；`NF-SEC-004` | `security.py`（`loads_yaml_secure`）；负例 `test_yaml_alias_bomb_rejected`、`test_yaml_depth_rejected` | enforced（控制面） |
| XML 实体 | XXE/实体膨胀/DTD | `limits.xml.entities=false`（默认禁实体）；错误码 `NF-SEC-005` 已登记；**当前无 XML 解析器**（未实现适配器） | `app/schema/limits.json`；`app/schema/error_codes.json` | planned（无解析器即无解析面；引入 XML 适配器前必须实现该上限） |
| PDF / DOCX | 恶意文档（嵌入对象/宏/超大解压流） | 首版未实现适配器 → `NF-IMP-004`（exit 3）显式拒绝，不静默当文本 | `app/docs/CONTRACT.md` §5.2；`app/schema/error_codes.json`（NF-IMP-004） | planned（未实现 = 不解析；不声称已安全处理） |
| OCR | 图片文字识别（不可信图像/模型依赖） | 首版未实现 → `NF-IMP-004`；若引入须评估模型/离线依赖与信任边界 | 同上 | planned |
| 深链 | 外部拉起端壳并注入参数 | 端壳未建；设计 = 参数校验 + 白名单路由 + 不直接执行文件写 | `app/docs/ARCHITECTURE.md` §7/§11（R-09） | planned（OPEN-TOOLCHAIN） |
| 分享 URI | 只读 URI 被滥用/越权读文件 | 脱敏前置 + 拒发（enforced）；FileProvider 路径限定与临时缓存清理（端壳未建） | `security.py:392`；`app/docs/CONTRACT.md` §6 | partial |
| pack 更新 | 恶意更新计划/冲突注入/回滚降级 | `pack-diff` 三类冲突不静默丢（`NF-PCK-006`）、摘要复核（`NF-PCK-004`）、备份+回滚（`NF-PCK-007`） | `app/docs/CONTRACT.md` §5.9；`app/schema/nf-pack-update.schema.json` | planned（语义冻结；核心未落） |
| WebView | 远程内容/脚本升权/外联 | 未引入；设计 = JS 关、文件关、无网络、CSP、只读预览 | `app/docs/CONTRACT.md` §6 | planned（引入前专项评审） |

## 4. 控制点状态表（逐条给证据或 OPEN 理由）

| 编号 | 控制点 | 状态 | 证据路径 / 判据 | 缺口（OPEN 理由） |
|---|---|---|---|---|
| C-01 | 相对路径合法性（`check_rel_path`） | enforced | `app/cli/nf_app/security.py:74`；`test_security_negative.py`（`test_unsafe_rel_path_rejected` 参数化） | — |
| C-02 | 安全解包与 symlink 拒绝（`inspect_zip_entries`/`extract_zip_safe`） | enforced | `security.py`；`test_zip_slip_rejected` 等 9 条 | — |
| C-03 | 解包上限（ratio/total/entries/nesting） | enforced | `app/schema/limits.json` zip 段；4 条超限负例 | — |
| C-04 | YAML alias/深度上限 | enforced | `security.py`（`loads_yaml_secure`）；2 条负例 | — |
| C-05 | JSON 深度/浮点/重复键/字节上限 | enforced | `security.py`（`parse_json_secure`）；4 条负例 | — |
| C-06 | safe_join 包含性（导出/落盘不越界） | enforced | `security.py`（`safe_join`）；`test_safe_join_escape_rejected` | — |
| C-07 | schema 结构校验 + 正反夹具 | partial | `app/cli/nf_app/schemas.py`；`test_schema_valid.py`/`test_schema_negative.py`（本机实测 87/88 passed） | 1 项红：`nf-project/minimal.json` 夹具缺 schema 必填引用字段 → 归 python-plane 修夹具或 schema |
| C-08 | 错误码单一真源（未登记码 fail-closed） | enforced | `app/cli/nf_app/errors.py:17-33`；负例统一经 `exit_for(code)==3` 断言 | — |
| C-09 | 分享脱敏（路径/家目录/邮箱/密钥形状） | enforced | `security.py:318-360`；`test_sanitize_masks_paths_and_secrets` | 裸用户名未覆盖 → OPEN-PRIVACY-01（TH-12） |
| C-10 | 分享拒发闸门 | enforced | `security.py:392`（`assert_share_safe`）；`test_assert_share_safe_rejects_secret` | 端壳分享面板未建 |
| C-11 | 确定性 canonical（Python oracle） | partial | `app/cli/nf_app/canonical.py`；`app/tests/test_oracle_parity.py` 已在，取证时刻 2 项红（拓扑序/包校验对账） | OPEN-QA-01 |
| C-12 | Pack 完整性（`pack-verify`） | partial | 语义：`app/docs/CLI.md`；结构：`nf-pack.schema.json`；实现：`app/core/src/ops/pack.rs` | 核心编译未过（E0658/E0605），测试无法执行 |
| C-13 | Pack 更新冲突不静默丢 | partial | `app/docs/CONTRACT.md` §5.9；`nf-pack-update.schema.json`；实现：`app/core/src/ops/update.rs` | 核心编译未过；冲突负例未跑 |
| C-14 | CCOS 任务不含密钥/绝对路径 | partial | `app/schema/ccos-task.schema.json`（`policy.secrets`）；`NF-CCOS-003` 已登记；实现：`app/core/src/ops/ccos.rs` | 核心编译未过；密钥扫描负例未跑 |
| C-15 | CCOS 结果回钉 + 人审 | partial | `app/schema/ccos-result.schema.json`；`app/docs/CLI.md`；实现：`app/core/src/ops/ccos.rs` | 核心编译未过；回钉负例未跑 |
| C-16 | C ABI 边界（版本校验/free/panic 兜底） | partial | `app/docs/CLI.md` §5；`app/core/src/ffi.rs`、`app/core/src/bin/nf-app-core.rs` | 核心编译未过；端壳未接（`app/android`/`app/desktop` 骨架在场但未构建） |
| C-17 | 组件 exported=false / FileProvider 限定 / 分享只读 URI | planned | `app/docs/CONTRACT.md` §6 | 端壳未建 → OPEN-TOOLCHAIN |
| C-18 | 深链参数校验 | planned | `app/docs/ARCHITECTURE.md` §7；R-09 | 端壳未建 |
| C-19 | WebView 硬化（若启用） | planned | `app/docs/CONTRACT.md` §6 | 未引入；引入前须专项评审 |
| C-20 | 诊断只落本地、无出站 | partial | 设计：`app/docs/ARCHITECTURE.md` §8；现状（§6 有 grep 判据） | 无门禁自动检查 → OPEN-QA-02 |
| C-21 | 供应链：锁文件 + 无网络拉取脚本 | partial | `app/core/Cargo.lock`；`app/scripts/build_core.sh` 不取网；`app/docs/DEPENDENCIES.md` | `.cargo/config.toml` 指向 rsproxy 第三方镜像 → OPEN-SUPPLY-001 |

## 5. OPEN 登记（不因本文件完成而关闭）

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-TH-01 | 核心侧解析/校验控制点未验证（C-12…C-16 已有源码但核心不可编译） | rust-core | 先修 2 处编译错误（E0658/E0605），再逐 op ≥1 负例（zip/YAML/digest 篡改/环/越界） |
| OPEN-TH-02 | 端壳信任边界（B-05：intent/深链/FileProvider/分享面板/WebView） | kotlin-ui | 端壳落地后补 exported/URI/路径限定 + 负例 |
| OPEN-PRIVACY-01 | 裸用户名（非路径形式）未被脱敏 | lead | 在 `security.py` 增加用户名探测（先评估误伤，加白名单）并入负例 |
| OPEN-QA-01 | oracle 对账（Python `canonical.py` vs Rust）2 项红（拓扑序/包校验），golden 夹具未落 | python-plane | 修 2 项对账 + 补 `app/tests/test_golden.py` + `app/fixtures/golden/` |
| OPEN-QA-04 | `nf-project/minimal.json` 夹具缺 schema 必填引用字段（`refs.base_pack.id/version` 等）→ 1 项 schema 测试红 | python-plane | 修夹具或同步 schema；改哪边都必须先改 `app/docs/CONTRACT.md` 与 `app/schema/README.md` 口径 |
| OPEN-QA-02 | 「无出站网络」缺自动门禁 | lead | 加静态检查项（`app/cli`/`app/core` 无 http/socket 调用）进 `app/gates/` |
| OPEN-SUPPLY-001 | `app/core/.cargo/config.toml` 把 crates-io 替换为 rsproxy 第三方镜像 | lead | 决定是否入库；CI 用默认源或 vendor；记入 `DEPENDENCIES.md` 供应链节 |
| OPEN-TOOLCHAIN | 无 Android SDK/Gradle/真机 → 端壳安全面不可实测 | toolchain-scout | 见 `app/results/TOOLCHAIN.md`（待落）；不可行则保持 OPEN |

## 6. 复跑命令（本件判据）

```bash
# 解析面负例（本机实测 47 passed，2026-11-15）
PYTHONDONTWRITEBYTECODE=1 python -m pytest app/tests/test_security_negative.py -q -p no:cacheprovider
# 核心单测（取证时刻：编译失败 2 处 → 修好后必须重跑；注意 cargo 配置按 cwd 发现）
cd app/core && cargo test --offline
# schema 正反夹具（本机实测 87/88 passed，2026-11-15；1 项为夹具/schema 漂移）
PYTHONDONTWRITEBYTECODE=1 python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q -p no:cacheprovider
# 错误码登记表仍在场且可解析（计数以实读为准，不钉数字）
grep -c '"code":' app/schema/error_codes.json
# 无出站网络（现状取证：当前 app/cli 无 socket/http/urllib/requests 调用）
grep -rnE "import (socket|http|urllib|requests)|from (http|urllib|requests)" app/cli app/core/src || echo "no network imports"
```

## 7. 不承诺（本件不声称的能力）

- 不声称 APP 已具备「防住全部恶意文件」的能力：控制面挡了解包/解析的已知攻击面，**核心解析器尚未实现**（B-02/B-03 的最终权威缺失）。
- 不声称端壳安全（intent/FileProvider/深链/分享面板/WebView）：端壳未建，全部 `planned` / `OPEN-TOOLCHAIN`。
- 不声称 CCOS 侧安全：CCOS 是外部执行面，本件只约束「交接格式与回钉」，不评价其内部实现。
- 不使用「不可抵赖 / 合规 / 认证」类表述；`UNOBSERVABLE` 两项就是不可观测，不是「已缓解」。
- 本件不是渗透测试报告；真实红队（文件管理器/恶意 pack/深链）需设备环境，见 `OPEN-TH-02`。

