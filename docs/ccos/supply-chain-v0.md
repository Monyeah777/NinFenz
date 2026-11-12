# 供应链对象 v0（材料清单 + 验证器摘要 + 结论绑定）

状态：**已实装**（`core/sbom.py`、`core/verifier_version.py`、`scripts/self_audit_probe.py`、`scripts/sbom.py`）。
> **最后更新：2026-11-13（复核）**：三摘要口径与「不做签名/不覆盖被测内容/非全仓清单」边界**逐项复核不变**；
> 现状数字：材料清单 **`count` 572 == `materials` 572**（`scripts/sbom.py --check` 绿）；`verifier_digest` 覆盖
> **`JUDGE_FILES` 10 个判定面脚本**；`verifier_status` 当前 **`current`**（来源 `results/ccos/self_audit.json`），
> 三态 `current/stale/unknown`（`stale` 退出码 1）。见「§现状对照」。

## 这份文档解决什么

发布结论此前只回答一个问题：「某个 SHA 的树是绿的」。但有人要把结论拿去用时，
真正想知道的还有两件：

1. **是谁判的**——判定逻辑本身改过没有；
2. **基于哪些输入**——这份交付由哪些文件构成。

本仓把这两个问题各做成一个**可复算的摘要**，并让发布结论同时绑定它们。

## 三个摘要各管一段

| 摘要 | 计算方式 | 回答的问题 |
|---|---|---|
| `head_start` / `head_end` | git rev-parse | 判的是哪棵树 |
| `verifier_digest` | 判定面脚本（10 个门禁脚本）内容 sha256 折叠 | 谁判的 |
| `materials_digest` | 显式范围内文件（协议 / 判定脚本 / 核心代码 / 收入文档）逐个 sha256 再折叠 | 基于哪些输入 |

三者互相咬合：改棵树 → 全部重算；改判定脚本 → 验证器摘要变；改协议或代码 → 材料摘要变。

## 材料清单（`nf-sbom/1`）

```bash
python scripts/sbom.py --write    # 生成 results/ccos/sbom.json
python scripts/sbom.py --check    # 与现场比对（材料不在场 / 摘要不符 / count 被改 都会报）
```

口径：只覆盖**显式范围**，不是全仓清单——范围越窄越好核，成本也不至于把每次检查拖长。

## 结论可复用性（`verifier_status`）

```bash
python scripts/verifier_status.py                    # 查仓库记录的自省摘要
python scripts/verifier_status.py --conclusion F.json  # 查任意一份结论文件
```

三态：`current`（可引用）/ `stale`（验证器已变，必须重跑）/ `unknown`（没有可比对的摘要）。
`stale` 退出码 1，可直接当脚本里的 gate。

## 现状对照（2026-11-13 · 以实跑为准）

| 面 | 本文声明 | 复核结果（读到本行时请重跑） |
|---|---|---|
| 三摘要 | head / verifier_digest / materials_digest | **不变**（互咬合：改树全变、改脚本验证器变、改输入材料变） |
| 材料清单 | 显式范围，非全仓 | **`count` 572 / `materials` 572**（`--check` 绿） |
| 验证器摘要 | 判定面脚本 10 个 | **`verifier_version.JUDGE_FILES` 恰 10 项** |
| 结论可复用性 | current / stale / unknown | **三态在文**；`stale` 退出码 1（可当 gate） |
| 当前状态 | — | **`current`**（来源 `results/ccos/self_audit.json`） |
| 实现件 | core/sbom + verifier_version + self_audit_probe + sbom | **四件全在** |
| 边界 | 不做签名 / 不覆盖被测内容 / 非全仓 / results 不入清单 / 跨机不可比 | **五条全在** |

> 本表只作「当时 → 现行」导航，不替代实跑。

## 复现与引用口径

```bash
python scripts/sbom.py --check            # 材料清单 == 现场（材料/摘要/count 任一不符即红）
python scripts/verifier_status.py         # 三态（stale 退出码 1，可直接当 gate）
python -m pytest desktop/tests/test_sbom.py desktop/tests/test_verifier_status.py -q
```

- 引用本文时：「三个摘要都是自我摘要，不做签名」= 长期口径；材料清单只覆盖显式范围，`results/` 属产出不入清单。
- 若 `sbom --check` 红：按提示重跑 `--write` 并 review 差异（材料增删应有明确原因）。

## 边界（必须写清）

- **不做签名**：三个摘要都是自我摘要，证明「内容没变」，不证明「谁发布的」。
- **摘要不覆盖被测内容**：`verifier_digest` 只覆盖判定脚本；被测内容由 HEAD 负责。
- **材料清单不是全仓清单**：范围外文件的变化不会让 `materials_digest` 变。
- **`results/` 不在材料清单里**（第 157 轮的决定）：材料清单记的是**输入**（协议 / 判定脚本 / 核心代码 / 文档）；
  `results/` 是**产出**。把产出混进材料清单会让「输入→产出」的对应关系失效，而 `results/` 里每份文件
  另有自己的新鲜度判据（各 probe 的 `--check`）。
- **跨机器不可比**：摘要只在本仓范围内有意义；换 fork 需重新生成。
