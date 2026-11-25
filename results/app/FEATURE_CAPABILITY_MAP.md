# NF Mobile 功能能力链地图

> 口径：以当前 Android **NF Mobile 0.2.0** 的可达界面与已接线能力为准；共享核心只记录被 APP 调用的部分。Desktop NF Studio、Python CLI/TUI、CCOS 执行面不计入本图。
> 说明：一个“能力节点”是一个功能组，组内包含多个细粒度操作；“所有功能”指当前 APP 可达功能面，不等于发布/签名/上架完成。
> 旧 8 屏中的独立 Protocol / Graph / Assembly 页已不再是主入口，其能力分别并入“创作台”和“交付台”，不重复计数。
>
> **v2 硬技术治理（2026-11-24）**：本图 92 节点仍是“当前可达功能面”；另建 112 节点覆盖基线（92 + 12 缺口 + 8 C9）与 24 项硬技术 / 10 条 Frontier Trials。新增 20 节点是治理目标，不代表已实现；0 项硬技术 proven。见 [硬技术治理包](governance/README.md)、[24 项阶梯](governance/HARD_TECH_LADDER.md)、[10 条 Trials](governance/FRONTIER_TRIALS.md)。

## 1. 能力链总览

```
C8  体验与治理（横切：导航 / 搜索 / 设计系统 / 自适应 / 无障碍 / 主题 / 语言 / 反馈）
C7  资产、协作与演进（Pack / 模板 / 项目 / 备份 / CCOS）
C6  交付与分发（导出 / 分享 / 签收 / 归档）
C5  质量与验收（L0–L1 / 复现 / 验收 / 人审）
C4  装配与生产（计划 / 槽位 / 装配 / 块编辑 / 补丁 / 合并）
C3  内容建模（协议 / 管线 / 规格 / 覆盖）
C2  结构理解（切片 / 映射 / 草稿 / 模板 / 样本）
C1  内容接入（文件 / 分享 / OCR / 文档 / 包）
C0  运行时底座（核心 / 契约 / 存储 / 安全 / 诊断）
```

主链是 **C1 → C2 → C3 → C4 → C5 → C6**；C7 在交付后接管资产演进，并把变更回灌 C2–C4；C0 支撑全部；C8 横切全部。

**链的硬约束**

- 上层只消费下层产物：C4 不自己解析文件，C6 不绕过 C5 直接导出。
- C5 失败回灌 C4/C3：问题定位到槽位、块、规格或管线，而不是只报“失败”。
- C7 的 Pack 更新回灌 C3：更新后必须重新创作/校验；C2 的模板候选可回灌 C3。
- C8 不产生内容，只改变全链的可达性、可读性与效率；C0 不产生业务语义，只提供 fail-closed 执行与可诊断性。

## 2. 分层与节点数

| 层 | 能力链角色 | 节点数 | 关键产物 | 主要入口 |
|---|---|---:|---|---|
| C0 | 运行时底座 | 7 | 稳定调用、持久化、错误与诊断 | 全局 |
| C1 | 内容接入 | 9 | 归一化文本、`nf-import/1` | 库 → 导入；系统分享 |
| C2 | 结构理解 | 8 | 切片、映射、导入草稿、项目引用 | 导入向导 |
| C3 | 内容建模 | 10 | 协议 / 管线 / 规格 / overlay | 项目 → 创作 |
| C4 | 装配生产 | 12 | Markdown、块编辑结果、nf-doc、批量包 | 项目 → 交付 |
| C5 | 质量验收 | 11 | 校验报告、验收清单、签收、评审 | 交付台 → 校验/评审 |
| C6 | 交付分发 | 9 | md/docx/pdf/epub/html/json/zip/skill/nf-doc/preserve | 交付台 → 导出 |
| C7 | 资产、协作与演进 | 13 | Pack 版本、项目包、备份、CCOS 记录 | 库 / Pack 中心 / 设置 / CCOS |
| C8 | 体验与治理（横切） | 13 | 导航、搜索、设计系统、无障碍、偏好 | 全局 |
| **合计** |  | **92** |  |  |

