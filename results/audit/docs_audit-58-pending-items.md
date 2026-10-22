---
id: AUD-0010
title: 六条挂账全部收口 + 出口/会话面外部核验（CCV3 假 v3 与 MCP 可缓存结果两处真缺陷）
date: 2026-09-21
scope: 作者指令「遗留全部补上」——处置 AUD-0009 §五 列出的全部遗留：六条挂账候选（透明日志 / CycloneDX / W3C VC / C2PA / CID 寻址 / 内容分级）、导出面入仓、外链巡检网络口径、外部实测线中**本环境可执行**的格式与协议面核验
verdict: pass
auditor: 本轮执行者
subjects:
  - verify.sh:bb69717b205769f5bf1e558e9dd15e7225f31de78cc0a4f18ffdea77f4a06dca
  - desktop/src/core/transparency_log.py:8aba0254fcf72230452600d5cb0305b5d5320cd3e95d8ed57ebe54a5d0ae46a1
  - desktop/src/core/rating_gate.py:468759e5d971fbe9319ab86e84d95031c13bc3df2c44dbffac0af3fcb071f74e
  - desktop/src/core/interop_export.py:cfabc28f442a8d43526d92fca8cb17ea74473f51de8f69e918042eb5062b24f8
  - desktop/src/core/ccv3_adapter.py:ec9bfacffcb0dd6a73f88652a7273d631e40c4efd8cecfb00a5f0be831a511ad
  - desktop/src/core/export_schema.py:9052dc891be0c70ceb5b42544eceeceeeb4dee8c4f107b1ec660913cf922ad3d
  - desktop/src/core/mcp_runtime.py:737e95ad29adfc9d1e41ce9faa41ae2ad7e668ecdc34a9b0468ce6afedc4d384
  - desktop/src/core/import_adapter.py:7b68a8c20b1a1cc4acf78ca0b27e0752d49d509d49916539ce4a7ad38622cf1b
  - desktop/src/core/library.py:e5a867a775bbab717c882250187578b7d057c51a233c334190e5179f903918bf
  - scripts/check_interop_schemas.py:f9c1add0ee80fb23a3913e32482027e9a4049c5ce70cb35b2b1be4afa075d091
  - scripts/check_external_links.py:1cbee65ba19a83fbcdf333e35b8d99c2e45f3b400f3a025860357baf7a806b02
  - library/intake.json:bf8c7552cafad2fde4b5273c83ba025e099e6e9b5edd894935638ca63ee881ee
  - docs/external-validation-assets/E1_ccv3_sample_lightmix_P04_chara.json:a91f402cdf59faaab6808b64b00c1874cb7cc6c8df4d44fbb5379be7736b8edb
  - results/interop-schema-validation.md:e2546c6407416b61912ac351d14d20c171167e36be4d4d3461f6c2fceb56c0c9

---
> 重审（2026-10-22）：CI 三刀合入后重绑（诊断目录绝对化/fetch-tags/wasm skip）

> 重审（2026-10-22）：R2：MCP 内部错误脱敏（重冻·修订）

> 重审（2026-10-22）：R2：MCP 内部错误脱敏（重冻）

> 重审（2026-10-22）：测试执行器、进程原子与 Windows shell 解析修复后重算代码度量基线与角色投影；既有审计结论不变

> 重审（2026-10-19）：check39 挂载五分钟入口判据（docs/quickstart.md ↔ scripts/quickstart_check.sh），verify.sh 结构性新增子判据

> 重审（2026-10-19）：verify.sh 恢复并补 _NF_BG_TESTS_PID 声明

> 重审（2026-10-19）：verify.sh 补 _NF_BG_TESTS_PID 声明（set -u 下 pre-push 钩子炸点）

> 重审（2026-10-19）：EOL 归一 + 译件重签

> 重审（2026-10-19）：verify.sh 诊断目录/临时变量修复后重绑

> 重审（2026-10-19）：诊断目录兜底：TMPDIR/仓库内 .rivet/tmp

> 重审（2026-10-19）：full 重叠回退（实测更慢且内容面互扰）

> 重审（2026-10-19）：full 档也重叠 + 单分片内层线程按核数

> 重审（2026-10-19）：knowledge_order_read 去 annotation 重叠，补 filtered-order/count；tdqs 两次 4.9、全部工具 >=4.9

> 重审（2026-10-18）：工具名归一：6 个旧名 -> _list/_search/_read；旧名 alias；官方 tdqs 4.9 两次

> 重审（2026-10-18）：动态队列 + 常驻集收敛 + 分片上限 16

> 重审（2026-10-18）：重叠范围收窄到 quick

