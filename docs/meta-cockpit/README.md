# 元认知生产驾驶舱

NF 的元认知生产驾驶舱把任务意图转换为可执行的方法组合，并把方法、上下文、状态变化和证据来源记录为可重放轨迹。它不是固定提示词模板，也不是评分器：驾驶舱内只报告状态、缺口与证据，质量结论由外部质检、盲评和人工复核产生。

## 运行面

```text
nf cockpit --prompt "比较三种方案的失败成本" --json
nf cockpit --prompt-file task.md --journal session.json --manifest-out manifest.json
nf cockpit-ab preregister --experiment experiment.json --out preregistered.json
nf help cockpit
nf help cockpit-ab
```

`nf cockpit` 默认离线、单轮按当前任务组合 1–3 个元认知原子；多轮时根据任务 facets、方法记忆和已验证状态继续重选。`--responses` 可接入外部记录的 JSONL 响应，`--context-dir` 保存每轮实际上下文。

## 运行时结构

- 33 个原子执行器、14 个方法节点与 10 节点内容管线；
- 5 节点元管线：方法路由、方法审计、过程监控、判据框架审计、证据标准选择；
- 6 类认知义务、任务画像、角色感知检索与结构化弃权；
- 有界 `thought_patch`、状态环阻断、方法历史、事件溯源与确定性重放；
- 离线配对盲评 A/B、预注册、功效分析、盲包、bundle 与内容寻址实验库。

生产产物不包含内部 `score`、`grade`、`rating` 或 `receipt` 字段。A/B 的胜率与统计结论只存在于实验报告中，不会反馈为驾驶舱内的分数。

## 边界

- 核心本体为确定性、离线实现，不调用外部模型；
- 外部模型在环和多模型 A/B 仍需作者显式触发，当前没有真实质量增量结论；
- HR-001 人工复核仍为 `PENDING`；
- 语义真伪保留人工复核兜底。

正式协议见 [COCKPIT_PROTOCOL.md](../../desktop/src/core/meta_cockpit/COCKPIT_PROTOCOL.md)，差异化边界见 [DIFFERENTIATION.md](../../desktop/src/core/meta_cockpit/DIFFERENTIATION.md)。
