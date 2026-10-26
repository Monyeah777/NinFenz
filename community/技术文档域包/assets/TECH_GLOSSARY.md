<!-- nf-asset: key="TECH_GLOSSARY" version="1.0" status="active" -->
# 资产键 TECH_GLOSSARY · 技术文档术语表

> 资产键：`TECH_GLOSSARY`｜消费方：M97 术语管理（登记/补定义/冲突检测）、`gate_profiles/techdoc-strict.json`（术语首用 / 别名一致性判据）｜寻址：`asset_get("TECH_GLOSSARY","API")`、`asset_query("TECH_GLOSSARY")`（I4 五接口，禁止直读）。
> 形态：人读表（§2）+ 机器可读列（术语/定义/别名/首用章节六列同源）——本件是术语唯一真源，正文用词以「术语」列为准。

## 1. 使用纪律

- 一个概念一个规范术语；「别名」列只作检索等价，**正文一律用规范术语**（同一产物内规范术语与别名不得并存，GB/T 19678.1 术语一致性）。
- 术语在正文**首次使用处**必须是已定义状态：先出现于本文档 §2 术语表章节，或就地括注定义；M97 以 `term_synced` 发布收敛结果，M80 门消费该事件。
- 新增术语先改本表再写正文；定义只写「是什么」，不写实现细节（实现细节归设计文档）。
- 缩写类术语（API/SLA/RMA/ESD/PCB/MTBF）首次出现给全称，或由 profile 的 `allowed_acronyms` 词表放行。

## 2. 术语表（机器可读列：术语 | 定义 | 别名 | 首用章节）

| 术语 | 定义 | 别名 | 首用章节 |
|---|---|---|---|
| 设备 | 本手册描述的单机产品 | 装置 | 全文 |
| API | 应用程序接口（Application Programming Interface）：设备对外提供的可编程调用约定 | 接口 | 接口说明 |
| SLA | 服务等级协议（Service Level Agreement）：对可用性与响应时限的承诺 | 服务等级 | 服务承诺 |
| RMA | 返修授权（Return Merchandise Authorization）：故障件返厂的授权编号 | 返修号 | 售后服务 |
| ESD | 静电放电（Electrostatic Discharge）：静电对电子器件的损伤现象 | 静电放电现象 | 安全须知 |
| PCB | 印制电路板（Printed Circuit Board）：器件贴装的基板 | 电路板 | 规格参数 |
| MTBF | 平均无故障时间（Mean Time Between Failures）：可靠性统计指标 | 无故障时间 | 规格参数 |
| 固件 | 设备内置的可升级控制程序及其版本号 | firmware | 升级说明 |
| 校准 | 用标准器具比对并修正设备读数的作业 | 标定 | 维护保养 |
| 老化 | 出厂前连续通电以筛除早期失效的工序 | 煲机 | 出厂检验 |
| 开箱 | 从包装中取出设备并核对随机附件的步骤集合 | 拆箱 | 开箱验收 |
| 变更单 | 记录一次设计/工艺变更及其影响范围的受控单据 | 变更记录单 | 修订记录 |
| 修订记录 | 文档每次发布所对应的版本、日期与变更摘要 | 版本历史 | 修订记录 |

## 3. 术语状态口径（M97 `term_synced` 数据面）

- `ok`：全部术语有定义、无同名多定义、正文用词与规范术语一致——方可放行渲染。
- `pending_definition`：存在已使用但未定义的术语——M80 门 fail，先补定义。
- `conflict`：同一术语出现多定义或规范术语与别名并存——M80 门 fail，先消解冲突。
- 回执字段：`{delta[], status[], count}`（protocol/event_registry.json 在册）；术语条目形状 `{term, first_use_chapter, definition, status}`。

## 4. 与其他资产的关系

- 章节模板（`TECH_TEMPLATE_*`）引用本表术语，不另造同义词；风格规则（`TECH_STYLE_RULES`）规定缩写首用写法；标准锚点（`STANDARDS_ANCHORS`）给出术语条款的出处。
- 术语表变更属包内容版本变更：同步修订 `package.version` 与本表 §2，不静默改词。