> 重审（2026-10-18）：TDQS 最终 4.8-4.9：补 local-only/no-auth、no offset、exact package、no pagination；12 工具均 >=4.8

> 重审（2026-10-18）：knowledge_order：分段 + no auth/network/rate/writes；本地 v4-pro 4.8

> 重审（2026-10-18）：quick 档测试与静态 check 重叠执行

> 重审（2026-10-18）：asset_read：删除 outputSchema 的 found（无匹配为错误），2 参数 schema 一致；本地 TDQS 4.8/4.9

> 重审（2026-10-18）：矩阵化落地后重绑一致性面

> 重审（2026-10-18）：CI 门禁矩阵化（32 片）

> 重审（2026-10-18）：TDQS lint：修复 4 个 titleIsMeaningful=false；asset_read 100 词标准版

> 重审（2026-10-18）：asset_read 第五轮：按 TDQS 50-100 词上限压到 100，保留 5 段与输出/参数/限制

> 重审（2026-10-18）：asset_read 第四轮：109 词 5 段 + 输出形状 + package 交互

> 重审（2026-10-18）：asset_read：补 package 只缩文件集不改 key 匹配（参数交互）

> 重审（2026-10-18）：asset_read 第四轮：恢复段落结构（5 段），目标 Conciseness 5

> 重审（2026-10-18）：asset_read 第三轮：84→74 词，压缩替代方案括号

> 重审（2026-10-18）：P3：缓存写走 atomic_write（脚本面纪律）

> 重审（2026-10-18）：asset_read 目标 5：再压到约 91 词，补 no glob/regex/fuzzy + package directory 语义

> 重审（2026-10-18）：asset_read 描述再压缩：去示例、缩短匹配句中句

> 重审（2026-10-18）：Glama 逐工具精修：asset_read 明确 key/package 意图与 when-not-use，去重只读尾句

> 重审（2026-10-18）：Glama TDQS：删除 12 工具重复只读尾句，改显式 when-not-use；保留错误/空结果/扫描行为

> 重审（2026-10-18）：P2：分片数按核数自适应

> 重审（2026-10-18）：Glama coherence：新增 pattern_ls/asset_ls；asset_read 兼容别名；同步 12 工具面

> 重审（2026-10-18）：Glama coherence：MCP 面 asset_get→asset_read（旧名保留兼容别名）；spec_ls/registry_query 描述边界

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

> 重审（2026-10-18）：P3：分层档位 + 判定缓存 + 受影响测试选择

> 重审（2026-10-18）：P2：check12 分片并行（verify_tests 执行器 + 权重基线）

> 重审（2026-10-17）：步骤5：在场/关键词组收敛到 _decl_check（等价性 15 例逐字节一致）

> 重审（2026-10-17）：步骤4：新增 check41/42（构建隔离 + 不可伪造 provenance）与对应判据模块

> 重审（2026-10-17）：拆聚合门：check32/33/35/36 失败逐条透出（只动 bash 呈现层）

> 重审（2026-10-17）：门禁提速收口：check39 剪枝定为 target/obj（刻意不剪 bin——实测零收益且可能承载入库脚本）；check39 7.15s→4.06s，差分 6/6

> 重审（2026-10-17）：门禁提速：check39 遍历再剪构建产物目录（target/bin/obj）——engine/rust/target 一处 22454 目录（gitignore），只含产物不含源；实测目录 24712→1949、遍历 4.36s→0.28s（15.5×），判定逐项等价（禁名命中与 desktop/src/ui 在场性一致），差分 6/6 通过；nf verify 冷跑 17.8s→16.3s

> 重审（2026-10-16）：门禁提速（收口）：修 check30 批量化引入的两处路径归一缺陷（git quotepath 非ASCII转义 + Windows glob 反斜杠）——被 test_check30_bump 当场抓出；另打破 gate_engine↔subcheck_cache 模块环（依赖倒置，只回稳定字段字典），并补两处静默兜底理由

> 重审（2026-10-16）：门禁提速：check30 的 127 次 git diff 合并为一次全量调用后按块取（实测 2.016s→0.196s，42 件逐字节等价）；连同 check39 遍历优化，22 条已迁入合计 30.6s→19.1s、nf verify 冷跑 28.7s→17.8s

> 重审（2026-10-16）：门禁提速：check39 遍历由 os.walk 换单遍 os.scandir（同层剪枝 + follow_symlinks=False，省掉每条目一次 lstat 与整棵被排除子树）；实测 10.34s→6.70s，结果集逐字段一致（24712 目录/7221 py），差分 6/6 通过

> 重审（2026-10-16）：L-D 并行结论：默认保持串行（并行结论不稳定：共享守护单例 + 派生面可写），verify_parallel.py 保留为开发侧工具；verify.sh 字节已变，重绑 digest

