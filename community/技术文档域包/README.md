# 技术文档域包（community 非叙事题材域包 · 技术文档题材装配流）

> 定位：**社区非叙事题材域包**（v2.1.0-C-b 战例落盘，T4.1 起升为第一个 **L2 参考域**），独占「技术文档」类（01 §6 R2 / 02 §8.5 第三方协议登记）。在官方 M90 技术文档结构（P90 链官方模块，core 依赖）之上**增强两域机制**——P40 术语管理（M97）/ P60 修订记录（M98）——经本包自带 **P06 管线**装载（R3 装配契约）。
> 协议声明：包根 `protocol.yaml`（01 §6.1 Schema，schema_version "2"，references 空列表）为**机读真相**，本 README 为**人读速览**，双源一致（check14 ⑥ / check15 ⑤）；登记三要件见 02 §8.3。
> 结构：modules/（2 技术文档模块 M97/M98，M91-M99 社区预留段在册 2 件）｜assets/（**9 内容资产**：术语表 + 六类章节模板 + 风格规则 + 标准锚点）｜gate_profiles/（严格质量门 profile，25 条标准条款映射）｜pipelines/P06_技术文档题材装配流管线.md
> 依赖边界（R1）：只依赖官方核心层（M00 / M80 / M90 等 13 件 core_modules，core_only true）；**不搬移** M90 官方模块入包 default/available 槽（I5 单一真相源）。

## 1. 包速览

| 项 | 值 |
| --- | --- |
| 管线 | **P06** 技术文档题材装配流（九层线性回卷，装配自官方 P00 通用骨架，题材派生 P90 链） |
| 自带模块（本包） | 2：M97 术语管理（P40 行为决策位） / M98 修订记录（P60 长期演变位） |
| 官方核心配合件 | 13：M00 / M80 / M90 等（含 M90 技术文档结构——本包题材底层） |
| 资产 | **9 文件**（术语表 1 + 章节模板 6 + 风格规则 1 + 标准锚点 1；经资产五接口寻址） |
| 质量门 | M80 结构门 6 条（含术语一致/无越层直写）＋ `gate_profiles/techdoc-strict.json` 严格 profile（25 clause） |
| references 引用 | 0（无跨包引用） |
| 主轴 | 技术文档题材流：M90 结构骨架 → M97 术语统一（P40）→ M98 修订追踪（P60）→ M80 质检渲染（P80） |
| L2 执行记录 | `nf assemble --build` → `out/*.md` → `nf assemble --check`（check_rc=0，见 protocol.yaml `package.outputs`） |

## 2. 模块装载清单（按层，15 = 核心 13 + 自带 2）

> 与 pipelines/P06_技术文档题材装配流管线.md 的 layers（default 列）严格一致。

| 层 | 挂载（default） | 模块职责 | 归属 |
| --- | --- | --- | --- |
| P00 数据基座 | M00、M90 | M00 数据槽/存档装载 + M90 结构骨架装载（DocState 产） | 核心 |
| P40 行为决策 | **M97** | 术语管理：DocState.terms 登记/补定义/冲突检测（term_synced） | 本包 |
| P60 长期演变 | **M98** | 修订记录：DocState.revision 版本递增/变更日志/回溯（revision_recorded） | 本包 |
| P80 输出呈现 | M80 | 官方输出门质检渲染（结构门 6 条，消费 term_synced/revision_recorded 与 profile） | 核心 |

## 3. 资产清单（9 文件，键 → 文件 → 用途）

| 资产键 | 文件 | 用途 |
| --- | --- | --- |
| `TECH_GLOSSARY` | assets/TECH_GLOSSARY.md | 术语表：术语/定义/别名/首用章节（M97 术语一致判据的数据源） |
| `TECH_TEMPLATE_SAFETY` | assets/TECH_TEMPLATE_SAFETY.md | 章节模板·安全（GB/T 19678.1 安全信息分级） |
| `TECH_TEMPLATE_UNBOXING` | assets/TECH_TEMPLATE_UNBOXING.md | 章节模板·开箱（到货验收 + 随机附件清单） |
| `TECH_TEMPLATE_INSTALLATION` | assets/TECH_TEMPLATE_INSTALLATION.md | 章节模板·安装（安装条件/步骤/验收） |
| `TECH_TEMPLATE_OPERATION` | assets/TECH_TEMPLATE_OPERATION.md | 章节模板·操作（启停/参数/例行检查） |
| `TECH_TEMPLATE_TROUBLESHOOTING` | assets/TECH_TEMPLATE_TROUBLESHOOTING.md | 章节模板·故障（症状/原因/处置三段式） |
| `TECH_TEMPLATE_SPECIFICATION` | assets/TECH_TEMPLATE_SPECIFICATION.md | 章节模板·规格（可测参数 + 规格变更记录） |
| `TECH_STYLE_RULES` | assets/TECH_STYLE_RULES.md | 风格规则 S1–S10（标题/标点/空格/缩写/弱表达/表格） |
| `STANDARDS_ANCHORS` | assets/STANDARDS_ANCHORS.md | 标准锚点（DITA 1.3 元素映射 / GB/T 19678.1 主题 / MS Style 条目） |

- 全部资产经 `asset_get` / `asset_query` 五接口访问（I4 禁止直读）；键表与 `protocol.yaml` 的 `assets.count: 9` 双源一致（check14 ⑥ 断言）。

## 4. 质量门（M80 双门 · profile 软门）

- **结构门（硬）**：编号合法 / 引用可寻址 / 结构完整 / **术语一致（消费 M97 term_synced）** / **无越层直写（M23 可见性前置）**——实现于 `desktop/src/core/quality_gate.py` 的 `default_rules()`（6 条，fail 级）。
- **质量门（软 · profile）**：`gate_profiles/techdoc-strict.json`，25 条 clause（DITA 1.3 / GB/T 19678.1-2018 / Microsoft Style Guide）。逐条报告入口：
  `python desktop/src/core/gate_profile.py --profile community/技术文档域包/gate_profiles/techdoc-strict.json --text <产物.md>`
- 5 条确定性文本规则（标题句式 / 标题末尾标点 / 单空格 / 缩写首用 / 弱表达）**仅经 profile 启用**；未装 profile 的叙事流默认行为不变（协议层不内嵌条目）。

## 5. L2 执行记录（可复现证据）

| 字段 | 值 |
| --- | --- |
| executor | `python scripts/nf.py assemble "写一份技术文档，要术语表和修订记录" --build --dest out` |
| date | 2026-10-26 |
| artifact | `out/*.md`（引用式八段完整版；同输入同输出，可重建） |
| check_rc | 0（`nf assemble --check` PASS：八段骨架 + 编号允许集 + 决策引用） |

## 6. 战例意义（C 线内容库资产化）

本包是 community 第 5 包、第一个非叙事题材域包——ROADMAP C 线「techdoc 域 = 新领域三步自然延伸」的完整落盘：①自带 M91-99 社区段题材模块（M97/M98）②派生管线（P06）③02 §8.5 登记 + registry protocols[] 第 5 条（经 nf register 工具链实战，30 方案）。T4.1 起补齐 9 项资产、M80 结构门 2 项实现与 25 条标准 profile，成为**第一个真正的 L2 参考域**（非叙事纵深战例）。verify.sh check14/check15 glob 遍历层自动纳入（4→5 包，PASS 24→25）。
