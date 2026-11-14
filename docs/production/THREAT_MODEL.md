# NF 生产平面威胁模型（NF-Final §8：边界 / STRIDE / 失败矩阵）
> ⛔ 操作指令：本文每条威胁绑定信任边界、控制点与判据；判定可跑（见文末复核命令）。改行必须同步 `results/production/threat_vectors.json`，否则判据红。
> 状态：v1（G0 · 2026-11-14）· 性质：边界与威胁声明（能防 / 不能防）· 机器向量：`results/production/threat_vectors.json`（`nf-threat-vectors/1`）
> 上位：`NF-Final-方案-2026-11-13.md` §8；Trust Fabric 面另见 `docs/trust/THREAT_MODEL.md`（两份不互相替代）
> 纪律：不把 T0/T1 写成 T3/T4；不写「不可抵赖 / 合规 / 认证」；未实现项写 `planned_gate`，不静默关闭。

## 这份文件管什么

- 覆盖方案 §8 的三张表：**§8.1 六条信任边界**、**§8.2 STRIDE 八行**、**§8.3 关键失败矩阵八行**。
- 每条威胁给「控制点 + 判据 + 状态」；状态只有四值：`enforced`（有代码 + 测试/门禁）/ `partial`（部分在场，缺口指向阶段）/ `planned`（未实现，禁止写成已防）/ `UNOBSERVABLE`（不可静态观测，须写理由）。
- 信任边界登记在 `protocol/boundaries.json`（`nf-boundaries/1`：边界 → 协议代码件 + 协议文档件，两件必须在场），本文与向量表逐条引用其 `B-0x` 编号。

## 信任边界（方案 §8.1，六条）

| 编号 | 边界 | 内容 | 威胁 | 当前控制 | 状态 |
|---|---|---|---|---|---|
| B-01 | 真源↔Wiki | spec/页面投影 | 第二真源、漂移、断链 | `scripts/geo_export.py`（生成物禁止手改 + 摘要判据）；`docs/standards/index.md` | partial（Wiki 编译器 G1） |
| B-02 | Spec↔Agent | task/context | prompt injection、越权、编造引用 | `desktop/src/core/injection_budget.py`（注入预算）；`06_Agent执行协议.md` | partial（slot/citation 运行时校验 G1） |
| B-03 | 生产↔治理 | 事件/产物 | 事件污染、证据注入、强制依赖 | `desktop/src/core/independence.py`（check49 全 core 闭包零跨界）；`patterns/dependency-direction/PATTERN.md` | enforced |
| B-04 | 治理↔外部 | 签名/TSA/日志 | 伪造、回拨、分裂视图 | `desktop/src/core/trust/public_anchor.py`（inclusion+SET+目标绑定）；`docs/trust/WITNESS_SPEC.md` | partial（公共日志提交/外部 witness 属外部操作） |
| B-05 | 本地↔外部材料 | 文档/网页 | 注入、角色伪造、隐私 | `desktop/src/core/fetch_guard.py`（取用前校验）；`SECURITY.md` | partial（上下文角色隔离 G1） |
| B-06 | 模型↔证据 | model card/eval | 替换、评测伪造 | `desktop/src/core/trust/model_card.py`（模型摘要绑定，替换即失效）；`results/trust/CLAIM_MATRIX.md` | enforced（评测本身不在本仓） |

## STRIDE 矩阵（方案 §8.2，八行）

| 编号 | 类别 | 威胁 | 控制点 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-TH-01 | S | 伪造 issuer/Agent 身份 | DSSE/PAE + issuer registry（keyid/alg 白名单、生命周期/吊销 fail-closed）+ typed entity 准入 | `desktop/tests/test_trust_dsse.py`、`test_trust_keys.py`、`test_trust_entity.py` | enforced |
| NF-TH-02 | T | 改 Wiki/spec/事件内容 | 生成物禁止手改 + 生成器判据（Wiki/spec 编译器待 G1） | `docs/standards/index.md`、`docs/verification-cards.md`、`scripts/geo_export.py` | partial（G1） |
| NF-TH-03 | T | 删尾事件并重算本地摘要 | prev 链 + 链头摘要 + 外部锚/时间戳核验（锚缺失显式不可判定） | `desktop/tests/test_trust_process.py`、`test_evidence.py`、`test_trust_anchor.py` | enforced |
| NF-TH-04 | R | 重放旧证据/旧模型卡 | 时效 + 吊销表 + 模型摘要绑定（替换使旧证据失效） | `desktop/tests/test_revocations.py`、`test_timestamp.py`、`test_trust_model_card.py` | enforced |
| NF-TH-05 | I | 证据/上下文泄露或被外部材料升级角色 | 外部材料按数据处理 + 参数边界 + 注入预算（角色隔离待 G1） | `desktop/tests/test_trust_boundary.py`、`test_injection_budget.py` | partial（G1） |
| NF-TH-06 | D | 超大 Wiki/上下文资源耗尽 | 证据单件/整包上限 + 注入预算（Wiki/任务预算上限待 G1） | `desktop/tests/test_injection_budget.py`、`test_evidence.py` | partial（G1） |
| NF-TH-07 | E | 类型/权限混淆与越权组合 | 类型注册表 + typed_admissibility + 组合准入（未知 type/越权组合 fail-closed） | `desktop/tests/test_trust_types.py`、`test_trust_entity.py` | enforced |
| NF-TH-08 | S | 自签自验冒充外部锚 | 验签方 ≠ 签名方（独立进程）+ 等级只写报告缺项；cosign 不在场按 WARN 记 | `verify.sh`（check42）、`desktop/tests/test_trust_verify.py`、`desktop/src/core/provenance_external.py` | enforced |

