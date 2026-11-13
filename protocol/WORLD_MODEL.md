# WORLD_MODEL · 确定性抽象状态契约

> 定位：把 JEPA/H-JEPA 的机制思想收窄为 NF 可机检的协议字段，不给外部路线背书。
> 版本：随 machine_contract 字段级新增（01 §7 V1，只增不删）。首战实例：M50 主循环。
>
> **复核（2026-11-14）**：schema 形状、机检语义、运行器与首战实例**复核不变**；本轮补「§现状对照」「§复现与引用口径」，并把扫描统计明确为**扫描器实读值**（不是需要维护的承诺）。

## 1. 一句话

`machine_contract.world_model` 是可选的确定性抽象状态世界模型：模块声明**有限状态变量**、**初始值**、**显式相位迁移图**与**长期不变式**。它回答“这个模块把世界抽象成哪几个状态、状态怎么变、什么永真”，不训练、不运行神经网络。

## 2. 与 JEPA 的映射（机制借鉴，不背书）

JEPA/H-JEPA 的核心不是预测像素或下一词元，而是**在表征空间中预测未来抽象状态**（LeCun 2022；arXiv:2211.10831，arXiv:2306.02572）。NF 只在协议层吸收以下三条可验证的机制：

| JEPA 机制 | NF world_model 对应 | 可机检含义 |
|---|---|---|
| 抽象表征而非原始输出 | `abstract_state.variables[]` | 只声明有限状态变量与类型，不建模文本生成 |
| 表征预测的有限状态动力 | `transition.phases[]` | 每个相位显式声明 `next/guard/writes`，迁移图闭合 |
| 防表征坍缩的约束 | `invariants[]` | 长期不变式如 `tick 单调不减`、`phase 有限` 可静态断言 |

非生成性、能量模型、VICReg/Barlow Twins 等是 JEPA 的训练机制，**不属于 NF 协议层校验对象**；本字段不声称复现其性能。

## 3. Schema 形状

```yaml
world_model:
  abstract_state:
    variables:
      - name: phase        # 变量名，全契约唯一
        kind: string       # string|integer|number|boolean|array
        source: M50        # 状态归属方（哪个模块拥有/写入该变量）
        slot: data_bus.round.phase   # 可选：M00 数据槽路径（须在 world_slots.json 注册）
        item_kind: string  # 仅 kind=array 可用
        note: 主循环抽象相位
      - name: tick
        kind: integer
        source: 通用:M10
    initial:
      phase: begin         # 每个已声明变量必须给初值；初值必须匹配 kind
      tick: 0
  transition:
    initial_phase: begin   # 必须在 phases[] 内
    phases:
      - phase: begin       # 相位名全图唯一
        next: run          # 必须指向 phases[] 内的相位
        guard: 回合开始并快照 M00 数据槽
        writes: []         # 可写槽位，可为空
  invariants:
    - "tick 单调不减"
    - "phase 只在有限集合内迁移"
  checks:
    - kind: finite_phase   # 机器可执行检查：state.phase 必须在 values 内
      field: phase
      values: [begin, run, end, archive, roll]
    - kind: monotonic      # 机器可执行检查：state.tick 不得倒退
      field: tick
    - kind: finite_sequence  # 机器可执行检查：state.phase_trace 每个元素都在 values 内
      field: phase_trace
      values: [begin, run, end, archive, roll]
```

## 4. 机检语义

`desktop/src/core/world_model.py` 在 check32 质量纵深汇总中常驻，硬门只验可无歧义项：

- `abstract_state.variables` 非空、变量名唯一、`kind/source` 合法；
- 可选 `slot` 非空且全契约唯一，并须在 `protocol/world_slots.json` 注册；注册后校验 `kind/item_kind/owner` 与变量声明一致；`world_slots` 自身每个路径段还须在 `M00_数据槽总线.md` 锚定；
- `initial` 与变量集合**双射**：既不多未知变量，也不缺已声明变量；
- 初值按 `kind`（含 `array.item_kind`）逐项匹配；
- `transition.phases` 非空、相位名唯一、`guard/writes` 齐全；
- `initial_phase` 与所有 `next` 必须落在 `phases` 内；
- 从 `initial_phase` 出发的迁移闭包必须覆盖全部相位，不可达相位 = FAIL；
- `invariants` 非空、每条非空字符串；
- 可选 `checks` 为机器可执行不变式：`finite_phase`（字段值有限）、`monotonic`（数值单调不减）、`finite_sequence`（数组元素有限）。

这些门只保证“抽象状态契约自洽”，不宣称叙事质量或模型优劣。

## 4.1 运行态（WorldModelRuntime）

`desktop/src/core/world_model.py` 还提供确定性的纯 Python 运行器：

