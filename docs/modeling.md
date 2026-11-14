# 内容建模三件（modeling）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13
> **复核（2026-11-13）**：三件划分 / 判据 / 边界**复核不变**；补可核现状（`nf model` 实读）：
> 词表 **12 个 scheme**（`literal` 0 个，全部有代码真源可比对）· 规范件 **37** / 说明件文件 **2445** / 回执受锚 **66** ·
> 数据契约 **54** 条（`quality_rule` 解析到 **42** 个 check + **24** 个 assertion）· 判据 `test_modeling` **12 例**。见「§现状对照」。

## 是什么

把三件此前只存在于人脑里的建模问题变成机检件（机制借鉴一句式：SKOS 的概念方案 / 标准治理的
normative·informative 二分 / 数据契约要素）：

| 件 | 真源 | 回答什么 |
|---|---|---|
| 词表登记册 | `protocol/vocabularies.json` | 全仓词表**有哪些、以谁为准**——真源变了册子没跟就 FAIL |
| 规范件与说明件 | `protocol/normative.json` | 哪些件**有约束力**、哪些只是解释 |
| 数据契约登记 | `protocol/data_contracts.json` | 每个机读件**谁管、按什么规则判、坏了怎么重建** |

## 怎么用

```bash
python scripts/nf.py model                 # 三件全跑
python scripts/nf.py model vocab           # 只看词表与真源是否漂移
python scripts/nf.py model normative       # 只看规范/说明件名单
python scripts/nf.py model contracts       # 只看数据契约登记
python scripts/nf.py model --json
```

## 判据（可证）

| 件 | 判据 |
|---|---|
| 词表 | scheme id 唯一；status 在册；值 ≥2 且不重复、不与 alias 撞车；**probe 指回真源后逐项比对**（`python_attr` / `json_path` / `literal`）；真源取不到即 FAIL |
| 词表（literal） | `probe.kind=literal` 表示以册为准（无代码真源），此时不比对只查形式 |
| 规范/说明 | 两名单交集为空；规范件必须**有主**（被 `protocol/RECEIPTS.json` 锚定，或显式 `covered_by` 且 `checkN` 真实存在）；**说明件不得被回执锚定** |
| 数据契约 | artifact 必须存在；`quality_rule` 必须解析到真实 `checkN` 或 `assertion:<id>`；owner / freshness 非空；status 在册 |

## 现状对照（2026-11-13 · 以 `nf model` 实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 词表 scheme | **12**（literal 0） | `nf model vocab` 头行 |
| 规范件 | **37** | `nf model normative` 的 `normative` |
| 说明件文件 | **2445** | 同上 `informative_files` |
| 回执受锚 | **66** | 同上 `receipts` |
| 数据契约 | **54** | `nf model contracts` 的 `contracts` |
| quality_rule 解析面 | **42 checks + 24 assertions** | 同上 `checks_seen` / `assertions_seen` |
| 常驻判据 | **12 例** | `test_modeling.py` |

> 本表只作「当时 → 现行」导航；数字以 `nf model --json` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py model            # 三件全跑（任一漂移即红）
python scripts/nf.py model --json     # 机读（schemes / normative / contracts 三段）
python -m pytest desktop/tests/test_modeling.py -q   # 12 例
```

- 引用本文时：「册子只做声明+比对，不复制真源；说明件不得被回执锚定」= 长期口径。
- 改真源后先跑 `nf model` 再改册；`literal` 档（以册为准）当前 0 个——出现即需说明理由。

## 边界

- 词表册**不复制**真源：它以 probe 指向真源，只做"声明 + 比对"；真源改动后先跑 `nf model` 再改册。
- 规范件名单不是"重要性排序"：它只区分**有无约束力**；解释性长文（`DEEP_DIVE`/`docs/**`/`results/**`）一律说明件。
- 数据契约的 `owner` 在 NF 里是**机制**而非个人（Bus Factor 1 的对策是让 check 当 owner）。