> 重审（2026-10-16）：L-D 并行收尾：check12 默认按核数并行（上限 16）+ 守护卫生；相关派生面重冻后重绑

> 重审（2026-10-16）：L-D 并行接线：check12 改走 scripts/verify_parallel.py（模块级并行，8 路实测 1255→409 s）+ 守护卫生（只收本次拉起的）；verify.sh 字节已变，重绑 digest


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> **digest 重绑（2026-10-02）**：`desktop/src/core/ccv3_adapter.py` 因外部实测发现 `scenario` 硬切（`content[:400]` 切在词中段 + 泄漏 `machine_contract` 围栏）而修复（新增 `_readable_head` 边界截断），digest 重绑；本件结论（六条挂账收口）未受影响——该修复为新增项，登记于 `results/docs_external-validation-v2.7.md` §4。
> subjects = 本波承重件十五件（门禁 / 透明日志 / 分级门 / 互操作导出 / CCV3 出口与判据 / MCP 运行时 / 还原适配器 / 图书馆真源 / 两个外部核验工具 / 链生成物 / 声明件 / E1 样本 / 取证报告）。
> **口径修正（2026-09-22）**：subjects **不含派生物**——透明日志生成物每次重生成都会变，
> 绑进审计只会制造假失效；派生物由自己的门禁自证（check31 golden / check35 回执 / check33 入仓面逐字节）。

## 一、逐条处置（原挂账 6 条 → 全部落地）

| # | 原挂账（触发条件） | 本波处置 | 落点 | 实测 |
|---|---|---|---|---|
| 1 | 透明日志（SCITT/Rekor 类） | **实现为确定性哈希链**：`leaf=H(path‖digest)`、`chain[i]=H(chain[i-1]‖leaf[i])`，域分隔前缀防跨类型碰撞 | `core/transparency_log.py` + `nf transparency` + 生成物 `protocol/generated/receipt_chain.json`（check31 golden 校验） | 48 节 · 链头 `cc45f8d6…`；改回执不刷新即 FAIL、改生成物即 FAIL；**不可抵赖性显式不宣称**（写入 `boundary`，门禁判其在位） |
| 2 | CycloneDX SBOM | **与 SPDX 同源不同形**（都读依赖登记面），`serialNumber` 由声明摘要派生 | `interop_export.cyclonedx_doc` + `nf interop --kind cyclonedx` | **官方 meta-schema 通过**（首轮 FAIL：根级自定义键越界 → 移入 `metadata.properties`） |
| 3 | W3C VC（内容凭证） | **VC 2.0 形状 + 未签名状态机读化**（本仓签名走 ssh 外挂锚，套件不同） | `interop_export.vc_document` + `--kind vc` | `@context`/`type`/`issuer`/`validFrom`/`credentialSubject.receiptRoot` 齐；无 `proof` 时 `x-nf-proof-status` 必须在场（门禁判） |
| 4 | C2PA 内容凭证 | **JSON 清单形状**（`claim_generator` + `c2pa.hash.data` 硬绑定 + `c2pa.actions`），封装/签名状态机读化 | `interop_export.c2pa_manifest` + `--kind c2pa` | 断言标签齐 + sha256 硬绑定；`x-nf-package-status` 明写「未封装（无 JUMBF/CBOR）、未签名（无 X.509）」 |
| 5 | CID 内容寻址 | **CIDv1（multibase base32 / raw codec 0x71 / sha2-256）**，纯标准库实现 | `interop_export.cid_index` + `--kind cid` | **multiformats 已知向量自校**：`sha256("")` → `bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku`；48 条回执各得 CID |
| 6 | 内容分级 | **声明驱动**：词表真源 = `library/intake.json: rating.vocabulary`；每件馆藏 frontmatter 声明 `rating`，投影到登记表新列 | `core/rating_gate.py` + `library.py:render_index_block`（分级列）+ 三件馆藏补 `rating` + check34 第 5b 面 | 馆藏 3 件（general×2 / teen×1）· 词表 general/teen/mature/unrated · 缺字段即 FAIL；入库闸门 gate 列表同批加 `rating_warn` |

## 二、其余三项遗留

