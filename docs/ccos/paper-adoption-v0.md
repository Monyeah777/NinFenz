# 论文筛选台账 v0（34 篇 · 处置可核）

状态：**34 篇；adopted 22 / deferred 7 / rejected 1 / not-applicable 4**（截至 2026-11-10，以 `protocol/paper_ledger.json` 为唯一真源）。

## 它是什么

把「读了哪些论文、读到了什么机制、最后移植了什么」变成**可核对象**：每篇必须有处置与理由；
`adopted` 必须给出仓内**落点**（模块/协议件）与**证据面**（判据或结果件），并逐条核文件存在。

台账只记「已读到的内容」，不引二手数字；判定 `not-applicable` 的条目也保留理由，便于复查。

## 四档处置的含义

| 处置 | 含义 | 硬性要求 |
|---|---|---|
| `adopted` | 机制已移植进仓，并能指出落点与判据面 | `targets` 与 `evidence` 非空且文件存在 |
| `deferred` | 机制有价值但当前面不具备（缺硬件/数据/场景），暂缓 | 必须写明理由与当前替代物 |
| `rejected` | 经核对不成立或误引 | 必须写明剔除理由 |
| `not-applicable` | 非论文条目（本仓自证/对照判断） | 必须写明它是什么 |

## 怎么用

```bash
python scripts/paper_ledger.py            # 校验（结构 + 引用面 + 计数）
python scripts/paper_ledger.py --stats    # 四档计数
python scripts/paper_ledger.py --write    # 重算 count/counts 并落盘
```

## 判据（可证）

```bash
python -m unittest desktop.tests.test_paper_ledger      # 5 项：自洽/处置完整/落点存在/计数/变异自证
```

## 边界

- **不是**文献综述：只记「本仓用它做了什么」，不评价论文本身的质量与影响；
- **不是**完整性承诺：34 篇是分轮筛选的结果，新增论文走同一张表（处置+理由+落点）；
- **不引二手数字**：论文里的实验数值不进本仓判据，除非本仓自己跑出来（见 `results/ccos/*`）。