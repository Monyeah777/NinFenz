# 断言表（assertions）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> **定位**：把「能确定性判定的形状类断言」从 check 代码搬进 `protocol/assertions.json`——新增规则 = 加一行数据。
> 最后更新：2026-11-13

> **复核（2026-11-13）**：机制口径不变（形状断言进数据、kind 封闭集四型、表自身过门）；补五处现状：① 现行 **24 条**断言（四型全用上）；② 每条 6 个必填键 + **`capability`**（能力归属）、**`evidence`**（证据锚）；③ severity 词表 = `fail`/`warn`（现行 24 条**全为 fail**）；④ 表级还有 `severity_vocabulary` / `capability_vocabulary`（16 项）/ `capability_index`（16 项）；⑤ 常驻判据 `test_assertions` **21 例**。见「§现状对照」。

## 是什么

把「能确定性判定的形状类断言」从 check 代码里搬到**数据**里：真源 `protocol/assertions.json`，
每条 = `id / severity / kind / params / message / fix`（必填 6 键）+ `capability`（该断言服务哪个判定能力）
+ `evidence`（证据锚，如 `check35 / conformance::public-surface`）。机制借鉴 Schematron 的
patterns→rules→assertions（ISO/IEC 19757-3）——**新增规则 = 加一行数据，不必改 check 代码**。

| 层级 | 字段 | 说明 |
|---|---|---|
| 表级 | `schema` | 现行 `nf-assertions/1` |
| 表级 | `severity_vocabulary` | 封闭词表 `fail`/`warn`（与 runner 逐项一致） |
| 表级 | `capability_vocabulary` / `capability_index` | 能力词表（现 16 项）与「能力 → check 号」索引 |
| 断言级 | 上述 6 必填键 + `capability` + `evidence` | id 唯一、每条必须有 `fix` |

## 怎么用

```bash
python scripts/nf.py assertions            # 跑全表（fail 级不通过即 exit 1）
python scripts/nf.py assertions --json
python scripts/nf.py lint --kinds          # 四型写法判据（信息类型化的"定型"面）
```

## 判据（kind 为**封闭集**，不自造 DSL）

| kind | 用途 | 必填 params |
|---|---|---|
| `regex_absent` | 某类件里**不得**出现某模式（如绝对路径泄漏） | `globs`、`pattern` |
| `regex_present` | 某件必须含若干锚点 | `path`、`patterns` |
| `count_at_least` | 匹配件数下限（如 IDL 五定义在场） | `glob`、`min` |
| `json_value` | 读 JSON 键并判定（`exists` / `nonempty` / `equals` / `in_vocab` / `contains_keys`） | `path`、`key`、`op`、（`value`） |

表自身也过门：schema、severity/kind 词表必须与 runner 的封闭集逐项一致、id 唯一、
**每条必须有 `fix`**（没有修复指引的断言不许入表）；`capability` 必须落在 `capability_vocabulary`
词表内且被 `capability_index` 覆盖（能力面防漏账）。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 断言条数 | 机制刚立（未计数） | **24 条**（四型全用上） |
| kind 封闭集 | 4 型（regex_absent / regex_present / count_at_least / json_value） | **不变**（runner 的 `REQUIRED` 与四型逐项一致） |
| 断言键 | 6 键 | **6 必填 + `capability` + `evidence`** |
| severity | 只写 fail 级语义 | 词表 `fail`/`warn`；**现行 24 条全 fail** |
| 能力面 | 未提 | `capability_vocabulary` **16 项** · `capability_index` **16 项** |
| 常驻判据 | 未计 | `test_assertions` **21 例**（表自身过门 + 四型 runner + 能力面） |
| schema | 未写 | `nf-assertions/1` |

> 本表只作「当时 → 现行」导航；真源 = `protocol/assertions.json`，数字以 `nf assertions --json` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py assertions            # 跑全表（fail 级不通过即 exit 1）
python scripts/nf.py assertions --json     # 机读全表（schema/词表/能力索引/24 条）
python -m pytest desktop/tests/test_assertions.py -q   # 表自身过门 + 四型 runner（21 例）
```

- 引用本文时：「kind 封闭集四型、只搬形状判定、不扩表达力」= 长期口径；条数与词表以数据文件实读为准。
- 新增断言须同时给 `fix` 与 `capability`（缺一即被表自身判据打红）。

## 边界

- 只搬「已在别处被判定过的形状类断言」，**不在本表里新增语义政策**；业务语义断言留在 check 代码里。
- 不引第三方依赖、不扩表达力：表达力扩张会让"零依赖 + 可读"同时失控。
