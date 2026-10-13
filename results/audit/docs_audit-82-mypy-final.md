---
id: AUD-0034
title: 类型分批收敛收尾（desktop/src 剩余 31 条全部清零，24 模块）
date: 2026-10-05
scope: 作者指令「按 rivet 62 计划执行（除外部）」——62 计划 §三·①「存量复杂度/类型分批收敛」；承接 AUD-0033。开工依据为内部实测（mypy desktop/src 错误条数 31）。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/silent_skip.py:7a9e953f959d31161f29dcb5de4ef755a63d31ff807bdf333403c4b048f07457
  - desktop/src/core/round_drill.py:0407fc814cbb7ea5bc610036a4cf3e4675977eaaf5b7fa11fa142e32d6504c0b
  - desktop/src/core/quant_metrics.py:ae2bd5a5b71531ee4cf4abe920f75a939a30a5bea105efa7aed011cc92369ce3
  - desktop/src/core/module_lifecycle.py:7b84396342e77fea32e6b54cd78e296f1dddf925937b8331dbcdebeb4e9ad1d0
  - desktop/src/core/market_analyzer.py:eb5edffc55470b5f4aa8e6151ab7bffded36a45ce3ecc69fcdc54de59071cbdf
  - desktop/src/core/protocol_golden.py:b37b80ee8691fd76ed2df41f5006285c92914449bdfd6a2210164c7bc1f3e353
  - desktop/src/core/knowledge_sig.py:2e1177ae8701b38cff3b26e92892b3cbef4a347a48b986dd8b1f95934f60323b
  - desktop/src/core/output_forms.py:3688d30b158493f56801ef84f6f0e60eff2cc670c7ebcf750ffd403599d1b68a
  - desktop/src/core/pipeline_loader.py:4c58b842a8b79abdce6917305f8f5c307e4334cfa377cb3dc1b9d6f226871588
  - desktop/src/core/community_inventory.py:1cd42c4d2588a5facbb26aa3b1216e39d8b0ba0e407694ef441ab9c51e38cf00
  - desktop/src/core/retriever.py:97409e06af9b66d2b30bfde8a660d90b661c008bfe002b0b0712b824c7f6c9c4
  - desktop/src/core/lazy_yaml.py:127a18733214df1a721ad9e2fad8c0bc8cc195a4ee2f7fc782a60f85eb24d641
  - desktop/src/core/json_schema.py:f3a4a6a14de5104e217af8b154505f9ca46fd6133081188209add78143e2b23e
  - desktop/src/core/export_schema.py:9052dc891be0c70ceb5b42544eceeceeeb4dee8c4f107b1ec660913cf922ad3d
  - desktop/src/core/orchestration.py:6c860bebc068000dbd8f7a68103b300ab662c0666c912159226f015cea43327c
  - desktop/src/core/machine_contract.py:8b1bb40cdacac3e1104baa90e4c16d433c4db58983144e30764dc61e08f6c541
  - desktop/src/core/decisions.py:f5f5f7d77cbe2bf3a91cc930f6658fba31fc05932ef299938897f50d16126ba1
  - desktop/src/core/layer_model.py:18822a9c4a8b39dc8076cbf40695e40588cb6025a5e59efe8f93769ef9315357
  - desktop/src/core/import_graph.py:b97893527ec592921f81b96d9d9bd945be938db31e5d8c39d71d5a1d96990d9b
  - desktop/src/core/bench.py:5d7ef263ca30a9888f2c32f4db2253406dfdc510b52fbb19958a3afefe9cf574
  - desktop/src/core/import_adapter.py:7b68a8c20b1a1cc4acf78ca0b27e0752d49d509d49916539ce4a7ad38622cf1b
  - desktop/src/core/daemon.py:6091dc72140524c34ba23662d457977511f49fcbee6573bd8cb0a2c91d405e5d
  - desktop/src/core/decision_layer.py:f230aa31538f795d3a75a9cef9a109d323374cd8edbfc79c577df3e6378c31b7
  - desktop/src/core/exporter.py:d396f742ccf012331c855c4f52f0925daebc6100cadff30d4e1f510a9dff4c04
  - protocol/code_metrics_baseline.json:d79747f4bcc83535036c10b88f1ddc7d1aa924e3f9f43131319211ef3750a163
---

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-13 · 投稿面整体架构对齐）：被审对象随本轮改动（issue 模板 / INDEX 须知 / intake.json submission 段 / verify.sh check34 接线）而变，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（同 §15 约定）——本轮不主张新的语义审计，只把既有结论重新绑定到新对象。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects 不含派生物；`protocol/code_metrics_baseline.json` 因 7 个模块行数/圈复杂度增长按工具指引重冻。

## 一、结果

`python -m mypy desktop/src --ignore-missing-imports` 错误条数 **31 → 0**（默认口径）。

## 二、交付（按修法归类）

| 类 | 模块 | 修法 |
|---|---|---|
| 真标注错配 | `import_graph` | `parse` 标注写成 3 元组而实现返回 2 元组 `(deps, dyn)`、调用方也按 2 元组解包——三处只有两处一致；标注改为 `Optional[Tuple[frozenset, bool]]`，两处差错同消 |
| 变量复用解耦 | `round_drill`（allowed→allowed_set）· `orchestration`（tools→wf_tools）· `export_schema`（e→entry） | |
| 声明/集合显式类型 | `module_lifecycle` · `market_analyzer` · `pipeline_loader` · `community_inventory` · `retriever` · `knowledge_sig` · `silent_skip` · `decisions` · `machine_contract` · `exporter` · `decision_layer` | 补 `dict`/`list`/`Dict[str, Any]` 标注 |
| 可空收窄 | `bench`（局部 match 判空）· `daemon`（spec is None 守卫）· `import_adapter`（body 拆原始值）· `json_schema`（py: Any） | |
| 平台/属性 | `lazy_yaml`（os.sys→import sys）· `layer_model`（getattr(node, lineno, 0)） | |
| 数值文本 | `quant_metrics`（float(x or 空串)，与原 float(None) 同落 except） | |
| 键归 str | `output_forms`（str(f.get(category))）· `protocol_golden`（str(len(...))） | |

## 三、验收证据（本机实测）

- `mypy desktop/src` 错误条数 **31 → 0**。
- `python -m unittest`（本批相关 19 组）→ **282 例**（skipped=1）全绿。
- `python scripts/code_metrics.py` → 7 个模块行数或圈复杂度增长，按工具指引重冻。
- `python scripts/verify_run.py` → **PASS=72 · WARN=0 · FAIL=0**。

## 四、遗留与设计偏差

1. **范围限定**：本次清零的是 `desktop/src`（core 库）；`scripts/**` 与 `desktop/tests` 未纳入本线。
2. radon 复杂度仍为存量；62 §三·② 余量与 §二·2 .NET 重冻不在本件范围。
3. `import_graph` 的标注错配是真缺陷面（三处不一致），但运行时按实现走、未产生错误行为；本件只校准标注，不改运行路径。

## 五、五维自评

| 维度 | 本波水位 | 说明 |
|---|---|---|
| 静态可核验 | ↑↑ | desktop/src mypy 归零；282 例单测 + 全量 verify 双绿 |
| 动态可执行 | → | 不涉执行面（两处守卫均收窄到原路径） |
| 架构纯度 | → | 只改类型标注/变量命名 |
| 资产密度 | → | 不新增内容资产 |
| 文档可执行性 | → | 文档未动 |
