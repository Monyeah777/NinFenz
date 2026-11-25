# NF 硬技术治理包

> 状态：2026-11-24；proven 24/24；未跑 Trials 0/10。
> 目标：用 24 个硬能力 + 10 条 Frontier Trials 证明“别人很难或做不到”的技术力；112 节点只做覆盖基线。

## 文件

- registry.json：112 覆盖节点 + 24 H + 10 Trials（机读）
- HARD_TECH_LADDER.md：24 项硬能力、护城河、阈值
- FRONTIER_TRIALS.md：10 条端到端硬挑战
- SCORECARDS.md：六层 × 四项 + Trials 状态
- GAP_BACKLOG.md：P0/P1 硬缺口
- ARCHITECTURE_TARGET.md：SDIR、构建图、证据、扩展、op
- HARD_TECH_REPORT.md：结论、现状、顺序、风险
- EXECUTION_STATUS.md：Wave 0 运行时落地与 Trials 证据
- trials/：T04/T07 等可复算结果 JSON
- benchmarks/：H4.4 等独立基准 JSON
- REVIEWS.md：标准/安全/可访问/对抗复核记录
- REFERENCES.md：硬技术对标锚点

## 口径

- 基本项（导入/导出/主题/搜索/备份/分享）是 table stakes，不作为技术力验收。
- H 能力必须满足：SDIR、求解、构建图、语义合并、可访问构造、证据、跨格式等价、复用图中的至少两项。
- 只有 proven 才算技术力；未 proven 不得写“已实现”。

## 校验

~~~bash
python app/scripts/hardtech_governance.py validate --strict
python app/scripts/hardtech_governance.py coverage
python -m pytest app/tests/test_hardtech_governance.py -q
~~~
