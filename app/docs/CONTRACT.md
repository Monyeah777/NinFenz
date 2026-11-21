# NF APP 契约层（A0 · 冻结件 v1）

> ⛔ 操作指令：本件是 APP 实施（`NF-APP-Final-方案-2026-11-15.md`）的 A0 契约冻结。任何 schema / 语义 / 错误码变更**必须**先改本件 + 对应 `app/schema/*.schema.json` + 夹具，再改两处实现（Rust 参考实现 `app/core/` 与 Python 消费面 `app/cli/`），并重跑 `app/gates/run_gates.py`。
> 状态：A0 冻结（2026-11-15）。性质：结果/契约件（不是规划件）。
> 依据：APP Final §4（粒度）/§6（数据模型）/§7（FR/NFR）/§9（Pack 更新）/§10（AI 与 CCOS）/§12（安全）/§18（验收）。

## 1. 范围与术语

APP = 人的控制面（Android/桌面/平板）；CCOS = 执行面；TUI/CLI = 终端与检验。本契约层冻结**三端共享的持久化格式与核心操作语义**：

| 名称 | 文件 | 用途 |
|---|---|---|
| `nf-pack/1` | `nf-pack.json` | Pack 清单（id/version/items/hashes/requires） |
| `nf-import/1` | `*.nfimport.json` | 导入识别结果（嗅探/结构抽取/映射建议） |
| `nf-doc/1` | `*.nfdoc.json` | 结构化文档（meta/sources/blocks；再装配输入） |
| `nf-protocol-pack/1` | `protocol/nf-protocol-pack.json` | 协议包（条款/字段/规则/示例/兼容/迁移） |
| `nf-pipeline-graph/1` | `*.nfg.json` | 作者管线图（节点/边/权重/参数/绑定） |
| `nf-md-spec/1` | `*.nfspec.json` | Markdown 规范（章节/槽位/约束/示例/验收/预算） |
| `nf-assembly-plan/1` | `*.nfplan.json` | 编译产物（步骤/模块/资产/权重/槽位/输出/回退） |
| `nf-validate-report/1` | `*.nfreport.json` | 校验报告（L0/L1/L2 + issue 定位 + fix） |
| `nf-template/1` | `template/nf-template.json` | 模板包（内嵌 protocol/spec 快照 + hashes） |
| `nf-pack-update/1` | `*.nfupdate.json` | base+overlay 更新计划（changes/impact/merge/conflicts） |
| `nf-overlay/1` | `overlay/nf-overlay.json` | 用户覆盖层（条款开关/参数/预设/自定义资产） |
| `nf-project/1` | `project.nfproject.json` | 项目引用集合（pack/protocol/graph/spec/assembly + 评审） |
| `nf-assemble-result/1` | `result.meta.json` | 装配元数据（digest/slots/missing） |
| `nf-export-manifest/1` | `*.nfmanifest.json` | 导出清单（files/source digest） |
| `nf-backup/1` | `nf-backup.json` | 更新备份清单（本地，时间戳仅此处允许） |
| `ccos-task/1` | `*.ccos-task.json` | 交给 CCOS 的执行任务（APP 不直连 API） |
| `ccos-result/1` | `*.ccos-result.json` | CCOS 回传结果 + 证据 + 人工复核状态 |

**单点真相**：协议/模块/资产/管线**内容**的真源仍是仓库根（`01`–`07`、`03_管线库`、`04_模块库`、`05_资产库`、`protocol/`）；APP 只新增**作者态/装配态/交付态**格式，不复制内容真源。任何 APP 产物引用真源一律用「ID + digest」双钉。

## 2. 规范 JSON（nf-canonical/1）与摘要

- 编码：UTF-8，无 BOM；换行 LF；禁用浮点（需要小数用整数定点或字符串）。
- 值域：null / bool / int / str / list / object（键必须是 str）；禁 NaN/Infinity。
- 文本：`json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` 的 UTF-8 字节（等价：键按 Unicode 码点序，紧凑分隔，最小转义 `" \\ \b \f \n \r \t` 与 `\\u00XX` 小写）。
- 摘要：`sha256(canonical_bytes)` 的 64 位小写十六进制。
- 文件项摘要：`sha256(file_bytes)`；**tree 摘要**：`sha256(canonical([{path, sha256, size}] 按 path 升序))`（不含 `nf-pack.json` 自身与签名文件）。
- 引用钉：`{id, version, digest}` 三元组；digest 缺一不可；unknown 引用 fail-closed。

**复算口径**：Rust `app/core` 为参考实现；Python `app/cli` 与 Kotlin 端必须逐字节一致（golden 夹具见 `app/fixtures/golden/`）。

## 3. 通用文件纪律