- `WorldModelRuntime(contract)`：加载契约并先做结构/语义校验；
- `validate_state(state, previous)`：状态键封闭、类型匹配、`checks` 全过；
- `advance(state, previous)`：按 `transition` 前进相位，并把旧相位追加进 `phase_trace`（若声明）；
- `replay(state=None, max_steps=100)`：从 `initial` 重放，直到回到已见相位或超限，产出逐步 trace。
- 每次 replay 附带 `digest`：对 `steps[]` 做规范 JSON SHA-256；同契约重放必同指纹。
- `extract_state(concrete)` / `validate_concrete(concrete)` / `advance_concrete(concrete)`：把 slot 绑定变成可执行映射，从 M00 具体 JSON 状态抽取、校验并写回抽象状态。
- `replay_concrete(concrete)`：从具体状态重放并产出含 `concrete_before/concrete_after` 的 trace。

CLI 入口：`nf worldmodel --run`；JSON 遥测出口：`nf worldmodel --run --json`；具体 M00 状态绑定：`nf worldmodel --run --state STATE.json [--json]`。

## 5. 首战实例

`04_模块库/通用类/M50_调度器.md` 已落地首个 `world_model`：

- 抽象变量：`pipeline`、`tick`、`phase`、`phase_trace`，均绑定 `slot`；
- 相位环：`begin → run → end → archive → roll → begin`；
- 不变式：状态变量有限、`tick` 单调不减、相位有限、迁移全可达、非 M50 不得直写 M00。
- 机器 checks：`phase` 有限相位、`tick` 单调、`phase_trace` 有限序列。

扫描统计基线：模块 1、变量 4、相位 5、不变式 5、checks 3、slots 4、槽位注册 10。

## 6. 边界

- `world_model` 可选；未声明时模块仍是合法 NF 模块。
- 该字段是**结果/协议**，不是规划；它不携带 JEPA 训练目标、损失函数或模型权重。
- 外部有效性只由作者显式触发的用户实测回填，不由本契约或扫描器自动证明。

## 7. 权威来源（引用 ≠ 背书）

- LeCun, Y. *A Path Towards Autonomous Machine Intelligence*, 2022. [arXiv:2211.10831](https://arxiv.org/abs/2211.10831)
- *Introduction to Latent Variable Energy-Based Models: A Path Towards Autonomous Machine Intelligence*, 2023. [arXiv:2306.02572](https://arxiv.org/abs/2306.02572)
- Ha, D. & Schmidhuber, J. *World Models*, 2018. [arXiv:1803.10122](https://arxiv.org/abs/1803.10122)
- Hafner, D. et al. *Mastering Diverse Domains through World Models*, 2023. [arXiv:2301.04104](https://arxiv.org/abs/2301.04104)
- Zbontar et al., *Barlow Twins: Self-Supervised Learning via Redundancy Reduction*, 2021. [arXiv:2103.03230](https://arxiv.org/abs/2103.03230)
- Caron et al., *Emerging Properties in Self-Supervised Vision Transformers (DINO)*, 2021. [arXiv:2104.14294](https://arxiv.org/abs/2104.14294)

## 现状对照（2026-11-14 · 以 world_model.scan / check32 / CLI 实读为准）

| 面 | 当前口径 | 复核方式 |
|---|---|---|
| 扫描结果 | 模块 **1**（M50）· 变量 **4** · 相位 **5** · 不变式 **5** · checks **3** · slots **4** · 槽位注册 **10** | world_model.scan 的 stats |
| 硬门接线 | **check32**（质量纵深汇总）常驻；nf verify --only 32 可单跑 | verify.sh |
| 校验器 | core/world_model.py：validate_contract / advance_phase / trace_digest / scan + WorldModelRuntime（validate_state / advance / replay / *_concrete） | 该模块 API |
| CLI | nf worldmodel（清单）· --walk（重放相位环）· --run（M50 实跑并打印 digest）· --state（具体 M00 状态绑定） | python scripts/nf.py worldmodel --help |
| 判据 | test_world_model **20 例** · test_world_slots（槽位注册表） | 本地实跑 |

**扫描基线不钉死**：上表数字是**当次实读**——新增 world_model 模块时数字会变，本文以命令为准；本文只固化「schema 形状 / 硬门语义 / 运行器 API」这些结构事实。

## 复现与引用口径

```bash
python scripts/nf.py worldmodel --run                 # M50 实跑 5 步 + digest（同契约必同指纹）
python scripts/nf.py worldmodel --json                # 结构化清单（模块/变量/相位/不变式/checks/slots）
python -m pytest desktop/tests/test_world_model.py desktop/tests/test_world_slots.py -q
```

- 引用本页时：「抽象状态契约自洽」不等于「世界模型质量好」——质量仍由 42 五维与真实战例判定。