## 3. 分层功能清单

### C0 运行时底座（7）

- **C0-01 共享核心桥**：Kotlin/JNI 调 Rust `nf-app-core`；统一 JSON 信封 `{ok, exit, result, error}`；覆盖 canonical / pack / import / protocol / graph / spec / assemble / validate / export / update / ccos / project 等 op；ABI 与原生库可用性诊断。
- **C0-02 契约与错误码**：共享 schema / limits / error_codes 单一真源；65 个错误码带 `message` + `fix`；未知版本/枚举/超限 fail-closed；canonical JSON + sha256。
- **C0-03 本地数据与原子写**：app 私有 `projects/`、`library/packs/`、`drafts/`、`exports/`、`contracts/`；原子写与临时文件；无网络、无账号、无遥测。
- **C0-04 平台文件/分享接入**：SAF/OpenDocument；FileProvider 只读 URI；SEND / SEND_MULTIPLE / VIEW / PROCESS_TEXT；应用快捷方式（新建、导入、搜索）。
- **C0-05 安全与隐私边界**：文件大小、zip 条目数、路径、解压总量限制；拒绝密钥形状；分享脱敏（绝对路径/用户名/邮箱/密钥）；manifest 移除 INTERNET / ACCESS_NETWORK_STATE。
- **C0-06 诊断与崩溃**：核心/ABI/错误码/构建诊断；崩溃日志；诊断包复制、导出、分享。
- **C0-07 存储与缓存**：项目/草稿/导出/Pack/归档/缓存分类统计；清理导入/分享缓存；导出与备份保留策略。

### C1 内容接入（9）

- **C1-01 文件导入**：SAF 单文件；文本、Markdown、JSON、CSV、HTML、ZIP 等；YAML 由核心适配器支持；64 MiB 上限；UTF-8 / UTF-16 BOM / 无 BOM 启发式；记录来源 name/mime/size。
- **C1-02 分享导入**：SEND、SEND_MULTIPLE、VIEW、PROCESS_TEXT；多条目队列；逐项导入 / 下一项 / 忽略其余；授权失效提示；透明确认卡转交主界面，不在接收页解析落盘。
- **C1-03 剪贴板与示例**：纯文本、CSV 剪贴板；内置示例内容；库首屏“粘贴一段，直接成稿”；快速粘贴入口。
- **C1-04 结构化文档**：PDF 文字层；DOCX `word/document.xml`；EPUB container/OPF/XHTML 章节；HTML 嵌套列表、表格、图片、代码块、引用块、实体 → Markdown。
- **C1-05 OCR**：图片中文 OCR（ML Kit bundled）；扫描 PDF 逐页 OCR，20 页上限并提示截断；失败给出可执行修复。
- **C1-06 CSV/TSV 表格**：文件或剪贴板解析为 Markdown 表格，保留表头与对齐。
- **C1-07 归档/包导入**：项目包、项目合集 `nf-bundle/1`、模板包 `nf-template/1` zip、preservation 归档；识别后分流到导入、项目或模板流程；缺绑定 Pack 时警告并给入口。
- **C1-08 接入治理**：魔数 → MIME → 扩展 → 内容特征嗅探；低置信不自动入库；重复 digest 检测（跳过 / 新建 / 更新现有草稿）；超限或未实现格式 fail-closed；不静默覆盖原文。
- **C1-09 来源与历史**：保留 source digest/name/mime/size；最近导入记录与清空；恢复上次预览；保存原始核心响应，拒绝用重序列化结果冒充核心产物。

### C2 结构理解（8）