- 路径：一律 POSIX 相对路径；禁 `..`、绝对路径、盘符、UNC、NUL、保留设备名；路径字符集 = 可打印 UTF-8 去控制字符。
- 符号链接：导入/解包**拒绝** symlink/junction/硬链（fail-closed，错误码 `NF-SEC-002`）。
- 包限制（默认，写在 `app/schema/limits.json`，可被测试夹具覆盖）：单文件 ≤ 64 MiB；包解压总量 ≤ 512 MiB；条目数 ≤ 5000；单 entry 压缩比 ≤ 100:1；zip 嵌套 ≤ 1 层；JSON 深度 ≤ 64；YAML 别名展开 ≤ 1000；XML 实体禁用。
- 未知字段：schema 顶层 `additionalProperties: false`；`x-` 前缀扩展字段允许（实现必须原样保留或明确拒收，不得静默丢弃）。
- 未知 enum/格式/规则 op：**fail-closed**（exit 3，错误码 `NF-E-UNKNOWN-*`），不得降级放行。

## 4. 错误模型与退出码

| 退出码 | 含义 |
|---|---|
| 0 | 成功（`--json` 时 stdout 为单行 JSON） |
| 1 | 校验失败（报告已写出；`verdict` 为 `fail`/`warn` 由调用方按等级判定） |
| 2 | 用法/IO 错误 |
| 3 | 拒绝（策略/未知格式/超限/不支持的版本；fail-closed） |
| 4 | 环境缺失（工具/依赖不在场，如 docx/pdf 导出器） |

错误码登记表 = `app/schema/error_codes.json`（单一真源；实现与测试都从它取，不允许散落字面量）。错误码前缀：`NF-IMP-`（导入）、`NF-MAP-`（映射）、`NF-PRT-`（协议）、`NF-GRF-`（管线）、`NF-SPC-`（md spec）、`NF-ASM-`（装配）、`NF-VAL-`（校验）、`NF-EXP-`（导出）、`NF-PCK-`（Pack/更新）、`NF-SEC-`（安全）、`NF-CCOS-`（交接）。

## 5. 核心操作语义（A0–A5）

### 5.1 Pack

- `pack verify`：校验 manifest schema（L0）→ 逐 item `sha256/size` → tree digest → `requires` 解析 → 输出 `nf-validate-report/1`。
- `pack hash`：给定目录生成 `items`（按 path 升序）+ tree digest；**确定性**：同输入同字节。
- 安装/替换：只写 app 数据目录（`library/packs/<id>/<version>`），base 只读；同 id 不同 version 并存；`latest` 指针单独文件。

### 5.2 导入/嗅探/映射（A3）

- 嗅探顺序：**魔数 → MIME/扩展 → 内容特征**；置信度 = 整数百分比 0–100（**禁浮点**，canonical 只有 int），低置信（< 60）必须在 `detected.candidates` 给候选且不得自动入库。
- 首版适配器：`text`、`markdown`、`json`、`yaml`、`zip`、`nftpl`（模板包）、`nfpack`（Pack）。次版：`html`、`docx`、`pdf`、`ocr`——**未实现即 exit 3 + NF-IMP-004**，不得静默当文本。
- 结构抽取：标题（行、级别、文本）、段落数、代码块（语言、行数）、表格（列名、行数）；总量上限按 §3。
- 映射建议：标题→章节（`heading`→`section`）、段落→槽位（`paragraph`→`slot`）、代码块→示例（`code_block`→`example`）、表格→结构化（`table`→`structured`）；每条带 `confidence` + `rationale`；无法映射入 `unmapped`（素材/未分类）。
- `nf-import/1` 必须保留原文（`text` 或 `text_digest`+原文文件）与来源；**不静默覆盖**已有项目（只生成 DraftProject）。

### 5.3 协议包（A2）

- 条款渲染：`text` 中的占位符 `{{field_id}}` 用字段值替换；缺必填字段 → `NF-PRT-003`；未知占位符 → `NF-PRT-004`（fail-closed）。
- 规则求值：封闭 JSON 表达式 DSL，op 白名单：`and/or/not/eq/ne/gt/gte/lt/lte/in/matches/exists/len`；字段操作数形如 `{"field":"F-001"}`；未知 op/类型不匹配 → `NF-PRT-005`。
- 兼容：`compat.protocol_min/max` 与 `proto_version` 不符 → 拒绝（NF-PRT-006）；`migrations` 只允许声明不可执行脚本。

### 5.4 管线图（A2）

