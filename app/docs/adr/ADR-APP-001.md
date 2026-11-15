# ADR-APP-001：APP 与 CCOS 分离：控制面不直连模型、不持密钥

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-001 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

方案要求 APP 承担「人做创作决策」的控制面，CCOS 承担「模型执行」的执行面。若 APP 直连模型 API：密钥必须进端、输出不可复算、离线不可用、隐私面扩大；若执行内置在端上：算力/包体/供应链风险不可控。

## 决策

1. APP 只产出 `ccos-task/1`（携带 pack/protocol/pipeline/spec 的 `{id,version,digest}`、inputs、variables、constraints、acceptance、budget、policy、provenance），传输形态首版为文件/zip；APP 不联网。
2. CCOS 回传 `ccos-result/1`；APP 侧 `ccos-import-result` 做 `task_digest` 回钉、artifacts 摘要校验、evidence 归档。
3. `human_review.required` 恒为 true：CCOS 结果必须经 APP 内人工复核才能进项目状态机（`reviewed`）。
4. `policy.secrets` 常量 `ccos-only`：任务/结果里出现密钥或越界策略字段即 `NF-CCOS-003`（exit 3）；任务生成前做绝对路径/用户名/密钥形状扫描。
5. 预算（max_tokens/max_chars/max_seconds）在任务里显式声明，由 CCOS 侧执行；APP 不消耗模型预算。

## 后果

**正面**

- 密钥与模型调用不进入 APP：端侧无凭证可偷、无出站请求可劫持。
- 任务/结果与 digest 可归档、可复算、可审计：同一 task 两次执行结果可对比。
- APP 可完全离线工作；CCOS 可替换（换模型/换供应商不动 APP 契约）。
- 人审是状态机的一等状态，AI 产出不能绕过。

**负面 / 代价**

- 多一道人工交接：实时性差于直连，端到端延迟由人决定。
- 跨侧排错成本：APP 只能给 digest 回钉与 issue 列表，模型侧失败原因需在 CCOS 侧查。
- CCOS 的可用性成为交付链路的外部依赖（不可用即无法完成 AI 步骤，但手工步骤不受影响）。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. APP 直连模型 API | 否决 | 密钥入端、不可离线、输出不可复算；违反 `CONTRACT.md` §6 隐私与「密钥只在 CCOS」 |
| B. APP 内嵌执行器 | 否决 | 端上算力/包体/模型分发不可控；供应链与许可面爆炸 |
| C. 在线 RPC 双向同步 | 否决 | 需账号与网络；与无遥测/无账号/离线定位冲突 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| `ccos-task/1` 结构（policy.secrets / budget / provenance） | `app/schema/ccos-task.schema.json` |
| `ccos-result/1` 结构（task_digest / human_review / evidence） | `app/schema/ccos-result.schema.json` |
| 交接语义（不得含密钥/绝对路径；人审恒 true；传输默认文件/zip） | `app/docs/CONTRACT.md` §5.11 |
| op 面（`ccos-build-task` / `ccos-import-result` 与 exit 语义） | `app/docs/CLI.md` §3 |
| 错误码（NF-CCOS-001…004） | `app/schema/error_codes.json` |
| 门禁项（CCOS task/result/人审用例） | `app/gates/gates.json` QA4 `q4-ccos` |

## 复审条件

- 新增传输形态（QR、本地桥、在线通道）前必须重评本决策。
- CCOS 侧协议版本变更或需要回传密钥/预算以外字段时。
- 若作者要求端上执行（离线生成）时——需新 ADR，不得逐条改实现绕过。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
