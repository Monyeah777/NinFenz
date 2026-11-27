# 审计趋势（同口径对比）

> 口径：`audit/runner.py` + `audit/rules.json` v2（166 条）+ `audit/scoring.json` v1；Python 3.11.9。
> 同一 commit 重跑两次产物逐字节一致（issues/meta/report 的 sha256 见各证据包 meta.json）。

| commit | 版本 | 规则 | 总分 | P0 | P1 | P2 | P3 | 证据 |
|---|---|---|---|---|---|---|---|---|
| aeae36b11 | 0.3.6 | 166 | **92.1** | 0 | 84 | 1371 | 255 | `audit/evidence/aeae36b11/` |
| 14fcc0dba | 0.3.7-preview.1 | 166 | **92.1** | 0 | 85 | 1376 | 256 | `audit/evidence/14fcc0dba/` |
| p1fix（P1 整改后） | 0.3.7-preview.1 | 166 | **94.0** | 0 | 0 | 1377 | 256 | audit/evidence/p1fix/ |
| c-dim（C 维度收口 + 规则校准） | 0.3.7-preview.1 | 166 | **95.51** | 0 | 0 | 1369 | 242 | audit/evidence/c-dim/ |
| p2-batch1（小批量 P2 + 交付面） | 0.3.7-preview.1 | 166 | **95.88** | 0 | 0 | 1369 | 229 | audit/evidence/p2-batch1/ |
| p2-batch2（重复代码 + 错误处理） | 0.3.7-preview.1 | 166 | **96.52** | 0 | 0 | 1294 | 229 | audit/evidence/p2-batch2/ |
| p2-batch3（报告样板 + UI 路径） | 0.3.7-preview.1 | 166 | **96.82** | 0 | 0 | 1264 | 229 | audit/evidence/p2-batch3/ |
| p2-batch4（Rust/Kotlin 重复块） | 0.3.7-preview.1 | 166 | **96.94** | 0 | 0 | 1261 | 221 | audit/evidence/p2-batch4/ |
| p2-batch5（truth-drift 收口） | 0.3.7-preview.1 | 166 | **96.94** | 0 | 0 | 1261 | 220 | audit/evidence/p2-batch5/ |
| p2-batch6（Rust 生产路径口径） | 0.3.7-preview.1 | 166 | **97.34** | 0 | 0 | 1241 | 220 | audit/evidence/p2-batch6/ |
| p2-batch7（包环收口） | 0.3.7-preview.1 | 166 | **97.64** | 0 | 0 | 1233 | 220 | audit/evidence/p2-batch7/ |
| p2-batch8（B-004 收口） | 0.3.7-preview.1 | 166 | **97.82** | 0 | 0 | 1017 | 220 | audit/evidence/p2-batch8/ |

## 维度分变化

| 维度 | 0.3.6 | 0.3.7 | 变化 | 说明 |
|---|---|---|---|---|
| A 架构与依赖方向 | 90 | 89 | −1 | 0.3.7 新增 1 处包间成环（ARCH-004） |
| B 模块边界与内聚 | 91 | 91 | 0 | |
| C 规模与复杂度 | 77 | 77 | 0 | 最大扣分项，未改善 |
| D 重复与抽象 | 94 | 94 | 0 | |
| E 错误处理与失败语义 | 79 | 79 | 0 | 与 C 并列最低 |
| F 并发与资源 | 94 | 94 | 0 | |
| G 状态与恢复 | 100 | 100 | 0 | |
| H 安全与隐私 | 97 | 97 | 0 | |
| I 性能与规模 | 97 | 97 | 0 | tool 规则未跑，分数只反映静态项 |
| J 测试充分性 | 97 | 97 | 0 | |
| K 依赖与供应链 | 100 | 100 | 0 | |
| L 构建与可复现 | 96 | 98 | +2 | 0.3.7 补了 release R8/资源压缩与签名配置检查项 |
| M 文档一致性 | 97 | 97 | 0 | |
| N 可访问性与 i18n | 98 | 98 | 0 | |

## 结论

- 0.3.7 相对 0.3.6 **没有可测量的质量改善**：总分持平，C/E 两个最低维度未动。功能补齐不改变结构债务。
- 下一步整改优先级由 `audit/remediation.md` 的 P1 决定：ARCH-002/003（反向依赖）、E-001（UI 层 50 处 getOrNull 吞错）、E-002（23 处空 catch）、E-003/E-009（错误码未在册/重复定义）、ARCH-004（包环）。
- 门禁阈值（总分 ≥95、单维 ≥80、P0=0）当前**未达标**（真实红）：`bash audit/ci/gate.sh` exit 1，未过项为总分 92.1、C 77、E 79。

## 整改后对比（P1 → 0）

- 2026-11-27 P1 整改把总分从 92.1 推到 **94.0**，P1 命中从 85 降到 **0**：ARCH-002/003（反向依赖）通过类型上移 + 策略上移修复；E-001 用 Result.orNullLogged() 把 51 处静默 getOrNull() 改成显式上报；E-002 的 23 处空 catch/except 补 best-effort 声明并校准规则口径；E-003/E-009 修错误码在册与唯一性。
- 仍差一口气：总分 94.0 < 门禁 95，C 77 < 80；下一轮做 C 维度结构性拆分（大文件/大函数/复杂度）。

## 门禁状态

- 第三次复审计（c-dim）：总分 95.51、P0=0、P1=0、error=0、no_targets=0，audit/ci/gate.sh PASS。
- 该分数包含 16 条规则校准（见 audit/calibration.md）；按校准前口径为 C 77 / 总分 94.0。两种口径都在证据包里可复算。

## 门禁状态（第四轮后）

- 最新证据 p2-batch1：总分 95.88，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS。
- 维度：A97 B94 C80 D94 E92 F95 G100 H100 I100 J100 K100 L100 M100 N100。
- CI：.github/workflows/audit.yml 在 push/PR 跑同一套 runner + gate 并上传证据包（actions 钉 SHA）。

## 门禁状态（第五轮后）

- 最新证据 p2-batch2：总分 96.52，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS。
- 本轮主要收益：D-002 3→1（共享 Markdown 渲染器）、E-006 6→0、E-007 47→0、F-005 18→0（口径收窄到生产代码后）。

## 门禁状态（第六轮后）

- 最新证据 p2-batch3：总分 96.82，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS。
- 本轮收益：D-003 4→0（共享 report_module）、B-001 25→0（ProjectPaths 单一构造点）。


## 门禁状态（第七轮后）

- 最新证据 p2-batch4：总分 96.94，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS。
- 本轮收益：D-004 5→0（subject_docs + jsonx 共享模块）、D-002 1→0（NfSurfaceKit）。


## 门禁状态（第八轮后）

- 最新证据 p2-batch5：总分 96.94，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS。
- engine/rust 全量测试 249 passed / 0 failed（OPEN-TRUTH-DRIFT 关闭）；Python 资产契约测试 58 passed。


## 门禁状态（第九轮后）

- 最新证据 p2-batch6：总分 97.34，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS；E 维度 100。


## 门禁状态（第十轮后）

- 最新证据 p2-batch7：总分 97.64，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS；A 维度 100。


## 门禁状态（第十一轮后）

- 最新证据 p2-batch8：总分 97.82，P0=0/P1=0/error=0/no_targets=0，audit/ci/gate.sh PASS；A/B/E 维度 100。
