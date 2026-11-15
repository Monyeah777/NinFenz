# NF APP 架构（arc42 + C4）

> ⛔ 操作指令：本件是 APP 面的架构**结果件**，不是路线图。任一条目若在仓库里指不到落点路径，必须写成 `OPEN` + owner + 下一步（见 §11）；状态词只有 `enforced` / `partial` / `planned` / `OPEN`（口径同 `app/docs/THREAT_MODEL.md` §0）。改本件必须同步 `app/docs/CONTRACT.md`、`app/docs/CLI.md`、`app/docs/adr/ADR-APP-*.md` 的对应条目。
> 状态：v1（2026-11-15）· 性质：架构结果件 · 取证时刻：2026-11-15 16:5x（本机检出 `e7855c237`；本机实测：`pytest app/tests` = **197 passed / 7 failed**；`cd app/core && cargo test --offline` = **编译失败 2 处**（E0658 `windows_by_handle`、E0605 `Option<u32>` 转 u64）；`app/android`、`app/desktop` 工程骨架在场但未构建。实现由 `rust-core` / `python-plane` / `kotlin-ui` 并行推进，**状态随证据变动，以复跑命令为准**）。
> 依据：`app/docs/CONTRACT.md`（A0 契约冻结）、`app/docs/CLI.md`（op/FFI 面）、`app/schema/*.json`（13 格式 + limits/error_codes）、计划 §5/§12/§16（作者本地输入，不入仓）；上位：`STRATEGY.md`（方向）、`AGENTS.md`（纪律）。

## 1. 引言与目标

NF APP = **人的控制面**。它把「作者 → 协议/图/规范 → 装配 → 校验 → 导出/分享 → 交 CCOS 执行 → 人审回填」做成三端（Android / 桌面 / 平板）一致、可复现、可检验的工程，执行面与密钥留在 CCOS，终端与检验留在 TUI/`nf`。

### 1.1 功能目标（每条给判据落点）

| 编号 | 目标 | 可核判据 | 状态（取证时刻） |
|---|---|---|---|
| G-1 | 13 个共享格式有单一真源，三端同语义 | `app/schema/*.schema.json` + `python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q` | partial（schema 15 件 + 正反夹具在场；schema 测试 **87/88 passed**（`nf-project/minimal.json` 夹具与 schema 漂移，owner python-plane）；三端同语义未验） |
| G-2 | 共享核心以单一实现承载全部 op 语义 | `cd app/core && cargo test --offline` + `app/docs/CLI.md` §3 op 表 | partial（`app/core/src` 取证时刻 25 个源文件 / 7,715 行；编译失败 2 处，owner rust-core） |
| G-3 | Python 控制面提供用户流（import/map/project/author/assemble/validate/export/share/pack/ccos/selftest） | `python -m pytest app/tests/test_cli_contract.py -q` | partial（`app/cli/nf_app/` 已落模块含 `__main__.py`/`cli.py`/`commands`/`pack.py`；`test_cli_contract.py` 7 项红，owner python-plane） |
| G-4 | Pack 可校验、可 diff/merge、可回滚（base+overlay） | `app/core` 的 `pack-verify`/`pack-diff`/`pack-merge`/`overlay-apply` + 负例 | partial（`ops/pack.rs`、`ops/update.rs` 已落；未通过编译/测试） |
| G-5 | 导入管线统一（嗅探 → 结构抽取 → 映射建议），未实现格式 fail-closed | `app/schema/nf-import.schema.json` + `NF-IMP-004` 负例 | partial（`ops/import_ops.rs` 已落；未通过编译/测试） |
| G-6 | 装配/校验/导出确定性（同输入同字节） | 两次运行 `diff`；golden 逐字节比对 `app/tests/test_golden.py` | partial（`test_oracle_parity.py` 已落；取证时刻 2 项红） |
| G-7 | APP 与 CCOS 只经文件/zip 交接，任务不含密钥/绝对路径 | `app/schema/ccos-task.schema.json`（`policy.secrets = "ccos-only"`）+ `NF-CCOS-003` | partial（`ops/ccos.rs` 已落；未通过编译/测试） |
| G-8 | 分享前脱敏（绝对路径/用户名/邮箱/密钥形状），剪贴板回填走普通导入 | `app/cli/nf_app/security.py:318-399` + 分享负例 | partial（脱敏/拒发实现 + 负例通过；分享面板/回填 UI 未建） |

### 1.2 非目标（明确不做）

- 不做通用 Markdown 编辑器 / 通用代码 IDE / 云同步 / 端上 LLM / 长驻 MCP（`app/README.md` 边界节）。
- 不复制仓库内容真源（`01`–`07`、`03_管线库`、`04_模块库`、`05_资产库`、`protocol/`）；只按 `{id, version, digest}` 引用（`CONTRACT.md` §1）。
- 不直连模型 API、不持有密钥（密钥只在 CCOS，`CONTRACT.md` §5.11）。
- 不加载/执行 pack 内的可执行代码：pack 是数据，不是插件。

## 2. 约束（架构必须满足的前提）

