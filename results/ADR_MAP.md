# NF Final 裁决映射（方案 §16.2 → `nf-adr/1` 登记投影）

> 状态：v1 · 2026-11-14 · 对应 `NF-Final-方案-2026-11-13.md` §16.2（WP-04）
> 依据：`decisions/ADR-0000`（决策正文不进公开仓，公开面只留可校验登记投影）、`protocol/adr/registry.json`（`nf-adr/1`）、`desktop/tests/test_nf_final_adr_contract.py`
> ⛔ 操作指令：本件是「方案裁决 → 注册表条目」的映射与实施状态；改注册表后必须重跑 `python scripts/adr_check.py --write` 与契约测试，不得手改 `results/ccos/adr_reconcile.json`。
> 性质：结果/状态件（映射与实施状态），不是决策正文。决策正文按 `ADR-0000` 留私有 Plan 仓 `governance/decisions-archive/`。

## 0. 结论

- 方案 §16.2 的 12 条裁决**全部有登记投影**：11 条新登记为 `ADR-011`…`ADR-021`，方案 ADR-0008 由既有 `ADR-010`（trust-noscore）覆盖，不重复登记。
- 编号偏差：方案用 4 位（ADR-0001…0012），注册表既有 3 位（ADR-001…010）；为保持既有编号连续，新增从 `ADR-011` 起，方案号记录在条目的 `plan_ref` 字段里（`ADR-0008` 在 `ADR-010` 上）。
- 每条新裁决都带 `topic`/`decision`/`falsifier`/≥2 件在场 evidence；`python scripts/adr_check.py --check` 与 `test_nf_final_adr_contract.py` 双判据可复跑。
- **实施状态不是全绿**：11 条里仅 `ADR-019`（生成物不可手改）与既有 `ADR-010` 有完整落点证据，其余为 PARTIAL/ABSENT，缺口对应 WP 见 §2。裁决「已登记」≠「已实现」，本表把两者分开写。

## 1. 映射表

| 方案 ADR | 注册表 ADR | topic | 裁决一句话 | 实施状态 | 缺口 → WP |
|---|---|---|---|---|---|
| ADR-0001 | **ADR-011** | plane-independence | 生产/治理双平面独立，契约是唯一边界对象；生产 MUST NOT import 治理，反向亦然 | PARTIAL（trust 验证器可独立运行；无 import 边界检查） | WP-02（`check_independence.py` + check49） |
| ADR-0002 | **ADR-012** | wiki-projection | Wiki 是投影不是第二真源；生成物禁止手改、须回指 spec_ref/digest | PARTIAL（生成器纪律已存在；Wiki 编译器缺） | WP-10（G1） |
| ADR-0003 | **ADR-013** | spec-driven | 无 spec 不生成；槽位有界；未知/歧义 spec fail-closed | PARTIAL（契约/machine_contract 在；spec 编译器缺） | WP-11（G1） |
| ADR-0004 | **ADR-014** | agent-adapter | Agent 是可替换 adapter，不在架构中心 | PARTIAL（7 个 adapter 模块 + 单测；无统一契约） | WP-20（G2） |
| ADR-0005 | **ADR-015** | ecosystem-reuse | 签名/时间戳/透明日志复用 in-toto/Sigstore/RFC3161，不自造 | PARTIAL（DSSE/RFC3161/in-toto/Rekor 适配在场；`cosign` 不在场） | WP-31（G3） |
| ADR-0006 | **ADR-016** | policy-adapter | 策略复用 OPA/Cedar，不自造策略引擎 | ABSENT（仅 `nf-trust-policy/1` 契约） | WP-42（G3/G4） |
| ADR-0007 | **ADR-017** | ai-bom-standard | AIBOM/模型卡对齐 CycloneDX/SPDX | PARTIAL（interop cdx/sbom 与 model card 在；AIBOM 导出缺） | WP-41（G4） |
| ADR-0008 | **ADR-010** | trust-noscore | AI 证据不写回运行时评分（既有 trust 裁决覆盖） | SUPPORTED（`verify.schema.json` `no_scoring` 恒真） | — |
| ADR-0009 | **ADR-018** | governance-attachment | 附件模式 none/observe/require，默认 none/observe | ABSENT（无三模式实现） | WP-32（G3） |
| ADR-0010 | **ADR-019** | generated-immutable | 生成物不可手改；生成物 == 实时重算或 digest 钉住 | SUPPORTED（check33/35/37 等判据在场） | 随 Wiki 生成面扩展（G1） |
| ADR-0011 | **ADR-020** | agent-portability | 跨 Agent 可移植是一等验收（同 spec 双 adapter 过同一校验） | ABSENT（无 parity 判据） | WP-20（G2） |
| ADR-0012 | **ADR-021** | self-audit-delivery | 自扫描/自补全是交付一部分；停止条件不满足不得过 Gate | PARTIAL（trust 面自审计在；方案级 S0–S15 缺） | WP-50（G5） |

## 2. 复现与判据

```bash
python scripts/adr_check.py --check                     # 登记投影 == 重算（含 evidence 在场对账）
python -m pytest desktop/tests/test_nf_final_adr_contract.py -q
python -m pytest desktop/tests/test_trust_adr_contract.py desktop/tests/test_decisions.py \
                 desktop/tests/test_publish_boundary.py -q
```

判据含义：

1. **字段**：id/title/status/topic/decision/falsifier 齐备；current 主题唯一；supersedes 无环（`core.adr.validate_adr`）。
2. **证据**：每条 evidence 指向仓内**在场**文件（`core.adr.reconcile`）。
3. **方案覆盖**：`plan_ref` 恰覆盖 ADR-0001…ADR-0012 各一次（`test_nf_final_adr_contract.py::test_registry_valid_and_evidence_present`）。
4. **发布边界**：`decisions/` 无真实决策件、`docs/adr/` 不存在（同上 `test_publish_boundary`）。
5. **变异自证**：删裁决 / 清空 falsifier / 改坏 evidence / 丢语义词 / 复制 current topic / 改错 plan_ref 六类注入都必须红。

## 3. 与方案 §16.2 的偏差

- **位置**：方案写「落 `docs/adr/`」，本仓按 `ADR-0000` 裁决落 `protocol/adr/registry.json`（机器可校验登记投影），散文正文留私有 Plan 仓；`docs/adr/` 被发布边界判据显式禁止。
- **编号**：方案 4 位 vs 注册表 3 位，新增自 `ADR-011` 起，映射由 `plan_ref` 字段承载（本表 §1 可读版）。
- **ADR-0008 不重复登记**：其语义已由 `ADR-010`（trust-noscore）承担，重复登记会产生同义裁决与 topic 冲突。