| 遗留 | 处置 |
|---|---|
| 导出面不入仓（只 stdout/--out） | **补上入仓面**：`nf interop --all --out results/interop` 落 **11 面**派生投影；check33 第 14 面断言「入仓面 == 实时派生」**逐字节**（投影不是真源，改声明件后重跑） |
| 本机网络实测（11/20 失败、重试最坏 ≈34s/条） | **补上工具侧对策**：域级熔断（`--breaker`，默认连续 3 次失败即跳过该域）+ 时间预算（`--max-seconds`），跳过项在报告里可见（`skipped` + `tripped_hosts`）；实测 20 条取样由「9 分钟未收口」变为 **27s 收口**（失败 6 / 跳过 28） |
| 外部实测线仍封存 | **补齐本环境可执行的部分**（GUI 级装载仍属用户侧，如实不宣称）：① **E1 出口面**：取 SillyTavern 写卡源码字面量核对 → 发现并修复「**假 v3**」真缺陷（见 §三）；② **E3 会话面**：取 MCP 官方 `schema/2026-07-28/schema.json` 校验本仓运行时应答 → 发现并修复 list 三面缺 `resultType`/`ttlMs`/`cacheScope` |

## 三、外部核验驱动的两处真缺陷（同 AUD-0009 的取证纪律）

**缺陷 1 · CCV3「假 v3」**（出口层结构错）：旧样本/旧导出只有顶层 v2 字段 + `spec`/`spec_version` 两个头，**没有 `data` 块**；而 SillyTavern 自身写卡逻辑（`src/character-card-parser.js` 的 `write()`）把 v3 内容放在 `data` 内（顶层仅向后兼容）。内部判据只校自述 schema，所以从未红过。
修法：`ccv3_adapter` 输出 **`data`（权威位）+ 顶层 v2 镜像（逐字段同源）**；`export_schema` 判据升级（`data` 必填 + `character_book` 在 `data` 内 + 镜像一致）；`import_adapter` 还原时优先读 `data`（兼容旧形状）；E1 样本按真实导出命令重生成，并加 `docs/external-validation-assets/README.md` 记录取证链。

**缺陷 2 · MCP 可缓存结果缺三键**（协议面结构错）：官方 schema 的 `CacheableResult.required = [cacheScope, resultType, ttlMs]`，本仓只在 `server/discover` 给了这三个键，`resources/list` / `tools/list` / `prompts/list`（与 `resources/templates/list`）都缺 → 官方 schema 判 FAIL。
修法：`mcp_runtime._cacheable()` 统一补齐；单测钉住五面必带三键；复验 4 方法全绿。

## 四、门禁与验收

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | **PASS=61 · WARN=0 · FAIL=0**（check1-37 不变；语义并入 check31 golden / check33 / check34） |
| `python -m unittest discover -s desktop/tests -q` | **961 例全绿**（本波 +21 例：透明日志 7 / 分级 5 / 互操作与入仓 4 / 外链熔断与预算 3 / MCP 可缓存 1 / CCV3 v3 形状 1） |
| `python -m ruff check .` · `python -m compileall -q desktop/src scripts` | 零违规 |
| 编码卫生（含新入仓的 11 面派生物） | 606 文本件 / 77 JSON / 9752 键 · 零违规（判据补 `{}` 与 `@`：URI 模板与 JSON-LD 保留键属外部标准既有形状） |
| `nf transparency` | 链自洽（48 节）· 在盘生成物一致 · 边界声明在位 |
| `nf interop --check` | 11 面一致（含入仓面逐字节） |
| `scripts/check_interop_schemas.py --fetch` | **13 面：官方 schema 通过 5（openapi / asyncapi / sbom / cyclonedx / mcp）+ 上游源码字面量通过 1（ccv3）+ no-schema 6 + unavailable 1** |
| `nf conformance` / `nf receipts` / `nf approve --verify` | conformant 27/27 · 回执折叠到根一致 · 批准有效 |
| `nf library verify --ssh-allowed-signers …` | 3 件在役 · WARN 0（NF-1 演示锚随内容变更用本地演示私钥重签，公钥与 allowed_signers 不变） |
| 外链巡检（域级熔断 + 时间预算） | 20 条取样 **27s 收口**：失败 6 / 跳过 28（跳过原因与 `tripped_hosts` 在报告里可见） |

## 五、遗留与不宣称（本波后）

1. **挂账 0 条**——AUD-0009 §五 的六条全部收口；**新的边界声明**取代新的挂账（写进产物而非留待办）：
   透明日志**不提供不可抵赖**（无第二署名方）、VC/C2PA **未签名/未封装**、资产槽版本面为自由槽版本。
2. **GUI 级外部实测仍未做**：SillyTavern 实际导入、宿主客户端装载属用户侧动作，本环境无法执行——
   本波只把「格式面/协议面」证到官方标准与上游源码口径，**不宣称装载成功**。
3. **prov 面 schema 取不到**：`www.w3.org/ns/prov.jsonld` 在本机返回 HTTP 300，记 `unavailable`，
   不据此判派生面不合规（口径已写进报告与工具）。
4. **分级是声明而非审核**：本门只判「声明在场且合规」，适龄判断责任仍在投稿人/消费方。
