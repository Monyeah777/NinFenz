# 隐私 QA（L14）

> ⛔ 操作指令：本件是 NF-Final §13A L14「隐私/法务」层的 QA 报告（G0/QG5 产物）；每条指标须有可复跑证据，未达标项进质量债，不写成全绿。
> 状态：v1（G0 · 2026-11-14）· 依据：`NF-Final-方案-2026-11-13.md` §13A.2 L14 / §15A.1
> 上层：`PRIVACY.md`、`docs/privacy/{DATA_MAP,DPIA,RETENTION}.md`、`protocol/privacy.json`

## 质量目标

- 数据最小化：证据/日志不存正文、不存绝对路径；凭据/PII 有检测与脱敏。
- 保留/删除可执行：每类数据有保留模式、删除方式与可复原证据；机密/受限类删除留 blame。
- 无秘密入仓：`results/`、`protocol/` 声明面无高置信凭据/PII；不可判定件显式呈报。
- 不越级声明：文档不写「合规/认证/不可抵赖」的正向声明。

## QA 活动与指标

| 活动 | 指标 | 门禁/判据 | 本轮实测 |
|---|---|---|---|
| 数据地图完整性 | 8 类数据、位置在场、分级四词表 | `test_privacy_contract.py::test_registry_*` | 8/8，路径全部在场 |
| 删除证据 | 每类删除 `{kind,ref}` 合法；机密/受限带 blame | 同上（复用 `core.delete_evidence`） | 8/8 合法 |
| PII/凭据扫描 | 声明面零命中；fixture 检测+脱敏抽样通过 | `test_privacy_contract.py::test_pii_*` | 见测试输出（0 命中） |
| 保留面约束 | `ephemeral` 落点被 gitignore；`immutable` 删除走归档+证据 | `test_privacy_contract.py::test_retention_*` | 通过 |
| 声明一致性 | 文档 ↔ 真源无漂移；禁用词只在否定语境 | `test_privacy_contract.py::test_docs_*` | 通过 |

## 质量债 / 残余风险

| 项 | 级别 | 说明 | owner | 复审 |
|---|---|---|---|---|
| 仓库外用户态数据（`~/.NinFenz`）不在仓内扫描面 | P2 | 本仓扫描面只覆盖入仓文本；用户态数据按 `PRIVACY.md` 删除流程处理 | user | 每次数据类变更 |
| 用户主动把私密内容写进公开仓不可撤销 | P2 | 发布边界只拒绝内部目录，不阻止用户手写 | user | 每次发布 |
| 无法律审核/合规认证 | P2 | 明确不作为对外保证（文档否定语境约束） | maintainers | 每次对外文案 |

## 结论

- 本轮隐私面判据：数据地图 + DPIA + 保留/删除测试全部可复跑；**不声称合规/认证**，残余风险显式登记。
- 未跑：无（本层不依赖外部服务）；全量 `verify.sh --full` 属 CI 档，不在本层结论内。