- **C2-01 格式嗅探与适配**：未实现格式返回 `NF-IMP-004`；不猜测、不造数据；适配器统一产出可审阅的 Markdown/结构。
- **C2-02 自动切片**：按标题/段落切片；显示覆盖率；建议“章节稿”或“自由稿”；切片预览。
- **C2-03 零切片（zero-slice）**：映射、例外、覆盖率、槽位值；采用切片映射；用切片直接建项目。
- **C2-04 映射建议**：core `map-suggest`；逐条 confidence；≥80 默认采纳；<60 标“低置信”；全部采纳/全部取消；未映射列表。
- **C2-05 导入草稿**：保存 `nf-import/1` + 映射决策 sidecar；草稿列表打开、重命名、删除；最近导入可重新打开。
- **C2-06 草稿转项目**：快速建项目 / 转为项目；按槽位名预填协议字段；保留映射可继续调整；生成项目引用。
- **C2-07 模板候选/模板包**：保存通过 `spec-validate` 的候选；复制/分享 JSON；导出模板包；导入候选；用模板建项目；删除/清空。
- **C2-08 Prompt / AI 样本**：保存用户主动确认的 Markdown 样本；复制/分享/删除/清空；分享 Prompt Pack；不自动上传、不调用模型。

### C3 内容建模（10）

- **C3-01 协议条款/字段**：条款启用/停用；字段必填/可选编辑；缺必填与未声明占位符本地预检。
- **C3-02 协议渲染/规则**：core `protocol-render`；规则求值与兼容性由核心 fail-closed；返回渲染条款列表。
- **C3-03 管线图编辑**：节点增删（stage/module/asset/branch/merge）、模块绑定、端口、权重展示、边增删；本地表单检查。
- **C3-04 管线校验**：core `graph-validate`；DAG/环、入口出口可达、端口、模式、必需阶段；问题定位。
- **C3-05 规格章节/槽位**：章节标题/必填；槽位名称/类型/必填；章节与槽位列表。
- **C3-06 规格校验**：core `spec-validate`；双向引用、约束、槽位定义；保存规格产物。
- **C3-07 作者覆盖**：只写项目 `nf-overlay`，不改 Pack base；保存到项目；返回 sha256 与状态提示。
- **C3-08 编辑安全**：撤销/重做；图编辑 900ms 防抖自动保存；未保存协议草稿恢复；保存中/失败错误卡。
- **C3-09 Pack 绑定/引用**：Pack id/version/tree；协议/图/规格 digest；Pack 缺失阻断创作并给 Pack 中心入口。
- **C3-10 模板覆盖/引用**：项目内模板 spec 覆盖；移除覆盖回 Pack 原 spec；模板参考复制/分享。

### C4 装配生产（12）

- **C4-01 装配计划**：core `graph-compile` 生成 plan；steps/slots/digest；计划持久化与恢复。
- **C4-02 槽位输入**：必填/选填与进度；粘贴、示例、清空、文件导入（1 MiB）；按 kind 清洗；预算字数、前缀、后缀、pattern。
- **C4-03 槽位批量导入**：按 `---` 或空行分段；仅填空槽 / 覆盖已有；统计填入、跳过、追加、丢弃。
- **C4-04 约束面板**：required / min / max / prefix / suffix / pattern 逐项问题；就地编辑；无问题提示。
- **C4-05 装配**：core `assemble`；返回 Markdown；必填缺失、预算/格式/非空校验失败阻断。
- **C4-06 预览**：Markdown 预览、全屏、复制、脱敏分享、保存为样本、分享 Markdown。
- **C4-07 块编辑**：编辑段落、上移/下移、删除、新增段落；撤销/重做；填入槽位；放弃编辑确认。
- **C4-08 变换**：批量替换/前缀/后缀/截断；手动变换 lower/upper/trim/collapse/prefix/suffix/replace/truncate；从单块修改推断；保存并复用变换。
- **C4-09 形式化**：从块内容建议槽位；形式化/忽略；填入对应槽位。
- **C4-10 nf-patch**：解析补丁；逐条选择应用；变更预览；拒绝统计；撤销；保存到项目稿；保存并重新装配；L1 预检。
- **C4-11 nf-doc 合并**：选择 2 个以上 `.nfdoc.json`；同名章节冲突保留；左/右/双方；块编辑；保存/分享合并结果。
- **C4-12 多项目批量装配**：选择项目；各用自身交付草稿；并行装配；逐项失败聚合；产出 `nf-batch/1` zip（单项目 md/nf-doc + 合并 md/nf-doc）。

