# protocol/ · 协议层 IDL（43 协议层顶尖化 A1）

> **定位**：把协议层契约字段从「正文 yaml 示例 + 各 parse 自行半解析」升为**正式 schema 定义（IDL 单一真相）**——契约「长什么样、哪些必填、值域如何」由一个可机检的定义文件说了算；正文示例/机读块/投影均由校验器按 schema 验收。
> **红线**：零第三方 JSON-schema 实现——校验器为自实现 JSON-schema 子集（见 `desktop/src/core/schema_lint.py`），不引 `jsonschema`；YAML 解析复用仓库既有 PyYAML 依赖（verify check16 已用）。**子集边界显式化**：schema 定义若使用白名单外关键字（oneOf/$ref/patternProperties/format…）即 check28 FAIL——校验器不自欺；标准实现交叉对照见 `desktop/tests/test_schema_reference.py`（可选依赖，装了才跑）。
> **元工具定位**：本层验收对象 = IDL/门禁/生成物/一致性机制自身的正确性；存量域包内容缺机读块（L0 过渡态）由 check16 过渡策略承接，不计入元工具质量缺口。
> **承接**：43 A1（IDL schema，`schema/`）/ A2（Conformance 分级，`export_conformance.json` + 01 §1.2）/ A3（扩展策略 + 影响分层，`EXTENSION.md`）/ A4（生成物同仓 golden，`generated/`）。四个里程碑的产物均已随 check28-31 常驻。

## schema/ · 契约定义（本层机器真相）

| schema 文件 | 校验对象 | 真相形态 |
|---|---|---|
| `contract.schema.json` | 模块头 `machine_contract` 机读块（01 §1.1 九键 + 可选 `tool_face` / `world_model`） | 04_模块库 + community/*/modules 模块文档内的 yaml 围栏 |
| `module.schema.json` | 注册表模块条目 | `desktop/src/core/registry.json` `modules[]`（02 §2 投影） |
| `pipeline.schema.json` | 管线声明 `Pipeline` | 03_管线库 + community/*/pipelines 管线文档内的 yaml 围栏 |
| `protocol.schema.json` | 社区包协议声明 `protocol.yaml` | community/*/protocol.yaml（01 §6.1） |
| `asset.schema.json` | 资产台账条目 | `05_资产库/provenance.json` `assets[]`（05 README 机读台账） |

> 每份 schema 均为 JSON object；顶层含 `$schema` / `$id` / `title` / `type: "object"` / `required[]` / `properties{}`。字段级新增须同步 schema（V1 只增不删）；结构性改契约定义须走 01 §7 V2 bump + 迁移记录（见 43 A3 EXTENSION.md）。

可选纵深字段的独立语义规范：`WORLD_MODEL.md`（确定性抽象状态契约，check32 硬门）；`world_slots.json`（M00 数据槽可绑定投影，由 `desktop/src/core/world_slots.py` 机检）；`tool_face` 由 `desktop/src/core/tool_face.py` 轻量校验。

## 扫描口径（A1 验收）

- **248 个模块文档**（`04_模块库` 13 + `community/*/modules` 235）全量纳入扫描：**在场 `machine_contract` 即校验**（现行 **248/248**；另有 3 件非模块文档含机读块，全仓合计 251）。存量旧格式模块（无机读块）按 check16 过渡策略不阻断，缺块计数见统计行。*（A1 验收时点为 44 件 / 23 有块；历史值见 CHANGELOG。）*
- **114 条管线文档**（`03_管线库` 3 + `community/*/pipelines` 111）、**111 份** community `protocol.yaml`、`05_资产库/provenance.json` 台账（3 条机制资产）全量过 schema。*（A1 时点为 8 条管线 / 5 份协议包。）*
- `protocol/schema/` 现有 **9 份** IDL：上表 5 份契约定义之外，另有 `integration` / `integration_strings` / `release` / `asset_contracts` 四份（分别在 A1 之后随接入面、发布编排、数字资产契约层加入）。
- 任一漂移（字段类型/必填缺失/枚举越界/编号格式错位）即 check28 FAIL。

## 新增一个契约件

1. 在对应文档维护真实 yaml/机读块（人读真相不变）。
2. schema 缺字段类型/值域 → 补 `properties` 或收窄 `enum/pattern`（字段级新增，不改名删义）。
3. 结构性改义 → 01 §7 V2 bump + 迁移记录 + schema 同步，verify 全绿方可提交。
