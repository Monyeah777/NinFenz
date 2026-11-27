# NF 审计报告（汇总）

> 本文件由 audit/ci/consolidate_report.py 生成，勿手改；明细见证据包与 remediation/calibration/trend。
> 证据：audit/evidence/79b61a71b；commit：79b61a71b；扫描根：D:/NinFenz

## 结论

- 总分 **99.0**（满分 100，口径 = 14 维加权）
- 问题：P0=0 / P1=0 / P2=862 / P3=16
- 规则：166 条（script 134 / tool 14 / manual 18）；pass=130 fail=4 error=0 no_targets=0 not-run=32

## 维度分

| 维度 | 名称 | 权重 | 得分 | 扣分 | 命中 |
|---|---|---|---|---|---|
| A | 架构与依赖方向 | 0.1 | 100 | 0 | 0 |
| B | 模块边界与内聚 | 0.06 | 100 | 0 | 0 |
| C | 规模与复杂度 | 0.1 | 90 | 10 | 878 |
| D | 重复与抽象 | 0.06 | 100 | 0 | 0 |
| E | 错误处理与失败语义 | 0.1 | 100 | 0 | 0 |
| F | 并发与资源 | 0.06 | 100 | 0 | 0 |
| G | 状态与恢复 | 0.06 | 100 | 0 | 0 |
| H | 安全与隐私 | 0.12 | 100 | 0 | 0 |
| I | 性能与规模 | 0.08 | 100 | 0 | 0 |
| J | 测试充分性 | 0.08 | 100 | 0 | 0 |
| K | 依赖与供应链 | 0.05 | 100 | 0 | 0 |
| L | 构建与可复现 | 0.05 | 100 | 0 | 0 |
| M | 文档一致性 | 0.04 | 100 | 0 | 0 |
| N | 可访问性与 i18n | 0.04 | 100 | 0 | 0 |

## 门禁

- 命令：bash audit/ci/gate.sh --evidence audit/evidence/79b61a71b
- 阈值：audit/ci/thresholds.json（总分 / 单维 / P0 / error / no_targets）

## 交付物索引

| 文件 | 内容 |
|---|---|
| audit/rules.json | 规则库（机读，166 条） |
| audit/evidence/<commit>/ | 证据包（issues/meta/report + 规则与 runner sha256） |
| audit/remediation.md | 整改台账（问题 → 修复 → 验证 → 关闭） |
| audit/calibration.md | 规则校准记录（证据 + owner + 到期） |
| audit/trend.md | 趋势与前后对比 |
| audit/ci/gate.sh | 一键门禁 |
| audit/tools/ | 外部工具配置（未接入项标 not-run） |

## 未跑项

- tool/manual 共 32 条未执行（离线无 detekt/ktlint/jscpd/jacoco/CodeQL 等）：不计分、不写成 pass，接 CI 后重跑。