### C5 质量验收（11）

- **C5-01 L0/L1 校验**：core `validate`；结构/契约；verdict；issue path/fix；L2 缺环境时 fail-closed，不降级当通过。
- **C5-02 问题定位/修复**：错误码 + 对象路径 + message + fix；最多展示 20 条；错误卡统一呈现。
- **C5-03 导出前门禁**：L1 必须 pass；正文编辑后标记 stale，需重新校验；不通过不导出。
- **C5-04 纠正 Prompt**：按 issues 生成修正 Prompt；分享给 AI/他人；回填仍走普通导入与校验。
- **C5-05 导出复现**：同输入两次导出逐字节比对；稳定/首个差异偏移。
- **C5-06 导出物校验**：manifest 的 bytes/sha256 与实际文件对账；导出记录 ok/fail。
- **C5-07 验收清单**：L1 通过 + 必填槽位已填 + 至少一次导出；三项全通过才可签收。
- **C5-08 设备签收**：Android Keystore ECDSA P-256；签名载荷含 project/accepted/time/artifact sha；公钥指纹；导出物变化则签收失效。
- **C5-09 项目人审**：reviewer + note；通过/驳回；需先校验/导出；subject digest；内容变更提示评审可能失效；通过后项目状态回写 reviewed。
- **C5-10 性质自检**：M1 / M12 / M25 确定性 property；PASS/FAIL 与失败 seed。
- **C5-11 归档链/升级**：preservation 的 predecessor 必须等于前包 SHA-256；链校验；旧包补 oais/grant/predecessor 升级。

### C6 交付分发（9）

- **C6-01 文档导出**：md、zip、docx、pdf、epub、html；PDF 优先 WebView HTML/CSS，失败回退基础文本；EPUB 轻量 EPUB3。
- **C6-02 数据/迁移导出**：json、skill（`SKILL.md` + `mcp.json` + `README.md`）、nf-doc；确定性 zip mtime。
- **C6-03 长期保存包**：preserve zip：`document.md`、`document.nfdoc.json`、`grant.json`、`oais.json`、`preservation.json`，有签收时加 `contract.json`；fixity、predecessor、确定性。
- **C6-04 DOCX 参考样式**：选择参考 DOCX；注入 styles / sectPr / theme / numbering / header / footer。
- **C6-05 分享/打开/复制**：分享 Markdown、导出文件、修正 Prompt、脱敏文本；系统 chooser；外部 App 打开；复制。
- **C6-06 导出记录**：最近 20 条格式/文件名/sha/时间/bytes/ok；清空记录；Markdown 导出成功后推进 exported，其他格式记录导出。
- **C6-07 能力授权**：read / comment / reassemble / export / share；0/7/30 天；撤销；写入 `grant.json`；导入侧校验 read。
- **C6-08 归档只读**：校验 preservation；读取 grant；只读预览；导出归档内容；恢复为导入稿；无 read 权限则拒绝。
- **C6-09 交付状态**：装配/校验/Markdown 导出推进项目状态；状态提示；失败回写提示。

### C7 资产、协作与演进（13）

