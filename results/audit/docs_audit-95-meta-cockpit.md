---
id: AUD-0047
title: 元认知生产驾驶舱主仓融合
date: 2026-10-30
scope: 将元原子运行时、动态驾驶、事件溯源、上下文预算、A/B 与正式协议融合进主仓；并收口桥接 Path 参数根相对/类型闸门、包入口惰性加载、生成物原子写与 manifest 可复算；不调用外部模型，不伪造 HR-001。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/cli_bridge.py:4247ed0e73dfc1ca319f6b9881f3b73a875b01ee6b24eda3d4fe861736cadad8
  - desktop/src/core/meta_cockpit/__init__.py:f31cbadd59e3f25aab850122bbcc4ad5adcf5a65596a38c4996f264a38427fd7
  - desktop/src/core/meta_cockpit/build_atom_menu.py:3e4d8fe2c0ad594f97ae41dc754886bc757527dde035c01a2ca0aa491f785466
  - desktop/src/core/meta_cockpit/runtime_executor.py:204a67ec93855257323887011395b0866ac8d5ae1c485362e89eb058ffe64bfb
  - desktop/src/core/meta_cockpit/cockpit_service.py:18280c6966dd618a8b09daa058b461fa43f89e99f11c797ca884338ff5c13bbf
  - desktop/src/core/meta_cockpit/cockpit_ab.py:6afcade08f2469aad4adc6f44e0e3d28a17712a85e3223f41b14c0020c2f88e7
  - desktop/src/core/terminal.py:9a86928171c71f4a2d3d324508fdafccb60fd7cc8423d52197185214a40ea30f
  - desktop/tests/test_meta_cockpit.py:017e3a591004b1e3c1bf28e8938ae22754e39ea61ae369e4ddcca1a556214280
  - desktop/tests/test_cli_error_framing.py:788460878349a907eadc21c74a1a689c9cdfe81888f5490c5a935b34fc121c8a
  - desktop/tests/test_nf_cli.py:18c407b6780205e50997d99ab9ea967e6ee066b2dca5d087e9eeea632d311804
  - scripts/nf.py:b8d793a9fcfec426276f177671af4d4f0e65d9b3b024002a9faa73b04e75d50d
  - tui/_surface.py:0845c376fd5ad601ae78b98326f1d2038b88c146d468d415efa694d8af1bb1f9
  - protocol/check12_weights.json:23ae580a475c8b27ebdfd72ca59c00cb9a19b13a84e3573f883ff5b9cd0e907d
  - protocol/coupling_baseline.json:b707d268a3bd295caade986ce6e80fd5ca1a3b24d75c60381e1d2e8bc27d1d49
  - docs/meta-cockpit/README.md:fa00a7fd014857af56e11f38ced1b7d888be053befaadb10b3dd494d27884316
  - docs/meta-cockpit/功能解析.md:de20c2340d19d541bcfde53f222a3acf22a6e440d8fb3dcf51a37aedf53c0c25
  - results/meta-cockpit-manifest.json:60c0e100798e49d393557ae5066c02d7e057ec27f386ee1a36ca3fc7740150ba

---
> 重审（2026-11-14）：通用中文块 10 顶尖化：补中文自检段（九字段/12+1/双协议/仅 stdio/零依赖/MIT/中英对偶/平台侧未验）+ 类目在中文站填「内容创作」不混用；判据扩展（中英互指）。

> 重审（2026-11-14）：通用英文块 09 顶尖化：补§自检（九字段/12+1/双协议/仅 stdio/零依赖/MIT/与 10 中英对偶/平台侧未验/不钉计数）+ 新增判据 test_generic_blocks_doc_contract（09↔10 传输段逐字相等、两份 JSON args 可解析一致）。

> 重审（2026-11-14）：轻量目录件 08 顶尖化：补字段自检（与 07 对偶、平台侧未验、不钉计数、无审核 SLA）+ 判据扩展（08 侧断言：自检段/指向 07/字段块逐行相等/入口不同）。

> 重审（2026-11-14）：轻量目录提交件 07 顶尖化：补字段自检 8 行 + 「短表单族（07/08/09/10）字段正文必须逐字一致」纪律；新增判据 test_short_form_submission_doc_contract（07 与 08 的字段块逐行相等 + 邮箱泄漏检查）。

> 重审（2026-11-14）：ModelScope 提交件 06 顶尖化：补字段自检 8 行（含**仅 stdio**、中文口径同义不同文提醒、平台侧未验、不钉计数）+ 带 JSON 校验的 stdio 配置检查；新增判据 test_modelscope_submission_doc_contract（含邮箱泄漏检查）。

> 重审（2026-11-14）：PulseMCP 提交件 05 顶尖化：补字段自检 8 行 + 本渠道三条特有须知（平台侧未验 / 邮箱只作审核联系且不得写进内容 / Cloudflare 拦脚本别用 curl 探测）+ 不钉计数；新增判据 test_pulsemcp_submission_doc_contract（含邮箱泄漏检查）。

> 重审（2026-11-14）：Glama 提交件 04 顶尖化：补「§口径分流」（仓库侧六项可核 / 平台侧未验 / 与 GLAMA.md 同源 / 不钉运行时计数 / Claim 账号一致性）+ 判据 test_glama_submission_doc_contract。

> 重审（2026-11-14）：mcp.so 提交件 03 顶尖化：补「字段自检」8 行（名称/仓库/站点/安装/12+1 工具/零依赖/图标真 400×400/许可）+ 平台侧未验 + 不钉运行时计数 + 403 提示；新增判据 test_mcpso_submission_doc_contract。

> 重审（2026-11-14）：Cline 提交件 02 顶尖化：改掉正文里钉死的「check1-40/PASS=72/约 2500 单测」（外部审核文案不该带会过期数字，改为以 nf stats 生成区为准）+ 补「审核要点自检」表（400×400 真像素/llms-install/12+1/双协议/平台侧未验/实测确认归作者）；新增判据 test_cline_submission_doc_contract。

> 重审（2026-11-14）：MCP 提交件 01 号顶尖化：补「同源自检」表（展示名/仓库/站点/安装/工具面/零依赖 六项与材料包同源）+「10 份必须同批更新」纪律；新增跨文件判据 test_mcp_submissions_doc_contract（编号连续/共享值一致/图标引用）。

> 重审（2026-11-14）：MCP 图标素材 README 顶尖化：补现状对照（真实像素 400²/512²、字节数、用途）+ 替换流程（两个一起改/记来源/只换一个会分叉）+「来源声明不可机检」诚实边界 + 复现命令；新增判据 test_mcp_assets_readme_doc_contract。

> 重审（2026-11-14）：MCP 投稿教程（SUBMIT）顶尖化：补「仓库侧可核 / 平台侧未验」现状对照（三处版本同值 1.0.5 / mcpName / schema 2025-12-11 / 12 工具+1 prompt / conformance 27/27）+ 复现口径；新增判据 test_mcp_submit_doc_contract。

> 重审（2026-11-14）：MCP 目录投稿文档顶尖化：补「仓库侧可核 / 平台侧未验」现状对照（server.json 1.0.5+packages 一致 / npm mcpName / 图标 400·512 真实像素 / submissions 10 件 / llms-install.md）+ 复现口径；新增判据 test_mcp_directories_doc_contract。

> 重审（2026-11-14）：HF Space README 顶尖化：补 §现状对照（4 模式 / 200 KB / 180 s / 零 pip / 两段 @sha256 钉版 / EXPOSE 7860 + CMD server.py / 缺树退出码 3 / doctor 实测 17/17）+ §复现口径；新增判据 test_hf_space_readme_doc_contract。

> 重审（2026-11-14）：接入面 README 顶尖化：补 §现状对照（14 面 / active 12·proposed 2 / 已用 kind 7 类 / 词表 kind 8·status 3·tier 2 / check38 子扫描）+ §复现口径（**没有 nf integrations 子命令**，走 check38 子扫描）；新增判据 test_integrations_readme_doc_contract。

> 重审（2026-11-14）：handovers/README 顶尖化：补齐与 decisions/README 同构的政策说明（本文件怎么读 / 目录白名单 / 为什么这么定 / 三命令 / 私有仓路径 / 判据点名）+ 复核位；新增判据 test_handovers_readme_doc_contract。

> 重审（2026-11-14）：接力模板顶尖化：补 §模板自检（五段/六必填/状态词表/未决项带判据/refs 可解析/公开面边界 + 三条只读命令），声明自检段不是第六段；新增判据 test_handover_template_doc_contract（模板↔protocol/handover.json↔CLI 三方对账）。

> 重审（2026-11-14）：DIFFERENTIATION 顶尖化：补「§载体对照」把 46 条核心逐项对到真源（7 项有载体）并如实登记 5 项缺口（12 层反模式 / Ruff+Mypy 全覆盖 / C901 / Radon / 豁免白名单）；新增判据 test_differentiation_doc_contract；manifest 已重算。

> 重审（2026-11-14）：COCKPIT_RELEASE_NOTES 顶尖化：补 §现状对照（33/14/10/5/8 逐值、PENDING 状态、machine digest 只指路）+ 把「12 层反模式审计」无代码载体标注为存疑；新增判据 test_cockpit_release_notes_doc_contract；manifest 已重算。

> 重审（2026-11-14）：COCKPIT_PROTOCOL 顶尖化：补「给人看≠给模型指令」分隔 + §现状对照（3 原子/8 轮/1 次重规划/deadline/36000+8000 预算/33 原子/fail-closed/盲评四值）+ 复现口径；新增判据 test_cockpit_protocol_doc_contract；manifest 已重算。

> 重审（2026-11-14）：ATOM_MENU 顶尖化：菜单生成器增「怎么读这一页」（字段/选择纪律/执行器关系/分组口径），重生成 33 原子菜单并同步 meta-cockpit-manifest 摘要；test_meta_cockpit 增读法判据。

> 重审（2026-11-14）：Go 客户端 README 顶尖化：补七调向量 55（28/6/7/3/1/6/4 与 results/ccos 逐文件对账）、7 子命令、Go ≥1.24 前提与「本机未装 Go → go test 本轮未跑」诚实标注；新增判据 test_go_client_doc_contract。

> 重审（2026-11-14）：STRATEGY 增「§六 五维载体（可核索引）」（只做导航不改口径：每维的机检载体/留证位置/复核命令），并扩展 test_strategy_contract 判据（五维载体逐行 + 留证位置在场 + 索引口径）。

> 重审（2026-11-14）：GLAMA 上架教程顶尖化：补「仓库侧可核 / 平台侧不可核」现状对照（Dockerfile 钉版+非 root+CMD serve+零 pip、glama.json maintainers、版本一致、12 工具+1 prompt）+ 复现口径；新增判据 test_glama_doc_contract。

> 重审（2026-11-14）：CHANGELOG 顶尖化：补三段说明（怎么产生 / 只追加不重写 / 现状 4+1 节），并把「节序从新到旧、日期单调不增、生成器 issues 空」写成判据 test_changelog_doc_contract。

> 重审（2026-11-14）：AGENTS.md 增「本仓高发误判」止损清单（生成物/冻结件、conformance 后重批准、译件三处同步、未跑完不许写全绿），并把该段纳入 test_agents_contract 判据（只增纪律不减纪律）。

