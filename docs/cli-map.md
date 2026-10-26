# NF CLI 命令地图（生成件 · 真源 = argparse 面 + terminal.FAMILIES）

> 本件由 `nf cli map --write` 生成，`nf cli map --check` 与实时重算逐字节对账；
> 手改会被下一次 check 判红。命令缺失/重复归族/空族见文末覆盖率块。

## 覆盖率

| 项 | 值 |
|---|---|
| 顶层命令 | 77 |
| 能力族 | 8 |
| 已归族 | 77 |
| 未归族 | 无 |
| 重复归族 | 无 |
| 空族 | 无 |

## 命令目录

| 命令 | 族 | 用途 | 机器面 | 相关文档 |
|---|---|---|---|---|
| `nf agent` | 装配与生产（forge） | 多 agent 协作契约（T10.3）：writer/critic/fact_checker/editor 四角色契约与域链（techdoc/regulatory）。角色引用既有模块/管线/gate profile，不新造能力；`plan… | 文本 | — |
| `nf approve` | 治理与决策（govern） | 内容绑定批准记录（机制借鉴 MCOP approved-changeset gate） | JSON | docs/en/release.md、docs/ja/release.md、docs/release.md |
| `nf assemble` | 装配与生产（forge） | 需求 → 自组装编排（44：一句话需求 → 装配计划；--check 对成品机器验收） | 文本 | docs/45_M2_回合级drill.md、docs/45_执行遥测规范.md、docs/45_质量纵深收口总档.md、docs/bench.md |
| `nf assertions` | 质检与验证（verify） | 数据化断言表（机制借鉴 Schematron；kind 为封闭集） | JSON | — |
| `nf asset` | 资产与货架（shelf） | 资产供应链台账（S2：add 入库 / verify 闭合 / inventory 盘点 / ls 浏览 / rm 摘除 / deprecate·restore 流转） | 文本 | docs/en/terminal.md、docs/interop.md、docs/ja/terminal.md、docs/meta/VERSION-MATRIX.md |
| `nf attest` | 治理与决策（govern） | 内容 attestation（内部差距：知识签名只自证可复现，无对外可验证的篡改证据）。签发时间戳取墙钟（`issued_at`），可用 `SOURCE_DATE_EPOCH`（可复现构建惯例）钉成固定值——机器面据此逐字节可复现。 | JSON | docs/attest.md、docs/EXPORT.md |
| `nf audit` | 治理与决策（govern） | 审计/验收（机制借鉴 Audit Report + Acceptance/Sign-off） | 文本 | — |
| `nf bench` | 服务与集成（integrate） | 执行结果跑分台（机制借鉴 ACP benchmark suite：外部实测的容器） | 文本 | — |
| `nf changelog` | 质检与验证（verify） | 变更日志生成：渲染确定（无墙钟，版本/日期由参数给）+ 逐条可溯源（只分组、不改写）；--write 把版本节插入 CHANGELOG 顶部并把 changes/unreleased/* 归档到 changes/<version>/ | JSON | docs/en/release.md、docs/ja/release.md、docs/meta/VERSION-MATRIX.md、docs/release.md |
| `nf cli` | 命令面与终端（meta） | CLI IA 机读层（T11.3）：从 argparse 命令面 + terminal.FAMILIES 构建 nf-cli-map/1（命令→族→用途→flags/has_json/相关文档），生成件 protocol/cli_map.… | 文本 | — |
| `nf cognition` | 图书馆与知识（library） | 认知族（机制借鉴 Glossary + SOP/Runbook/Playbook 分档） | JSON | — |
| `nf combine` | 资产与货架（shelf） | 组合引擎：任选若干域包（或直接点模块/资产）→ 层位堆叠 / 依赖闭包 / 事件闭包 / 资产借阅 / 合法性判定 → 可复算证书（T4）；`breadth` 对全部两两 + 抽样三元/四元/五元/六元跑同一套不变量证明广度；`mater… | 文本 | docs/combos.md、docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf completion` | 命令面与终端（meta） | 生成 shell 补全脚本（bash/zsh/fish；用法：nf completion bash >> ~/.bashrc） | 文本 | — |
| `nf conformance` | 质检与验证（verify） | 一致性报告工件（机制借鉴 MCOP runConformanceSuite：make it checkable instead of trusted） | JSON | docs/decision-layer.md、docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf daemon` | 命令面与终端（meta） | NF 执行层常驻守护：把「每条命令一次解释器启动」（实测 ~400 ms 固定成本）换成「一次启动、长期热跑」，客户端只做一次套接字往返。只绑 127.0.0.1 + 一次性令牌；单线程串行；每次请求比对 core/scripts 源码指… | 文本 | docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf decide` | 治理与决策（govern） | 决策层端口：把选择写成类型化问题交给决策模型；模型在门禁之外，缺适配器/超时/输出不合 schema 一律 abstained | JSON | — |
| `nf decisions` | 治理与决策（govern） | 决策记录（机制借鉴 ADR：supersede-only + 不可改） | 文本 | — |
| `nf demo` | 上手与自检（start） | 一键交付物演示（T3.1：默认 P06 技术文档全链 → 可交付 Markdown；叙事域用 `nf demo narrative` = P04 轻混 → CCV3） | 文本 | docs/en/terminal.md、docs/ja/terminal.md、docs/quickstart.md、docs/terminal.md |
| `nf design` | 治理与决策（govern） | 决策辅助工具族（v2.6-A：可选装载——钢人论证工作单） | 文本 | docs/41_波C_W3_实测记录.md、docs/需求收敛模板.md |
| `nf diff` | 质检与验证（verify） | 版本差异检测（41 波C C2：两份签名/文档 → 字段级差异 + 兼容判定） | JSON | docs/41_波C_C1_C2_实测记录.md、docs/迁移指南-基于nf-sig-diff.md |
| `nf doctor` | 上手与自检（start） | 环境自检（快速只读体检：关键文件/registry/schema/核心库——不开 verify 慢跑） | JSON | docs/45_质量纵深收口总档.md、docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf domain` | 资产与货架（shelf） | 域包工厂：读内部域规格（.rivet/private_archive/ai_packs/specs/<code>.json）生成 protocol.yaml / README / 模块×2 / 管线 / 资产×3（含 provenance… | 文本 | — |
| `nf driver` | 服务与集成（integrate） | 指令档机器面路由（机制借鉴 ACP driver override） | JSON | — |
| `nf endpoint` | 服务与集成（integrate） | 服务端点契约（机制借鉴 microsoft/ai-chat-protocol） | JSON | docs/interop.md |
| `nf events` | 服务与集成（integrate） | 全仓事件背书核对（补 check16/26 之外：社区域包订阅是否真有发布方） | JSON | docs/interop.md |
| `nf explain` | 质检与验证（verify） | check 修复指引（41 波C C5：缺什么/补什么/示例 三段式） | 文本 | docs/41_波C_C1_C2_实测记录.md、docs/迁移指南-基于nf-sig-diff.md |
| `nf facts` | 上手与自检（start） | SSOT：唯一机读事实产物 protocol/facts.json；--check 做逐字节比对 + 跨源不变量 + 字面量禁区断言（历史 MIT 句单独放行） | JSON | — |
| `nf handover` | 治理与决策（govern） | 接力协议（机制借鉴 SBAR；空未决即不合格交接） | 文本 | — |
| `nf help` | 命令面与终端（meta） | 显示 nf 或指定子命令的帮助 | 文本 | docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf impact` | 图书馆与知识（library） | 变更影响面预检（A4 前置：拟删除 module/protocol 前查破坏性影响） | 文本 | — |
| `nf import` | 装配与生产（forge） | 读入外部产物：`nf import <SKILL.md\|chara.json>`（旧面）；`nf import docx <file> [--json/--out]`、`nf import dita <file> [--json/--ou… | JSON | — |
| `nf interop` | 服务与集成（integrate） | 互操作导出面：把既有声明件实时派生为外部标准工具可读的文档（不新增真源；同一输入两次导出逐字节一致） | JSON | docs/en/terminal.md、docs/endpoint.md、docs/interop.md、docs/ja/terminal.md |
| `nf ir` | 质检与验证（verify） | 内容 IR（T7.2）：document/section/paragraph/claim/citation/entity/slot_ref 节点图；每节点稳定 id（路径+内容哈希）；render 规范形逐字节确定性；check 输出 s… | 文本 | — |
| `nf knowledge` | 图书馆与知识（library） | 双源知识层（机制借鉴一句式：编译时机按数据域选择） | 文本 | docs/en/terminal.md、docs/ja/terminal.md、docs/meta/VERSION-MATRIX.md、docs/terminal.md |
| `nf layers` | 上手与自检（start） | NF 抽象阶梯（真源 = protocol/LAYERS.json，机制借鉴多视图描述 / 稳定依赖 / 适应度函数 / 单一真源+生成投影）：抽象轴四阶（契约→资产→引擎→出口）、入口面（只登记角色，永不作为真源）、验证纵切（贯穿四阶的… | JSON | docs/en/layers.md、docs/en/terminal.md、docs/ja/layers.md、docs/ja/terminal.md |
| `nf library` | 图书馆与知识（library） | 云端图书馆机器面（内部差距：library 无 CLI 面、MCP 检索不覆盖馆藏、元数据非一等公民） | 文本 | docs/agent/ROUTES.md、docs/en/release.md、docs/examples/state-front/techdoc_front.md、docs/ja/release.md |
| `nf license` | 质检与验证（verify） | 图书馆许可证门（内部差距：登记表无许可列，入库产物不承载共享条款） | JSON | docs/library.md |
| `nf lint` | 质检与验证（verify） | 机械检查/修复（内部差距：既有扫描器只报告不修，仓库无 auto-fix） | JSON | docs/en/lsp.md、docs/en/terminal.md、docs/ja/lsp.md、docs/ja/terminal.md |
| `nf locales` | 治理与决策（govern） | 语言面：注册表 ⇄ 文件在场双向对账（入口锚点/切换行/结构；文档译件路径镜像 + source_sha256 防过期） | JSON | — |
| `nf lsp` | 服务与集成（integrate） | LSP 服务器（stdio Content-Length 分帧；诊断与 nf lint 同源，领域符号表来自 core/nf_language；--print-config 出编辑器配置） | 文本 | docs/en/lsp.md、docs/ja/lsp.md、docs/lsp.md、docs/nfal.md |
| `nf market` | 资产与货架（shelf） | 市场协议查询（B4：依赖闭包 + 挂载冲突预检；list 目录视图） | JSON | docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf model` | 治理与决策（govern） | 内容建模三件（机制借鉴 SKOS 概念方案 / 规范-说明件二分 / 数据契约要素） | JSON | docs/modeling.md |
| `nf module` | 资产与货架（shelf） | 模块生命周期（v2.8 波B S5：status 位 + deprecate/restore + 引用门禁 verify） | 文本 | docs/en/terminal.md、docs/ja/terminal.md、docs/machine_contract.md、docs/terminal.md |
| `nf nfal` | 质检与验证（verify） | NFA-L：声明层借既有 YAML + JSON-Schema IDL，命令层是封闭 guard 表达式（无用户函数/循环/赋值/IO）；用法见 docs/nfal.md | 文本 | docs/nfal.md |
| `nf output` | 资产与货架（shelf） | 产出形态面：把「产出一律是散文」的缺口机制化——形态清单（protocol/output_forms.json）、包级产出面（community/<包>/outputs/INDEX.json）、T0–T4 档位判定、T4 可复算面重算比对… | 文本 | — |
| `nf patterns` | 图书馆与知识（library） | 实践包品类（机制借鉴 ACP patterns：与内容域包并列的实践规范包） | 文本 | docs/patterns.md |
| `nf pipeline` | 资产与货架（shelf） | 管线脚手架（v2.8 波B S4：pipeline new——自 P00 骨架派生新管线） | 文本 | docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf postmortem` | 治理与决策（govern） | 复盘（机制借鉴 SRE postmortem） | 文本 | — |
| `nf preset` | 装配与生产（forge） | 预设配置（指令集 F：端壳退役后按「端壳能力一律落 CLI」把预设接成命令；落点 = NF_HOME，非仓库） | 文本 | — |
| `nf receipts` | 治理与决策（govern） | 协议层回执单根（把回执覆盖面从馆藏扩到协议层机读产物） | JSON | docs/interop.md |
| `nf register` | 装配与生产（forge） | 协议登记本地助手（B3-B：protocol.yaml → registry protocols[]） | 文本 | — |
| `nf registry` | 质检与验证（verify） | 契约注册表内容寻址（T8.2）：每包 canonical manifest 的 SHA-256（CID）+ 顶层 root；只读扫描、不改各包；本版不含签名（sig 留空，只做内容寻址与篡改检测） | 文本 | docs/verification-cards.md |
| `nf related` | 图书馆与知识（library） | See-Also 关联查询（41 波C C4：market/图书馆条目人读引用链） | JSON | docs/41_波C_W2_C3_C4_实测记录.md |
| `nf release` | 质检与验证（verify） | 发布前体检与编排：默认=体检（verify + 基线自描述 + e2e + 覆盖率 + 报告新鲜度）；--plan=发布计划（只读）；--freeze [--apply]=冻结链（conformance → approve → recei… | JSON | docs/45_质量纵深收口总档.md、docs/en/release.md、docs/ja/release.md、docs/meta/VERSION-MATRIX.md |
| `nf rename` | 资产与货架（shelf） | 模块改名引用重链（A5：references 中引用该模块的条目批量更新） | 文本 | — |
| `nf render` | 装配与生产（forge） | 协议多出口渲染（A3：protocol.yaml → agents/claude/skill rules） | 文本 | — |
| `nf review` | 治理与决策（govern） | 逐行审查：机械预筛候选行 → 决策模型逐行判（是否缺口/严重度）→ 确定性证据复核 → 只把**有证据**的放进修复清单 | JSON | — |
| `nf rfc` | 图书馆与知识（library） | 协议件 RFC 索引（机制借鉴 HMP：把协议版本史做成可机读头） | JSON | — |
| `nf run` | 装配与生产（forge） | 跑全链管道：模块选择→装配→质检→导出 | 文本 | docs/en/mcp.md、docs/en/terminal.md、docs/ja/mcp.md、docs/ja/terminal.md |
| `nf runtime` | 装配与生产（forge） | 参考运行时（T7.3）：载入装配计划与状态，按管线层序执行并产 trace；MockModel 按 contract_digest+step 确定性派生响应（无随机/无网络）；record/replay 复现同一 trace 与产物 di… | 文本 | — |
| `nf score` | 质检与验证（verify） | 基线相对回归评分（内部差距：现有门禁全为绝对门，无 delta/回归判据） | JSON | docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf security` | 质检与验证（verify） | 内容供应链安全扫描：把 community/ 与 library/ 的正文当**外来内容**做只读形态扫描（不联网、不执行、不改写）——指令注入标记（单源 core.trust_boundary）、可执行/主动内容、明文凭据（只回掩码）、… | 文本 | docs/security/threat-model.md、docs/verification-cards.md |
| `nf serve` | 服务与集成（integrate） | MCP 运行时服务（C1：mcp.json 快照或实时仓库面 → stdio JSON-RPC，供 MCP client 拉起） | 文本 | docs/41_波C_C8_transport评估.md、docs/44_M2_AI通道内容规范.md、docs/agent/AGENT_START.md、docs/agent/agent_组装指令包_v0.2.md |
| `nf shell` | 命令面与终端（meta） | NF 终端（端壳退役后的人机交互入口）：把既有 CLI 命令面按能力菜单组织成可交互会话（数字 0-7 看菜单 / 任意 nf 命令直通 / /help /quit）。纯 stdlib、确定性；写入类命令须显式确认（--yes 或交互输入… | JSON | docs/en/layers.md、docs/en/terminal.md、docs/ja/layers.md、docs/ja/terminal.md |
| `nf sig` | 质检与验证（verify） | 协议知识签名（41 波C C1：01-36 文档/管线/模块 → 结构化签名，知识指纹） | JSON | docs/41_波C_C1_C2_实测记录.md、docs/41_波C_W3_实测记录.md、docs/42_M5_Release-checklist.md、docs/attest.md |
| `nf spec` | 装配与生产（forge） | Spec Registry 查询（v2.5.0 Wave3：版本化 spec 查询）；T7.1 契约语义核心：`nf spec check --core [--json]`（五概念模型 + W1/W2/W3）与 `nf spec cano… | JSON | docs/verification-cards.md |
| `nf st-validate` | 质检与验证（verify） | ST 制卡校验器原型 v0（任务书 A-S3：R1 结构 / R3 世界书 / R4 变量） | JSON | docs/examples/st-validate/README.md、docs/reference/trace-as-state-ab-proposal.md |
| `nf state-front` | 服务与集成（integrate） | 条件先行排布（灵感来源 arXiv:2609.02702 的 condition-first；NF 只做排布纪律） | JSON | docs/reference/trace-as-state-ab-proposal.md |
| `nf stats` | 上手与自检（start） | 出口自动化：README/README.en/llms.txt 的数字由产物实算生成，禁止手改 | JSON | docs/42_M1_协议可执行性自测规范.md、docs/42_M5_Release-checklist.md、docs/en/terminal.md、docs/fde-sample/evidence/deliverable.md |
| `nf telemetry` | 质检与验证（verify） | 遥测 semconv 映射（内部差距：trace 为自定 JSON，对外界不可消费） | 文本 | docs/45_执行遥测规范.md |
| `nf terminal` | 命令面与终端（meta） | NF 终端（端壳退役后的人机交互入口）：把既有 CLI 命令面按能力菜单组织成可交互会话（数字 0-7 看菜单 / 任意 nf 命令直通 / /help /quit）。纯 stdlib、确定性；写入类命令须显式确认（--yes 或交互输入… | JSON | docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf toolface` | 服务与集成（integrate） | 模块工具面浏览（45：machine_contract.tool_face 可选建议层，AI 裁量不入门禁） | JSON | docs/en/terminal.md、docs/ja/terminal.md、docs/terminal.md |
| `nf transparency` | 治理与决策（govern） | 透明日志：由 protocol/RECEIPTS.json 确定性派生哈希链（RFC 6962 风格域分隔），并校验在盘生成物 | JSON | docs/receipts.md |
| `nf verify` | 质检与验证（verify） | 门禁单进程引擎：把 verify.sh 的 check 收进**一个进程**跑，省掉每条一次的解释器启动（实测全量门禁起 42 次 $PY3）。判据**一字不改**——已迁入的 check 与 verify.sh 的输出逐字一致（由 te… | JSON | docs/security/threat-model.md |
| `nf who-refers` | 图书馆与知识（library） | 引用反查（A2：谁引用了某模块，遍历 registry references） | 文本 | — |
| `nf workloop` | 治理与决策（govern） | 构建回路：从公开待办真源（type_backlog / pipeline_advisory）组类型化问题问决策层，产出**工单**（含完成判据与验收命令）；决策模型只选择不落笔，工单只落内部档案 | JSON | — |
| `nf worldmodel` | 服务与集成（integrate） | world_model 浏览（JEPA-inspired 确定性抽象状态契约，check32 硬门） | JSON | docs/en/terminal.md、docs/ja/terminal.md、docs/meta/DEEP_DIVE.md、docs/terminal.md |

## 能力族

| 族 | 名称 | 命令 |
|---|---|---|
| forge | 装配与生产 | `nf agent`, `nf assemble`, `nf import`, `nf preset`, `nf register`, `nf render`, `nf run`, `nf runtime`, `nf spec` |
| govern | 治理与决策 | `nf approve`, `nf attest`, `nf audit`, `nf decide`, `nf decisions`, `nf design`, `nf handover`, `nf locales`, `nf model`, `nf postmortem`, `nf receipts`, `nf review`, `nf transparency`, `nf workloop` |
| integrate | 服务与集成 | `nf bench`, `nf driver`, `nf endpoint`, `nf events`, `nf interop`, `nf lsp`, `nf serve`, `nf state-front`, `nf toolface`, `nf worldmodel` |
| library | 图书馆与知识 | `nf cognition`, `nf impact`, `nf knowledge`, `nf library`, `nf patterns`, `nf related`, `nf rfc`, `nf who-refers` |
| meta | 命令面与终端 | `nf cli`, `nf completion`, `nf daemon`, `nf help`, `nf shell`, `nf terminal` |
| shelf | 资产与货架 | `nf asset`, `nf combine`, `nf domain`, `nf market`, `nf module`, `nf output`, `nf pipeline`, `nf rename` |
| start | 上手与自检 | `nf demo`, `nf doctor`, `nf facts`, `nf layers`, `nf stats` |
| verify | 质检与验证 | `nf assertions`, `nf changelog`, `nf conformance`, `nf diff`, `nf explain`, `nf ir`, `nf license`, `nf lint`, `nf nfal`, `nf registry`, `nf release`, `nf score`, `nf security`, `nf sig`, `nf st-validate`, `nf telemetry`, `nf verify` |

## 复跑

```
python scripts/nf.py cli map --check --json
python scripts/nf.py cli map --write
```
