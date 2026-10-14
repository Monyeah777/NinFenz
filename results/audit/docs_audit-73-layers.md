---
id: AUD-0025
title: 抽象阶梯 v2 落地 —— 两轴 + 纵切 + 适应度函数（契约/资产/引擎/出口 × 入口面 × 验证纵切）
date: 2026-09-26
scope: 作者指令「对标顶尖架构设计再改一版」。把 NF 的分层从「混装的梯子」收成两轴 + 纵切，并落成有判据的协议件：真源 protocol/LAYERS.json + 语义判据 core/layer_model.py（并入 check27 R7）+ 生成投影 docs/layers.md + ADR-0004。外部只作机制借鉴（多视图描述 / 稳定依赖与依赖倒置 / 适应度函数 / 单一真源+生成投影 / ADR / 退役治理），开工依据全部来自仓库内部差距实证（见正文），不作立项理由或质量背书（STRATEGY §3.2/§3.3）。
verdict: pass
auditor: 本轮执行者
subjects:
  - protocol/LAYERS.json:0285b8b1fdf20b9ca9cd0857118cd7f3c09946256d33a6d42028a5c41aad0023
  - desktop/src/core/layer_model.py:7464fad8e9703b76b6582a641fb80c5a93c4bbf87b5d2aad191e610eafe64dd2
  - desktop/tests/test_layer_model.py:74ef800a95d1caed9d88809f76708b6de4427c6be9412387e5531e807f8ebf42
  - desktop/src/core/purity_scan.py:9daeeedc9e7708c920512c895c02ed4a91eeaf2d7c99696cb5c0ff6902dab686
  - desktop/tests/test_purity_scan.py:27512feb0957c73f6e464c2fd595b1176ad70f597cbc0300cd9329644ad0bc6b
  - scripts/nf.py:97aadeb530bd78fd9cc206ed96d45eab75a61e7f3167fefcb0bc774536cb6257
  - verify.sh:5567d1139ec88b355884403a70ba8d4b73b584c78bd3245ad4a14c18e8e29b95
  - docs/layers.md:be79f2699cee390f03d54d6d0428daee6964674dcbb5d0e6967bfbb150395450
  - docs/L3_FROZEN.md:9dad824e749aac75ee4cf583adb48d0ede9c02a0a717ff43d314cbbfcb3cf3af
  - protocol/assertions.json:c706b8b3b136fccfc6f50e957d25c87327611532db66e85259ed7bead4bee016
  - protocol/data_contracts.json:d6fbdd2e886a5295728dcbb5c48a14e543d1b5fc64eacd20b8a3af7120404990
  - protocol/normative.json:c1bbc14c92cea6bd66ff6cb54fdcf91bf3072f66adee7027f1d3f42e70fe1825
  - protocol/glossary.json:4561ddb5a221f8fc5beca4cfcca07580b3ea4dd403eb23434549a8eaa8409a60
  - desktop/src/core/receipts.py:1c7cc5069aaa48b5804f0efd2f4bdd522166a3c070a549506789b6e292d499be
  - desktop/src/core/doc_hygiene.py:5cc5d9d0fe0bea3f609d26759ac497aeb92363b0c6b045c1ca6cd67687bae850
  - decisions/ADR-0004-抽象阶梯两轴与纵切.md:3b6c3e41b67b3b7684125160e8cdd16ad84b1a1808f2ef584246af2075d06196

---
> 重审（2026-10-14）：预推收口二：CoT 自述改口径 + 快路径末尾 ** 语义对齐 pathlib（实测 66217 vs 0）

> 重审（2026-10-14）：引入 nf audit rebind 命令（core/audit.py + CLI + 顺序纪律 + 两处面收敛）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI）：重审并更新 digest 口径机器化，替换手搓脚本

> 重审（2026-10-14 · 数字资产契约 S 档续）：被审对象随本波改动（protocol/normative.json 并入可移植 schema / CONFORMANCE.md IDL 集 8→9），subjects 依「重审并更新 digest」机械重绑；既有结论不变。

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / core/layer_model.py 由 nf layers --write 联动刷新职能投影 / code_metrics 基线重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。

> 重审（2026-10-14 · ADR-0006 L11 职能坐标）：被审对象随本波改动（protocol/LAYERS.json 增 roles 段 / desktop/src/core/layer_model.py 接 L11 / docs/layers.md 生成区刷新 / protocol/code_metrics_baseline.json 按工具指引重冻），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · ADR-0006 取代 ADR-0004 边界条款）：被审对象 `decisions/ADR-0004` 的 frontmatter 随取代链变为 `status: superseded` / `superseded_by: ADR-0006`（正文逐字节未动），subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计，既有结论不变。

> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-13 · 核心语义通用化）：被审对象 verify.sh 随本波改动（check4/check5 判据键集由「认知/白描」泛化为「可见性/profile」），subjects 依「重审并更新 digest」处置；本轮为**机械重绑**，不主张新的语义审计，既有结论不变。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物：`protocol/RECEIPTS.json`、`protocol/conformance_report.json`、
> `protocol/generated/*`、`results/interop/*`、`decisions/INDEX.md` 均为可复算投影或每次重签即变，
> 按既有口径不入审计绑定（分别由 check35 / check31 / check33 / check36 自证）。

## 一、内部差距（开工依据）

1. **分层是文档不是架构**：L3 端壳退役前**零判据**——一个「阶」可以整体消失而无任何 check 察觉，
   能力重分派只能事后靠 check39 兜住。阶梯若无适应度函数，必然复现同类事故。