> 重审（2026-11-14）：需求收敛模板顶尖化（8 字段 / steelman 3 形态 / audit 2 形态 / 当前 0 份库存 / 首例阻塞 / reference 分类 + 现状对照 / 复现）+ 契约判据 test_requirement_template_doc_contract。

> 重审（2026-11-13）：迁移指南顶尖化（签名文档 4 / 历史面 15（4 根+2 protocol+9 schema）/ 影响度 3 值 / 命令三形态 + 现状对照 / 复现）+ 契约判据 test_migration_guide_doc_contract。

> 重审（2026-11-13）：P03 样本冻结约束固化：新增 freeze 判据 test_full_sample_p03_doc_contract（sha256/非空白行/5 条裁定），样本字节已还原；权重增量重测。

> 重审（2026-11-13）：完整版样本（P03）顶尖化：补可核锚（层 9 / 槽位 27 / token 71 / 事件 18 / hard 0 / advisory 11 / 去重 23（官方 20+包内 3）/ assets 23 内容 / NF-1 在场）+ 现状对照 + 复现口径；「默认装配 24」计法不吻合实读，标注为待澄清（不改历史句）。

> 重审（2026-11-13）：验证卡册顶尖化：散文去掉钉死的 40 条/check1-40/PASS=70（生成区早已 42/76，属真漂移），改为指向生成区；新增判据 test_verification_cards_doc_contract（生成区与 verify.sh 一致 + 散文禁钉数）。

> 重审（2026-11-13）：文本卫生文档顶尖化（补漏记的第 5 条 SemVer 规则 / 4399 文本·1240 JSON·269070 键·111 版本 + 现状对照 / 复现）+ 契约判据 test_text_hygiene_doc_contract。

> 重审（2026-11-13）：终端入口文档顶尖化（77 命令/203 索引/8 族/9 区/13 表单/42 斜杠词/4 阻塞/24 确认动词/139 例 + 现状对照 / 复现）+ 契约判据 test_terminal_doc_contract；权重增量重测。

> 重审（2026-11-13）：层切片页补本层机构分布（前三机构及条数，读自 catalog body 字段），重生成五页；判据断言每页机构分布与真源相等；iface 页现显示 IETF 15 / W3C 7 / OASIS 5。

> 重审（2026-11-13）：层切片页补本层统计：生成器 _layer_body 增「本层可达 X/Y」与「绑定最多前三」（按主锚+辅锚排序，读自 binding packs），重生成五页；判据同步断言每个层页的统计与前三；code_metrics 重冻（geo_export 295 行）。

> 重审（2026-11-13）：标准层切片页顶尖化：生成器补「怎么读本页」段（切片口径/行字段/互指/投影）并重生成五个层页；code_metrics 重冻（geo_export 267 行）；新增契约判据 test_standards_layer_doc_contract（data 层为锚，另验五层同构）。

> 重审（2026-11-13）：标准主索引顶尖化：生成器补索引页「口径与复现」段（生成物纪律/行字段/锚点/其它面/投影）并把两段文案提为模块常量；重生成后索引 +8 行；代码度量重冻（geo_export 253 行）；新增契约判据 test_standards_index_doc_contract。

> 重审（2026-11-13）：标准答题卡（生成物）顶尖化：生成器补「口径与复现」段（生成物纪律/计数来源/可达性/投影定位）后重新生成；新增契约判据 test_answer_cards_doc_contract（含 geo_export --check 新鲜度实跑）；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：ST 制卡清单顶尖化（修 W1 级别 S→M 与真源一致 / 29 条 M6 S17 R6 / 自动面 1 / 待定 3 / st-validate 原型 + 现状对照 / 复现）+ 契约判据 test_st_quality_checklist_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：RFC 头文档顶尖化（4 件逐条/全 Active/3+1 类别/链 0/4 值词表 + 现状对照 / 复现）+ 契约判据 test_rfc_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：发布策略声明件顶尖化（11 步 ID 全列/冻结链 3/版本面 3/工件 4/锚 3 段 + 现状对照 / 复现；en·ja 译件同步后重签）+ 契约判据 test_release_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：回执文档顶尖化（3 条馆藏/66 件协议/66 节链/算法三式/验证器三项 + 现状对照 / 复现）+ 契约判据 test_receipts_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：五分钟入口文档顶尖化（修 Python ≥3.10→≥3.11 真漂移 / 6 步与脚本 slug 对齐 / 300s / check39 + 现状对照 / 复现）+ 契约判据 test_quickstart_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：管线抽象执行文档顶尖化（114 管线/282 模块/13 基座/hard 0/advisory 1142 三分解/2 子命令 + 现状对照 / 复现）+ 契约判据 test_pipelinerun_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：实践包文档顶尖化（7 条全 active/6 必填键/2 值词表/INDEX 投影对账 + 现状对照 / 复现）+ 契约判据 test_patterns_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：冻结粘贴卡顶尖化（8 段/编号域/7 项/分片 2 段 + 现状对照；新增正文 sha256 防篡改锚，正文未改）+ 契约判据 test_paste_card_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：产出形态文档顶尖化（116 条/12 类别/六档状态分布/106 包/1050 件/机验率 0.7688/34 例 + 现状对照 / 复现）+ 契约判据 test_output_forms_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：NFA-L 文档顶尖化（5 子命令/6 函数/9 类型/6 码+A0201/迁移 110-110 散文 0/44 例 + 现状对照 / 复现）+ 契约判据 test_nfal_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：模块边界冻结文档顶尖化（7 字段/248 全签/漂移语义/契约 id + 现状对照 / 复现）+ 契约判据 test_module_signature_doc_contract；并修 live_doc_counts 红（设计自查清单 / 45 总档 / conformance 三处钉计数补实测留痕）；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：建模三件文档顶尖化（12 scheme/37 规范件/54 契约/42 checks+24 assertions/12 例 + 现状对照 / 复现）+ 契约判据 test_modeling_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：需求澄清快照文档顶尖化（补来源/差异/复现/非计划声明，正文原样保留）+ 契约判据 test_meta_archive_sample_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：版本矩阵文档顶尖化（修 v0.92 ⏳→✅ 与 CHANGELOG 一致 / 29 行 / 基线 repo_stats / 3 例 + 现状对照 / 复现）+ 契约判据 test_version_matrix_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：元层路标文档顶尖化（版本三处一致 / 基线不手写 / check39 端壳零回潮 + 现状对照 / 复现）+ 契约判据 test_meta_roadmap_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：元驾驶舱功能解析顶尖化（33 原子前缀分布/M0–M4/10·5 节点/3·5 约束/13 例；并把「14 方法节点」标为待澄清）+ 契约判据 test_meta_cockpit_analysis_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：元驾驶舱说明顶尖化（33 原子两处一致/内容管线 10/元管线 5/六类义务/13 例/CLI 旗标补全 + 现状对照 / 复现）+ 契约判据 test_meta_cockpit_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：机读块 retro-fit 文档顶尖化（作用域 13 件/L0 0/全库 248/6 组字段/幂等 + outputs 待补 1 件如实说明 / 现状对照 / 复现）+ 契约判据 test_machine_contract_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：LSP 接入文档顶尖化（11 能力/16 方法/8MiB/utf-16/77 例 + 现状对照 / 复现；en·ja 译件同步后重签）+ 契约判据 test_lsp_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：MCP 接入文档顶尖化（能力表工具 7→12 全列 / 1 prompt / dual-era / 8MiB / 现状对照 / 复现；en·ja 译件同步后重签）+ 契约判据 test_mcp_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：语言面文档顶尖化（修「五份指南」→6 份含 LSP / 12 译件 / 3 语全 entry+guides；en/ja 译件同步后重签）+ 契约判据 test_locales_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：图书馆机器面文档顶尖化（补 3 件全 active / 分级 3-of-3 / 许可 2+1 / 词表 4 值 / verify 绿 + 现状对照 / 复现）+ 契约判据 test_library_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：抽象阶梯文档顶尖化（生成区外补现状对照：4 阶/5 子级/4 入口/6 纵切/7 派生/2 退役/10 规则/27+19 例 + 复现；生成区未手改）+ 契约判据 test_layers_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：双源知识层文档顶尖化（补 6 源·3+3 / 可见性 4+2 / order 6 / M23 / lint 绿 / usage total 0 / 35+10 例 + 现状对照 / 复现）+ 契约判据 test_knowledge_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：I/O 类型面文档顶尖化（补 9 值词表/248 模块/308-of-1141·27.0%/0 不匹配/write 幂等 + 现状对照 / 复现）+ 契约判据 test_io_types_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：互操作总览顶尖化（12 种类/入仓 12 面/外部校验逐面 14 行 6-7-1 / 现状对照 / 复现）+ 契约判据 test_interop_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：他证通道说明页顶尖化（补「自跑≠他证」第 4 条 + 面谱 2-5-4-3 分档 + 现状对照；改生成器 render_doc 后重出说明页，不重跑 --emit 以保护回填表）+ 契约判据 test_interop_thirdparty_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：FDE 栈位文档顶尖化（修 mcp.json 失效引用 → 运行期产物 + 12 件互操作面清点 + 370/1200 + 五条达标线 + 现状对照 / 复现）+ 契约判据 test_fde_stack_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：FDE 照做步骤顶尖化（两命令期望串原文 / 两出口期望串 / 全量 vs --checks-only 时间预算 / 变更记录 / 现状核对）+ 契约判据 test_fde_run_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：FDE 交付物样本顶尖化（修同页 4≠5：四道门→五道门 G1–G4+G5，改生成器后 --run 重生成；manifest sha 同步）+ 契约判据 test_fde_deliverable_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：FDE brief 顶尖化（诉求→判定→落点逐条复核口径 / model_agnostic 字段路径 / brief 不进门禁 / 四门+G5 澄清 / 复现）+ 契约判据 test_fde_brief_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：FDE 样例说明顶尖化（补 6/2/48/47/4/370 机读现状 + check32 注册点 + 现状对照 / 复现）+ 契约判据 test_fde_sample_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：外部验证资产说明顶尖化（修记录↔盘上 sha/体积不一致：11,632B/a91f402c / P0 仍 ✗ / 只读复核 + 现状对照 / 不重出纪律）+ 契约判据 test_external_validation_assets_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：端点点契约文档顶尖化 + 权重增量重测 + 层位刷新后的机械重绑（最终轮次）。