- 节点 id `N\d{2,3}`、边 id `E\d{2,3}`，全图唯一。
- 校验（L0）：节点/边引用存在；边 from/to 存在；端口在声明集合内；kind↔必填字段（module 节点必须有 `module_ref`）；权重仅 stage/module 且 0..100；`settings.required_stages` 必须被满足；图必须有 ≥1 stage、≥1 module。
- 校验（L1）：**无环**（拓扑排序失败 → NF-GRF-004）；入口/出口可达；分支节点出边 ≥2、merge 节点入边 ≥2；`mode=simple` 时禁止 branch/merge/asset 节点。
- 编译 `graph compile`：拓扑序 → `nf-assembly-plan/1` steps（`S\d{2}` 连续编号，从 01）；step 带 stage/module/weight/inputs（来自入边 `from_port`）；**step.stage = 该模块节点沿入边反向最近的 stage 节点 id**（不是下游 stage；找不到 → NF-GRF-005）；输出 plan digest = sha256(canonical(plan 去掉 digest))。

### 5.5 MD spec（A2）

- 章节 `SEC-\d{2}`、槽位 `SLT-\d{2,3}`；order 唯一且从 1 连续；slot.section 必须存在于 sections；sections.slots 与 slots.section 双向一致（NF-SPC-002）。
- 约束：`min_chars/max_chars/max_tokens` 正整数且 min ≤ max；`acceptance[].id` 唯一（`A-\d{2}`）；引用 `references[]` 必须有 digest。
- 预算：全 spec 预算 = Σ slot 预算；`nf-md-spec/1` 可选顶层 `budget.{max_total_chars,max_total_tokens}`——**给了才判**，超出 → NF-SPC-004（未给则不判总预算，不默认放行单元预算约束）。

### 5.6 装配（A2/A5）

- 输入：plan + spec + `inputs`（slot→值）；输出：Markdown + `nf-assemble-result/1` 元数据（plan/spec digest、slot 填充、缺失槽位、耗时不算（禁时间戳进产物））。
- 渲染规则（确定性）：按 section.order → section.slots 顺序；标题层级：spec 的 `heading_level`（默认 2）+ section 深度；槽位缺失：required → `NF-ASM-002`（fail），optional → 记 `missing`；代码块围栏语言取 slot.kind=code 的 `lang`。
- 阶段预览：`assemble --stage ST##` 只渲染该阶段可达 section；整篇 = 全部。
- 块级编辑：`assemble --block <section_id> --base-markdown <既有 Markdown>` 只替换该节（保留其余字节）；缺 `base_markdown` → NF-ASM-004（不猜全文）；块编辑后必须重跑 L0 校验。
- 失败回灌：渲染/校验失败必须给出 `path`（指向 plan step 或 spec slot）与 fix；不得静默跳过（NF-ASM-003）。

### 5.7 校验（A2）

- L0 结构：目标是否满足其 schema + 引用在场。
- L1 契约：spec 的 constraints/acceptance 对装配结果逐条求值；issue 路径 = `result.sections[i].slots[j]`。
- L2（可选 NF）：调用仓库协议层判据（`nf` CLI 子进程）——环境缺失 → exit 4（NF-VAL-005），不得降级当通过。
- 报告必须带 `target.digest`；同输入两次报告逐字节一致（禁时间戳）。

### 5.8 导出（A5）

- 形式：`md`、`zip`、`json`、`docx`、`skill`。`docx` = 核心直出 OOXML（WordprocessingML，确定性 zip，Unicode/CJK 可用）；`skill` = skill/MCP 脚手架包（`SKILL.md` + `mcp.json` + `README.md` + 可选 result.md/meta，`nf-mcp-scaffold/1`）。`pdf` **不内置**：用平台打印另存为 PDF（Android PrintManager / 桌面 javax.print）→ 核心 `export --format pdf` 返回 exit 4 + NF-EXP-004（OPEN，不冒充）。
- zip 确定性：entry 顺序 = path 升序；mtime 固定 1980-01-01T00:00:00Z；权限 0644/0755；不写 extra field；同名冲突拒绝（NF-EXP-003）。
- manifest（`nf-export-manifest/1`）：输出件摘要 + 来源 project/plan/spec digest；同输入同字节。

### 5.9 Pack 更新 / Overlay（A4）

- diff：base vs new（目录）→ added/removed/modified（path 升序）；impact = 受影响项目（引用该 pack 且 digest 变化）+ overlay 键；breaking = 删除或 schema 变更。
- overlay 迁移：稳定 ID（clause/field/slot/node 的 id）自动迁移；**冲突三类**：删除（本地有改动而新版删除）、重命名（同 ID 不同 path）、schema 变更（字段类型/必填变化）；冲突不静默丢，必须进 `conflicts[]` 并要求用户决定（默认 `defer`）。
- 应用：备份（`backups/<ts>/...`？——时间戳只进**本地备份指针**，不进 canonical 产物）→ 原子替换 → 复验 → 失败回滚；旧版保留。
- 同 id+version 不同 digest = 篡改/冲突 → 拒绝（NF-PCK-004）。

