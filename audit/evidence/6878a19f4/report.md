# NF 审计报告（离线可复现）

- 审计对象：NF 0.3.6 源码（mobile 0.3.6 / 内核 1.0.5）
- 源码根：D:/NinFenz
- commit：6878a19f4
- 规则库版本：2；scoring 版本：1
- Python：3.11.9；执行器：nf-audit-runner/1.0（sha256 3d12b4e8057f9fe4）
- 规则总数：166（script 134 / tool 14 / manual 18）

## 评分总览

| 维度 | 名称 | 权重 | 扣分 | 命中数 | 维度分 |
|---|---|---|---|---|---|
| A | 架构与依赖方向 | 0.10 | 0 | 0 | 100 |
| B | 模块边界与内聚 | 0.06 | 0 | 0 | 100 |
| C | 规模与复杂度 | 0.10 | 13 | 1064 | 87 |
| D | 重复与抽象 | 0.06 | 0 | 0 | 100 |
| E | 错误处理与失败语义 | 0.10 | 0 | 0 | 100 |
| F | 并发与资源 | 0.06 | 0 | 0 | 100 |
| G | 状态与恢复 | 0.06 | 0 | 0 | 100 |
| H | 安全与隐私 | 0.12 | 0 | 0 | 100 |
| I | 性能与规模 | 0.08 | 0 | 0 | 100 |
| J | 测试充分性 | 0.08 | 0 | 0 | 100 |
| K | 依赖与供应链 | 0.05 | 0 | 0 | 100 |
| L | 构建与可复现 | 0.05 | 0 | 0 | 100 |
| M | 文档一致性 | 0.04 | 0 | 0 | 100 |
| N | 可访问性与 i18n | 0.04 | 0 | 0 | 100 |

**总分：98.7**（= Σ 维度分 × 权重）

问题命中（按规则实际上报）：P0=0 / P1=0 / P2=899 / P3=165，合计 1064

证据包 issues.json 按单规则最多保留 200 条（防超大文件），实际保留 472 条；完整命中数见 meta.json 的 rule_status.hits。截断不影响评分与门禁。

## 规则执行状态

script 规则：pass=128 / fail=6 / error=0 / no_targets=0；tool+manual 未执行（not-run）=32

口径：tool / manual 规则记 not-run，不计扣分、不写成 pass；no_targets（无目标文件）与 error（执行异常）同样不计扣分、不算通过。

## P0/P1 命中清单

无 P0/P1 命中。

## 未执行项（tool / manual）

| 规则 | 级别 | 类型 | 工具/方式 | 说明 |
|---|---|---|---|---|
| C-004 | P2 | tool | detekt | 离线不可用（缺 detekt jar）；CI 跑 audit/tools/detekt.yml |
| D-001 | P2 | tool | jscpd | 离线不可用（缺 node 依赖）；CI 跑 jscpd |
| D-006 | P2 | manual | 人工抽样 |  |
| E-012 | P2 | manual | 人工抽样 |  |
| F-001 | P1 | manual | 人工抽样 |  |
| F-008 | P2 | manual | 人工抽样 |  |
| F-009 | P2 | tool | android-strictmode | 离线不可用，需真机 StrictMode 报告 |
| F-010 | P2 | tool | android-lint | 离线缺 android.tools:lint-gradle，CI 跑 |
| G-001 | P1 | manual | 人工抽样 |  |
| G-009 | P2 | manual | 人工抽样 |  |
| G-010 | P2 | manual | 人工抽样 |  |
| H-007 | P2 | manual | 人工抽样 |  |
| H-013 | P2 | tool | pip-audit | 离线不可用，CI 跑 |
| H-014 | P1 | tool | codeql | 离线不可用，CI 跑 .github/workflows/codeql.yml |
| H-015 | P1 | tool | gitleaks | 离线不可用，CI 跑 |
| I-001 | P1 | tool | macrobenchmark | 真机 macrobenchmark 尚被测试 APK 混淆冲突阻断，未接入 |
| I-007 | P2 | manual | 人工抽样 |  |
| I-008 | P2 | tool | macrobenchmark | 同 I-001，未接入 |
| I-009 | P2 | manual | 人工抽样 |  |
| I-012 | P3 | manual | 人工抽样 |  |
| J-001 | P1 | tool | jacoco | 离线不可用，CI 跑 |
| J-013 | P3 | tool | pit | 离线不可用，CI 跑 |
| J-015 | P2 | manual | 人工抽样 |  |
| K-014 | P2 | tool | cyclonedx | 离线不可用，CI 跑 |
| K-015 | P2 | tool | cargo-audit | 离线不可用，CI 跑 |
| L-001 | P2 | tool | reproducible-build | 需两次构建+比对，CI 跑 |
| M-001 | P2 | manual | 人工抽样 |  |
| N-002 | P2 | manual | 人工抽样 |  |
| N-003 | P3 | manual | 人工抽样 |  |
| N-006 | P3 | manual | 人工抽样 | 伪 locale en-XA 覆盖率 85%（1237/1453，缺 216）——真实 i18n 缺口，纳入人工跟踪（owner: 内部；到期 2026-12）；不打自动分。 |
| N-010 | P2 | manual | 人工抽样 |  |
| N-011 | P3 | manual | 人工抽样 |  |

## 复现

    python audit/runner.py --root D:/NinFenz --commit 6878a19f4 --out audit/evidence/6878a19f4

同一输入重跑：文件遍历与命中排序均为确定性，issues.json / meta.json / report.md 逐字节一致。