## 关键失败矩阵（方案 §8.3，八行）

| 编号 | 攻击 | 期望 | 边界 | 判据 | 状态 |
|---|---|---|---|---|---|
| NF-FM-01 | 手改 Wiki 页 | 重编译覆盖 + 生成物/新鲜度检查 FAIL | B-01 | `docs/standards/index.md`、`scripts/geo_export.py`、`docs/verification-cards.md` | partial（G1） |
| NF-FM-02 | 删除一个 spec/页 | 覆盖/链接检查 FAIL（Wiki 建后为 wiki check FAIL） | B-01 | `docs/standards/index.md`、`scripts/geo_export.py` | partial（G1） |
| NF-FM-03 | Agent 编造引用 | 输出校验 FAIL（引用必须命中 wiki id/spec ref） | B-02 | `protocol/production/task.schema.json`、`desktop/tests/test_schema_reference.py` | planned（G1） |
| NF-FM-04 | 用错 spec/模块 | spec 编译/装配 FAIL（未知/缺失 spec fail-closed） | B-02 | `protocol/production/spec.schema.json`、`desktop/tests/test_schema_reference.py` | planned（G2） |
| NF-FM-05 | 生产被治理阻塞 | 默认不阻塞；require 才阻断（双平面 import 边界静态可证） | B-03 | `desktop/tests/test_independence.py`、`scripts/check_independence.py` | enforced |
| NF-FM-06 | 治理验证 NF 外产物 | 通过（独立 bundle/policy 复算；缺外产物端到端 fixture） | B-03 | `desktop/src/core/trust/verify.py`、`desktop/tests/test_trust_verify.py` | partial（G3） |
| NF-FM-07 | 删尾事件并重算 | 锚/签名 FAIL | B-04 | `desktop/tests/test_trust_process.py`、`test_trust_anchor_evidence.py` | enforced |
| NF-FM-08 | 撤销 issuer 后旧签名 | 验证失败/降级报告 | B-04 | `desktop/tests/test_revocations.py`、`test_trust_keys.py` | enforced |

## 状态词表与证据规则

- `enforced`：控制点在代码里，且 `results/production/threat_vectors.json` 的 `evidence` 至少含一个 `desktop/tests/**` 或 `scripts/**` 或 `verify.sh`（判据机检）。
- `partial`：控制点部分在场；必须写 `planned_gate`（G0–G5），不得把缺口藏进 `enforced`。
- `planned`：未实现；必须写 `planned_gate`，文档/报告不得出现「已防」表述。
- `UNOBSERVABLE`：不可静态观测；必须写 `reason`，进 `ACCEPTED-RISK` 由 owner 复审。

## 与 Trust Fabric 威胁模型的关系

- `docs/trust/THREAT_MODEL.md` 判**治理/信任面**（T0–T4 等级、DSSE/锚/删除矩阵）；本文判**NF-Final 生产/装配面**（§8 六边界 + STRIDE + 失败矩阵）。
- 两份共享同一纪律（不越级声称、未实现写 OPEN/planned、证据可复跑）；编号空间不重叠：trust 用 `TH-xx`/`DT-xx`，本文用 `NF-TH-xx`/`NF-FM-xx`。

## 复核命令

```bash
python -m pytest desktop/tests/test_production_threat_vectors.py -q
python -m pytest desktop/tests/test_boundaries.py -q
python scripts/nf.py check boundaries 2>/dev/null || true   # 边界登记若无 CLI 入口，以上面测试为准
```

## 不承诺

- 本文不声称「不可抵赖 / 合规 / 认证」；`partial`/`planned` 项就是未完成的控制面，不作为对外保证。
- T3/T4（外部见证/公共锚已提交）不在本文声称范围；本仓只提供离线复算与显式缺项。
