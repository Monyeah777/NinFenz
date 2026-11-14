# 数字资产契约（asset contracts）

> 本文是**格式规范**：真源 = `protocol/asset_contracts.json`，可移植 schema = `protocol/schema/asset_contracts.schema.json`，
> 机检入口 = `python scripts/nf.py asset contract`（与 verify check40 同源）；读到即执行，勿当资料。
> 最后更新：2026-11-13

> **复核（2026-11-13）**：四面口径与判据不变；补四处现状：① 声明表现状 **22 面条 + 1 链**（`data` 10 / `code` 7 / `script` 4 / `index` 1 / `chains` 1）；② CLI **六旗标**（`--root` / `--face` / `--export` / `--freeze` / `--run-tests` / `--json`）——其中 `--freeze` 是**显式棘轮**（按当前内容重冻 sha256）、`--run-tests` 显式开启才执行被声明代码；③ 资产面现状（`nf asset verify`）：**台账 103 · 托管 308 · 未托管 0 · 孤儿头 0**；④ 常驻判据 `test_asset_contract` **59 例**（+ 四面分面测试）。见「§现状对照」。

## 这份规范解决什么

「AI 生成的资产能不能收」此前只散在 check 代码与人脑里：格式对不对、字段全不全、有没有被人改过、
生成的代码有没有禁用面、多语言脚本 A 的输出是不是 B 的输入。本文把这些问题收成**一张声明表**——
声明即契约：**指不出判据的资产不许登记**。

## 四面

| 面 | 判什么 | 关键原语 |
| --- | --- | --- |
| `data` | 格式 / 字段完整性 / 防篡改 | `format`（json·csv·markdown·text·yaml·toml·jsonl·graphml·mmd）、`schema`、`schema_siblings`、`required_fields`、`required_columns`、`required_any_columns`、`min_rows`、`min_nodes`、`link`、`sha256` |
| `code` | AST 规范 / 禁用调用 / 可证空指针 / 测试件 | `deny_calls`；第二实现线走**结构模式**：`forbid_regex` + `regex_limits`（计数棘轮，不做 AST 也不假装 AST） |
| `script` | 多语言脚本 I/O 契约对齐 | 脚本内 `# nf-io: inputs=… outputs=…` 头 + `inputs`/`outputs` 声明 + `chains`（A 的输出必须匹配 B 的输入） |
| `index` | 包自述与实况**双向对账** | 读包自带 `outputs/INDEX.json`：声明的件 / schema / inputs 必须在场，`outputs/` 下的实况必须都被声明 |

## 便携格式（S2）

- 声明 schema：`protocol/schema/asset_contracts.schema.json`——**可执行**：声明不符即 FAIL（⑤），不是文档摆设。
- 导出：`python scripts/nf.py asset contract --export` → `protocol/generated/asset_contract.frictionless.json`
  （Frictionless Data Package；`fields` 是 JSON Schema `properties` 的尽力映射，原始 schema 逐字段留在
  `x-nf-json-schema` 里——**映射丢信息就是装饰，故不丢**）。导出面同样判漂移（④）。

## 带自己的资产来验

```bash
python scripts/nf.py asset contract --root <你的目录>          # 四面全跑
python scripts/nf.py asset contract --root <你的目录> --json   # 机读结果
```

被验目录需要 `protocol/asset_contracts.json`（声明）与 `protocol/data_contracts.json`（登记册：谁判 / 谁管 / 坏了怎么重建）。

> 本仓库自验：`nf asset contract`（四面 + 链）与 verify **check40** 同源；分面调试用 `--face data|code|script|index`。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 四面 | data / code / script / index | **不变**（另有一条 `chains` 跨脚本链接声明） |
| 声明条数 | 未计数 | **22 面条 + 1 链**：data 10 · code 7 · script 4 · index 1 · chains 1 |
| CLI 旗标 | 未列全 | **六旗标**：`--root` / `--face` / `--export` / `--freeze` / `--run-tests` / `--json` |
| 导出面 | frictionless 导出（④ 判漂移） | `protocol/generated/asset_contract.frictionless.json` 在场；`--export` 重生成 |
| 同源判据 | check40 | **不变**（verify.sh 内 check40） |
| 资产面 | 未涉 | `nf asset verify`：台账 **103** · 托管 **308** · 未托管 0 · 孤儿头 0 |
| 常驻判据 | 未计 | `test_asset_contract` **59 例**（+ `test_asset_contract_faces` 等分面件） |

> 本表只作「当时 → 现行」导航，不替代实跑；数字以 `nf asset contract --json` / `nf asset verify` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py asset contract --json        # 四面 + 链（机读）
python scripts/nf.py asset contract --face data   # 单面调试
python scripts/nf.py asset verify                 # 台账/托管/孤儿头闭合
python -m pytest desktop/tests/test_asset_contract.py -q   # 59 例常驻判据
```

- 引用本文时：「四面 + 声明即契约 + 指不出判据不许登记」= 长期口径；条数与资产面以实跑为准。
- 棘轮纪律：`--freeze` 只在**有意变更**后显式执行（review 后重冻），不由扫描器自动写；`--run-tests` 默认关闭（门禁不执行被声明代码）。

## 纪律（都是实测换来的）

- **缺依赖不放行**：YAML 契约缺 PyYAML 时报缺口，不静默跳过（跳过 = 假绿）。
- **可减缺口要可见**：没有 schema 的件记 `no_schema`，不判死也不藏。
- **同一 artifact 不许两册各说一套**：资产册声明为数据的 `protocol/*.json` 必须在 `data_contracts` 登记。
- **写通道必须有主**：自带写入口的件必须声明落点件，且登记册 `owner` 按文件名点名它。