2. **角色与物混装**：此前「终端执行层 / 协议层 / 资产层 / AI 装配」把**谁在动**与**被加工的物**
   放进同一根梯子，于是出现「终端在最底、AI 在顶」的错位（本轮对话实证）。
3. **阶之间没有接口面**：`protocol/module_signatures.json` 已冻结 248 个**模块**边界，但
   「契约/资产/引擎/出口」之间没有接口面声明——改实现与改接口无法区分。
4. **文档必然漂移**：验证卡册实测漂移（卡数 37/38/39、行数 1797/2409，生成器未随仓库分发）——
   分层表若手写，会以同样方式腐烂。
5. **退役无规程**：L3 退役是临时动作（临场分派 + 事后补判据），没有「能力重分派 → 入口补齐 →
   判据改判 + 记录」的可复用流程。

## 二、交付

| 面 | 落点 |
|---|---|
| 真源 | `protocol/LAYERS.json`（nf-layers/1）：四阶 ×（真源面/接口面/实现面/变更档/judged_by/status）+ 资产五子级 + 入口面 + 验证纵切 + derived 豁免名单 + 退役规程 |
| 语义判据 | `desktop/src/core/layer_model.py` 的 L1–L10（真源在位 / 归属互斥 / 接口子集 / 依赖向下无环 / 入口非真源 / 引擎不反向 import 入口 / 退役阶不被依赖 / 判据可解析 / 豁免诚实 / 生成区==实时渲染） |
| 门禁接线 | 纯度体检 check27 新增 **R7**（把阶梯 issues 汇入既有纯度报告）——**不新增 check 序号**（ADR-0002），基线仍 v2.29 · check1-39 · PASS=68 |
| 形状类断言 | `protocol/assertions.json` 增 3 条（layers-declaration-in-place / layers-generated-region / layers-no-abs-path），11 → 14 条（kind 仍封闭四类，ADR-0003） |
| 生成投影 | `docs/layers.md` 阶梯表进 `nf:layers` 生成区，`nf layers --write` 渲染（L10 断言逐字一致） |
| CLI | `nf layers` / `--json` / `--verify` / `--write` |
| 决策 | `decisions/ADR-0004-抽象阶梯两轴与纵切.md`（accepted，已入回执锚定），`decisions/INDEX.md` 重投影 |
| 术语 | `protocol/glossary.json` 增 **抽象阶梯**、**验证纵切**（逐字命中真源与使用面） |
| 登记 | `protocol/normative.json` 收 LAYERS.json；`protocol/data_contracts.json` 29 → 30 件（quality_rule=check27）；`protocol/RECEIPTS.json` 49 → 51 件（+LAYERS.json +ADR-0004） |
| 单元测试 | `test_layer_model.py` 21 例（L1–L10 各一变异样本 + 真仓库零 issue + 渲染幂等 + LF 落盘 + CLI 面）；`test_purity_scan.py` 增 R7 接线与「无阶梯件不误伤」2 例 |

## 三、验收证据（本机实测）

- `bash verify.sh` → **PASS=68 · WARN=0 · FAIL=0**，`check` 数仍为 **39**（证明「并入不涨号」）。
- `nf layers --verify` → 通过（阶 4 · 资产子级 5 · 入口面 4 · 纵切件 6 · 规则 10）。
- 真实面规模（防空面假绿）：契约 52 件 · 资产 2218 件 · 引擎 255 件 · 出口 26 件；派生物豁免 9 件。
- `nf conformance` → **conformant 27/27**；`nf decisions verify` → 4 条 accepted 全一致；
  `nf receipts` → 51 件根一致；`nf approve --verify` 有效；`nf interop --check` 逐字节一致；
  `nf stats --check` 一致；`purity_scan` 0 issue；`text_hygiene` 0 issue。
- 变异捕获力：L1–L10 每条规则各有一个违规样本被单测钉住（含「接口面超出真源面」「退役阶被依赖」
  「生成区被手改」三类最容易漏的形态）。

## 四、遗留与设计偏差

1. **阶归属判据是有界的**：只判阶梯自己声明的真源面，不给全树逐文件贴标签——全树归属是另一个量级的
   承诺，未纳入本波（避免造没人消费的重台账）。
2. **未新增违规基线台账**：阶梯是新增面、无存量违规；个别例外如需挂账，复用纯度体检既有的
   `IMPORT_RESIDUE` 机制（按需装配：不产无消费者的件）。
3. **旧审计摘要重绑**：本波改动触及既有审计的被审对象，按仓库既有实践（commit `ba1cb08`）
   重绑 digest 使审计面自洽——**每轮改动后重绑一次**（含修 `nf` 的 stderr 编码缺陷、以及
   check27/卡册的描述面补齐），三轮共 **63 条 subject 记录**；重绑只校准摘要、不重写旧结论，
   本波实际改动面由本件承担记录责任。
4. **本轮不做**：`desktop/` 目录去端壳化改名（独立一波需作者立项）；`docs/L3_FROZEN.md` 退役事实改写
   （只加互链，不改写历史）；给阶梯开独立 check 序号（遵 ADR-0002）。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑ | L1–L10 十条语义判据 + 3 条形状类断言 + 21 例单测变异覆盖；基线不涨号仍全绿 |
| 动态可执行 | ↑ | `nf layers --verify` 与 check27 同源可复跑；生成区由真源渲染，手改即红 |
| 架构纯度 | ↑↑ | 角色与物分离、跨阶只依接口面、依赖向下无环、入口非真源——纯度为第一次有「阶」维度 |
| 资产密度 | → | 不新增内容资产（本波是架构面） |
| 文档可执行性 | ↑ | `docs/layers.md` 读到即能跑；阶梯表为投影，双语入口与四型清单同步登记 |
