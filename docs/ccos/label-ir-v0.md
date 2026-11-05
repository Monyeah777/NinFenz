# 标注 IR v0（`cc_label` 的声明层）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-05
> **Status**: v0 已实装**声明层**（`core/label_ir.py` + `nf label ir|validate`）· **载体写入未实装**

## 是什么 / 不是什么

`nf-label/1` 是一份**纯数据 IR**：描述「某对象按某个标准**应当**带哪些标识」，并校验声明的形状与
档位齐备度。它**不**写载体、**不**读载体、**不**证明文件里真的带标识——本仓没有标识写入子系统，
任何「已写入水印/已嵌入元数据」的宣称都不可证。

## 规则表（GB 45438 分类 · v0 映射）

| id | 面 | kind | 从哪档起必需 | 要求 |
|---|---|---|---|---|
| E1 | 显式 | text | minimal | `where`（start/end/ui）+ `value` |
| E2 | 显式 | audio | full | `value`（可听提示） |
| E3 | 显式 | metadata | full | `key` + `value`（生成合成声明字段） |
| I1 | 隐式 | watermark | full | `algorithm` + `value` |
| I2 | 隐式 | metadata | minimal | `key` + `value`（文件元数据字段） |

v0 映射**待按标准原文复核**：本表给的是「哪几类要求」而不是条款号；换标准要改 `STANDARD` 并补判据。

## 怎么用

```bash
# 组装 IR（不给 --items 就是空声明，靠校验面把缺口暴露出来）
nf label ir 产出/海报.png --level minimal --items items.json --out 产出/海报.label.json

# 校验（退出码：ok=0 / invalid=1 / 用法错=4）
nf label validate 产出/海报.label.json
```

`items.json` 是声明项数组，每项带 `face`（explicit/implicit）+ `kind` + 该 kind 的必填字段。

## 判定（可证）

| 检查 | 不过 |
|---|---|
| schema == `nf-label/1`、standard == 当前标准、level ∈ {minimal, full} | invalid |
| `object.path` 非空、`object.digest` 为 64 位十六进制 sha256 | invalid |
| `explicit` / `implicit` 是数组，且每项 kind 在该面允许集合内 | invalid |
| `carrier.embedded` 是布尔 | invalid |
| 档位必需的每条规则都有匹配声明项（kind 相符 + 必填字段非空） | invalid（列出缺哪几条） |
| `carrier.embedded=true` 但本仓无写入子系统 | **ok + warning**（不当成功，只如实提示自称） |


## sidecar 回退载体（v0 已实装）

嵌入载体做不到时，ABI 允许回退 sidecar：把标注 IR 写到对象旁的 `<对象>.label.json`，**与对象摘要绑定**。
`nf-label-sidecar/1` 的 `embedded` **恒为 false**（常量，不是参数）——它证明「这份声明与这份对象对得上」，
不证明「对象里真的带标识」。

```bash
nf label write --object 产出/海报.png --ir 产出/海报.label.json   # 写旁车（绑定摘要）
nf label read 产出/海报.png                                      # 读旁车 + 对账
nf label list                                                    # 清点仓内全部旁车
```

| 检查 | 不过 |
|---|---|
| 旁车在场且 schema == `nf-label-sidecar/1` | invalid |
| 旁车内 IR 通过 `nf-label/1` 校验 | invalid |
| **对象摘要 == 旁车绑定摘要** | invalid（「对象已被改动，标签声明已过期」） |
| 对象可读（被删/权限不足） | invalid |

写盘走 `atomic_write`：半截旁车会让读者读到假声明。读判据只读旁车 + 对象摘要，不联网、不猜。

## 与 `cc_label` 的关系

`cc_label(obj, contract)` 要返回 `{label: {contract, standard, fields, carrier, embedded}}`。v0 做实两块：
**声明层**（IR 形状与齐备度）+ **sidecar 回退**（把声明落到对象旁并与摘要绑定）；`embedded` **恒为
false**，无法证「对象里真的带标识」。因此 ABI 里 `cc_label` 记为 `partial`，不升级为 `implemented`。

## 复核

```bash
python -m unittest desktop.tests.test_label_ir   # 16 项：档位/形状/自称提示/CLI 往返
```
