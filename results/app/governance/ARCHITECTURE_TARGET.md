# NF 硬技术目标架构

> 性质：目标架构 + 执行记录。SDIR / 构建图 / 证据包 / 求解 / 复用已落地；24 个 H 中 10 项有可复算证据，其余仍是目标。
> 目的：用语义文档 IR、内容寻址构建图、约束求解、证据链和声明式扩展，支撑 10 条 Frontier Trials。

## 1. 四个新契约

### 1.1 nf-sdir/1（Semantic Document IR）

~~~text
nf-sdir/1
  source[]:
    id, bytes_sha, mime, pages, name
  blocks[]:
    id, type, text, attrs, children, source_ref, bbox, hash
    type: document|section|heading|paragraph|list|list_item|table|table_row|table_cell|
          figure|caption|footnote|footnote_ref|crossref|citation|code|math|quote|index
  relations[]:
    from, to, kind: crossref|caption|footnote|toc|index|cite|anchor
  accessibility[]:
    block, alt, lang, role, header, reading_order
  provenance[]:
    block, source_id, page, bbox, transform, input_hashes
~~~

约束：

- 每个 block 有稳定 id 和 content hash。
- 每个关系可双向解析；悬空关系 fail-closed。
- 每个 block 可追到 source/page/bbox/transform；无溯源不能进 SDIR。
- 每个可访问字段可缺省，但缺失必须显式记为 missing，不得静默。

### 1.2 nf-build-graph/1（内容寻址构建图）

~~~text
nf-build-graph/1
  nodes[]:
    id, kind: input|transform|output, input_hashes, output_hash, cache_key
  edges[]:
    from, to, port
  outputs[]:
    path, sha256, bytes
  environment:
    core_version, schema_version, font_hashes, locale, fixed_mtime
~~~

约束：

- 同输入、同环境、同版本 → 同输出 sha。
- 每个输出可追到输入 hash、transform、plan hash。
- 缓存键包含所有影响输出的环境因素（字体、locale、mtime 规则）。
- 失败不写半成品；写临时文件 + rename + fsync。

### 1.3 nf-evidence/1（证据随包）

~~~text
nf-evidence/1
  artifact_sha, bytes
  input_shas[]
  plan_sha
  validation:
    profile, validator, version, errors, warnings
  provenance:
    graph_sha, block_lineage[]
  signature:
    alg, value, public_key, key_fingerprint
  tool_versions:
    core, schema, validators
~~~

约束：

- 证据与产物分离但绑定；篡改任一字段可检出。
- 离线验证不依赖网络/账号/时间戳服务。
- 签名不等于 CA/TSA；身份边界写清楚。

### 1.4 nf-extension/1（声明式扩展）

~~~text
nf-extension/1
  id, type: adapter|renderer|validator|theme|preset
  compat:
    min_app_version, schema_version
  capabilities[]
  signature
~~~

约束：

- 只允许声明式扩展；不执行任意代码。
- 扩展失败隔离，不得破坏主流程。
- 严格模式拒绝未签名扩展；普通模式允许本地未签名但明确标注。
- 扩展不得联网、读密钥、越权读文件。

## 2. 新 core op

| 组 | op | 作用 |
|---|---|---|
| SDIR | sdir-import | 源文档 → nf-sdir/1，带保真账本 |
| SDIR | sdir-validate | 结构/关系/溯源/可访问性校验 |
| SDIR | sdir-diff | 块/表格/关系级差异 |
| SDIR | sdir-merge | 三方合并，冲突报告 |
| 规划 | plan-solve | 由 spec+模块+资产求解合法 plan |
| 规划 | plan-explain | unsat core / 选择理由 |
| 构建 | build-plan | 生成 nf-build-graph/1 |
| 构建 | build-run | 执行构建，产出 artifacts + evidence |
| 构建 | build-incremental | 最小重建集 |
| 导出 | export-profile | 单 IR 多 Profile |
| 导出 | export-accessible | PDF/UA、EPUB A11y、DOCX 可访问 |
| 证据 | evidence-verify | 离线验证产物+证据+签名 |
| 复用 | reuse-index | 跨项目块索引 |
| 复用 | reuse-impact | 更新影响传播 |

