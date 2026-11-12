# 执行结果跑分台（bench）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

> **复核（2026-11-13）**：五维口径与「离线确定性、不调模型、分数只是相对可比量」不变；补四处现状：① 五维**权重显式**（structure 0.30 / traceability 0.30 / closure 0.20 / prose 0.10 / selfcheck 0.10）；② 用例套件现 **2 例**（`p02-campus-emotion` / `p03-western-cross`）；③ `bench run` 五旗标（`--case` / `--artifact` / `--model` / `--out` / `--json`）；④ **别与端壳混**：2026-09-09 退役的是 GUI 端壳基准脚本（已删，退役清单见 `docs/L3_FROZEN.md`），`nf bench` 是**机制面执行结果跑分台**，仍在册。见「§现状对照」。

## 是什么

把「任意 AI 按 NF 协议产出的成品」丢进用例，做**五维确定性评分**并留档，支持多跑/多模型比对
（机制借鉴 ACP 的 benchmark suite）。它不做质量宣称——分数是**相对可比量**。

维度与权重（真源 `core/bench.WEIGHTS`）：

| 维度 | 判什么 | 权重 |
|---|---|---|
| `structure` | 八段骨架完整度 | 0.30 |
| `traceability` | 编号真值 / 无编造 | 0.30 |
| `closure` | 事件闭合自陈（触发/结算计数 + 闭合声明） | 0.20 |
| `prose` | 正文 AI 味（`prose_lint`） | 0.10 |
| `selfcheck` | 自检清单完整度 | 0.10 |

前两维复用 `assemble_plan.check`（即 `nf assemble --check` 的同一引擎），第三维用样本自陈，第四维用 `prose_lint`。总分为加权和（0–100）。

## 怎么用

```bash
python scripts/nf.py bench run --case desktop/tests/fixtures/benchmark/suite/p03-western-cross \
    --artifact <产物.md> --model <模型名> --out runs/model-a.json
python scripts/nf.py bench compare runs/*.json
python scripts/nf.py bench report runs/*.json
```

| `bench run` 旗标 | 作用 |
|---|---|
| `--case` | 用例目录（含 `case.json`） |
| `--artifact` | 被评产物 md（缺省 = 用例 `default_artifact`） |
| `--model` | 跑次来源标识（模型/客户端名） |
| `--out` | run 记录写盘（缺省 = 打印） |
| `--json` | 结构化输出 |

## 边界

- 只跑**离线确定性**判据，不调模型；判据取用例 `expected`（`min_total` 总分下限 + `min_segments` 八段骨架下限，任一不达即判 `fail`——声明即判据）。
- 跑分是"外部实测的容器"（E1/E2/Y5 回填时把产物丢进来即可比对），**不替代** verify 门禁。
- **同名不同物**：端壳 GUI 基准脚本已随 L3 端壳线 2026-09-09 永久退役（不在树，见 `docs/L3_FROZEN.md`）；`nf bench` 属机制面跑分台（check36 治理面消费其用例/复现性），两者不可互相指代。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 五维 | structure / traceability / closure / prose / selfcheck | **不变**（权重 0.30/0.30/0.20/0.10/0.10，真源 `core/bench.WEIGHTS`） |
| 用例套件 | 1 例（p03-western-cross） | **2 例**（+`p02-campus-emotion`） |
| 用例判据 | `expected` = 总分下限 + 骨架下限 | **不变**（`min_total` / `min_segments`） |
| CLI 面 | run / compare / report | **不变**；run 五旗标见上表 |
| 常驻判据 | 未计 | `test_governance_faces` 的 bench 用例（用例数下限 + 确定性复评 + 低分判 fail + 多跑比对） |
| 与端壳关系 | 未提 | 端壳 GUI bench 已退役；本命令**在册**（`nf bench --help` 可用） |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py bench run --case desktop/tests/fixtures/benchmark/suite/p03-western-cross --json
python scripts/nf.py bench compare runs/*.json
python scripts/nf.py bench report runs/*.json
```

- 引用本文时：「离线确定性五维、分数为相对可比量、不替代门禁」= 长期口径；用例数与权重以 `core/bench.py` 与套件目录实读为准。
- 真实外部跑分按 STRATEGY 封闭期（E1/E2/Y5 作者触发）回填，agent 不主动安排外部实测。