- **C7-01 Pack 安装**：zip 或内置示例；manifest/hash；同 id+version 不覆盖；app 私有目录；安装后校验提示。
- **C7-02 Pack 校验/信任**：`pack-verify`；tree/count；固定 tree、取消固定、tree 不一致警告（本地信任，非签名）。
- **C7-03 Pack 详情/卸载**：条目、tree、目录、安装时间；卸载确认；项目引用保护，归档项目不受影响。
- **C7-04 更新计划**：选 base + 新 zip 或 `.nfupdate.json`；`pack-diff`；added/removed/modified；breaking、影响项目、overlay 键。
- **C7-05 冲突裁决**：keep_mine / take_new / defer；默认 defer；未全部裁决不得应用（NF-PCK-006）。
- **C7-06 应用/回滚**：原子替换 + 复验；新版本落 `packs/<id>/<version>`；版本回滚删除更新版本；迁移前备份可恢复 projects/drafts 等。
- **C7-07 项目生命周期**：从 Pack 新建；复制、重命名、对比、归档、恢复、永久删除；复制项目 ID；归档撤销。
- **C7-08 状态/历史**：draft → authoring → assembled → validated → exported → reviewed 相邻推进；历史条数与明细；分享历史。
- **C7-09 项目包/合集**：单项目完整包分享/导入；`nf-bundle/1` 全项目导出；缺 Pack 警告并跳转 Pack 中心。
- **C7-10 本地备份/恢复**：备份 projects/archive/drafts + prefs/trust/search 等 meta；manifest sha；恢复前检查 + 当前快照；回滚上次恢复；保留 5 个；删除备份。
- **C7-11 模板/项目复用**：项目保存为模板候选；导出模板包；模板引用；导入模板建项目；项目内 spec 覆盖。
- **C7-12 CCOS 交接**：加载 ccos-task / ccos-result；导入前预检；reviewer + note；通过/驳回；项目 reviewed 回写；清除会话；拒密钥形状；不联网。
- **C7-13 能力层级/策略**：Free 默认全开；Pro/CCOS 规则表；无购买/授权入口；未知能力默认 Free。

### C8 体验与治理（13）

- **C8-01 导航/外壳**：5 目的地（库/工作台/创作/交付/我的）；单层详情栈；返回；状态保存/恢复；底部栏或 NavigationRail。
- **C8-02 工作流**：五阶段（创作/装配/校验/交付/评审）；进行中/已交付/全部；唯一下一步；流程页。
- **C8-03 库管理**：项目/最近/Pack/归档；6 状态筛选 + 全部；最近/标题/状态排序；左滑归档/工作流；撤销归档；最近项目优先。
- **C8-04 全局搜索**：项目、Pack、条款、字段、节点、章节、槽位；按类型/Pack 过滤；最近搜索；键盘 ↑↓ / Enter / Esc。
- **C8-05 命令面板/快捷方式**：9 个命令（导入、新建、搜索、Pack 中心、Pack 更新、CCOS、设置、错误码、导入项目包）；最近使用前置；静态快捷方式 + 最近项目动态快捷方式。
- **C8-06 设计系统**：primitive → semantic → component tokens；4dp 网格；NfType；颜色/对比度/排版/间距/动效/节奏；设计系统预览与屏幕审计工具。
- **C8-07 自适应**：compact / medium / expanded；720dp 内容上限；手机/折叠/平板/多窗口；横屏；200% 字号头部压缩/图标化。
- **C8-08 无障碍/触觉**：contentDescription、角色、48dp 触达、polite/assertive 实时区域、触觉反馈、大字号；语音读屏全屏逐项以真机人工验收为准。
- **C8-09 主题**：system / light / dark；动态取色（Android 12+）；深色窗口背景/系统栏；设计 token 统一。
- **C8-10 语言**：中文 / English / 跟随系统；per-app locale；values-en；文案资源化；错误码中文/英文资源。
- **C8-11 反馈/恢复**：空态 CTA；Notice / ErrorNotice；错误码 + fix；Snackbar 撤销；自动保存；禁用/忙碌态；进度提示。
- **C8-12 隐私/诊断/关于**：本地处理、无网络权限、无账号/遥测；诊断复制/导出；崩溃分享/清除；65 错误码检索；关于/许可/隐私。
- **C8-13 首启引导**：3 步引导；跳过/上一步/下一步；载入示例；示例已存在提示；失败重试；引导完成持久化。

## 4. 一条真实主路径（把 92 个节点串起来）

