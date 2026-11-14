# protocol/ · 协议层 IDL（43 协议层顶尖化 A1）

> **定位**：把协议层契约字段从「正文 yaml 示例 + 各 parse 自行半解析」升为**正式 schema 定义（IDL 单一真相）**——契约「长什么样、哪些必填、值域如何」由一个可机检的定义文件说了算；正文示例/机读块/投影均由校验器按 schema 验收。
> **红线**：零第三方 JSON-schema 实现——校验器为自实现 JSON-schema 子集（见 `desktop/src/core/schema_lint.py`），不引 `jsonschema`；YAML 解析复用仓库既有 PyYAML 依赖（verify check16 已用）。**子集边界显式化**：schema 定义若使用白名单外关键字（oneOf/$ref/patternProperties/format…）即 check28 FAIL——校验器不自欺；标准实现交叉对照见 `desktop/tests/test_schema_reference.py`（可选依赖，装了才跑）。
> **元工具定位**：本层验收对象 = IDL/门禁/生成物/一致性机制自身的正确性；存量域包内容缺机读块（L0 过渡态）由 check16 过渡策略承接，不计入元工具质量缺口。
> **承接**：43 A1（IDL schema，`schema/`）/ A2（Conformance 分级，`export_conformance.json` + 01 §1.2）/ A3（扩展策略 + 影响分层，`EXTENSION.md`）/ A4（生成物同仓 golden，`generated/`）。四个里程碑的产物均已随 check28-31 常驻。
>
> **复核（2026-11-14）**：IDL 单一真相、子集边界与四道 check 接线**复核不变**；本轮**修三处陈旧钉数**（「五份契约定义」实为 9 份 schema 中 5 份内容契约；「44 个模块 / 现行 23/44」实为 248 份模块文档、13 份在场机读块；「8 条管线 / 5 份 protocol.yaml」实为 114 / 111），改为「以 `schema_lint.LINT_INPUTS` 实读为准」并补「§现状对照」「§复现与引用口径」。

## schema/ · 九份 IDL 定义（本层机器真相；其中五份是内容契约定义）

| schema 文件 | 校验对象 | 真相形态 |
|---|---|---|
| `contract.schema.json` | 模块头 `machine_contract` 机读块（01 §1.1 九键 + 可选 `tool_face` / `world_model`） | 04_模块库 + community/*/modules 模块文档内的 yaml 围栏 |
| `module.schema.json` | 注册表模块条目 | `desktop/src/core/registry.json` `modules[]`（02 §2 投影） |
| `pipeline.schema.json` | 管线声明 `Pipeline` | 03_管线库 + community/*/pipelines 管线文档内的 yaml 围栏 |
| `protocol.schema.json` | 社区包协议声明 `protocol.yaml` | community/*/protocol.yaml（01 §6.1） |
| `asset.schema.json` | 资产台账条目 | `05_资产库/provenance.json` `assets[]`（05 README 机读台账） |

> 每份 schema 均为 JSON object；顶层含 `$schema` / `$id` / `title` / `type: "object"` / `required[]` / `properties{}`。字段级新增须同步 schema（V1 只增不删）；结构性改契约定义须走 01 §7 V2 bump + 迁移记录（见 43 A3 EXTENSION.md）。


**其余四份**（非内容契约）：`asset_contracts.schema.json`（资产契约）· `integration.schema.json` / `integration_strings.schema.json`（接入面）· `release.schema.json`（发布策略）——同受 check28 的子集白名单约束。

可选纵深字段的独立语义规范：`WORLD_MODEL.md`（确定性抽象状态契约，check32 硬门）；`world_slots.json`（M00 数据槽可绑定投影，由 `desktop/src/core/world_slots.py` 机检）；`tool_face` 由 `desktop/src/core/tool_face.py` 轻量校验。

## 扫描口径（A1 验收）

- **扫描面 = `core/schema_lint.LINT_INPUTS` 的 9 条通配**（模块文档 / 管线文档 / `community/*/protocol.yaml` / 资产件 / `registry.json` 等）：**在场 machine_contract 即校验**；存量旧格式模块（无机读块）按 check16 过渡策略不阻断，缺块计数见统计行。**具体件数以 `LINT_INPUTS` 实读为准，本文不钉**（2026-11-14 实读：模块 248 · 管线 114 · protocol.yaml 111 · 资产 md 363）。
- 上述扫描面全量过 schema（管线文档、community `protocol.yaml`、`05_资产库/provenance.json` 台账条目都在内）。
- 任一漂移（字段类型/必填缺失/枚举越界/编号格式错位）即 check28 FAIL。

## 新增一个契约件

1. 在对应文档维护真实 yaml/机读块（人读真相不变）。
2. schema 缺字段类型/值域 → 补 `properties` 或收窄 `enum/pattern`（字段级新增，不改名删义）。
3. 结构性改义 → 01 §7 V2 bump + 迁移记录 + schema 同步，verify 全绿方可提交。

## 现状对照（2026-11-14 · 以 schema_lint / verify.sh 实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| schema 件数 | **9**（5 内容契约 + 4 其它面） | `ls protocol/schema/*.json` |
| 子集白名单 | **16** 个关键字：`$id` `$schema` `additionalProperties` `description` `enum` `items` `maxItems` `minItems` `minLength` `minimum` `pattern` `properties` `propertyNames` `required` `title` `type` | `schema_lint.SUBSET_ALLOWED_KEYS` |
| 扫描面 | **9** 条通配（`schema_lint.LINT_INPUTS`） | 该常量实读 |
| 门禁接线 | **check28**（schema 校验）· **check29**（Conformance 分级）· **check30**（bump 迁移）· **check31**（生成物 golden） | `verify.sh` + `nf verify --only 28` |
| 交叉对照 | `desktop/tests/test_schema_reference.py`（可选依赖 `jsonschema`，装了才跑） | 该测试 |

**不钉件数**：模块/管线/protocol.yaml/资产件数随内容演进；本文只固化「扫描面 = LINT_INPUTS」「白名单 16」「四道 check 接线」这些**结构事实**。

## 复现与引用口径

```bash
python scripts/nf.py verify --only 28                        # 单跑 schema 校验（子集白名单越界即 FAIL）
python -c "import sys;sys.path.insert(0,'desktop/src');from core import schema_lint as s;print(len(s.SUBSET_ALLOWED_KEYS), s.LINT_INPUTS)"
python -m pytest desktop/tests/test_schema_reference.py -q    # 与标准实现交叉对照（需 jsonschema）
```

- 引用本层时：「IDL 单一真相 + 自实现子集（不引第三方）」是长期口径；schema 用了白名单外关键字 = check28 FAIL，不是「换个写法也行」。

## trust 层 IDL（独立面）

Trust Fabric 的 7 份 schema 在 `protocol/trust/*.schema.json`：entity / dsse / process / claim-bundle / anchor / policy / verify。

- **与 `protocol/schema/` 刻意分开**：后者是内容契约/协议投影面的 IDL，由自实现子集校验器（check28）守；trust 层用 draft 2020-12 的完整关键字（`$defs` / `oneOf` / `const` / `uniqueItems`），由 `core.json_schema` 叶子校验器判定。两套校验器面不同，件数不混算。
- 判据：`python -m pytest desktop/tests/test_trust_schemas.py -q`（7 件 schema + 正/反样例 + 变异自证 + 标准实现对照）。
- trust 层 schema **不计入**本目录的 schema 件数与 `LINT_INPUTS` 扫描面；后两者仍以实读为准。