| 编号 | 约束 | 来源/证据 | 对架构的强制后果 |
|---|---|---|---|
| C-01 | 本机离线：Gradle / Android SDK / kotlinc / Go 不在场；crates.io 直连被失效代理拦截 | `results/app/BASELINE.md` §2.1 | 核心必须能在 `app/core` 内自足构建；端壳构建证据只能 OPEN-TOOLCHAIN |
| C-02 | 不引入网络拉取脚本 | `CONTRACT.md` §6 供应链；`app/scripts/build_core.sh` 不取网 | 依赖只经锁文件；`.cargo/config.toml` 的第三方镜像属偏差，登记 OPEN-SUPPLY-001 |
| C-03 | 许可 MIT | 实读 `LICENSE`（2026 Monyeah777） | 依赖须为宽松许可（见 `app/docs/DEPENDENCIES.md`）；NOTICE 义务单独登记 |
| C-04 | 确定性：canonical 产物禁时间戳/随机/绝对路径/环境 | `CONTRACT.md` §7 | 产物只由输入决定；人读字段（history/at、provenance）按 schema 注解从 digest 剔除 |
| C-05 | 无遥测、无账号、本地处理 | `CONTRACT.md` §6；`app/README.md` | 无出站网络层；诊断只落本地；崩溃上报不设计 |
| C-06 | 不占用仓库门禁 check1–57 | `results/app/BASELINE.md` §0.5 | APP 门禁独立在 `app/gates/`；接仓库门禁只能新增 check58+ |
| C-07 | 真源单一：协议/管线/模块/资产内容只在仓库根 | `CONTRACT.md` §1/§9 | APP 只新增作者态/装配态/交付态格式（13 件），不自建第二真源 |
| C-08 | 三端同字节：Rust 参考实现 ↔ Python ↔ Kotlin 对同一请求同响应 | `CLI.md` §6 | golden 夹具 + oracle 对账是发布前置，不是可选项 |
| C-09 | 人类可读错误与可执行修复 | `CONTRACT.md` §4；`app/schema/error_codes.json` | 每个错误码带 `message` + `fix`，实现不得散落字面量 |

## 3. 上下文与边界

### 3.1 业务上下文（C4 Context）

```
                 ┌────────────────────────── 外部（不受 APP 控制） ──────────────────────────┐
                 │  内容真源仓（protocol/、01–07、03/04/05）   模型/执行面 CCOS（持密钥）    │
                 └───────▲───────────────────────────────▲──────────────────────▲──────────┘
                         │ 只读引用 ID+digest              │ ccos-task/1            │ ccos-result/1
                         │                                 │ (文件/zip)             │ (文件/zip)
┌──────────┐   author   ┌─┴──────────────────┐   导出/分享   ┌┴──────────────┐   人审    │
│ 作者(人) │───────────▶│   NF APP           │─────────────▶│ 读者/外部编辑器 │          │
└────┬─────┘            │ Android / Desktop  │              └───────────────┘          │
     │ 终端/检验        │ 平板（控制面）      │◀──────────────────────────────────────────┘
     ▼                  └────────┬───────────┘
┌──────────────┐                  │ 复用（不重写）
│ TUI / nf CLI │──────────────────┘
└──────────────┘
```

外部角色：**作者**（导入/映射/作者/评审）、**读者/外部编辑器**（收 md/zip/json/剪贴板文本）、**CCOS**（执行面，持密钥，回传结果）、**内容真源仓**（协议/管线/模块/资产）、**平台**（Android intent/FileProvider/分享面板、Windows/macOS 文件与签名体系）、**TUI/`nf` CLI**（终端与检验的既有入口）。

### 3.2 技术上下文

| 外部系统 | 接口形态 | 方向 | 契约 |
|---|---|---|---|
| 内容真源仓 | 文件（`protocol/**`、`03_管线库/**` 等）+ digest | APP 读 | `CONTRACT.md` §9（引用不复制） |
| CCOS | `ccos-task/1` / `ccos-result/1` 文件或 zip | 双向 | `app/schema/ccos-task.schema.json`、`ccos-result.schema.json` |
| TUI / `nf` CLI | 子进程 + JSON（`--list-actions --json`、`--selftest`、L2 校验） | APP 调 | `tui/nf.py`、`tui/README.md` |
| 平台 Android | `Intent` / `FileProvider` / 分享面板 / 剪贴板 | 双向 | `CONTRACT.md` §6（exported=false、路径限定、只读 URI） |
| 平台 Windows/macOS | 文件关联、MSIX/公证、剪贴板 | 双向 | `app/scripts/RELEASE_CHECKLIST.md` |
| 文件系统 | 用户数据目录（library/backups/cache/exports） | 双向 | §7.1（布局设计，实现待端壳） |

### 3.3 与仓库既有平面的边界（硬边界）

