# ADR-APP-006：TUI 是终端真源：Studio 复用，不重写命令面

| 项 | 值 |
|---|---|
| 编号 | ADR-APP-006 |
| 状态 | accepted |
| 日期 | 2026-11-15 |
| 范围 | NF APP（Android / Desktop / 平板控制面 + 共享核心） |
| 上位 | `STRATEGY.md` → `app/docs/CONTRACT.md`（A0 冻结）/ `app/docs/CLI.md` |

## 背景

仓库已有可运行的 TUI（`tui/nf.py` 约 76 KB + `tui/_surface.py`）：菜单/动作是 `nf` CLI 真命令的受控调用，已内建写盘确认、密钥遮蔽、路径包含性判据，`--selftest` 9 项全绿，`--list-actions --json` 输出 34 动作/80 命令。桌面 Studio 若自建命令层：出现第二套命令面，语义漂移且检验面翻倍。

## 决策

1. TUI 是终端/检验的**真源**：Agent 与人都用它做只读检验与受控写盘；不重写 `tui/`。
2. Studio 通过既有接口复用：`python tui/nf.py --list-actions --json`（机读动作面）、`--selftest`（自检）、`--exec`（脚本面）；新能力先进 `nf` CLI/TUI，再进 Studio。
3. 菜单动作必须是 `nf` 真命令的受控调用；写盘需显式确认，密钥只从环境变量读并遮蔽。
4. Studio 的 TUI 集成不得改变 TUI 输出契约；需要新增动作时改 CLI/TUI 源码并更新 `--list-actions` 快照。

## 后果

**正面**

- 命令面单一：自动化（agent）与 GUI 走同一真命令，行为一致。
- 检验面单一：`--selftest` 一套自检覆盖两处入口。
- 避免「GUI 悄悄实现语义」这类最难发现的分叉。

**负面 / 代价**

- Studio 的复杂度转移到命令契约（`--list-actions` 输出成为兼容面，改动需同步）。
- TUI 承受 GUI 来的写操作需求，动作面会膨胀（需持续治理）。
- TUI 的终端交互限制（无富界面）会让部分作者流程必须回 Studio。

## 替代方案（及否决理由）

| 方案 | 结论 | 理由 |
|---|---|---|
| A. Studio 自建命令层 | 否决 | 第二套命令面；与 TUI 语义漂移 |
| B. 只保留 CLI、砍掉 TUI | 否决 | 既有能力回退；agent 入口变差 |
| C. TUI 只读、写操作只在 Studio | 否决 | 与既有写盘确认机制冲突；自动化断链 |

## 证据落点

| 证据 | 路径 / 判据 |
|---|---|
| TUI 实现与自检 | `tui/nf.py`、`tui/_surface.py`、`tui/README.md` |
| selftest 9 项 / 34 动作 / 80 命令（实读） | `results/app/BASELINE.md` §0.2/§2.1 |
| 门禁项（TUI selftest 全绿） | `app/gates/gates.json` QA4 `q4-tui` |
| 边界声明（TUI 集成 = 复用不重写） | `app/README.md` 布局与边界节 |
| 判据命令 | `python tui/nf.py --selftest`；`python tui/nf.py --list-actions --json` |

## 复审条件

- TUI 动作/命令面变更（`--list-actions` 输出变化）时。
- Studio 需要 TUI 未覆盖的写操作时——先在 CLI/TUI 扩，再在 Studio 用。
- TUI 自身退役/重写时（仓库 L3 端壳已退役的先例，见 `docs/L3_FROZEN.md`）。

> 本 ADR 只声明决策与边界。实现状态以 `app/docs/ARCHITECTURE.md` §5/§11、`app/results/GATES.json` 与现场复跑命令为准；未落地项写 `OPEN`，不得据本 ADR 声称「已实现」。