> 重审（2026-11-13）：指令档路由文档顶尖化（修判据过度陈述「逐名一致」→子集校验 / 3 工作流·3 指令档·8 工具·1 提示活绑定 / 现状对照 / 复现）+ 契约判据 test_driver_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：域包文档顶尖化（修可达 332/不可达 38/绑定 1200 记录 2400 锚位 + 空壳 73·36·2628 + specs 可见性说明 / 现状对照 / 复现）+ 契约判据 test_domain_packs_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：决策层文档顶尖化（修三处计数陈旧 101/1142/1244 + 补 openai-json 适配器 / 三原语三候选活绑定 / 现状对照 / 复现）+ 契约判据 test_decision_layer_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：一致性报告文档顶尖化（契约 10→27 条 / 门禁 35→check1-42 / 现场 27-27 root / 冻结链三环 / 现状对照 / 复现）+ 契约判据 test_conformance_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：组合引擎文档顶尖化（修 107→111 包/C(111,2)=6105/证书 18/产物化 5 / 五不变量活绑定 / 现状对照 / 复现）+ 契约判据 test_combos_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：可信时间戳 v0 文档顶尖化（两子命令/落盘三件/time-record 接入/五判定/信任锚不预置/1MiB 活绑定 / 现状对照 / 复现）+ 契约判据 test_time_token_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：供应链对象 v0 文档顶尖化（三摘要/材料 572/JUDGE_FILES 10/三态活绑定 / 现状对照 / 复现 + sbom 重算）+ 契约判据 test_supply_chain_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：吊销 feed v0 文档顶尖化（修旧边界「还没走那条线」与已实装 ed25519 矛盾 / 五子命令·链深 2·43+16 例活绑定 / 现状对照 / 复现）+ 契约判据 test_revocation_feed_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：威胁模型文档顶尖化（修两处与 G4 自相矛盾：无水印/不做水印 → 五格式载体+PNG LSB 水印现状 / A1–A9·G1–G6 活绑定 / 现状对照 / 复现）+ 契约判据 test_threat_model_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：研究层 v0 文档顶尖化（8 方法/7 切片/depth 映射/16 例活绑定 / 现状对照 / 复现）+ 契约判据 test_research_methods_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：发布结论文档顶尖化（修两处陈旧数字：1882.7s/4833 条权重·25 门/540 模块 / 五步与快照语义活绑定 / 复现）+ 契约判据 test_release_conclusion_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：论文筛选台账 v0 文档顶尖化（34/22·7·1·4 计数活绑定 / adopted 落点+证据面文件存在 / 脚本三选项 / 5 例 / 现状对照 / 复现）+ 契约判据 test_paper_adoption_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：一次性审计脚本清单顶尖化（文档表 ⇄ ORPHANS 双向活绑定 / 移出件判据入口核实 / 5 例 / 现状对照 / 复现）+ 契约判据 test_one_shot_audits_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：方法包 v0 文档顶尖化（11 域/65 动作/31 类目/judges 31 全覆盖活绑定 / 4+37 例 / CLI 三用法 / 现状对照 / 复现）+ 契约判据 test_method_packs_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：本地 HTTP 面 v0 文档顶尖化（三端点/契约 local.* / 18 例 / MAX_BODY/LOOPBACK/CSP 活绑定 / MCP-Http 鉴权边界澄清 / 现状对照 / 复现）+ 契约判据 test_local_api_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：标注 IR v0 文档顶尖化（修两处自相矛盾/重复小节：边界「没有实测」与载体节冲突、同名「与 cc_label 的关系」×2 / 16+33 判据 / 四探针结果件 / 现状对照 / 复现）+ 契约判据 test_label_ir_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：密钥透明目录 v0 文档顶尖化（修失效 CLI 引用 kt-witness→四真实子命令 / 形状与边界活绑定 / 15 例 / 现状对照 / 复现）+ 契约判据 test_key_transparency_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：判据族谱顶尖化（修失效引用 test_c2_envelopes→test_cognition_bridge / 探针数字活绑定 / 登记件重建 534·232·0.264）+ 契约判据 test_judge_families_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：判据设计十一问顶尖化（登记件陈旧→--write 重建 / 533 模块·硬 231·比例 0.2645 / 11 问齐 / 现状对照 / 复现）+ 契约判据 test_judge_questions_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：同构判据矩阵说明档顶尖化（修边界「5 条」旧措辞→9 层/9 条 / 矩阵 9 行 6 字段 / 11 例 / 现状对照 / 复现）+ 契约判据 test_isomorphism_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：证据判定向量集 v0 文档顶尖化（修单反引号围栏 / 样例 count 15→28 / 补 3 个 decision 用例 / 分布 18·4·6 / 现状对照 / 复现）+ 契约判据 test_evidence_vectors_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：证据包 v0 文档顶尖化（修跨段数字失同步 10→13 条 / 25→38 条 / 向量 28 / 66+8 判据 / 现状对照 / 复现）+ 契约判据 test_evidence_bundle_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：双核不变量文档顶尖化（复核位 / 9 层与矩阵 11 例 / JUDGE_FILES 10 / precheck 23 门 + 2 慢门 / 现状对照 / 复现）+ 契约判据 test_dual_core_invariants_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：check-policy v0 文档顶尖化（五个 CLI 入口含 --intent-from-text / 草稿四账 / 现状对照 / 复现）+ 契约判据 test_check_policy_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：CCOS ABI v0 文档顶尖化（复核位 / 本文机检声明 / 五数字活绑定 38·28·23·9·5 / 现状对照 / 复现口径）+ 契约判据 test_ccos_abi_v0_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：bench 执行结果跑分台文档顶尖化（五维权重表 / run 五旗标 / 用例 2 例 / 端壳同名边界 / 复现口径）+ 契约判据 test_bench_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：attest 内容 attestation 文档顶尖化（六旗标含 --selfcheck/--json / check42 入口 / 库签名边界 / 三级不降级 / 9 例）+ 契约判据 test_attest_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：asset_contract 数字资产契约文档顶尖化（22 面条+1 链 / 六旗标含 --freeze·--run-tests / 资产面 103·308 / 59 例 / 复现口径）+ 契约判据 test_asset_contract_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：assertions 数据化断言表文档顶尖化（字段表 6+2 / 表级词表与能力索引 / 24 条现状 / 复现口径）+ 契约判据 test_assertions_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：approval 内容绑定批准文档顶尖化（6 字段表 / 冻链第 2 环 / 1 条记录现状 / 复现口径）+ 契约判据 test_approval_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：Y5 外测作业书顶尖化（未执行/封存状态如实 + 菜单 v0.3 四处口径同步 + Y5 回填位）+ 契约判据 test_ai_menu_fieldtest_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：装配指令包顶尖化（通道 A 桌面→CLI / R1–R8 / 八段最低要求 / 12 工具 / 复核位）+ 契约判据 test_assembly_pack_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：L3_FROZEN 端壳退役真相源顶尖化（最后复核 / 退役+保留双侧机检面 / CI 22 workflow 全量点名 / 复现口径）+ 契约判据 test_l3_frozen_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：EXPORT 出口管制声明顶尖化（修正「不自制 ed25519」与事实不符 / 标准公开算法+纯标准库+可选 ssh-keygen / 声明⇄机检面 / 复现口径）+ 契约判据 test_export_statement_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：45 质量纵深收口总档顶尖化（结构/挂账不变、五维水位与各面数字现状、波次号≠产品版本、复现口径）+ 契约判据 test_master_closure_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：45 执行遥测规范顶尖化（phase 四值含 build / 字段按 phase 子集 / records 形态 / semconv 载体与 E3 待办 / 复现口径）+ 契约判据 test_telemetry_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：45 M3 载荷提案顶尖化（registry 443/438 现状活绑定 / 开放项如实 untyped 待办 / 复现口径）+ 契约判据 test_payload_proposal_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：45 M2 回合级 drill 规范顶尖化（样本 5→6 含 selfrun / 测试 6 例 / --check-trace 回读口径 / 复现命令）+ 契约判据 test_round_drill_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：44 M2 AI 通道内容规范顶尖化（模块 44→248 / 管线 8→114 / 工具 4→12 / 默认实时面 / drill R1–R8）+ 契约判据 test_ai_channel_spec_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：44 M1 演练覆盖真源顶尖化（8 集口径与实现统一：_hits 接 lexicon + p07_en 纳入测试 / 现状对照 / 复现口径；P06 记录同步 8 套）+ 契约判据 test_m1_drill_coverage_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：M5 设计自查清单顶尖化（六问口径不变 / 判据映射表 / 现状对照 / 复现口径）+ 契约判据 test_design_checklist_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：M5 工程收口顶尖化（快照横幅 / 交付物现状 / bench 边界澄清 / 复现口径）+ 契约判据 test_m5_closure_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：M5 Release checklist 顶尖化（docs/meta 路径修正 / 自动化入口 / 退役项如实 / 复现口径）+ 契约判据 test_release_checklist_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：M4 资产评估报告顶尖化（快照横幅 / 资产面 111 包·465 文件·台账 103·孤儿 0 活绑定 / 结论口径不变 / 复现口径）+ 契约判据 test_asset_report_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：M3 纯度体检规范顶尖化（规则族 R1–R8 / R7·R8 载体 / 单测 34 例 / explain 文案差异如实 / 复现口径）+ 契约判据 test_m3_purity_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：M2 回合状态头规范顶尖化（v1 复核 / 铁律 L1–L5 双源核对 / 硬断言 4→6 / 重入与复现口径）+ 契约判据 test_m2_round_header_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：42 M1 自测规范顶尖化（v1 复核扩写 / 规则 4→6 / 单测 3→18 / 8 集 / FIELD-001 挂账 / 复现口径）+ 契约判据 test_selftest_spec_contract；M4 契约 glob 修正；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：M4 文档分类普查顶尖化（快照横幅 / 清单规模 8→34·45 现状 / lint --kinds 分工 / 复现口径）+ 契约判据 test_m4_census_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：P06 演练集顶尖化（快照横幅 / 44 覆盖真源接续 / 判据覆盖面如实 7 套与 p07_en 例外 / 复现口径）+ 契约判据 test_p06_drill_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：P03 演练集顶尖化（快照横幅 / 8 例实跑复核 / 8 份夹具与 RULE_LAW 6 条现状 / FIELD-001 挂账 / 复现口径）+ 契约判据 test_drill_doc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：W5 实测记录顶尖化（快照横幅 / D4 接线现状复核 plog 出边已移除 / D3 与风格棘轮分工 / 复现命令）+ 契约判据 test_w5_record_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：W3 实测记录顶尖化（快照横幅 / C8·C9 接续指引 / 交付件与现行口径对照 / 复现命令）+ 契约判据 test_w3_record_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：W2 C3/C4 实测记录顶尖化（快照横幅 / 三处修复现状复核 / 扫描面 44→248 活绑定 / 复现口径）+ 契约判据 test_w2_c3c4_record_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：C9 回合装载指针 v0 顶尖化（v0 快照+已被 v1 接续 / P03 装配数 27·23 与真源对齐 / 样例笔误修正 / 复现口径）+ 契约判据 test_c9_pointer_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：C8 transport 评估顶尖化（评估快照+结论复评 / 本地 HTTP 面 vs 远程通道口径分离 / 复现命令 / 33_ 归档）+ 契约判据 test_c8_transport_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：C7 实测记录顶尖化（历史快照横幅 / 现状对照 4→12 工具与无需快照入口 / 复现口径 / E3 真源）+ 契约判据 test_c7_record_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：C1C2 实测记录顶尖化（历史快照横幅 / 现状对照 / 复现口径 / 归档事实标注）+ 契约判据 test_c1c2_record_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：quickstart 参考顶尖化（去死安装命令 / 环境前提 / 三步自检 / raw 直链 / 阅读指引）+ 契约判据 test_quickstart_reference_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-13）：commands 参考顶尖化（契约数 16→27 / 去重空段 / library 生命周期分行 / exit2 口径）+ 契约判据 test_commands_reference_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：assembly 参考顶尖化（编号两通道 + 裸号不变量 + exit2 口径 + 参考机检面）+ 契约判据 test_assembly_reference_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：SKILL.md 顶尖化（契约数 16→27 修正 / 常见失败模式 / 维护者校验段）+ 契约判据 test_skill_md_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：NF-WORLDCAMPUS 馆藏顶尖化（补 verified/stale_after/回执 + 取件核验段 + 许可挂账口径；knowledge lint 时效欠账清零，判据收紧为零 WARN）+ 契约判据 test_library_worldcampus_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：NF-TECHDOC 馆藏顶尖化（15 件内嵌重嵌至 2026-11-12 快照 / verified 更新 / §8 取件核验 / 回执重签；派生样例 techdoc_front 同步重嵌）+ 契约判据 test_library_techdoc_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：NF-1 馆藏顶尖化（正文头日期对齐 generated / 补 §8 取件与核验 / 回执重签）+ 契约判据 test_library_nf1_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：library/INDEX 顶尖化（人读区补三步取件/机检面 + 日配额对齐 intake；生成区未手改）+ 契约判据 test_library_index_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：library/ALIAS 顶尖化（生成器加「标题」列 → ALIAS 重生成；投影一致性保持）+ 契约判据 test_alias_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：decisions/README 顶尖化（读法/判据入口段 + 路由工具占位路径 + 白名单与 payload/ERRATA 事实对账）+ 契约判据 test_decisions_readme_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：decisions/INDEX 顶尖化（标记外补读法/修复指引 + 生成区等价契约）+ 契约判据 test_decisions_index_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：ADR-9001 证据纪律顶尖化（允许三类/禁止六项与 decisions.py 逐条对齐 + 示例表正反例 + 修错证 check35→check33）+ 契约判据 test_adr_9001_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：ADR-9000 模板顶尖化（写法指引七键表 + 三段要点 + 投影/勘误/私有仓纪律）+ 契约判据 test_adr_9000_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：ADR-0000 决策记录顶尖化（可核验面段 + 四条决策项精化 + payload-policy/白名单/ERRATA/RECEIPTS 事实交叉）+ 契约判据 test_adr_0000_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：TECH_TEMPLATES 资产顶尖化（读法/机检 + 模板语义四类/子集不变式 + T904 note 例补齐 + 校验面）+ 契约判据 test_tech_templates_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：TECH_RULES 资产顶尖化（读法/机检 + 规则语义四类/warn|fail 档位 + schema/条目/键清单对账 + 校验面）+ 契约判据 test_tech_rules_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：STYLE_DNA 资产顶尖化（读法/机检 + 三式配置纪律 + 示例档语义 + Phase 1/2 标识符口径 + 不越界阈值声明）+ 契约判据 test_style_dna_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：05_资产库/用户自定义 README 顶尖化（读法/机检 + 键清单/schema 速览与资产文件对账 + nf-asset 头/台账三方 + 校验面）+ 契约判据 test_user_assets_readme_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：05_资产库 README 顶尖化（读法/机检段 + 五接口清单同源 01 §3 + provenance/asset_keys/用户自定义三源覆盖 + 单层货架硬规 + §6 引用映射口径）+ 契约判据 test_asset_library_readme_contract；权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：M80 输出质检门顶尖化（唯一输出闸 / gate_action 单源 / 8 段判定记录 / 零事件固定节点豁免理由 / 硬门不可关）+ 契约判据 test_module_m80_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M50 调度器顶尖化（world_model writes 改回 world_slots 在册冻结路径 / 全局调度器 layer·mounts 约定 / 三形态与机读投影口径）+ 契约判据 test_module_m50_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M24 规则组合顶尖化（零事件+resolve 接口口径 / 不虚构 token 口径 / 依赖面与 02 §4 对账 / I4 配方表边界）+ 契约判据 test_module_m24_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M23 可见性边界顶尖化（零事件+filter 接口口径 / 依赖面与 02 §4 对账 / 只读纪律 / Phase 2 迁移口径）+ 契约判据 test_module_m23_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M10 节拍推进顶尖化（outputs 补全为双事件 payload 并集 / io_types 按规则重推 / tick_day 发布订阅对账 / 三形态与 I3·I4 边界）+ 契约判据 test_module_m10_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M00 数据槽总线顶尖化（纯内部基座豁免依据 / 冻结槽位与 world_slots 对账 / 02 §4 依赖对账）+ 契约判据 test_module_m00_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M90 结构装配顶尖化（四形态口径 / 机读块 ⇄ §2 Module 同源 / P90 八层挂载对账 / fail-closed 边界）+ 契约判据 test_module_m90_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M22 事件编排顶尖化（outputs/payload 补全为 narrative_event 注册字段全集 / 七订阅在册 / inputs 空显式声明 / I3·I4 边界）+ 契约判据 test_module_m22_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M20 知识条目库顶尖化（零事件+query 接口口径 / 双挂载 P70 active + P00 available 同源 / I3·I4 边界 / query 只读）+ 契约判据 test_module_m20_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M13 实体交互顶尖化（outputs/payload 补全为 interaction_update 注册字段全集 / 三形态 / I3·I4 边界 / M12 search 接口引用）+ 契约判据 test_module_m13_contract；权重增量重测、边界重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M12 模板检索库顶尖化（零事件模块 interfaces 补全 search / 三形态口径 / I3·I4 只读边界）+ 契约判据 test_module_m12_contract；check12 权重增量重测、模块边界按新契约重冻结。本轮为机械重绑。

