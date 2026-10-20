# 05_资产库（Asset Library）
>
> 宁封子 NinFenz — 资产数据层（两级结构版；版本随仓库版本块）
> 定位：**机制资产槽 + 资产寻址索引**。核心仓库只读数据层——域包资产随各域包分发到 community/<域包>/assets/；本目录只保留用户自定义扩增槽与机制资产索引。
> 逻辑（判断、结算、管线）一律在 03_管线库 / 04_模块库 / 域包管线中实现；本层**只提供数据与扩增入口，不含行为**。
---

## 1. 资产归属总览（两级结构）

| 归属 | 位置 | 内容 |
| --- | --- | --- |
| 官方核心机制资产 | 05_资产库/用户自定义/ | M80 输出 profile（STYLE_DNA）、M90 模板/规则（TECH_TEMPLATES / TECH_RULES）——域中立机制资产，台账见 provenance.json |
| 域包内容资产 | community/<域包>/assets/ | 各域包自带（键清单 / 溯源自各包 assets/README.md），核心不复制副本 |

## 2. 目录结构

```
05_资产库/
├── README.md            ← 本文件（总索引 / 扩增协议）
├── provenance.json      ← 机制资产供应链台账（机读真相）
└── 用户自定义/           ← 扩展槽（900+ 命名空间，见 §5 扩增协议）
    ├── README.md        ← 登记记录 / 资产键清单 / schema
    ├── STYLE_DNA.md
    ├── TECH_RULES.md
    └── TECH_TEMPLATES.md
```

> 域包资产（各域内容）整体随域包分发到 community/<域包>/assets/。**本目录不再保有域内容资产副本**；运行期寻址一律经包内 assets/README.md 键表 + asset_get 五接口。
>
## 3. 运行期访问接口（真源 = 01_核心协议.md §3）

本层文件为**静态数据源**；运行期统一经五类访问接口读取，禁止模块直读散文件：

| 接口 | 用途 | 示例 |
| ------ | ------ | ---------- |
| asset_get(key, id) | 按资产键 + 条目 ID 精确取单条 | asset_get('TECH_RULES','R901') |
| asset_query(key, 条件) | 按条件（tags / 类型 / 时段…）查询条目集 | asset_query(key, type=…) |
| asset_match(key, 输入特征) | 相似度匹配 | asset_match(key, features) |
| asset_roll(key, 权重表) | 按权重随机抽取 | asset_roll(key) |
| asset_register(key, 新条目) | 用户自定义条目注册（进 用户自定义包） | 见 §5 扩增协议 |

> 接口详细约定见 01_核心协议.md §3（本仓真源）；源框架「五类统一访问接口」为数据出处。
>
## 4. 资产溯源

- 机制资产（本库）：溯源键表 + version/status 位见 provenance.json（`nf asset add` 建档维护，verify check23 自证）。
- 域包内容资产：源文件/行区间/schema 以各域包 assets/README.md 为唯一真相；本库不做第二份溯源。

## 5. 扩增协议（新增资产 → 用户自定义包）

1. **唯一 ID**：沿用资产键前缀 + 序号，后缀区 900+（官方 001-899，自定义 900+），如 T901。
2. **键词表在册 + schema 必填**：键须在 protocol/asset_keys.json 词表在册；新增条目须满足对应资产键的 required_fields 与 field_types（键表与 schema 见 用户自定义/README.md 与各域包 assets/README.md）。
3. **注册登记**：经 asset_register 登记后写入 05_资产库/用户自定义/，禁止改写官方与域包资产。
4. **三原则**：不覆盖官方条目 / 不污染官方命名空间 / 可追溯（注明创建时间与用途）。
5. **机器台账（40 总纲 v2.7 波A S2）**：本库资产供应链托管于根目录 provenance.json（溯源键表 + version/status 位，`nf asset add` 自动建档维护，verify check23 闭合自证）；官方作者侧机制资产（用户自定义/ STYLE_DNA / TECH_RULES / TECH_TEMPLATES）为首批入库战例（tier=official）。
6. **单层货架不变量（2026-09-20 作者裁决收口）**：资产货架（各域包 assets/ 与本库 用户自定义/）为**单层**——密度体检 / 键表投影 / 行数基线三面均以非递归 glob 取件，子目录里的资产会「台账可见、三面不可见」（静默丢口径）。故 `nf asset verify` 与 verify check23 断言**货架不得含子目录**；需要分组请用**键表**与「一包多文件」表达，不要建子目录。

## 6. 模块-资产引用映射（核准结论）

- 官方核心机制模块：M80 消费 STYLE_DNA（输出 profile）；M90 消费 TECH_TEMPLATES / TECH_RULES（结构模板与规范校验）——均经五接口寻址。
- M00 数据结构自洽无外部资产引用；其余核心模块不依赖散文件，资产引用落在各域包键表内。
- 运行期一律经五类接口读取，禁止模块直读散文件（含域包内资产）。

---
*机制资产由作者侧维护；域内容资产由各域包按行区间切片生成（保真、可溯源），迁移过程零语义改写。*
