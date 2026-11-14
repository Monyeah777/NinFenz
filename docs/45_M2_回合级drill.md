# 45 A2 · 回合级 drill（执行转录回合断言）

> ⛔ 操作指令：回合级断言口径（阅读即执行）。
> 最后更新：2026-11-13

> **状态：回合级断言口径沿用（2026-11-13 复核样本与调用面）**——R-R1–R-R4 判据不变；样本集新增真实语料自跑样本 `selfrun-2026-10-20.json`；常驻判据 `test_round_drill` 6 例；`nf assemble --check-trace` 的回读要求「trace 写时带过 `--rounds`」——缺则 exit 2「未执行漂移断言」（见文末「现状对照」）。

## 用途

在 execution_drill 句子级之上，把整段执行转录按回合切块断言：
- R-R1 每回合至少一条引用（§ / 第N节·步·章 / L行 / 模块编号）；
- R-R2 每回合有推进/状态留痕（推进/进入/写回/快照/存档/状态）；
- R-R3 每回合不得出现装配允许集外编号；
- R-R4 回合计数连续性（跳号 → WARN 清单，不 FAIL）。

样本集（`desktop/tests/fixtures/execution/rounds/`）覆盖 R-R1–R-R4：`good.json`（合规）· `bad.json`（R1+R3）· `bad_r2.json`（R2）· `bad_r3.json`（R3）· `gap_ok.json`（R4 跳号 → 仅 WARN，verdict 仍合规）· `selfrun-2026-10-20.json`（真实语料自跑转录样本，2026-10-20 增补）。

## 调用

- 独立：`python -c "from core import round_drill as rd; rd.scan(转录文本, allowed)"`
- 装配验收联用：`nf assemble "<需求>" --check <转录.md> --rounds`
- 轨迹回读自证：`nf assemble "<需求>" --check-trace trace.json`——**要求 trace 写时带过 `--rounds`**（回合级判定的口径来源），否则 exit 2「未执行漂移断言」，不把「没做」读成「通过」。

## 转录标记约定

行首 `回合 N：` 或 `第 N 回合` 开新回合；未检出回合标记 → FAIL（提示转录格式）。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 当时（本文快照） | 现行（读到本行时请重跑确认） |
|---|---|---|
| 判据 | R-R1–R-R4（4 条） | **不变**（`core/round_drill.py` 顶部文档串为真源） |
| 样本集 | 5 份（good/bad/bad_r2/bad_r3/gap_ok） | **6 份**（+`selfrun-2026-10-20.json` 真实语料自跑样本） |
| 常驻判据 | 未计入 | `test_round_drill` **6 例**（R1/R2/R3/R4 + 通过路径） |
| 调用面 | 独立 scan + `--check --rounds` | 同左；另有 **`--check-trace` 回读**（须 trace 带 `--rounds`，否则 exit 2） |
| 状态头口径 | 06 §11 | **不变**（回合状态头 v1；见 `docs/42_M2_回合状态头_v1.md`） |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/nf.py assemble --help   # 看 --check / --rounds / --check-trace 参数
python -m pytest desktop/tests/test_round_drill.py -q   # 6 例回合级判据
```

- 判据真源：`desktop/src/core/round_drill.py`（R-R1–R-R4 注释即口径）；样本在 `desktop/tests/fixtures/execution/rounds/`。
- 引用本文时：4 条判据 = 长期口径；样本份数与测试例数以目录/文件实读为准。
