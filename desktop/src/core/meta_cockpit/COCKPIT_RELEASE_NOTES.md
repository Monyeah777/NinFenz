# NF 认知方法驾驶舱 · 发布说明

> 状态：机器层验收通过，HR-001 待人工签字；外部模型实测冻结。
> 当前 machine digest 由 `core.meta_cockpit.runtime_executor.machine_digest()` 输出。
> 主仓审计：`results/audit/docs_audit-95-meta-cockpit.md`。
> **复核（2026-11-14）**：能力清单与边界**复核不变**；补「§现状对照」把可核实数字钉到真源，并把原文一处**无代码载体**的表述标注为存疑（不删、不粉饰）。

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

## 现状对照（2026-11-14 · 以资产/常量实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 方法论原子 | **33** | `meta_atoms.json` 的 `atoms` |
| 方法节点 | **14** | `method_*.json` 文件数 |
| 内容管线 | **10 节点** | `cognition_pipeline.json` |
| 元管线 | **5 节点** | `cognition_meta_pipeline.json` |
| 方法记忆回合 | **8** | `method_memory.MAX_HISTORY` |
| 运行时身份 | `runtime_executor.machine_digest()` + `meta_runtime_manifest.build()` 的 `file_digests`（本文件同在其中） | 两个函数实读，**本文不钉摘要值**（钉值必与自身循环） |
| 人工复核状态 | **PENDING**（运行器 `PENDING-REVIEW`） | `runtime_executor.review_status()` |
| A/B 子命令 | **7 形态**：preregister / packets / analyze / save / verify / index / audit | `nf cockpit-ab --help` |
| 存疑项 | 原文「**12 层 Agent 反模式审计**」在仓内**只有本文与 `DIFFERENTIATION.md` 提及**，未找到对应实现或判据（`st_quality` 是制卡质量门，不是 12 层反模式审计） | grep 全仓 + `st_quality.py` 实读 |

> 本表只作「当时 → 现行」导航；数字以资产实读为准。存疑项**如实登记**，待作者裁决是补实现还是改表述。

## 当前边界

- HR-001 未签字，运行器保持 `PENDING-REVIEW`；
- 跨模型与多 seed 外部实测未执行；
- 语义真伪仍由人工复核兜底；
- 公共源模块依赖环仍是 residual；
- 主仓集成不清理并发会话的既有工作区改动。
