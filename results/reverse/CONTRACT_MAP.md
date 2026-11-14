# 契约地图（CONTRACT MAP）

> ⛔ 操作指令：本件是 §4A R1（契约提取）人读结果；机读真源 `results/reverse/contracts.json`（`nf-reverse-contracts/1`），判据 `desktop/tests/test_reverse_contracts.py`。每条契约需能指到 artifact、字段、消费方、证据；隐式契约必须写风险，未文档化不得写成已文档化。
> 状态：v1（2026-11-14 · G0 §4A R1）· 前置：`results/reverse/INVENTORY.md`（R0）
> 方法：真源 → 机读契约（schema/注册表/声明件）→ 消费方 → 证据逐层提取；隐式契约从代码约定与纪律文档反推。

## 1. 显式契约（11 组）

| 编号 | 契约层 | artifact 数 | 关键字段 | 消费方（例） | 状态 |
|---|---|---|---|---|---|
| X-01 | IDL schema 九件（`protocol/schema/`） | 9 | id/name/category/mounts/structure/layers/protocol/freeze_chain | `core/schema_lint.py`、`verify.sh` | documented |
| X-02 | trust 契约十四件（`protocol/trust/`） | 14 | bundle_id/merkle_root/inclusion_proofs/anchors/no_scoring/issuers | `trust/bundle.py`、`trust/verify.py`、`scripts/trust_verify.py` | documented |
| X-03 | 生产平面五件（`protocol/production/`） | 5 | slot/spec_refs/budget/steps/fallback/citations | `test_schema_reference.py`、`test_assurance_contract.py` | documented（无编译器） |
| X-04 | 运行时注册表（`core/registry.json`） | 1 | modules/mount_points/subscriptions/protocols/truth_source | `registry_loader.py`、`registry_sync.py` | documented |
| X-05 | 模块 machine_contract（`04_模块库/`） | 1+ | machine_contract/inputs/outputs/mounts | `machine_contract.py`、`verify.sh` | documented |
| X-06 | 管线声明（`03_管线库/`） | 3 | id/name/structure/layers/dependencies | `pipeline_loader.py`、`verify.sh` | documented |
| X-07 | 资产契约台账（`protocol/asset_contracts.json`） | 1 | data/code/script/index/chains | `asset_contract.py`、`verify.sh` | documented |
| X-08 | 语言面注册表（`protocol/locales.json`） | 1 | locales/docs/canonical/coverage/source_sha256 | `locales.py`、`verify.sh` | documented |
| X-09 | 域包 DOMAIN_SPEC（`community/*/outputs/`） | 100 | kind/code/domain/section/subdivisions/content_tier | `domain_pack.py`、`verify.sh` | documented（字段族不统一） |
| X-10 | 跨域登记族（隐私/运维/法务/AI/a11y/i18n/保证/RAID/产品/CQ） | 9 | schema/claims_boundary/data_classes/risks/countermetrics | 各 `test_*_contract.py` | documented（测试消费） |
| X-11 | 评测协议/效度（`protocol/eval*/`） | 2 | frozen_before_run/dimensions/preregistration/inter_rater | `eval_harness.py`、`eval_validity.py` | documented |

## 2. 隐式契约（8 组）

| 编号 | 层次 | 落点 | 关键字段/约定 | 消费方 | 风险 |
|---|---|---|---|---|---|
| I-01 | canonical JSON + 域分隔 | `core/trust/canonical.py` | canonical_bytes/LEAF_DOMAIN | bundle/dsse/signature | RFC 8785 子集未全量对照 |
| I-02 | Merkle/叶前缀 | `core/trust/bundle.py` | leaf_hash/merkle_root/inclusion_proof | trust verify、Node/.NET parity | 变更需重跑冻结向量 |
| I-03 | 路径包含性 | `core/paths.py` | validate_path | ledger/atomic/keys | symlink/短路径未数学证明 |
| I-04 | UTC/ISO-8601 | `core/iso8601.py` | is_iso_instant/parse_instant | ops/i18n/trust | 本地时区仅显示层，靠审查 |
| I-05 | 错误码 + 修复指引 | `error_codes.py`/json | 「修复指引」约定 | verify/purity_scan | 文案约定非 schema 必填 |
| I-06 | 原子写 | `core/atomic_write.py` | write_text | independence/ops/repo_stats | 跨文件系统未测 |
| I-07 | 冻结链顺序 | `docs/release.md` | conformance→approve→receipts | nf.py/verify.sh | 未由 schema 强制 |
| I-08 | 生成物禁手改 | 生成区文件头 | 「生成/禁止手改」 | geo_export/verification_cards | 新增生成区需同时加判据 |

## 3. 缺口（G-01…G-05）

- G-01 生产/Wiki/spec 契约无运行时编译器（G1/G2）。
- G-02 trust 十四件 schema 未统一接入 verify 逐件校验（当前测试 + 部分 check）。
- G-03 隐式契约未全量机检（R3 耦合 / R6 不变量会继续补）。
- G-04 100 份域包 DOMAIN_SPEC 未统一 schema。
- G-05 跨域登记族未进 verify check（G5 候选 check49/50 扩展）。

## 4. 复核命令

```bash
python -m pytest desktop/tests/test_reverse_contracts.py -q
python -c "import json;d=json.load(open('results/reverse/contracts.json',encoding='utf-8'));print(len(d['explicit']),len(d['implicit']),len(d['gaps']))"
```

## 5. 交接（R2–R6）

- R2 行为重建：用本件「消费方」列逐个读调用链（仓库面 → 生成物 → 校验链 → 失败语义）。
- R3 耦合：从 X-04/X-05/X-06 的字段与 import 图交叉，补 real 耦合/重复实现清单。
- R4 失败考古：从证据/错误码/check 面回溯历史失败模式。
- R5 同行对照：只作机制借鉴，不引入外部背书（STRATEGY §3）。
- R6 不变量：把 I-01…I-08 转成可机检不变量清单（含反例），回填 G-03。