> 重审（2026-11-12）：M06 契约补全 + 判据 test_module_m06_contract；check12 权重增量重测。本轮为机械重绑。

> 重审（2026-11-12）：M08 环境状态模块顶尖化（三形态口径 / I3·I4 边界 / 机读投影口径 / 事件名在册）+ 契约判据 test_module_m08_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：P90 结构装配管线顶尖化（读法/机检段 + 02 §7.1 同源判据 + 空行收口）+ 契约判据 test_pipeline_p90_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：P01 标准管线顶尖化（读法/机检段 + 三处同源判据 + 空行收口）+ 修 P70 optional 与 02/registry 三处漂移；契约判据 test_pipeline_p01_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：P00 管线骨架顶尖化（读法/机检段 + 运行规则空行 + 派生后验收出口）+ 契约判据 test_pipeline_p00_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：07 出厂与预设导航顶尖化（读法段 + 节→机检映射 / 7 处标题空行 / AGENT_START 七段描述同源 / 机制段余量 M99 / §7 九项机检映射 + 状态列口径 / 日期同步）+ 契约判据 test_navigation_doc_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：06 Agent 执行协议顶尖化（读法段 + 节→机检映射 / §10 标题空行 / RFC Date 与最后更新同步）+ 契约判据 test_execution_protocol_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：02 联动注册表顶尖化（读法段 + 节→机检映射 / 7 处标题空行 / 两处跨文件引用精度 / §7 源文切片去 § 形态 / 日期同步）+ 契约判据 test_registry_doc_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：01 核心协议顶尖化（读法段 + 节→机检映射表 / 编号桥 / §引用精度 / 末尾分隔线 / 空行收口）+ 契约判据 test_core_protocol_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：README.ja 日本語入口镜像顶尖化（六步验收 / FAQ 三类 / ROUTES / 版本真源 / TUI 使用说明 / 中日混入修正）+ 契约判据 test_readme_ja_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：README.en English 入口镜像顶尖化（六步验收 / FAQ 三类 / ROUTES / 版本真源 / 最后更新与旧宣言收口）+ 契约判据 test_readme_en_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：README canonical 入口顶尖化（五节结构 / 快速开始六步带验收 / FAQ 三类高频问题 / 版本与 npm+pyproject 同源 / 命令与旗标真实 / stats 区外零计数）+ 契约判据 test_readme_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：llms-full 完整单文件顶尖化（12 工具面补全 / WARN 期望修正 / fail-closed 边界 / 安装说明书指针 / Node engines 与 npm 真源对齐）+ 契约判据 test_llms_full_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：llms-install 安装面顶尖化（三条安装路线 / MCP 能力面与 mcp_package 同源 / 双时代协议常量同源 / 运行数字与 repo_stats+实时 doctor 对账 / 探针四帧修正 / fail-closed）+ 契约判据 test_llms_install_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：llms.txt 机器入口清单顶尖化（按任务选入口七行 / 入口面覆盖 34 件 / 补 WORLD_MODEL·LAYERS·NFA-L·域包协议 / 事实描述同源 / fail-closed）+ 契约判据补入口覆盖；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：ai-menu B1 菜单面顶尖化（菜单单源 / 九层与 M22/样本节号/Y5 等事实同源 / 执行前自检与停止条件）+ 契约判据 test_ai_menu_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：DEEP_DIVE 心智模型顶尖化（三正交/五条不变式与 01 §5 同源、五维纵深、六步运行表、十问逐问映射）+ 契约判据 test_deep_dive_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：ROUTES 云端导购顶尖化（入口链馆线落点 / 镜像路径可核 / 决策流 A-H / 出库前自检 / fail-closed）+ 契约判据补结构决策流与前缀分支；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：AI_ROUTING 入口路由顶尖化（三档自测证据 / 档位⇄落点⇄验收 / driver.json 同源 / fail-closed）+ 契约判据 test_ai_routing_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：AGENT_START 入口顶尖化（七段分流 / DRIVER OVERRIDE 同源 / 三档可执行 / 失败即停）+ 契约判据 test_agent_start_contract（含变异自证）；check12 权重按增量实测更新。本轮为机械重绑。

> 重审（2026-11-12）：L4 塌缩守卫：五个扫描型判据补非空下限断言

> 重审（2026-11-11）：L4 判据质量：文字卫生 markdown 面收敛到 repo_face 单点扫描面（66547→370 件）+ .worktrees 静态剪枝

> 重审（2026-11-11）：L4 判据质量：test_version_map 治理面改 git 追踪面（241 件等价，14.0s→0.05s）

> 重审（2026-11-11）：L4 判据质量：test_ci_diagnostics Dockerfile 扫描面改 git 追踪面（去本地快照假红）

> 重审（2026-11-11）：llms.txt 判据修正：URL 正则反斜杠（CodeQL 高危正则漏检修复）

> 重审（2026-11-11）：L3 收官：llms.txt 卡册生成器死指针 + conformance 计数漂移修复 + 机器入口契约判据

> 重审（2026-11-11）：L3 导航面：ROUTES 死指针修复（README B2/📚 段已移出）+ 路由契约判据

> 重审（2026-11-11）：L3 文档导航面：全仓相对链接判据 + 两处伪代码坏链修复（community 资产档）

> 重审（2026-11-11）：allstar security 契约化：唯一通过条件对账 + 内容质量边界（L2 43/43 收官）

> 重审（2026-11-11）：allstar outside 契约化：权限开关显式收紧 + 组织级豁免边界 + 执行主体单点

