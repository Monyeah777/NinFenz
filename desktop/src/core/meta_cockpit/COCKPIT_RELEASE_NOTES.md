# NF 认知方法驾驶舱 · 发布说明

> 状态：机器层验收通过，HR-001 待人工签字；外部模型实测冻结。
> 当前 machine digest 由 `core.meta_cockpit.runtime_executor.machine_digest()` 输出。
> 主仓审计：`results/audit/docs_audit-95-meta-cockpit.md`。

## 可用入口

```text
nf cockpit --prompt "<目标>"
nf cockpit-ab --help
python -m unittest tests.test_meta_cockpit
```

`nf cockpit-ab`：

```text
preregister / packets / analyze / save / verify / index / audit
```

## 已验证能力

- 33 个方法论原子及 14 个方法节点；
- 任务画像、facet witness、coherence 与任务原生 handoff；
- 单轮 1–3 原子动态组装，无固定全程计划；
- 会话恢复、哈希链、并发锁、原子写；
- role-aware 本地检索与 trust/advisory 隔离；
- 8 回合方法记忆与状态环阻断；
- structured abstention、secret guard；
- 离线 blind paired A/B、power、预注册、固定 stopping rule；
- content-addressed A/B bundle 与本地实验库；
- 12 层 Agent 反模式审计与代码—文档契约。

## 当前边界

- HR-001 未签字，运行器保持 `PENDING-REVIEW`；
- 跨模型与多 seed 外部实测未执行；
- 语义真伪仍由人工复核兜底；
- 公共源模块依赖环仍是 residual；
- 主仓集成不清理并发会话的既有工作区改动。