| 既有平面 | 它是什么 | APP 与它的关系 | 边界判据 |
|---|---|---|---|
| `desktop/src/core/**`（Python 核心：pipeline/assemble_plan/assembly_runtime/exporter/output_forms 等） | 仓库既有生产/装配/校验/导出实现 | **不重写、不 import、不改动**；APP 的 A0–A5 语义参考实现是 Rust（`app/core`）；L2 校验可经子进程调 `nf`（`NF-VAL-005` fail-closed） | 改动面：`git status` 只出现 `app/**` 与 `results/app/**`；`CONTRACT.md` §9 |
| `engine/rust/**`（91 文件只读快线 + ABI 版本号 cdylib） | 跨语言对账/ABI 范式先例 | **只借鉴范式，不复用代码**：APP 核心 `crate-type = ["rlib","cdylib"]` 与 `nf_app_core_abi_version` 是同一写法（不同 crate） | `app/core/Cargo.toml` vs `engine/rust/Cargo.toml`；`CLI.md` §5 |
| `protocol/**`（9 件 schema + 5 件 production schema + 台账 JSON） | 协议/生产平面真源 | APP 只读；`nf-assembly-plan/1` 与 `protocol/production/assembly.schema.json` 是**不同物**，桥接靠 `graph-compile` + 适配器（后续） | `CONTRACT.md` §9 逐行对照表 |
| `tui/nf.py` + `tui/_surface.py` | 终端/检验的真源 | **复用不重写**；Studio 只调 `--selftest` / `--list-actions --json` | `python tui/nf.py --selftest`（9 项 ✔，`results/app/BASELINE.md` §2.1） |
| `verify.sh`（check1–57） | 仓库门禁 | **不改**；APP 门禁独立（`app/gates/run_gates.py`），接仓只能 check58+ | `results/app/BASELINE.md` §0.5；C-06 |
| `app/schema/**` | APP 契约层单一真源 | 本架构的输入，不由核心/端壳反向定义 | `app/schema/README.md`「冻结纪律」 |

## 4. 方案策略

### 4.1 分层（自上而下）

```
┌─ 端壳层 ────────────────┐  Android(Kotlin+CMP) · Desktop(CMP/Kotlin) · TUI(既有)
│  只做 UI/交互/平台集成   │  执：界面、表单、图表、分享面板、文件关联、无障碍
└─────────┬───────────────┘
          │ 用户流（不实现语义）
┌─────────▼───────────────┐  app/cli/nf_app（Python 控制面）：编排 op、脱敏、路径/数据目录、
│  控制面                 │  项目状态机、分享/回填、CCOS 打包、selftest；不复制语义
└─────────┬───────────────┘
          │ CLI/JSON 或 C ABI JSON（同一信封）
┌─────────▼───────────────┐  app/core（Rust nf-app-core）：canonical/pack/import/protocol/
│  共享核心（语义唯一实现）│  graph/spec/assemble/validate/export/update/overlay/ccos/project
└─────────┬───────────────┘
          │ 只读 schema/limits/error_codes（数据，不是代码）
┌─────────▼───────────────┐  app/schema/*.json：13 格式 + limits + error_codes（单一真源）
│  契约层                 │
└─────────────────────────┘
```

### 4.2 五条硬口径

1. **单一真源**：格式只在 `app/schema/`；内容只在仓库根；错误码只在 `app/schema/error_codes.json`；上限只在 `app/schema/limits.json`。
2. **ID+digest 双钉**：任何跨文件引用用 `{id, version, digest}`；unknown 引用 fail-closed（`NF-E-002`）。
3. **确定性**：canonical = `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` 的 UTF-8 字节；禁浮点；digest = sha256(canonical)。
4. **fail-closed**：未知版本/枚举/op/超限 → exit 3；不降级、不猜测、不静默丢弃（`CONTRACT.md` §3）。
5. **进程即契约**：UI→控制面→核心的每次跨越都是 JSON 信封（`{ok, exit, result, error}`）；信封变化 = 破坏性变更（`CLI.md` §2/§3）。

### 4.3 C4 Container（容器视图）