> 重审（2026-11-11）：allstar binary_artifacts 契约化：Scorecard 判定镜像 + 全仓零二进制工件 + ignorePaths 白名单

> 重审（2026-11-11）：allstar dangerous_workflow 契约化：Scorecard 规则镜像 + 全仓工作流零命中 + branchList 全分支语义

> 重审（2026-11-11）：allstar branch_protection 契约化：平台保护设置镜像 + required 检查作业名对账 + 平台独有缺口

> 重审（2026-11-11）：allstar 根配置契约化：仓库级/组织级字段口径 + fail-open 边界 + label 前置条件判据

> 重审（2026-11-11）：requirements-lint/sast/audit 三份固定集契约化（同族机械同步）：生成头改为仓库内可复现命令（--extra lint/sast/audit pyproject.toml；audit 保留 --allow-unsafe），hash 完备/自包含/ASCII/禁重复与 extras 纳入判据，并新增跨文件版本一致性对账（含 ci，cross-platform 同时装全部）；lock_digest 变化 → 重生成 THIRD-PARTY-NOTICES.md；新增 test_requirements_pins_contract（3 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：requirements-ci 契约化：每钉版 hash 完备（sha256 64hex、无重复）、直钉与 pyproject ci extra 镜像一致、生成命令改为仓库内可复现（--extra ci pyproject.toml，去掉不存在的外部输入）、自包含（禁 -r/-c/-e）、ASCII/CRLF/结尾换行、禁重复/extras；编辑头部后 lock_digest 变化 → 用生成器重写 THIRD-PARTY-NOTICES.md（44 组件）并同步判据。新增 test_requirements_ci_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：gitee_ingest 脚本契约化：**推送顺序修为先 origin（真源）后 Gitee（镜像）**（原顺序会让镜像领先真源、下一次非快进永久卡死镜像），两处推送都加 pull --rebase 重试；幂等（来源：Gitee Issue #N 认账）、令牌仅从 env + secret=TOKEN 回显脱敏、API 响应有界、issue 分页上限、gitee 通道闸门/配额/超长/密钥/注入/frontmatter 闸门、原子写、36 进制编号；新增 test_gitee_ingest_script_contract（3 项含五类变异自证 + 幂等功能测试）。本轮为机械重绑。

> 重审（2026-11-11）：library_ingest 脚本契约化：标准库+core 白名单、正文真源优先级（文件>env>API）、超长/密钥形状/空壳/frontmatter 形状/白名单/配额六道拒收闸门、注入记档、36 进制编号、原子写、日志脱敏、禁执行面；新增推送韧性（push 失败 pull --rebase 重试一次，仍失败在 Issue 留可执行提示——workflow 仅 issues:opened 触发，静默丢失不可接受）；新增 test_library_ingest_script_contract（3 项含五类变异自证 + 真源优先级功能测试）。本轮为机械重绑。

> 重审（2026-11-11）：net-probes 契约化（workflow 家族收官）：仅手动触发（禁 schedule/push/PR，历史重写后金标缺失只会每周假红）、金标未前移期间 continue-on-error=true（诊断信号，须写明理由）、快照 ref 参数化 + git archive + Python tarfile 解包 + 不可用 fail-fast、树外构建、双 RID 交付形态、跑批 7 个占位符全解析、探针清单在场、失败证据工件（failure-only）保留 7 天；新增 test_net_probes_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：external-links 契约化：非门禁定位（禁 push/PR 触发、独立并发组、禁调 verify.sh）、离线扫描步永远绿 + 联网步 fail-closed（禁兜底写法、pipefail、tee 落盘）、联网硬预算 --max-seconds 600（防慢站点拖到 job 超时）、报告只传 .artifacts/ 本 run 副本（禁受跟踪路径）、工件保留 7 天；新增 test_external_links_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：ci-health 看门狗契约化：只读（禁 checkout / 写仓库）、权限恰为三 read、4 次/天 schedule + push main + dispatch、最新一次口径（排除自身 / cancelled/skipped 不算失败 / pending 跳过）、schedule 面补分页（长期不跑的 workflow 会滑出窗口假绿）、失败必须 ::error + exit 1、安全面快照 continue-on-error 与 NA 兜底；新增 test_ci_health_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：dotnet-build 契约化：树外构建铁律（RUNNER_TEMP + Copy-Item engine/dotnet，树内不留 bin/obj）、.NET 8 主版本守卫、三处 build 都检查  + =Stop、两平台矩阵 fail-fast false、三个 csproj 在场对账、只读、工件含 matrix.os 与日志且保留 7 天；新增 test_dotnet_build_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：rust-crate 契约化：三处 cargo 调用都必须 --locked（test/bin/pyo3）、两平台矩阵 fail-fast false、Linux 专属面（bin parity 34 判据 + PyO3 cdylib 构建）必须显式 runner.os 门控、只读（禁写仓库）、Cargo.toml/lock 四件输入在场对账、失败日志工件含 matrix.os 且保留 7 天；新增 test_rust_crate_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：cross-lang 契约化：full 模式（正负例都 --require-full，UNKNOWN=0）、正例 --digest 逐字节、覆盖棘轮 --coverage、只读铁律（禁 git commit/push/--write/nf.py）与分工铁律（禁调 verify.sh，基线门只在 ci-verify）、.NET 8 主版本守卫、退化证据工件保留 7 天；新增 test_cross_lang_workflow_contract（4 项含五类变异自证，注释豁免）。本轮为机械重绑。

