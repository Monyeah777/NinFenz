# 机读块 retro-fit（L0 → L1/L2）
> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令与判定，勿当资料阅读。
> 最后更新：2026-11-13

## 是什么

把**没有机读契约**（L0）的模块补上 `machine_contract`——**只做投影，不编造**：

| 字段 | 来源 |
|---|---|
| `id` / `name` | 标题行 `# 模块 Mxx · 名称` |
| `category` / `layer` | 人读头 `类别：` / `挂载点：Pxx` |
| `inputs` | 人读头 `依赖：` 段内的 `Mxx` 令牌 |
| `events.publish/subscribe` | 人读头 **∪ 正文 yaml 事件契约**（取全集——只读头会漏订阅侧） |
| `outputs` / `interfaces` | 人读头未声明 → `[]`（不猜） |
| `conformance` | 按可证事实：在册 + 被管线引用 → `L2`；否则 `L1` |

> **复核（2026-11-13）**：字段来源映射**复核不变**；补可核现状与一处**作用域澄清**：
> `machine_contract.scan()` 的取证范围是**官方核心模块**（`04_模块库/`），本轮实读 **checked 13 · L0 0 · issues 0 · warns 0**；
> `nf module contract` 则报**全库 L0 = 0**（248 个机读契约模块）。`outputs` 另有 1 件可按**事件载荷证据**补全（M15 帮派势力：
> `faction_event` 字段），`module outputs --write` 会落盘——**本轮不落盘**（避免在文档轮次改资产；留待资产轮）。见「§现状对照」。

## 怎么用

```bash
python scripts/nf.py module contract            # 覆盖报告（仍为 L0 的件数）
python scripts/nf.py module contract --write    # 补机读块（幂等；本轮实跑 0 件）
python scripts/nf.py module outputs --write     # 有事件载荷证据的模块补 outputs（幂等）
```

## 现状对照（2026-11-13 · 以实读为准）

| 面 | 现值 | 复核方式 |
|---|---|---|
| 官方核心取证范围 | **13 件** | `machine_contract.scan()` 的 `checked` |
| L0（无机读块） | **0 件** | `scan()` 的 `l0` + `nf module contract` |
| 全库机读契约模块 | **248 件** | `nf module types` 头行 |
| 字段映射 | **6 组**（id/name · category/layer · inputs · events · outputs/interfaces · conformance） | 本页「是什么」表 |
| `--write` 幂等 | 是（本轮实跑 0 件） | 连跑两次第二次必为 0 |
| outputs 待补 | **1 件**（M15，证据 = 事件载荷字段） | `module outputs --write`（本轮未落盘） |

> 本表只作「当时 → 现行」导航；数字以 `scan()` 与 `nf module types` 实读为准。

## 复现与引用口径

```bash
python scripts/nf.py module contract     # L0 覆盖报告（0 件即全库已有机读块）
python -m pytest desktop/tests/test_module_m00_contract.py -q   # 代表件契约形状
```

- 引用本文时：「只做投影，不编造；未声明就写 `[]`」= 长期口径。
- 补块/补 outputs 会改模块正文 → 必须随后 `nf module signature --write` 重冻结边界签名。

## 边界

- 补块会改变模块**边界签名** → 须 `nf module signature --write` 重冻结。
- 新事件若未登记进 `protocol/event_registry.json`，门禁会报缺口（如实登记为 `declared`）。