```
┌─────────────────────────────── 设备/主机（单用户） ─────────────────────────────────┐
│                                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                 │
│  │ Android 端壳      │   │ Desktop 端壳      │   │ TUI（既有）       │                 │
│  │ Kotlin + CMP     │   │ Kotlin + CMP     │   │ python tui/nf.py │                 │
│  │ app/android/**   │   │ app/desktop/**   │   │ tui/**           │                 │
│  └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘                 │
│           │ C ABI(JSON)          │ C ABI(JSON)          │ 子进程               │
│  ┌────────▼──────────────────────▼──────────────────────▼─────────┐                 │
│  │ nf-app-core（Rust，rlib+cdylib）  app/core/**                    │                 │
│  └────────▲───────────────────────────────────────────────────────┘                 │
│           │ CLI/JSON                                                               │
│  ┌────────┴──────────────┐        ┌───────────────────────────┐                     │
│  │ 控制面 nf_app（Python）│───────▶│ 契约层 app/schema/*.json   │（只读）             │
│  │ app/cli/**            │        │ limits / error_codes       │                     │
│  └────────┬──────────────┘        └───────────────────────────┘                     │
│           │ 文件/zip（ccos-task/result）                                             │
│  ┌────────▼──────────────┐        ┌───────────────────────────┐                     │
│  │ CCOS 交接目录（外部）  │        │ 用户数据目录（library/     │                     │
│  │ 由外部执行面读写       │        │ backups/cache/exports）    │                     │
│  └───────────────────────┘        └───────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

容器职责与落点：

| 容器 | 职责 | 落点 | 判据命令 | 状态 |
|---|---|---|---|---|
| Android 端壳 | 移动/折叠/平板作者流；平台分享/深链/文件关联 | `app/android/**`（工程骨架在场：`build.gradle.kts`/`gradlew`/wrapper） | `bash app/scripts/build_android.sh debug`（缺 SDK → exit 4；无 APK 产物） | OPEN-TOOLCHAIN |
| Desktop 端壳 | 作者台：Graph/DSL/Pack/评审/打印/TUI 集成 | `app/desktop/**`（工程骨架在场：`build.gradle.kts`/`gradlew`/wrapper） | `bash app/scripts/build_desktop.sh package`（无 Gradle 发行版 → exit 4） | OPEN-TOOLCHAIN |
| TUI | 终端真源：菜单/动作/自检 | `tui/nf.py`、`tui/_surface.py` | `python tui/nf.py --selftest`（9 ✔） | partial（复用面在场；Studio 集成待端壳） |
| 共享核心 | 全部 op 语义的唯一实现 | `app/core/src/**`（取证时刻 25 文件 / 7,715 行） | `cd app/core && cargo test --offline` | partial（编译失败 2 处，owner rust-core） |
| 控制面 | 用户流/脱敏/数据目录/CCOS 打包 | `app/cli/nf_app/**` | `python -m pytest app/tests/test_cli_contract.py -q` | partial（owner python-plane） |
| 契约层 | 13 格式 + limits + error_codes | `app/schema/**`（15 件 JSON） | `python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q` | partial（15 件可解析；schema 正反测试 87/88 passed） |
| APP 门禁 | QA0–QA6 + S0–S15 聚合 | `app/gates/run_gates.py`、`gates.json`、`dimensions.json` | `python app/gates/run_gates.py --only QA0` | partial（门禁可跑；QA1 核心面必红，见 R-01） |

### 4.4 C4 Component（核心 + 控制面内部）

```
napp-core（app/core/src/）                       nf_app（app/cli/nf_app/）
┌───────────────────────────┐                  ┌─────────────────────────────┐
│ canonical.rs   nf-canonical│                  │ __init__.py   版本/入口约定  │
│ pack.rs        hash/verify │                  │ paths.py      仓库/核心定位  │
│ import.rs      sniff/extract│                 │ errors.py     错误码→信封    │
│ protocol.rs    clauses/rules│                 │ canonical.py  Python oracle  │
│ graph.rs       validate/DAG │                 │ schemas.py    结构 pre-flight │
│ spec.rs        sections/slot│                 │ io_utils.py   原子写/严格读   │
│ assemble.rs    render       │                 │ security.py   解析/路径/脱敏  │
│ validate.rs    L0/L1/L2     │                 │ core.py       subprocess 桥   │
│ export.rs      md/zip/json  │                 │ (待落：__main__/import/project│
│ update.rs      diff/merge   │                 │  /share/ccos/selftest)      │
│ overlay.rs     apply/migrate│                 └─────────────────────────────┘
│ ccos.rs        task/result  │
│ project.rs     状态机/校验   │
│ cli.rs         op 分发/信封  │
│ ffi.rs         C ABI 3 函数  │
└───────────────────────────┘
```

> 上图是**设计落点**，不是已实现清单：`app/core/src/` 当前只有 `lib.rs` 占位与 `bin/nf-app-core.rs` 空 main（取证时刻）。文件名与 `CLI.md` §3 的 op 分组一一对应；实际文件名以 rust-core 交付为准，若不同须回填本图。

## 5. 构件说明（职责 / 落点 / 判据）

### 5.1 核心 op 分组（与 `CLI.md` §3 同序）

| 组 | op | 语义要点（取自 `CONTRACT.md`） | 判据 | 状态 |
|---|---|---|---|---|
| canonical | `canonical` | 禁浮点/NaN/非字符串键；结果 `{canonical, digest}` | `cargo test`；oracle 对账 `app/tests/test_oracle_parity.py` | partial（`canonical.rs` 在场；核心编译未过） |
| pack | `pack-hash` `pack-verify` | items 按 path 升序；tree = sha256(canonical([{path,sha256,size}]))；路径不安全 → `NF-PCK-003` | 同上 + 安全负例 | partial（`ops/pack.rs` 在场；核心编译未过） |
| import | `import-sniff` `import` `map-suggest` | 魔数 → MIME/扩展 → 内容特征；置信度 <0.6 给候选不自动入库；未实现格式 → `NF-IMP-004` | `app/tests/test_e2e_first_loop.py -k import` | partial（`ops/import_ops.rs`、`yaml.rs` 在场；核心编译未过） |
| protocol | `protocol-validate` `protocol-render` | 占位符渲染 + 封闭 DSL（op 白名单）；未知 op → `NF-PRT-005` | `app/tests` 契约用例 | partial（`ops/protocol.rs` 在场；核心编译未过） |
| graph/spec | `graph-validate` `graph-compile` `spec-validate` | L0 结构 + L1 契约（DAG/可达/端口/权重/双向引用） | 同上 | partial（`ops/graph.rs`、`ops/spec.rs` 在场；核心编译未过） |
| assemble | `assemble` | 确定性渲染；必填缺失 `NF-ASM-002`；块编辑只替换该节 | `app/tests/test_e2e_first_loop.py` | partial（`ops/assemble.rs` 在场；核心编译未过） |
| validate | `validate` | L0/L1 报告带 target.digest；L2 不可用 → `NF-VAL-005`（exit 4） | 同上 | partial（`report.rs`/`ops/` 在场；核心编译未过） |
| export | `export` | md/zip/json；zip 固定 mtime 1980-01-01、无 extra field；docx/pdf → `NF-EXP-004`（exit 4） | golden 逐字节 | partial（`ops/export.rs` 在场；核心编译未过） |
| update | `pack-diff` `pack-merge` `overlay-apply` | 三类冲突不静默丢；备份→原子替换→复验→失败回滚 | E2E `-k update or rollback` | partial（`ops/update.rs` 在场；核心编译未过） |
| ccos | `ccos-build-task` `ccos-import-result` | 密钥形状 → `NF-CCOS-003`；人审恒 true | E2E `-k ccos` | partial（`ops/ccos.rs` 在场；核心编译未过） |
| project | `project-validate` | 引用失配/状态非法 → exit 1 | 契约用例 | partial（`ops/project.rs` 在场；核心编译未过） |

### 5.2 控制面构件（`app/cli/nf_app/**`）

| 构件 | 职责 | 落点（取证时刻实际行号） | 判据 | 状态 |
|---|---|---|---|---|
| `canonical.py` | Python 侧 canonical/摘要独立实现（oracle），不依赖 Rust | `app/cli/nf_app/canonical.py`（139 行） | `python -m pytest app/tests/test_oracle_parity.py -q` | partial（实现已在；对账用例取证时刻 2 项红） |
| `errors.py` | 错误码 → 退出码/信封；未登记码 fail-closed（RuntimeError） | `app/cli/nf_app/errors.py`（92 行） | 契约用例 | partial |
| `security.py` | 解析硬化（zip/YAML/JSON/路径）+ 分享脱敏 | `app/cli/nf_app/security.py:74`（路径）、`:336`（脱敏）、`:392`（分享 fail-closed） | `python -m pytest app/tests/test_security_negative.py -q`（47 passed） | partial（实现 + 47 负例通过；XML/PDF/DOCX/OCR 未实现） |
| `schemas.py` | jsonschema 结构 pre-flight；语义权威仍在核心 | `app/cli/nf_app/schemas.py` | schema 正反用例 | partial |
| `io_utils.py` | UTF-8 stdio、严格读、原子写、摘要 | `app/cli/nf_app/io_utils.py` | 契约用例 | partial |
| `core.py` | subprocess 桥；核心缺失 → `NF-E-005`（exit 4），不降级 | `app/cli/nf_app/core.py` | 契约用例 + 缺核心负例 | partial |
| `paths.py` | 仓库根/核心候选路径发现（可用 `NF_APP_REPO_ROOT` 覆盖，不写死盘符） | `app/cli/nf_app/paths.py` | 契约用例 | partial |
| 用户流入口 | `python -m nf_app`（import/map/project/author/assemble/validate/export/share/pack/ccos/selftest） | `app/cli/nf_app/__main__.py`、`cli.py`、`commands/` | `python -m nf_app --help`；`python -m pytest app/tests/test_cli_contract.py -q` | partial（入口已落；7 项契约测试红） |

## 6. 运行时视图

### 6.1 首闭环（计划 §18.2 七步 → 本架构的时序）

```
作者           控制面(nf_app)            核心(nf-app-core)              文件系统
 │  选 sample pack │                          │                           │
 │───────────────▶│ pack-verify ────────────▶│ 逐 item sha256/tree       │
 │                │◀──────── nf-validate-report/1 ──────────────────────│
 │  导入 md       │ import-sniff → import ──▶│ 嗅探/抽取/映射建议         │
 │                │ map-suggest ────────────▶│ heading→section …         │
 │  映射确认      │◀──────── nf-import/1 ───────────────────────────────│
 │  改图/参数/权重│ graph-validate/graph-compile ─▶│ L0/L1 + 拓扑序       │
 │                │◀──────── nf-assembly-plan/1 ────────────────────────│
 │  装配          │ assemble(plan,spec,inputs) ─▶│ Markdown + meta        │
 │  校验          │ validate L0/L1 ──────────▶│ nf-validate-report/1      │
 │  导出          │ export md/zip/json ──────▶│ manifest + 产物            │
 │  分享          │ share：脱敏→预览→系统分享    │ 分享缓存（可清理）        │
 │  CCOS 交接     │ ccos-build-task ─────────▶│ ccos-task/1（无密钥）     │
 │  外部执行面    │                （文件/zip 出站；APP 不联网）           │
 │  人审回填      │ ccos-import-result ──────▶│ 回钉 task_digest + 人审    │
```

### 6.2 Pack 更新 / 回滚（base+overlay）

1. `pack-diff`（旧 base vs 新 base）→ `nf-pack-update/1`：`added/removed/modified` 按 path 升序，`impact` = 受影响项目 + overlay 键，`breaking` = 删除或 schema 变更。
2. 冲突三类（删除/重命名/schema 变更）进 `conflicts[]`，默认 `defer`；未裁决 → `NF-PCK-006` 不应用。
3. `pack-merge`：备份（本地指针可带时间戳，不进 canonical）→ 原子替换 → 复验 → 失败回滚（`NF-PCK-007`）；旧版保留。
4. 同 `id+version` 不同 digest = 篡改/冲突 → `NF-PCK-004`（exit 3）。

### 6.3 启动加载（端壳）

- 端壳冷启动只做三件：读 `app/schema` 版本兼容 `compat.min_app_version` → 读数据目录 `latest` 指针 → 打开项目引用。**不联网、不登录、不扫描外部目录**（C-05）。
- 核心库按需加载：Android/Desktop 通过 C ABI 调 `nf_app_core_abi_version` 校验 ABI，再按 op 调用（`CLI.md` §5）。
- 未知 schema 版本 / ABI 不匹配 → 拒绝加载并给升级指引（`NF-E-001`），不猜测兼容。

### 6.4 失败路径（退出码语义，`CONTRACT.md` §4）

| 退出码 | 场景 | 端壳行为 |
|---|---|---|
| 0 | 成功 | 展示结果/写产物 |
| 1 | 校验失败（报告已写出） | 展示 `issues[].path` + `fix`，不写「成功」 |
| 2 | 用法/IO | 提示路径/权限，保持当前状态 |
| 3 | 拒绝（安全/未知/超限/版本） | 阻断并解释，不提供「强制继续」 |
| 4 | 环境缺失（工具/依赖不在场） | 明确 OPEN（如 L2 校验、docx/pdf 导出），不禁用为「通过」 |

## 7. 部署视图

| 平台/形态 | 产物 | 构建入口 | 签名/分发 | 状态 |
|---|---|---|---|---|
| Android | APK（debug）/ AAB（release） | `bash app/scripts/build_android.sh release` | Play App Signing / upload key（不入库） | OPEN-TOOLCHAIN（无 SDK）+ OPEN-EXTERNAL（无账号） |
| Windows 10/11 x64 | MSIX（Store 优先）/ EXE 侧载 | `bash app/scripts/build_desktop.sh package` + `MakeAppx` | Authenticode（`app/scripts/sign_windows.ps1`） | OPEN-TOOLCHAIN + OPEN-EXTERNAL |
| macOS 13+ arm64 | `.app` / dmg | `bash app/scripts/build_desktop.sh package`（macOS 上） | Developer ID + Hardened Runtime + notarytool（`app/scripts/notarize_macos.sh`） | OPEN-EXTERNAL（本机非 macOS） |
| TUI | 源码 + 打包 exe/sh | `tui/build_exe.ps1`、`tui/build_exe.sh` | 无签名要求（仓库既有） | partial（复用面在场） |
| 核心库 | `libnf_app_core`（rlib/cdylib）+ `nf-app-core` CLI | `bash app/scripts/build_core.sh --release --test` | 随端壳打包 | planned（源码占位） |

### 7.1 数据目录布局（设计口径，落点待端壳）

```
<平台应用数据目录>/nf-app/
  library/packs/<id>/<version>/     # 只读 base（校验通过的 pack）
  projects/<project-id>/            # project.nfproject.json + 作者输入 + assembly
  overlay/<project-id>/             # nf-overlay/1 用户层
  backups/<timestamp>/              # 更新前备份（仅本地指针带时间戳）
  cache/share/                      # 分享缓存（可清理；文件权限最小化）
  exports/                          # 导出产物（用户可见目录）
  diagnostics/                      # 本地诊断日志（无出站）
  ccos/outbox|inbox/                # 与 CCOS 的交接目录（文件/zip）
```

- 布局是**设计**：端壳未建，目录常量实现待落（OPEN-DATADIR，owner kotlin-ui）；在此之前不得声称「数据目录已实现」。
- base 只读；`latest` 指针单独文件；同 id 不同 version 并存（`CONTRACT.md` §5.1）。

### 7.2 更新通道

- Pack 更新走 `pack-diff/pack-merge`（数据面）；APP 自身更新走各平台商店/签名安装包（Windows MSIX、macOS Sparkle、Android Play/staged rollout）。
- 更新通道的签名校验、回滚、灰度都属发布面 → `app/scripts/RELEASE_CHECKLIST.md`（W4/M4）为 OPEN，不在本架构声称实现。

## 8. 横切概念

| 概念 | 口径 | 落点/判据 | 状态 |
|---|---|---|---|
| 确定性 | 同输入同字节；禁时间戳/随机/绝对路径/环境；排序按码点 | `CONTRACT.md` §7；`app/cli/nf_app/canonical.py`；`app/tests/test_golden.py` | partial（Python oracle 已在，golden 未落） |
| 错误模型 | 码 → exit/severity/message/fix 只从登记表取 | `app/schema/error_codes.json`；`app/cli/nf_app/errors.py:17` | partial |
| 限额 | 单点登记，实现读取，不散落字面量 | `app/schema/limits.json`；`app/cli/nf_app/security.py:41`（DEFAULT_LIMITS 兜底） | partial |
| 解析硬化 | zip/YAML/JSON/XML/路径默认拒绝 | `CONTRACT.md` §3；`security.py`；`NF-SEC-*` | partial（XML/PDF/DOCX/OCR 未实现 → planned，见 THREAT_MODEL） |
| 安全边界 | exported=false；分享只读 URI + 临时缓存；WebView 若用则 JS/文件/网络全关 | `CONTRACT.md` §6 | planned（端壳未建） |
| 隐私 | 本地处理、无遥测、无账号；分享前脱敏 | `app/docs/PRIVACY.md`；`security.py:336` | partial |
| 诊断 | 只落本地 `diagnostics/`，不联网；无崩溃上报 | C-05 | planned（端壳未建） |
| 无障碍/本地化 | TalkBack/RTL/字体缩放/pseudo-locale 抽查 | `app/docs/QA_PLAN.md` §2 | OPEN-TOOLCHAIN |
| 性能 | 启动/装配/导出/内存/包体预算与口径 | `app/docs/PERF_BUDGET.md` | OPEN（本机无运行时，逐项 no-data + owner） |

## 9. 架构决策（ADR 索引，详见 `app/docs/adr/`）

| ADR | 决策 | 状态 |
|---|---|---|
| ADR-APP-001 | APP 与 CCOS 分离：APP 不直连模型、不持密钥、经任务/结果文件交接 | accepted |
| ADR-APP-002 | 共享核心用 Rust，端壳用 Kotlin/CMP | accepted |
| ADR-APP-003 | Wiki/Spec/Pack 单一真源，APP 只按 ID+digest 引用 | accepted |
| ADR-APP-004 | Pack = base + overlay；更新走 diff/merge/回滚 | accepted |
| ADR-APP-005 | 统一 nf-import 管线（嗅探/抽取/映射），未实现格式 fail-closed | accepted |
| ADR-APP-006 | TUI 是终端真源，Studio 复用不重写 | accepted |
| ADR-APP-007 | VIP 只做领域 IDE 面（作者/图/DSL/评审），不做通用 IDE | accepted |
| ADR-APP-008 | 分享四形态 + 剪贴板回填（脱敏前置） | accepted |
| ADR-APP-009 | 16KB page / target 36 / ABI 进 CI 门禁 | accepted |
| ADR-APP-010 | Apple Silicon 优先（macOS arm64 先发） | accepted |
| ADR-APP-011 | JSON-C ABI 替代 UniFFI（离线依赖不可得） | accepted-with-deviation |

## 10. 质量要求（QAS 场景）

| 编号 | 质量属性 | 场景 | 判据 | 状态 |
|---|---|---|---|---|
| QAS-1 | 确定性 | 同一 pack/plan/spec 两次装配 | 两次输出 `sha256` 相同；`test_golden.py` 逐字节（待落） | partial（oracle 对账 2 项红） |
| QAS-2 | fail-closed | 未知 schema 版本/枚举/超限输入 | exit 3 + 登记码；`test_security_negative.py`（47 passed） | partial（控制面负例通过；核心侧未验证） |
| QAS-3 | 可复现构建 | 离线机器从锁文件构建核心 | `cd app/core && CARGO_NET_OFFLINE=true cargo build` 成功 | planned（需先 `cargo fetch`；当前源码占位） |
| QAS-4 | 契约一致 | 同一请求三端响应 | Rust/Python/Kotlin 同一 JSON 字节（`CLI.md` §6） | planned（golden 未落） |
| QAS-5 | 隐私 | 分享含绝对路径/邮箱/密钥形状的文本 | 脱敏后再次 `find_sensitive` 为空；否则 `NF-E-002` 拒发 | enforced（控制面：`security.py:392` + 负例通过；端壳分享面板未建） |
| QAS-6 | 性能 | 首闭环 ≤ 30 s（sample pack，≤500 槽） | `time python -m pytest app/tests/test_e2e_first_loop.py -q`（本机 no-data） | OPEN（见 PERF_BUDGET） |

## 11. 风险与技术债（每条给 owner + 下一步）

| 编号 | 风险 | 影响 | 缓解/下一步 | owner | 状态 |
|---|---|---|---|---|---|
| R-01 | 核心不可编译（取证时刻 2 处编译错误） | 全部 op 不可执行，QA1/QA2 门禁必红 | 修 E0658 `windows_by_handle`、E0605 `Option<u32>` 转 u64，再跑 `cd app/core && cargo test --offline`；门禁 QA1 | rust-core | OPEN |
| R-02 | Android/Desktop 构建不可执行（工具链缺失） | 无 APK/安装包；设备/16KB/无障碍无证据 | 工程骨架已在；等 `app/results/TOOLCHAIN.md`（待落）结论与外部工具链 | toolchain-scout / kotlin-ui | OPEN-TOOLCHAIN |
| R-03 | UniFFI 偏差 | 与计划 §5.1 字面不一致 | JSON-C ABI 等价实现；回切条件见 ADR-APP-011 | lead | accepted-with-deviation |
| R-04 | L2 校验依赖 `nf` CLI 子进程 | 未装 `nf` 时 L2 不可用 | exit 4 + `NF-VAL-005`，不降级；文档不写成通过 | lead | OPEN（语义已定） |
| R-05 | docx/pdf 导出未实现 | 交付形态受限 | exit 4 + `NF-EXP-004`；次版补导出器探测 | lead | planned |
| R-06 | 依赖镜像入库（rsproxy） | 供应链重定向风险 | `app/core/.cargo/config.toml` 是否入库/CI 用源需评审；建议 CI 默认源或 vendor | lead | OPEN-SUPPLY-001 |
| R-07 | Python 控制面依赖 jsonschema | 新增第三方运行依赖 | 登记进 `app/docs/DEPENDENCIES.md`；版本钉死；离线安装策略待定 | python-plane | partial |
| R-08 | 进程死亡/崩溃恢复未实现 | 长任务中断后状态需人工确认 | 备份+复验+回滚已定；恢复点设计待 A6/Q | lead | planned |
| R-09 | 数据目录/文件关联/分享 URI 无实现 | 平台集成面空白 | 端壳落地时补；深链/URI 校验进 THREAT_MODEL | kotlin-ui | planned |
| R-10 | 性能全无实测 | 预算不可验收 | `PERF_BUDGET.md` 逐项 no-data；有运行环境后补测 | lead | OPEN |
| R-11 | 门禁 QA1 的 cargo 命令从仓库根执行、绕过 `.cargo/config.toml` | 本机网络下 QA1 恒红（非代码问题） | 门禁内 `cwd=app/core` 或 `--offline`；登记 OPEN-QA-03 | lead | OPEN |

## 12. 术语表

| 术语 | 含义（本件口径） |
|---|---|
| Pack | 可分发的数据包：`nf-pack/1` 清单 + items；kind ∈ base/template/overlay |
| base / overlay | base = 只读内容层；overlay = 用户覆盖层（条款开关/参数/预设/自定义资产） |
| 真源 | 协议/管线/模块/资产内容的唯一承载地（仓库根）；APP 只引用不复制 |
| digest | `sha256(canonical_bytes)` 的 64 位小写十六进制；引用钉 `{id, version, digest}` |
| tree digest | `sha256(canonical([{path, sha256, size}] 按 path 升序))`，不含清单自身与签名件 |
| canonical | 键按码点升序、紧凑分隔、无浮点/NaN 的 UTF-8 JSON 字节（nf-canonical/1） |
| fail-closed | 未知/超限/不支持一律拒绝并给登记错误码，不降级放行 |
| L0 / L1 / L2 | L0 结构（schema+引用在场）/ L1 契约（约束与验收逐条求值）/ L2 仓库协议层（可选，缺失 exit 4） |
| golden | 由 Rust 参考实现生成的期望输出夹具，Python 逐字节复核 |
| oracle | 与参考实现独立的第二实现（此处 = Python `canonical.py`），用于对账 |
| CCOS | 执行面（外部）：接收 `ccos-task/1`、回传 `ccos-result/1`；密钥只在其侧 |
| TUI | 终端界面（`tui/nf.py`）：菜单/动作/自检的既有真源 |
| VIP | 面向专业作者的高阶作者面（pro/expert 模式 + 领域工作台）；非通用 IDE（ADR-APP-007） |
| OPEN / OPEN-TOOLCHAIN / OPEN-EXTERNAL | 未完成/工具链不可得/外部条件不可得；必须带 owner 与下一步 |

## 13. 复跑入口（本件判据汇总）

```bash
# 契约层
python -m pytest app/tests/test_schema_valid.py app/tests/test_schema_negative.py -q
# 核心
cd app/core && cargo test --offline   # cargo 配置按 cwd 发现；从仓库根用 --manifest-path 会绕过 .cargo/config.toml
# APP 门禁（QA0–QA6 + S0–S15）
python app/gates/run_gates.py --only QA0 QA1 QA2 QA5 QA6
# TUI（复用面，不重写）
python tui/nf.py --selftest
# 依赖面
cd app/core && cargo tree --offline -e normal
```

**判据命令的两个操作约束（本机实测踩到，写进契约面）**：

1. `cargo` 的配置按 **cwd** 发现，不按 `--manifest-path` 所在目录发现。从仓库根执行 `cargo test --manifest-path app/core/Cargo.toml` 会绕过 `app/core/.cargo/config.toml` 的镜像配置 → 本机直连 crates.io 失败（代理拦截）。正确写法：`cd app/core && cargo test --offline`（或先设 `CARGO_NET_OFFLINE=true` + 显式源）。
2. `app/gates/gates.json` 的 QA1 `q1-core-test` 用的是 `cargo test --manifest-path app/core/Cargo.toml --quiet`（从仓库根跑）→ 在本机网络条件下会因第 1 条失败。这是门禁命令设计问题，不是核心失败；登记 `OPEN-QA-03`（owner lead），修法：门禁内 `cwd=app/core` 或加 `--offline` 且保证镜像/缓存可用。
> 本件为架构声明：`planned` / `OPEN` 项不是已实现能力，不得在交付/发布材料中被引用为「已完成」。