1. **C1**：从微信/QQ/文件管理器分享一个 Markdown/PDF/DOCX/EPUB，或从库中粘贴一段文本。
2. **C2**：核心嗅探 → 自动切片 → 显示映射 confidence → 保存导入草稿，或直接用切片建项目。
3. **C3**：在创作台调整协议条款/字段、管线节点/边/端口、规格章节/槽位；保存为项目 overlay。
4. **C4**：交付台编译 plan → 填/批量导入槽位 → 约束面板检查 → 装配 → 预览/块编辑/变换/补丁。
5. **C5**：跑 L1 → 按 issue path 修复 → 重新校验 → 导出物 sha 对账 → 验收清单全过 → 设备密钥签收。
6. **C6**：导出 md/docx/pdf/epub/html/json/zip/skill/nf-doc/preserve；分享、打开、记录、授权。
7. **C7**：Pack 更新/回滚、项目归档/备份、模板复用、CCOS 人审回填；变更再回灌 C3/C4 重新走 C5。

## 5. 证据落点

| 层 | 主要代码/文档 |
|---|---|
| C0 | `app/core/`、`app/android/.../core/`、`.../data/AtomicFiles.kt`、`FileAccess.kt` |
| C1 | `.../ui/screens/ImportScreen.kt`、`.../share/`、`.../data/*Importer.kt` |
| C2 | `ImportScreen.kt`、`.../model/ImportDoc.kt`、`.../data/ZeroSliceSession.kt`、`ImportDraftStore.kt` |
| C3 | `.../ui/screens/AuthorScreen.kt`、`.../data/AuthorArtifactStore.kt` |
| C4 | `.../ui/screens/DeliveryScreen.kt`、`.../ui/BatchAssembler.kt`、`.../ui/screens/NfDocMergeScreen.kt`、`PatchScreen.kt` |
| C5 | `DeliveryScreen.kt`、`.../data/ContractStore.kt`、`ContractSigner.kt`、`PreservationVerifier.kt` |
| C6 | `DeliveryScreen.kt`、`.../data/*Exporter.kt`、`ExportVerifier.kt`、`CapabilityGrant.kt` |
| C7 | `PackCenterScreen.kt`、`PackUpdateScreen.kt`、`SettingsScreen.kt`、`CcosScreen.kt`、`.../data/BackupService.kt` |
| C8 | `ui/NfMobileApp.kt`、`ui/theme/`、`ui/design/`、`ui/components/`、`state/Nav.kt` |

## 6. 边界（避免把能力图读成发布声明）

- 不含 **Desktop NF Studio**、**Python 控制面/CLI**、**TUI**、**CCOS 执行面**；APP 只做本地控制面与文件交接。
- CCOS 是 **文件交换 + 人审**，不是端上 AI/联网执行；APP 不持密钥、不直连模型。
- 不含 release 签名、Play 上架、公证、设备矩阵等发布工程项；这些是发布面，不是产品功能面。
- 语音读屏只登记“语义/触达/字号/实时区域”的代码能力；TalkBack/Jieshuo 的全屏逐项走查属于真机人工验收，不把未复跑项写成已通过。

## 7. 统计

- 能力层：**9**（C0–C8）
- 能力节点：**92**
- 主链：**6 层**（C1–C6）
- 支撑：**C0 底座 + C7 演进 + C8 横切**
- 对外交付格式：**10**（md、zip、docx、pdf、epub、html、json、skill、nf-doc、preserve）
- 错误码：**65**

## 8. v2 硬技术叠加层（目标，不是已实现）

- 覆盖基线：**112** 节点（92 基线 + 12 缺口 + 8 C9）；当前 92 个可达，20 个为治理目标。
- 硬技术：**24** 项（6 层 × 4：接入、结构化、编排、装配、交付、迭代复用）；当前 **0 proven**。
- Frontier Trials：**10** 条；当前 **0 通过**。
- 基本项（导入/导出/搜索/主题/备份/分享）降为 table stakes，不再作为技术力验收。
- 入口：[治理包](governance/README.md)、[24 项阶梯](governance/HARD_TECH_LADDER.md)、[10 条 Trials](governance/FRONTIER_TRIALS.md)、[目标架构](governance/ARCHITECTURE_TARGET.md)、[报告](governance/HARD_TECH_REPORT.md)。