JSON 信封不变；旧 op 不删；旧 nf-doc/Markdown 作为 SDIR 适配器。

## 3. 数据流

~~~text
source
  → sdir-import（保真账本 + 溯源）
  → nf-sdir/1
  → plan-solve（类型/约束/资源）
  → nf-build-graph/1
  → build-run / build-incremental
  → artifacts
  → export-profile / export-accessible
  → nf-evidence/1 + signature
  → package / share / archive
~~~

回灌：

- 用户编辑块 → block hash 变化 → build graph 只重算依赖 → evidence 更新。
- 评审/签收 → evidence 记录 reviewer/validation；不覆盖旧 evidence。
- Pack 更新 → overlay 合并 → 影响项目 → 重新 plan/build/validate。
- 复用图更新 → 影响项目列表 → 冲突检测 → 人工裁决。

## 4. 子系统改动

### app/core（Rust）

- 新模块：sdir、build、solve、merge、evidence、reuse。
- 新 op 接入现有 CLI/FFI 信封；不改 ABI 版本语义，只加能力。
- 确定性：固定 mtime、排序、hash、无时间戳/随机/绝对路径进产物。
- 失败：半成品不落盘；错误码带 path/fix；未知版本 fail-closed。

### app/schema

- 新增 4 个契约；旧 schema 不改。
- 版本迁移：nf-doc/1 → nf-sdir/1 适配器；旧项目可读，新项目写 SDIR sidecar。
- 所有新 schema 必须有正反夹具、limits、错误码。

### app/android

- 导入：SDIR 预览、保真账本、低置信人工确认。
- 创作：块/关系/可访问性编辑；不暴露原始 JSON。
- 交付：多 Profile、可访问导出、证据包、离线验证。
- 迭代：语义 diff/merge、冲突裁决、复用图影响列表。
- Pack：签名/信任/回滚 UI，明确“本地 pin ≠ 签名”。

### app/tests / scripts

- 新语料与 ground truth；golden；property；fuzz；跨格式。
- hardtech_bench.py 跑 10 Trials；结果落 results/app/governance/。
- 真机矩阵：500 页、杀进程、200% 字号、横屏、深色、CJK/RTL。

### 不做

- 不做通用 Markdown 编辑器/代码 IDE/云同步/账号/端上 LLM/任意代码插件。
- 不把“能导入/能导出/能搜索”当硬技术力。

## 5. 迁移与兼容

1. 旧 nf-doc/Markdown 继续可读；新 SDIR 作为内部 IR，导出旧格式不变。
2. 旧项目首次打开：生成 SDIR sidecar，保留原文件；失败回退旧路径。
3. Pack/overlay 兼容：Pack 仍是数据，不执行代码；扩展清单签名。
4. 版本：nf-sdir/1 起；破坏性变更升版本 + migration；N-2 可迁移。
5. 降级：新版本写出的项目在旧版本打开时，明确拒绝或只读，不静默丢字段。

## 6. 边界与失败模式

- 版式分析低置信：标 low-confidence，人工确认；不静默猜。
- 表格合并单元格：保留拓扑；无法解析时保留原图 + 文本。
- 脚注/交叉引用悬空：fail-closed，给 path/fix。
- 500 页 OOM：流式/分块/检查点；超限明确拒绝。
- 构建不确定：字体/时间戳/locale 全部进 cache key；不确定则失败。
- 合并冲突：0 静默丢失优先；无法裁决则保留双方 + 冲突报告。
- 求解超时：有界搜索 + unsat/超时说明；回退人工。
- 签名/回滚：未签名严格拒绝；冻结/降级攻击有测试。
- 扩展恶意：无网络/无密钥/无任意代码；失败隔离。

## 7. 验收接口

每个 H 能力必须有：

- benchmark（语料 + 指标 + 阈值）
- ground truth
- 可复跑命令
- 证据落点
- kill criteria

没有这些，不进入 H 梯子；只有 proven 才写“已实现”。
