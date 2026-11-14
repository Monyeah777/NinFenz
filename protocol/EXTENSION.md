# protocol/EXTENSION.md · 协议扩展策略与变更影响分层（43 A3）

> **定位**：明确协议「什么算字段级新增、什么必须结构 bump」，并把 `nf diff` 的判定从兼容性一维升为「兼容判定 + 影响度三档」。任何对 01/02/03/04/05/06/07/registry/machine_contract/schema 定义的变更，先查本表定影响度，再按对应流程走。
> **版本红线**：registry_schema_version / protocol.schema_version / machine_contract.schema 独立演进（01 §7 V3）；字段级新增不 bump（V1 只增不删）；结构性变更必须 bump + 迁移记录（V2）。
>
> **复核（2026-11-14）**：三档判据、派生三问、域包装卸不变量与回放样本**复核不变**；本轮补「§现状对照」「§复现与引用口径」——把「三档各自处理、check30/check13 怎么接线、哪些数字不许钉」写清。

## 判据表

### 派生三问（字段级新增与专门化的准入判据）

任何「从既有定义派生出新类型/新键」的变更（additive 与 bump 都适用），必须先答三问：
1. **基类是什么**——派生自哪个在册定义（模块契约键 / schema / 协议件编号），基类必须**在册**且可解析；
2. **新增面是什么**——只增不删、不改义（V1 红线）；新增键/枚举值必须同步进 schema 定义；
3. **旧消费方可读性**——缺该键的旧消费方必须能**忽略而不歧义**（可忽略新增，不得改变既有字段语义）。

三问齐 → 可派生；任一答不出 → 不派生（留在散文或候选层，不写进契约）。

| 影响度 | 判定 | 示例 | 处理 |
|---|---|---|---|
| editorial | 纯措辞/注释/说明/值域注解性文字；无任何机器字段增删改义 | 错误信息文案、注释补全、描述语改写 | 走既有文档纪律；不涉版本字段；`nf diff` 仅 editorial |
| additive | 字段级新增：新可选/必填字段、枚举值域新增、键新增（不删不改既有名） | 43 A1 把 `techdoc` 加进管线 type 值域；43 A2 给 machine_contract/协议包加 `conformance` 位 | schema 定义同步补 `properties`；V1 只增不删；**不 bump** registry/protocol 版本；迁移记录可选（复杂新增建议留档） |
| bump | 结构性：字段删除/改义/重排、实体拆分合并、引用语义/装配语义变化、版本槽位升级 | registry_schema_version v1→v2（02 §9.3 首例）；protocol.schema_version v1→v2（references 引入） | 必须 bump 相应版本字段 + 按 01 §7 迁移实操四步留档（现状快照/bump 声明/迁移说明/校验回读）；check30 拦截无迁移记录的 bump diff |

### 域包装卸不变量（机制层零依赖域包）

> 本条把「域中立」从定位语落地为**可执行的装卸不变量**——此前它只存在于 `verify.sh` 的注释与散落表述中，未作为判据声明。

**判据**：移除任一社区领域包后，段 A（官方核心）与段 C（代码层）的门禁结论应保持成立；段 B 对缺包只记 `WARN` 跳过，不产生 `FAIL`。

| 观察点 | 结论 | 证据 |
|---|---|---|
| 缺包行为 | 段 B 记 `WARN`（如「校园情感领域包不在场（跳过其结构校验）」），门禁不加 FAIL | `verify.sh` 段 B |
| 机制层依赖 | 官方核心 13 件 / 管线库 / schema / 例程均不按包名分支 | 段 A（check1-6）与段 C（check12 起的代码层门禁）的判据不含具体包名条件 |
| 域包可替换性 | 三个域（叙事 2 类 + 非叙事 1 类）共用同一套官方核心，仅替换题材层模块与管线 | 技术文档域包 = 官方核心 13 件 + 自带 2 件 + 1 条管线（P06） |

**含义**：新增或移除域包属**内容侧变更**（`additive` 或 `editorial`），不构成对机制层的结构性变更，故**不触发 V2 bump**，也不改变段 A / 段 C 的结论。

## `nf diff` 影响度（与 verdict 互补）

- `verdict` = 兼容判定（破坏/需评审/兼容——41 波C C2 保留不改语义）。
- `impact` = 影响度三档（本表）：`bump`（doc 编号变更 / 引用或章节移除 / 版本槽位变化）> `additive`（纯新增引用/章节/schema 名）> `editorial`（仅正文/计数/摘要变化）。CLI 打印在 `判定` 下方。

## 三档回放实证（历史变更抽查 3+1 例）

| 历史变更 | 落点 | 影响度 | 依据 |
|---|---|---|---|
| registry_schema_version v1→v2（机读投影 registry.json 引入） | 02 §9.3 | bump | V2 结构性新增投影实体；四步迁移记录在场 |
| protocol.schema_version v1→v2（references 组合引用通道引入） | 01 §7 迁移记录 | bump | V2 结构性新增跨包引用语义；四步迁移记录在场 |
| 模块头 machine_contract 机读化（九键投影） | 01 §1.1 + 模块文档 | additive | 模块文档字段级新增（01 迁移记录 1.2：V1 只增不删，非 V2 bump） |
| 管线 type 值域补 `techdoc`（P90/P06 实际使用暴露） | 01 §2 + pipeline.schema.json | additive | 值域新增非结构（43 A1 check28 收口） |

> 以上为 EXTENSION 判据的回放校验样本：凡归档为 bump 的均有迁移记录、凡 additive 的均未 bump 版本字段——check30 + check13 常驻守住该边界。

## 现状对照（2026-11-14 · 以 `nf diff` / check30 / check13 实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| 影响度三档 | **3 档**：`editorial` / `additive` / `bump`（判定进位关系确定：bump > additive > editorial） | `nf diff` 的 `判定` 行 + `nf diff --json` |
| 派生三问 | **3 条**（基类在册 / 只增不删不改义 / 旧消费方可忽略） | 本文「派生三问」段 |
| 门禁接线 | **check30**（结构性变更缺迁移记录即拦）+ **check13**（协议版本一致性/迁移完整性四步） | `python scripts/nf.py verify --only 30` / `--only 13` |
| 域包装卸 | 移除社区包后，段 A / 段 C 结论不变；段 B 只记 `WARN` 不加 `FAIL` | `bash verify.sh --checks-only` 的段 B 输出 |
| 回放样本 | **4 例**历史变更（2 bump + 2 additive）逐例落点与依据在文 | 本文「三档回放实证」表 |

**不钉运行时数字**：本文不写「当前 registry 版本号 / schema 件数 / 迁移记录条数」这类会漂的值；版本真源是 `01 §7` / `02 §9.3` 与各 schema，实证以 `nf diff` 实读为准。**唯一必须钉的是判据结构**（三档 + 三问 + 两 check 接线）。

## 复现与引用口径

```bash
python scripts/nf.py diff <旧文件> <新文件> --json    # verdict（兼容判定）+ impact（三档）
python scripts/nf.py diff --history 20 01_核心协议.md  # 从 Git 重建演进时间线（逐版影响度）
python scripts/nf.py verify --only 30                  # 单跑 check30（bump 必须有迁移记录）
```

- 引用本页时：`verdict`（兼容/需评审/破坏）与 `impact`（三档）**是两套判定**，不要互相替代；改 schema 先定影响度再走流程。
