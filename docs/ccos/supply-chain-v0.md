# 供应链对象 v0（材料清单 + 验证器摘要 + 结论绑定）

状态：**已实装**（`core/sbom.py`、`core/verifier_version.py`、`scripts/self_audit_probe.py`、`scripts/sbom.py`）。

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

## 边界（必须写清）

- **不做签名**：三个摘要都是自我摘要，证明「内容没变」，不证明「谁发布的」。
- **摘要不覆盖被测内容**：`verifier_digest` 只覆盖判定脚本；被测内容由 HEAD 负责。
- **材料清单不是全仓清单**：范围外文件的变化不会让 `materials_digest` 变。
- **跨机器不可比**：摘要只在本仓范围内有意义；换 fork 需重新生成。
