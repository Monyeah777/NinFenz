# reasoning：认知舱推理面（deterministic reasoning plane）

本包把"推理期算力怎么花"做成确定性、只读、可复算的运行时层：候选先验
（steering）→ 状态图搜索（search）→ 步级判定（value）→ 计划记忆
（memory）→ 归因（counterfactual）→ 证书（certificate）→ 每回合门面
（session）。全部 stdlib-only，不调用模型，**没有内部标量评分**。

## 包边界

- `ReasoningSession` 是唯一对外门面；`constrained_loop.run(..., reasoning=...)`
  在每回合调用 `begin_turn`（只读重排候选 + 可选搜索）与 `record_turn`（步级
  判定 + 扣预算），失败 fail-closed 为 `termination="reasoning-error"`。
- 子模块可以直接 import（`portfolio` / `anytime` / `memory` / `counterfactual` /
  `certificate` / `parallel`），但都保持纯函数/只读；不写 journal、不写门禁。
- 不依赖 `core.meta_cockpit` 之外的东西；对外部模型完全无感。

## 模块表

| 模块 | 作用 | 主要 schema |
|---|---|---|
| `bridge.py` | 只读桥接 `cognitive_cockpit` / `live_selector` / `coherence` / `method_memory`；`state_digest`、`shadow_execute`、`candidate_actions` | — |
| `budget.py` | 预算对象（nodes/depth/seconds/unit）、按结构缺口数的 compute-optimal 式分配、`should_stop` 早停判据 | `nf-cognition-budget/1` |
| `value.py` | `step_verify`：确定性 checks（witness）+ 整数 `gains` + `pass/fail/unknown`；外部 advisory 只留 digest | `nf-step-verdict/1` |
| `steering.py` | 均匀先验 + log 域偏置 `p' ∝ p·exp(β·s)`；β ≤ 0.5；top-1 ≥ 0.95 关闭 | `nf-steering-audit/1` |
| `search.py` | 认知状态图搜索：默认 `best_first`（整数词典序键、最优子回传、coherence 硬剪枝、transposition），`puct` 可选；预算耗尽降级为完整 greedy 路径 | `nf-cognition-search/1` |
| `portfolio.py` | 多后端 successive-halving 竞速（预留式预算分摊） | `nf-search-portfolio/1` |
| `anytime.py` | 跨回合 anytime 会话：预算结转、gap 单调、`advance(0)` 幂等 | `nf-anytime-session/1` |
| `memory.py` | digest-only 计划案例库：精确 Beta 下界、契约漂移失效、quarantine；**不存内容** | `nf-plan-memory/1` / `nf-plan-memory-key/1` |
| `counterfactual.py` | leave-one-out 必要性 + 有界最小化；预算耗尽记 `unknown`，不误判必要 | `nf-plan-attribution/1` |
| `certificate.py` | 可独立复核的搜索证书：L1 结构自洽 / L2 重放重算，三值 `pass/fail/indeterminate`；checks 从不被信任 | `nf-cognition-certificate/1`（+`nf-cert-policy/1`、`nf-cert-budget/1`） |
| `parallel.py` | 批量扩展搜索；顺序 best-first 作确定性兜底（`sequential-fallback`） | `nf-cognition-search/1` |
| `trace.py` | canonical JSON 字节 + sha256 digest（session/journal 共用口径） | — |
| `session.py` | 每回合门面：`begin_turn` 只读、`record_turn` 判定、`summary` digest-only | `nf-reasoning-policy/1`、`nf-reasoning-turn/1`、`nf-reasoning-session/1`、`nf-reasoning-record/1` |
| `reasoning_policy.json` | 默认策略（mode/β/search/portfolio/memory） | 见 `reasoning_policy.schema.json` |

## 四个核心 schema

1. `nf-step-verdict/1`：`checks[{id,ok,witness}]`、`mandatory`、`verdict`、
   整数 `gains{unmet,coherence,facet,new_keys}`、`violations`、
   `advisory[{source,role:"external-advisory",digest}]`、`no_score`、`digest`。
   **没有 value/score/weights/components**；外部证据永不升级为本地事实。
2. `nf-steering-audit/1`：`prior_source:"uniform"`、`normalization:"none"`、
   `beta_applied/beta_cap/clamped/disabled`、每候选 `prior_terms/bias/posterior`。
3. `nf-cognition-search/1`：`best_path/visits/stats/search_stats/budget/trace_digest`；
   公开结构递归无 `reward/q/value/score/weights`，只有整数计数与 digest。
4. `nf-cognition-budget/1`：`Budget` 的规范化描述 + digest；fail-closed 校验。

## CLI 用法

```bash
# 默认（auto：结构缺口 >= min_gaps 时跑一次 best-first）
python3 scripts/nf.py cockpit --prompt "..." --reasoning --json

# 指定模式/节点/先验/策略文件
python3 scripts/nf.py cockpit --prompt "..." --reasoning \
    --reasoning-mode search --search-nodes 200 --reasoning-beta 0.3 \
    --reasoning-policy /tmp/reasoning_policy.json --json
```

`result["reasoning"]` 是 `nf-reasoning-session/1` 汇总（`mode/turns/search_nodes/
orders_digest/audits_digest/no_scoring`）；`result["run"]["reasoning"]` 同源。
不带 `--reasoning` 时输出面与原来完全一致（测试覆盖）。

**已知不一致（待修）**：CLI 的 `--reasoning-mode` choices 含 `steer`，
但 `ReasoningSession.MODES = ("auto", "search", "off")`；传 `steer` 会被
`ReasoningSession` 以 ValueError 拒绝（CLI exit 2），而 `off` 不在 CLI choices 里。
本包测试按实际契约覆盖 `off/auto/search` 与 β>0 的 steering 行为，未把
`steer` 当成合法 mode。

## 与 `constrained_loop` 的接线

- `constrained_loop.run(..., reasoning=session)`：
  - 每回合在候选生成后调用 `reasoning.begin_turn(turn_state, candidates, ledger)`
    → 返回重排后的候选 + `nf-reasoning-turn/1` trace；搜索计划首簇排到最前。
  - 回合提交后调用 `reasoning.record_turn(...)` → `nf-step-verdict/1` 记一步，
    并从 session 搜索预算里扣除上一轮实际节点数。
  - 任一异常 → `termination="reasoning-error"`（fail-closed，不静默降级）。
  - 结果顶层追加 `reasoning.summary()`；journal/事件仍走既有链路。
- 审计块（steering audit / search trace）只进 journal/state，**不进模型 payload**：
  模型只看到候选/约束与 `pass|fail|unknown`。

## 明确不做的事

- **结构完成 ≠ 质量**：`completion_gaps` 闭合、`verdict=pass`、证书可达
  `complete` 只说明"计划在结构上可执行并可闭合缺口"，不代表内容质量。
- **未接门禁**：本包尚未接入 `check45` / M1 事件库 / gate；证书与 session
  summary 目前只作为运行结果字段，不会让任何门禁变绿。
- 不做模型打分、不做联网、不写外部状态；`memory` 只存 digest/计数/原子簇，
  不存 goal/artifact 内容。

## 测试

仓库测试（unittest 风格）：

```bash
python3 -m pytest desktop/tests/test_reasoning_*.py -q
```

覆盖：包/策略校验、`nf-step-verdict/1` 无标量、β≤0.5、预算守恒、搜索确定性/
transposition/降级、session 只读与 mode 行为、portfolio 记账、anytime gap 单调、
memory Beta/漂移/无内容、counterfactual bounded/unknown、certificate 三值与
六类篡改、parallel 兜底、CLI `--reasoning` 接线。
