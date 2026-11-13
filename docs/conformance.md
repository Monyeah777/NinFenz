# 一致性报告工件（conformance）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

## 是什么

把**廉价、离线可复算**的契约跑一遍并封缄成一件可归档、可比对的产物：
`protocol/conformance_report.json`（每契约 id/ok/detail/digest + **Merkle 根** + `verdict`）。
动机与 MCOP 同源：**make it checkable instead of trusted**（NF 同样是 Bus Factor 1）。

## 契约表（27 条 · 2026-11-13 复核）

`canonical-digest-determinism` · `schema-clean` · `purity-clean` · `doc-kinds` ·
`library-verify` · `library-projection` · `pipeline-dryrun` · `module-signature` ·
`io-types` · `type-backlog` · `event-backing` · `declaration` · `rfc-heads` · `patterns` ·
`endpoint-contract` · `knowledge-sources` · `assertions` · `modeling` · `decisions` ·
`handover` · `postmortem` · `audit` · `cognition` · `st-quality` · `mcp-package` ·
`state-front` · `public-surface`。

现场结论（2026-11-13 实跑）：**27/27 conformant**，`root = c94a8576675b749e`。

## 怎么用

```bash
python scripts/nf.py conformance            # 跑一遍 + 与在盘报告比对（在盘 != 实时重算即 FAIL）
python scripts/nf.py conformance --write    # 归档当前报告（变更后必须重写）
```

冻结链位置：`conformance --write` → `approve protocol/conformance_report.json` → `receipts --scope protocol --write`
（真源 `core/release_gate.DEFAULT_FREEZE_CHAIN`；`nf release --freeze --apply` 按此序执行）。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 契约条数 | 10 条 | **27 条**（`contracts` 长度 27） |
| 现场 verdict | 未写死 | **conformant 27/27**，root `c94a8576675b749e` |
| 报告结构 | id/ok/detail/digest + Merkle 根 + verdict | **不变**（另含 `passed`/`total`） |
| 与 verify.sh 关系 | 「不等于全量门禁」（当时未记门禁条数） | **门禁已到 check1-42**（42 道）；本件仍是「可归档的第二维护者视角」，只收离线可复算契约 |
| 冻结链 | 未提 | **conformance → approve → receipts**（`nf release --freeze` 消费） |
| 提交纪律 | 「verdict != conformant 不得声称可提交」 | **不变** |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py conformance            # 比对在盘报告（不等于实时重算即 FAIL）
python -m pytest desktop/tests/test_conformance_run.py desktop/tests/test_conformance_scan.py -q
```

- 引用本文时：「10 条」= **2026-09-14 快照**；现行 27 条，以 `protocol/conformance_report.json` 实读为准。
- 纪律：改契约或改门禁后必须 `--write` 重写报告并随提交归档；`verdict != conformant` 时不得宣称可提交。

## 边界

- 本工件**不等于** `verify.sh` 全量门禁（后者 check1-4x，2026-11-13 实测 check1-42；含动态与内容面）；这里是"一次跑完、
  可归档的第二维护者视角"，刻意只收**离线可复算**的契约，避免重复跑与循环依赖。
- `verdict != conformant` 时不得宣称本波可提交。