### 5.10 项目（A6 前置）

- `nf-project/1` 只存**引用** + 状态 + 评审；不内嵌 pack 内容（模板包除外）。引用两形：**Pack 引用** `{id,version,tree}`；**作者态文件引用** `{id,version,digest,path,sha256}`（语义身份 + 内容摘要 + 文件身份；graph/spec/assembly 三件同形——`nf-project.schema.json#/$defs/artifactRef`，禁止只给其一）。protocol 引用 = `{id,version,digest}`；overlay 引用 = `{path,sha256}`。
- 状态机：`draft → authoring → assembled → validated → exported → reviewed`；回退必须显式 `--force` 且记 history（append-only，禁时间戳进 canonical？history 允许 at 字段但只用于人读，digest 计算排除 history）。
- 评审：`review.state` ∈ none/pending/approved/rejected；approved 必须带 reviewer + note + subject digest（绑定被批对象，改一处即失效）。

### 5.11 CCOS 交接（A6）

- `ccos-task/1` 由项目生成：携带 pack/protocol/pipeline/spec digest、inputs、variables、constraints、acceptance、budget、policy、provenance；**禁**含密钥/绝对路径/本机用户名。
- `ccos-result/1` 导入：校验 task_digest 回钉 → artifacts 摘要 → evidence → 状态；`human_review.required` 恒 true（APP 人审确认）；密钥/预算/策略字段出现即拒（NF-CCOS-003）。
- 传输：文件/zip 默认；QR/本地桥可选（OPEN）。

## 6. 安全纪律（A0 冻结）

- 解析：zip slip / zip bomb / symlink / YAML bomb / XML entity / JSON depth / 大小上限——默认全拒并给 NF-SEC 错误码；负例进 `app/tests/test_security_negative.py`。
- WebView（若 UI 用）：JS 关闭、文件访问关闭、无网络、CSP；WebView 只用于**本地只读预览**。
- 组件：Android `exported=false` 默认；深链/intent 参数校验；FileProvider 路径限定；分享只读 URI + 临时缓存清理。
- 隐私：本地处理、无遥测、无账号；诊断只落本地；密钥只在 CCOS；分享前预览 + 脱敏（绝对路径/用户名/邮箱模式）。
- 供应链：APP 依赖不引入网络拉取脚本；构建隔离（check41 口径）；依赖版本钉死并留 LOCK。

## 7. 确定性（NFR-DET）

- 所有 canonical 产物（pack/import/protocol/graph/spec/plan/report/export/update/task/result）**禁时间戳、禁随机、禁绝对路径、禁环境信息**；同输入两次运行逐字节一致。
- 唯一例外：`nf-project/1.history[].at` 与 `ccos-*/provenance.*_at` 是人读字段；计算 digest 时按各 schema 的 `digest_exclude` 声明剔除（schema 内 `x-digest-exclude` 注解，实现必须遵守）。
- 排序一律按码点升序（path/键/id 列表），不使用 locale 排序。

## 8. 兼容与版本

- 每个 schema 的 `schema` 常量即版本（`nf-xxx/1`）；破坏性变更 = 新版本号 + migration 声明；未知版本 fail-closed（NF-E-VERSION）。
- `compat` 块（pack/protocol/template）声明 `min_app_version`；APP 启动检查不满足即拒绝加载并给升级指引。

## 9. 与仓库既有格式的边界

| 既有 | APP 侧 | 关系 |
|---|---|---|
| `protocol/production/assembly.schema.json`（nf-assembly/1） | `nf-assembly-plan/1` | **不同物**：前者是仓库生产平面计划（pipeline P## + 模块字符串），后者是 APP 作者图编译产物（节点/权重/槽位）。桥接 = `graph compile` 输出 + 仓库适配器（A2 后续），不互改 |
| `protocol/schema/pipeline.schema.json`（P## 声明） | `nf-pipeline-graph/1` | 同上：声明 vs 作者图 |
| `protocol/production/spec.schema.json`（nf-spec/1） | `nf-md-spec/1` | 前者是引用三元组（kind/ref/digest），后者是 MD 章节/槽位/预算；APP 的 references 字段引用前者 |
| `protocol/*.json` 真源 | Pack 内容 | APP 不复制；只按 ID+digest 引用 |

## 10. 验收钩子

- schema 正/反样例：`app/fixtures/schema/{valid,invalid}/`；每个 schema ≥1 正 ≥2 反（反例必须指定期望错误码）。
- golden：`app/fixtures/golden/<op>/`（input + expected）. 由 Rust 参考实现生成、Python 消费面复核；`--bless` 只允许在人工确认后使用。
- 门禁：`python app/gates/run_gates.py` → `app/results/GATES.json` + `app/results/SELF_AUDIT.json`（S0–S15）。