> 重审（2026-11-11）：docker-nfal 契约化：只 build 不推送（禁 docker push/login/secrets/REGISTRY）、push 与 PR 的 paths 同一锚点、两作业各自恰一个诊断工件（修复 nfal 工件错放进 hf-space 作业的真问题）、工件保留 7 天、Dockerfile FROM 必须 @sha256（纯函数对账）；新增 test_docker_nfal_workflow_contract（5 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：e2e-desktop 契约化：无 GUI 不变量（禁 PySide6/QT_QPA_PLATFORM/pyside6/xvfb）、PR 全量触发（禁 paths）、python3 调 scripts/e2e_desktop_headless.py + pipefail + tee、禁兜底假绿、工件 always + 保留 7 天、与 release-gate 同脚本交叉对账；新增 test_e2e_desktop_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：coverage 契约化：覆盖率门槛 --fail-under=80 与 --include=desktop/src/core/* 与 release-gate 交叉对账、NF_COVERAGE=1 + verify_tests --jobs + coverage combine、pipefail + exit rc fail-closed、冷启动 3 目录、诊断工件 always + 保留 7 天；新增 test_coverage_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：cross-platform 三平台依赖口径修复：非 Windows 平台此前只装 requirements-ci，而 --full 的 check12 与 ci-verify unit-tests 同套测试（需要 ruff/bandit）→ style/sast 棘轮 fail-closed 长期红；现三平台统一安装 ci/lint/sast 三份固定集，Windows SAST 步骤只跑基线。判据新增三份固定集必装 + 缺件变异自证。本轮为机械重绑。

> 重审（2026-11-11）：cross-platform 契约化：修复 **报告新鲜度 fail-open**（原顺序 --write → --check，写入后 check 永远通过；改为先 check 再 write，并把顺序钉进判据）、三平台矩阵 fail-fast false、显式 --full 档位、Windows SAST nt 段、冷启动前置 3 目录、Linux 库 RUNNER_OS 守卫、两工件保留 7 天、checkout fetch-depth/tags；新增 test_cross_platform_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：npm-package-check 契约化：只读（禁 npm publish / 令牌 / secrets）、PR 全量触发（禁 paths）、stage→verify→冒烟→pack→tarball 同口径、站点数字对账、stage 后受跟踪改动必须为零（带修复指引）、stage 输出落盘并进工件（保留 7 天）；新增 test_npm_package_check_workflow_contract（5 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：gitee-poll 契约化：跨端入库共用 library-write 写锁（与 library-ingest 交叉对账）、无 GITEE_TOKEN 时显式 skip 不假红（2026-11-07 实测 144 次/天教训）、checkout 凭据保留显式说明（origin 推送依赖）、子令牌只从 env 取且日志脱敏、双端推送/Gitee API v5 对账、诊断工件保留 7 天；新增 test_gitee_poll_workflow_contract（5 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：linux-parity-refresh 契约化：只读不变量（禁 contents: write / git push / git commit）、dispatch+周 schedule、漂移判定双 diff 非空 + 键级 SAST 比对、证据件（sast-posix/vectors.diff/projections.diff）always 上传且保留 7 天；新增 test_linux_parity_refresh_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：dependency-audit 契约化：四份固定集全审（ci/lint/sast/audit）、审计器 --require-hashes、fail-closed（禁兜底假绿）、审计输出 tee 落盘并进工件（保留 7 天）、PR 路径面与周 schedule；新增 test_dependency_audit_workflow_contract（4 项含五类变异自证 + 固定集在场/ASCII 对账）。本轮为机械重绑。

> 重审（2026-11-11）：library-ingest 契约化：issues 触发仅 opened、写权限仅 contents+issues、标题守卫、编号并发串行且不可取消、正文强制走 API（E2BIG 事故口径）、checkout 凭据保留显式说明（push 依赖，与其它 workflow 相反）、诊断工件保留 7 天；新增 test_library_ingest_workflow_contract（5 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：scorecard 契约化：顶层 read-all + analysis 权限（security-events/id-token/contents/actions 各只读或仅需）、评分不可取消、四类触发面、publish_results=true 与 sarif 格式、SARIF/摘要工件保留期、摘要可追溯字段（run_id/commit/sha256/empty_results_are_not_clean）；清理过期 v2.4.3 叙述与 upload-sarif 的 v3/v4 注释错位；新增 test_scorecard_workflow_contract（4 项含六类变异自证 + 与 codeql.yml 同 SHA 交叉对账）。本轮为机械重绑。

> 重审（2026-11-11）：codeql 契约化：PR 路径过滤补 packaging/**（含公网 hf-space server.py 与 js/ts 工具链）、init/analyze 必须同 SHA（删过期 v3 SHA 注释）、SARIF category 按语言区分；新增 test_codeql_workflow_contract（4 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：CI 真红修复（分片 12）：test_pipeline_loader 的「缺 YAML 回退」夹具只还原 sys.modules，未还原 lazy_yaml 的 (_TRIED,_YAML) 缓存——同进程后续用例永久看到缺 PyYAML（world_model / quant 域包 setUpClass 报 ClosureError）；补缓存还原后本地 shard 12 rc=0。本轮为机械重绑。

> 重审（2026-11-11）：npm-publish 双通道契约化：per-job 最小权限（id-token 仅 npmjs / packages:write 仅 GitHub Packages）、发布永不取消、tag-版本一致性（两条通道同口径）、OIDC provenance、幂等跳过、证据工件 always + 保留 30 天；修正 tag 不一致提示里的过期版本线表述；新增 test_npm_publish_workflow_contract（4 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：release-gate 发布闸门契约化：最小权限 / **永不取消**（cancel-in-progress false，发布体检不许被取消）/ tag-only 触发 / fetch-depth+tags / nf release 体检 + e2e 落盘 + 覆盖率门槛 ≥80 / 证据工件 always + 保留 30 天；新增 test_release_gate_workflow_contract（4 项含变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：lint 工作流契约化：required check 名稳定（ruff-check-e9-f63-f7-f82 / ruff-style-ratchet）、棘轮 fail-closed、规则集与 ruff.toml select 同源、检查面为 style_check 扫描面子集；硬化 PR 限 main、ruff 输出 github 注释、工件含 style-counts.json 且保留 7 天；新增 test_lint_workflow_contract（5 项含变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：sast 工作流契约化：最小权限/并发取消/触发限 main/超时/工具 --require-hashes 固定/棘轮 fail-closed（禁 || true）/工件 always + 保留 7 天；SECURITY.md 的 SAST 行改为与脚本 SCAN_TARGETS 同源（去掉不存在的 sast-extra 与非阻塞声明）；新增 test_sast_workflow_contract（5 项，含写权限/PR 不设限/|| true/无保留期/扫描面缺 tui/基线缺平台段变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：ci-verify 主门禁契约化：顶层最小权限/并发取消/触发面限 main/每作业超时/32 片矩阵连续性/gate 对 needs 显式判红/工件 always 上传与 7 天保留；新增强化项（pull_request 限 main、工件 retention 7 天）；新增 test_ci_verify_contract（4 项，含写权限/去超时/gate 非 always/矩阵缺片/工件无保留期变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：dependabot 覆盖补齐：新增 pyproject extras 镜像（pip /）、Rust 引擎 5 个 crate（含 wasm 组件的 wit-bindgen）、容器 digest 3 处 docker 面；分组纪律（major 不分组）与 license/标签/前缀纳入契约；新增 test_dependabot_contract（4 项，含删面/非法节奏/不存在目录/major 入组/重复面变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：CODEOWNERS 顶尖化：承重面显式归人（协议件/门禁本体/判据/治理件/核心库/CI/投稿面/分发站点）、catch-all 置首、owner 与 MAINTAINERS 同源；新增 test_codeowners_contract（5 项：死规则/承重面覆盖/owner 同源/顺序/变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：STRATEGY 可核化：新增 test_strategy_contract（5 项：五段/政策内核/五维在场 + 内部链四载体在场 + 发布边界事实（根层无方案文档、agent 入口在场）+ 引用可解析 + 变异自证）。STRATEGY 本体零改动（作者政策面），本轮只做可核化。

> 重审（2026-11-11）：AGENTS.md 可核化：修正一处退役事实（删除「桌面端显示环境缺失横幅」——桌面 GUI 端壳 2026-09-09 已永久退役，见 docs/L3_FROZEN.md）；新增 test_agents_contract（4 项：闸门段/破坏性命令清单/引用可解析/事实对账 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：许可链总闸：新增 test_license_chain（LICENSE 是唯一真源；canonical MIT 文本完整性 + LICENSES/MIT.txt 逐字节一致 + pyproject/REUSE/CITATION/Zenodo/codemeta/notices 六处声明全等 + 入口文档不宣称 copyleft + 变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：THIRD-PARTY-NOTICES 顶尖化（连带生成器修复）：生成器改为 fail-closed（查询失败不写盘、返回 2）；notices 从「44 行中 34 行查询失败占位」重生成为 44 个组件的真实 SPDX 清单（pin 真源 + 锁摘要新鲜度锚 + 归属声明/分发边界/零依赖可证/双许可表态/人工核对段）；新增 test_third_party_notices_contract（6 项，含 fail-closed 打桩与变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：REUSE 判据按一手调研补强：override 顺序（宽表在前）、投稿面逐文件覆盖（git 追踪面，白名单外必须命中 override）、LicenseRef 命名规则、包级元数据标注为「非 REUSE 3.3 字段」；同步修掉 test_governance_docs 里恒真的 reuse gap 判据。本轮为机械重绑。

> 重审（2026-11-11）：REUSE.toml 顶尖化：三级许可声明结构（全仓 MIT 聚合 + 投稿面 override 拆为 library 与 community 两条）+ 投稿面口径注释（作者自投/第三方投稿同按投稿条款）+ 许可文本自身不声明；新增 test_reuse_contract（5 项：TOML 结构/聚合许可与 LICENSE 一致/override 不空转/许可文本双向闭合/变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：CITATION.cff 顶尖化：作者从 entity 的 name 改为 person（family-names），避免被当机构；补「不钉 version/date-released」策略注释与两源并存说明；与 .zenodo.json 的 title/license/作者双源一致；新增 test_citation_contract（5 项：schema 必填/无未知键 + person 判定 + 双源一致 + 版本策略 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：.zenodo.json 修复：许可从 AGPL-3.0-only（与 LICENSE/REUSE/pyproject/CITATION 的 MIT 矛盾）改回 MIT，删除三个不存在文件的引用（LICENSING.md/COMMERCIAL.md/TRADEMARK.md）与失效的「v1.1.0 许可分层」段；新增 test_zenodo_contract（4 项，许可四源一致 + 双源 title/creators + 失效引用 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：SUPPORT 口径回归修复：申诉复核主体改指 MAINTAINERS 的回避路径（涉 Owner 由外部第三方，无第三方记「未复核」），去掉「未参与原处置的维护者」这一单人仓不存在的角色；判据 test_support_contract 扩到 7 项（新增复核主体同源 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：MAINTAINERS 维护者文档顶尖化：执行主体真源（Owner 具名 + 职责与不可代行面 + 安全/行为双经办）、单维护者三条硬约束（涉己外部第三方回避 / 可复核性代替双人复核 / 90 天失能只读预案）、晋升四硬条件、响应与 SLA 边界；新增 test_maintainers_contract（4 项，含删 Owner/删回避/删天数/悬空链接变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：SECURITY 安全策略顶尖化：通道分工（漏洞→本件 / 行为→COC / 使用→SUPPORT，互不代收）、六项报告模板、7 天确认 + 90 天协调披露、CVE/致谢/无赏金边界、修掉两处悬空引用（tests/test_repo_trust.py、core/gate_inproc.py）；新增 test_security_contract（4 项，含删段/删时限/悬空链接变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：CODE_OF_CONDUCT 顶尖化：通道分工（行为举报受理归属在本件、SECURITY 只界定漏洞）、四档处置（可跳档）、7 天确认 / 14 天申诉 / 30 天复核目标、利益冲突回避与外部第三方复核、报复与恶意举报独立违规；新增 test_coc_contract（4 项，含删段/删时限/悬空链接变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：SUPPORT 入口面顶尖化（含调研补强：私密直达 URL / 状态位承诺 / 复现三件套 / Markdown 相对链接可解析判据）；新增 test_support_contract 6 项，含配置放开、悬空路径、悬空链接变异自证。本轮为机械重绑。

> 重审（2026-11-10）：SUPPORT 入口面顶尖化：先自查 → 去哪问（五类通道 ⇄ config.yml/表单/声明件）→ 提 Issue 前自检四项（与 bug_report checklist 同源）→ 怎么问（最小复现/一次一件）→ 之后会发生什么（不静默丢弃）→ 支持边界；新增 test_support_contract（4 项，含配置放开与悬空路径变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：CONTRIBUTING 入口面顶尖化：§5 重写为「入口分流（空白 Issue 已关 + 四条分流 ⇄ config.yml）/ 改动域四类（代码面清单照抄 library/intake.json 声明）/ 三个模板各自守什么 / 一次一件事 / 提 PR 前自检」；新增 test_contributing_contract（5 项，含配置放开与悬空路径变异自证）；§4.2 补代码面清单真源注记。本轮为机械重绑。

> 重审（2026-11-10）：PR 模板与两个 Issue 表单同构化（改动域/问题→做法→影响面/可核验收命令+期望/门禁自检四项/Closes-Refs+只做一件事声明）；新增 test_pr_template_contract（4 项，含删段与悬空路径变异自证）；本轮为机械重绑，不主张新的语义审计。

> 重审（2026-11-10）：config.yml 入投稿面声明

> 重审（2026-11-10）：权重件随表单契约更新

> 重审（2026-11-10）：新增 issue 表单契约判据后重绑

> 重审（2026-11-10）：merge 后重绑

> 重审（2026-11-10）：论文台账系统化 + 方法包深度判据

> 重审（2026-11-09）：冻结链

> 重审（2026-11-09）：台账表内自洽判据（序号连续 + 红绿不交叠 + 解析拒绝畸形输入）

> 重审（2026-11-09）：方法包文档「N 种用法」与列举条数/命令存在性绑定判据

> 重审（2026-11-09）：包可跑入口真跑判据（11 域 14 命令，退出码 0/2 合规）

> 重审（2026-11-09）：红证据棘轮改比例口径（绝对数会惩罚新增测试）

> 重审（2026-11-09）：core 引用面映射（355 模块 / 未引用 34，棘轮只减不增）

> 重审（2026-11-09）：红证据加 negative_assertion 档（assertRaises）：硬证据 20→99，无 149→139

> 重审（2026-11-09）：红证据登记（硬证据 20 / 疑似 221 / 无 149，棘轮只减不增）

> 重审（2026-11-09）：矩阵文档点名每层变异测试（一致性绑定第二条）

> 重审（2026-11-09）：文档入口列与包 runnable 绑定判据（消灭第二真源）

> 重审（2026-11-09）：方法包声明可跑入口 runnable，清单与文档共用（含入口存在性判据）

> 重审（2026-11-09）：脚本孤儿棘轮（6 个冻结 + 文档点名 + 自指排除）

> 重审（2026-11-09）：能力清单（静态 AST 扫描 scripts/*，可查而非猜）

> 重审（2026-11-09）：方法包补「可跑入口」列 + 入口命令存在性判据

> 重审（2026-11-09）：文档引用的探针数字判据（判据数/变异体数/覆盖率绑定结果件）

> 重审（2026-11-09）：文档仓库路径存在性判据（引用面第四条，59 处全命中）

> 重审（2026-11-09）：maps_to 词表判据（引用面第三条）

> 重审（2026-11-09）：判据族谱 v0 收入 docs/ccos（7 族 + 每族失效方式）

> 重审（2026-11-09）：文档相对链接存在性判据（14 条全部解析）

> 重审（2026-11-09）：criteria_refs 悬空修复（5 包）+ 引用存在性判据

> 重审（2026-11-09）：结论可落盘 --out（配合 verifier_status 复核）

> 重审（2026-11-09）：路径旗标覆盖棘轮（22 个已知缺口冻结，禁止新增未覆盖）

> 重审（2026-11-09）：第十一个域 operations（运维可观测性）：6 动作 3 证据类

> 重审（2026-11-09）：补 --threshold CLI 真跑覆盖（trigger 块与计数自洽）

> 重审（2026-11-09）：供应链对象 v0 收入 docs/ccos

> 重审（2026-11-09）：发布结论记录材料清单摘要（供应链闭环）

> 重审（2026-11-09）：json_doc 统一 + 耦合重算（材料清单入仓）

> 重审（2026-11-09）：材料清单对象（nf-sbom/1：显式范围 + 摘要折叠 + 篡改必红）

> 重审（2026-11-09）：CLI 输出确定性判据（两条只读命令逐字节比对）

> 重审（2026-11-09）：第十个域 supply-chain（供应链安全）：6 动作 3 证据类，锚点落 packaging/静态扫描/溯源

> 重审（2026-11-09）：文档判据变异测试（层数/门数/域数/动作数/类目数）

> 重审（2026-11-09）：变异探针扩到三判据（9 变异体 / 7 合法变体，杀死率 1.0 误报 0.0）

> 重审（2026-11-09）：方法包例子路径补全 + 引用存在性判据

> 重审（2026-11-09）：第九个域 privacy（隐私工程）：6 动作 3 证据类，锚点落 ingress/到期/吊销面

> 重审（2026-11-09）：判据接线：resource 核入 verify_commitment，authority 核入 replay

> 重审（2026-11-09）：修重放回归：authority 必须随记录回放（含回归判据）

> 重审（2026-11-09）：证人核对接入生产路径：session.step(root=) + CLI 传 ROOT

> 重审（2026-11-09）：文档数字漂移判据（层数 / precheck 门数）

> 重审（2026-11-09）：结论可复用性查询（verifier_status：current/stale/unknown）

> 重审（2026-11-09）：双核不变量 v0 收入 docs/ccos（九层 + 自省闭环）

> 重审（2026-11-09）：发布结论记录验证器摘要（自省层闭环）

> 重审（2026-11-09）：耦合面重算（288 模块）

> 重审（2026-11-09）：自省层对象：验证器摘要（判定面脚本内容摘要）+ 探针 + 判据

> 重审（2026-11-09）：对抗+资源入矩阵（8/9）：证人文件核验 + 两本账；文档同步

> 重审（2026-11-09）：对抗层：counterexample 必须带可复算证人（file+case）

> 重审（2026-11-09）：资源层同构判据 #7：两本账（cog_steps/cc_cost_ms）并列记、不合并

> 重审（2026-11-09）：资源层记账起点：证据判定附 cost_ms（只记耗时，不参与判定）

> 重审（2026-11-09）：同构矩阵数据搬到 fixtures（单源），测试只留反射查证

> 重审（2026-11-09）：授权层对象：control 记录 authority（终态算子必填）+ 同构判据 #6 + 变异测试

> 重审（2026-11-09）：两种导入风格判据（包路径 + 裸名）

> 重审（2026-11-09）：快照25 两处红：--pack-checklist 进编码闸 + 矩阵判据支持裸模块名

> 重审（2026-11-09）：证据图结果新鲜度判据（陈旧即红）

> 重审（2026-11-09）：探针结果新鲜度：--check + 判据（结果陈旧即红）

> 重审（2026-11-09）：precheck 名单拆成数据件（precheck_gates）+ 探针改原子写

> 重审（2026-11-09）：判据变异探针：两条判据 × 3 变异体，杀死率/误报率入 results

> 重审（2026-11-09）：同构矩阵反射查证抽函数 + 变异测试（指向不存在方法必须 False）

> 重审（2026-11-09）：时钟纯度负向用例 + 探针代理扩词（19/22）

> 重审（2026-11-09）：门禁负向用例探针（命名代理，只出比率与缺口清单）

> 重审（2026-11-09）：同构矩阵加变异测试列（每层必须能被改坏打死）

> 重审（2026-11-09）：观测同构判据 #3 变异测试（改来源/改序/改证人必红）

> 重审（2026-11-09）：桥信封守卫变异测试（第三类信封必须被抓）

> 重审（2026-11-09）：判据 #4 变异测试：词表核对接出独立函数，故意改坏必红

> 重审（2026-11-09）：方法包文档 v0（八域）+ 文档计数判据

> 重审（2026-11-09）：precheck 20 闸门：补时钟纯度 + 报告确定性（快照24 漏检面）

> 重审（2026-11-09）：方法包可执行化：checklist 投影 + nf cognition --pack-checklist

> 重审（2026-11-09）：第八个域 handoff（协作交接）：可接续帧/承诺落证/角色分离/分歧留档/第三方复验/版本钉定

> 重审（2026-11-09）：第七个域 resilience（韧性工程）：6 动作 3 证据类，锚点落既有隔离/变异/回滚面

> 重审（2026-11-09）：判据时钟纯度闸门（读此刻必须登记理由）

> 重审（2026-11-09）：判定判据日期稳定：同树同基准日重算（跨午夜不再假红）

> 重审（2026-11-08）：反模式守卫：桥只允许两类信封

> 重审（2026-11-08）：同构矩阵：缺失理由必须点名具体对象（新判据）

> 重审（2026-11-08）：九双生层同构矩阵（覆盖项必须有真实测试）

> 重审（2026-11-08）：同构判据 #5（负空间层）：abstain 必带检索边界

> 重审（2026-11-08）：同构判据 #4（语义层）：claim_kind 单一词表

> 重审（2026-11-08）：文档锚点：生成物前缀兜底（git 不可用时也能判）

> 重审（2026-11-08）：同构判据 #3（观测层）：回灌记录与契约失败集逐项对应

> 重审（2026-11-08）：precheck 快车道扩到 16 闸门（补 calibration/grouped/evidence_graph/atom_catalog）

> 重审（2026-11-08）：提交前自查快车道（precheck：按名单跑既有横向门禁）

> 重审（2026-11-08）：快照20 红修复：--pairs 入闸/json_doc/分组表接入探针/耦合重算

> 重审（2026-11-08）：同构判据 #1：commitment 绑定时点引用（ts_digest）

> 重审（2026-11-08）：桥线格式守卫（commitment/obligation 字段集钉死）

> 重审（2026-11-08）：证据图探针（陈述⇄证据二部图，H=悬挂比）

> 重审（2026-11-08）：第六个域 data-provenance（数据溯源：说明书/字段溯源/缺失语义/许可/版本钉定/泄漏）

> 重审（2026-11-08）：文档锚点：忽略生成物路径（payload/dist）+ 修 62 项计数

> 重审（2026-11-08）：分组报告模块（先分组再汇总；n<2 不能谈方差）

> 重审（2026-11-08）：口头置信触发策略（触发器非证据）+ CLI --threshold

> 重审（2026-11-08）：calibrate 文案收口

> 重审（2026-11-08）：cog calibrate CLI（可靠性表出口）

> 重审（2026-11-08）：校准度量 core/calibration.py（分箱/ECE/可靠性表，只计数不评分）

> 重审（2026-11-08）：快照现场体检（--status：锁/运行目录/最近结论一份看全）

> 重审（2026-11-08）：快照墙钟上限（--max-wall-s，超时判红留证）

> 重审（2026-11-08）：Ingress 启动自检（四道闸探针，非空转判据）

> 重审（2026-11-08）：MCP 红队用例集（8 条，逐条核闸门）

> 重审（2026-11-08）：文档锚点判据（docs/ccos 每篇必须指到真实实现）

> 重审（2026-11-08）：所有方法包动作：锚点或显式概念声明（判据）

> 重审（2026-11-08）：锁拒绝的集成判据（退出码 2 + 指引）+ 锁目录 env 钩子

> 重审（2026-11-08）：快照锁：json_doc/atomic_write/sink 登记/文档计数/编码闸门

> 重审（2026-11-08）：快照锁等待模式（--lock-wait，死锁立刻接管）

> 重审（2026-11-08）：锁存活探测走受控进程原子（S603/S607 收口）

> 重审（2026-11-08）：--sheet 入确认闸（(cog, --sheet)）

> 重审（2026-11-08）：快照锁 + sink 登记（lock 自清）

> 重审（2026-11-08）：快照互斥锁（并发会话互清 worktree 的实测对策）

> 重审（2026-11-08）：claim-check 直吃作业单（免手抄 evidence）

> 重审（2026-11-08）：主张→证据作业单（每个 required 一条 unknown 槽）

> 重审（2026-11-08）：采集单：半填必须点名「采集未完成」

> 重审（2026-11-08）：五包组合判据（并集去重/逆序不丢/同序可复现）

> 重审（2026-11-08）：采集单校验器（协议绑定/状态机/维度完整/盲评负对照）

> 重审（2026-11-08）：耦合面重算（eval_harness→method_pack 边）

> 重审（2026-11-08）：eval harness 采集检查单（D-06 作业面）

> 重审（2026-11-08）：注入防御包动作加代码锚点判据

> 重审（2026-11-08）：新增方法包 prompt-injection-defense（注入防御域）

> 重审（2026-11-08）：方法包引用还清 k.standard 原子债；A4 判据改为合成死码

> 重审（2026-11-08）：评测设计包接主张编译（efficacy/cost/reliability 三态）

> 重审（2026-11-08）：新增方法包 evaluation-design（评测设计域）

> 重审（2026-11-08）：拍屏探针第五轮（10 配置全扫描，负结果锁死）

> 重审（2026-11-08）：快照红修复：job 描述/面信封/权重/耦合面

> 重审（2026-11-08）：全量门禁收口：json_doc/atomic_write/面判别键/dead-code/静默跳过/路径旗标/ingress 接线

> 重审（2026-11-08）：terminal 族登记 cog + 终端投影刷新 + CRLF 归一

> 重审（2026-11-08）：Ingress 网关（认证/白名单/限流/同意/回执）

> 重审（2026-11-08）：工具清单派生自真实 TOOL_DEFS（D-04 关账）

> 重审（2026-11-08）：预注册评测协议 + harness（D-05 关账，新增 D-06 真实测量债）

> 重审（2026-11-08）：原子组合覆盖层（13 复合原子）+ 死码 12→1（D-01/D-02 关账）

> 重审（2026-11-08）：桥接真实证据包（D-03 关账）

> 重审（2026-11-08）：闭包台账（21 条断言 → 真实判据 → 反例 → 状态）+ 审计脚本

> 重审（2026-11-08）：K1 作业账本 + K4 事件流 + K8 启动自检（P6 第二件）

> 重审（2026-11-08）：MCP 兼容头（工具清单 _meta 增强 + 签名钉根 + 吊销 + 调用回执）

> 重审（2026-11-08）：ADR 注册表 + 16 份文档台账 + 分层依赖判据（P0 补账）

> 重审（2026-11-08）：双核桥（commitment + 回灌 + 闭环）

> 重审（2026-11-08）：原子目录 v2 + 不变量 A1–A5 + 候选健康 B1–B5

> 重审（2026-11-08）：判据注册表 + 主张编译（证据义务清单/三态核对）

> 重审（2026-11-08）：元算子层（11 ops + 触发引擎 + 双 trace + 反仪式化）

> 重审（2026-11-08）：认知工作台 L0（discourse/15 moves/records/replay + nf cog）

> 重审（2026-11-08）：几何提示同步探针（尺寸反解 + 双假设 + 偏移搜索；谱峰不变反例）

> 重审（2026-11-08）：同步层探针（同步字平铺 + 网格搜索，负结果可复算）

> 重审（2026-11-08）：DCT 水印探针（QIM vs 关系嵌入，q70/q50 实测）

> 重审（2026-11-08）：密钥透明目录 v0（版本根/追加链/包含证明/分叉见证）

> 重审（2026-11-08）：水印鲁棒性基准（16 攻击 × BER）+ 文档实测表

> 重审（2026-11-07）：方法包 v0 收尾（风格/度量重冻）

> 重审（2026-11-07）：方法包 v0（3 个领域包 + 组合 + 研究计划接线）

> 重审（2026-11-07）：认知核研究层：方法库 + 切片计划器 + CLI（切片检索词/方法论路径/证据台账）

> 重审（2026-11-07）：向量面收口：三形态跨实现同判 + 信封 subject 三摘要面

> 重审（2026-11-07）：命令树拆分（production 321→117 行 + 新组 evidence_face 207 行）

> 重审（2026-11-07）：门禁修：silent-skip 理由 / 两个文本参数登记 / --mode 复核

> 重审（2026-11-07）：Go 客户端补齐 cc_check/cc_label/cc_attest/cc_replay/cc_diff/cc_resolve（6 份向量集）

> 重审（2026-11-07）：Go 客户端补 receipts/attest 两形态；向量集扩到 28 条（三形态）

> 重审（2026-11-07）：cc_check 文本层：法规原文→意图草稿（规则抽取，四张账）

> 重审（2026-11-07）：吊销公钥信任锚（钉根 + 有界委派 + 过期/scope/链深判据）

> 重审（2026-11-07）：载体层：WebP/MP4/PDF 附加块 + PNG 像素水印（判据含 JPEG 不扛的期望行为）

> 重审（2026-11-07）：RFC 3161 可信时间戳（timestamp 模块 + CLI + 证据复验时间锚）

> 重审（2026-11-07）：快照落点纯函数化 + 3 条隔离判据（同盘/出树/日志）

> 重审（2026-11-07）：revocations_seed 进二进制豁免 + 两份文档项数同步（62→65 / 34→43）

> 重审（2026-11-07）：ed25519 吊销签名（非对称：验证方只持公钥）+ 回归判据

> 重审（2026-11-07）：batch_target 登记修正（位置参数进文本面，不进旗标名单）

> 重审（2026-11-07）：口径同步 3022 件 / 23.92 MB

> 重审（2026-11-07）：nf evidence batch（目录逐件复验，整批不可用即失败）

> 重审（2026-11-07）：instruction_evidence 临近过期提前 7 天 WARN + 重录 verify/release

> 重审（2026-11-06）：快照模式：内层日志边跑边落盘 + 陈旧快照自动清理

> 重审（2026-11-06）：机器面 NF_HOME 可移植（nf.py 变更）

> 重审（2026-11-06）：bash 身份守卫（WSL 空输出不再冒充判据红）+ Windows 两坑入文档

> 重审（2026-11-06）：CLI 命令树拆分 + 旗标字面读取（nf.py 变更）

> 重审（2026-11-06）：Rust 侧 SINK_ALLOW 同步 + 陈旧二进制守卫 + 漂移判据

> 重审（2026-11-06）：task-27 吊销新鲜度：revocations/evidence/nf.py 变更，重绑被审对象

> 重审（2026-11-06）：快照落点改仓库同盘 + TEMP 重定向（防满盘 ENOSPC）

> 重审（2026-11-06）：发布结论器加 --snapshot（HEAD 快照里跑，免疫并发改动）

> 重审（2026-11-06）：JPEG 载体 P0 硬化（nf.py/CLI 文案变化）+ 口径清理，重绑被审对象

> 重审（2026-11-06）：JPEG APP15 载体（扫描数据不变）+ 真 PNG 夹具判据

> 重审（2026-11-06）：Q0-r2：evidence verify 增 --policy-digest 期望比对（nf.py 参数面变化），重绑被审对象

> 重审（2026-11-06）：耦合面重冻（载体模块行数变化后 metrics 面漂移）

> 重审（2026-11-06）：cc_label PNG iTXt 载体（可读回/不改像素/CRC 合法）

> 重审（2026-11-06）：注册 --decision 参数进编码/路径闸门（其提交遗漏）

> 重审（2026-11-05）：Q0 决策证据绑定：scripts/nf.py 增 --decision 入口、evidence/attest/nf_verify 增 decision 绑定，重绑被审对象摘要

> 重审（2026-11-05）：M2：证据面双实现 parity（三形态+仓外单文件）与 CLI↔HTTP 同证据判据落地；重绑 check12 权重摘要

> 重审（2026-11-05）：M1：ABI 错误面登记 + docs/ccos 一致性判据落地，重绑被审对象摘要

> 重审（2026-11-05）：容器面加固：路径安全闸门 / 重名判死 / 解压上限（攻击矩阵 33→35）

> 重审（2026-11-05）：cc_label sidecar 回退（nf-label-sidecar/1，绑定对象摘要）

> 重审（2026-11-05）：隔离静态判据（打桩面）+ 三个机器判据进常驻集

> 重审（2026-11-05）：证据判定向量集（跨语言一致性锚点）+ 文档

> 重审（2026-11-05）：--compile 参数登记进编码/路径闸门

> 重审（2026-11-05）：cc_check 编译面 v0：意图 → 封闭词表策略（不可表达逐条挂账）

> 重审（2026-11-05）：权重实测后重冻（报告须最后写）

> 重审（2026-11-05）：新鲜度步：修 UP031 + 前置测试改结构断言

> 重审（2026-11-05）：受影响选片 v2（四类规则 + 文档目录前缀 + 硬兜底面）+ 纯函数判据

> 重审（2026-11-05）：G2 吊销分发件（签名 feed：签发/校验/合并，防回滚）+ nf.py 导入块排序

> 重审（2026-11-05）：label 声明层补登记（编码闸门/路径旗标）+ 删零引用函数

> 重审（2026-11-05）：cc_label 声明层（nf-label/1 IR）+ 供应链核对进发布结论

> 重审（2026-11-05）：G1 外部锚点：证据包可声明并可核对（防整链截断），双实现同口径 + 攻击矩阵 33 条

> 重审（2026-11-04）：H1 修复：--trust-repo 环境变量不再泄漏（信任门不再被绕过）+ 新增回归判据

> 重审（2026-11-04）：分片 1/8 抽检修复：编码闸门/路径旗标名单补全、删零引用常量与函数、耦合基线重冻

> 重审（2026-11-04）：证据线 fail-closed 加固：chain 段必填 / 吊销表坏件判 invalid（攻击矩阵 25→29）

> 重审（2026-11-04）：抽检第二个分片：原子写纪律（包/报告走 atomic_write，临时写例外登记）

> 重审（2026-11-04）：check12 修复波：JSON 面登记 / json_doc 收敛 / Rust 回执去重同步 / 基准 JSON 纯净

> 重审（2026-11-04）：本地 HTTP 面 v0（nf serve --http 三端点）落地 + 端点契约登记 local.*

> 重审（2026-11-04）：cc_resolve（契约面反查）+ 一条链复现脚本落地

> 重审（2026-11-04）：cc_replay 轨迹 + cc_check 单对象策略体检落地（新模块 check_policy）+ 回执去重

> 重审（2026-11-04）：证据复验器扩三种形态 + 攻击矩阵基准（26 项校验路径与基准落地）

> 重审（2026-11-04）：证据包缺省落点改到临时目录（不往仓库落盘）+ CCOS ABI v0 收口

> 重审（2026-11-04）：CCOS ABI v0 + 证据包校验器落地（scripts/nf.py 与 core/terminal.py 摘要变更；并修复本分支既有漂移）

> 重审（2026-10-30）：新增契约级 Git 演进时间线；结构化 Markdown YAML 字段与 JSON schema 差异纳入影响度

> 重审（2026-10-30）：全仓审计口径复核：显式 legacy 清单、subjects 根内解析、Path 参数闸门、惰性导入与 manifest 可复算

> 重审（2026-10-30）：桥接 Path 参数统一根相对与类型闸门；公共子模块惰性加载；生成菜单原子写；入仓 manifest 增加实时复算判据

> 重审（2026-10-29）：CLI 命令树无损分组、meta-cockpit 接线与恢复分支全量验证后重绑；既有结论不变

> 重审（2026-10-29）：恢复分支全量验证：纯度修复、零引用清理、public API 接线、ReDoS/CLI 闸门/文档路径与模板示例修复

> 重审（2026-10-29）：恢复分支全量验证：接线 meta-cockpit 公共模块、清理零引用、修复 ReDoS/CLI 闸门/公开文档路径后重绑；既有结论不变


# 元认知生产驾驶舱主仓融合审计

> 日期：2026-10-30
> 范围：`desktop/src/core/meta_cockpit/`、CLI 桥、终端命令族与自动化测试
> Machine digest：`59357b7056a68bfbd64cdd85333aadfb95c34fdf06f1216563cee56f5e01ce5c`
> Manifest digest：`c9469a7f54041e7c041e353a768bad98054b72bcb4775639f7463754b985abfc`

## 结果

- 33/33 原子执行器在场，14 个方法节点、10 节点内容管线与 5 节点元管线可加载执行。
- 元管线好样本 PASS：5 节点、17 个原子轨迹全部 PASS。
- 六类 fail-closed 突变均被抓：缺执行器、无效方法路由、预算耗尽、缺判据、未知任务类型、输出类型不匹配。
- 动态驾驶验证：不同任务/注入产生不同 need 序列，状态完成且轨迹无 `score`。
- 事件账本验证：提交后可加载、哈希链校验通过、确定性重放与当前状态一致。
- A/B 验证：预注册、盲包、功效分析、强效应、重复 ballot 拒绝、bundle/store 往返均通过。
- 发布清单验证：运行代码、契约、协议与正式说明纳入统一 digest；HR-001 保持 `PENDING`。
- CLI 入口验证：`nf cockpit` 与 `nf cockpit-ab` 可发现、可帮助、可执行；终端能力族与生成投影同步。

## 验证证据

| 检查 | 结果 |
|---|---|
| `tests.test_meta_cockpit` | 11/11 PASS |
| 最终受影响合并集 | 292/292 PASS |
| 终端/TUI/代码度量/权重/文本卫生受影响集 | 233/233 PASS |
| CLI/JSON 形状/耦合/模块命名受影响集 | 79/79 PASS |
| Ruff | PASS |
| 风格棘轮 | 10022 ≤ 基线 10032 |
| 代码规模 | 310 文件；最大行数 7643；最长函数 1262；最大复杂度 116 |
| 耦合 | 0 未登记环；258 模块；SDP 10/10 登记 |
| 元管线运行 | `PENDING-REVIEW`，机器层 PASS |

## 遗留边界

- HR-001 必须由作者或指定复核人签字，本审计未生成 approve 记录。
- 真实跨模型、多 seed A/B 未运行；不宣称已测得质量增量。
- 语义真伪仍由人工复核兜底。
- 工作区存在本次任务前已有的并发修改；本轮未执行 stash、reset、restore 或清理。

## 设计偏差

- 内部原型使用扁平模块导入与 `D:\\NinFenz` 绝对路径；主仓版本改为 `core.meta_cockpit` 包、相对导入和仓库根推导。
- 内部一次性 spike 脚本未直接入库；高价值断言已转为主仓 unittest 契约。
- `jsonschema` 作为可选标准实现使用；缺失时退回主仓确定性 JSON Schema 子集并 fail-closed。
