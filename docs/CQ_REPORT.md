# 全仓代码质量审查报告（CQ REPORT）

> ⛔ 操作指令：本件是 NF-Final §13B 全仓 CQ 审查的当前阶段报告（CQ0/CQ1）；机读扫描件在 `results/cq/`，质量债在 `docs/QUALITY_DEBT.md`，人工审查清单 `docs/REVIEW_CHECKLIST.md`，判据 `desktop/tests/test_cq_scan_contract.py`。数字为一次实测快照，复跑命令见文末——不把「扫描通过」写成「全绿/无问题」。
> 状态：v1（G0 · 2026-11-14，CQ0/CQ1 完成；CQ2–CQ6 未做）
> 纪律：缺失工具记 **BLOCKED**，不冒充通过；本阶段只做自动扫描，不含人工高危审查（CQ2）。

## 范围（§13B.2 分层）

A 信任/治理核心 · B 生产/装配核心 · C 协议/契约/数据 · D 工具/CLI/TUI · E 测试 · F 引擎（Rust/.NET）· G 配置/CI/供应链 · H 文档/声明 · I 生成物/载荷。
CQ1 自动扫描覆盖 A–E、G/H 的文本面（Rust/.NET 引擎只登记工具链，未跑 cargo/dotnet 构建；生成物只审来源与一致性）。

## 工具矩阵（CQ0，版本固定）

| 工具 | 状态 | 版本/说明 |
|---|---|---|
| python | ok | Python 3.11.9 |
| ruff | ok | ruff 0.16.8 |
| bandit | ok | bandit 1.9.4 |
| radon | ok | 6.0.1 |
| mypy | ok | 2.3.1（compiled） |
| coverage | ok | Coverage.py 7.16.1 |
| vulture | ok | 2.16 |
| shellcheck | ok | ShellCheck |
| node | ok | v24.19.0 |
| cargo | ok | cargo 1.99.1 |
| dotnet | **BLOCKED** | `dotnet --version/list-sdks` 在本机不可用（环境限制；不冒充 .NET 门禁通过） |
| cosign | **BLOCKED** | 不在场（外部签名锚未验；verify check42 已按 WARN 记） |
| gitleaks | **BLOCKED** | 不在场（秘密扫描由 CI + `privacy_contract` 覆盖，不冒充已扫） |

机读：`results/cq/toolchain.json`。

## CQ1 全量自动扫描（一次实测快照）

| 维度 | 扫描面 | 问题数 | 状态 |
|---|---|---|---|
| syntax-python | 1,283 个 .py | 0 | 绿 |
| json-parse | 1,344 个 .json | 0 | 绿 |
| shell-syntax | 14 个 .sh | 0 | 绿 |
| yaml-parse | 144 个 YAML | 0 | 绿 |
| ruff | core + scripts | 0 | 绿 |
| bandit | core（SAST） | 39（high 0 / medium 4 / low 35） | 无阻断；低/中危进质量债 |
| radon-cc | core（383 文件） | CC>15 共 302 个函数；max CC 99 | 存量热点，见下 |
| vulture | core（置信度≥80） | 2 | P3 |
| claims-words | README + docs 一层 | 0（同形技术词已排除） | 绿 |

**分诊**：P0=0、P1=0；P2=54（bandit medium 4 + radon 热点 top50）；P3=37（bandit low 35 + vulture 2）。明细 `results/cq/findings.jsonl`。

## 热点（radon CC top）

| 文件 | 函数 | CC | 行 |
|---|---|---|---|
| `scripts/nf.py` | `main` | 99 | — |
| `desktop/src/core/domain_pack.py` | `validate` | 86 | — |
| `desktop/src/core/pack_combo.py` | `combine` | 83 | — |
| `desktop/src/core/ops.py` | `validate_ops` | 79 | — |
| `desktop/src/core/domain_pack.py` | `manifest_verify` | 75 | — |

完整 top20 见 `results/cq/hotspots.md`。存量热点已由 `protocol/code_metrics_baseline.json` 棘轮冻结（只许收敛，新增必红）。

## 阶段结论与下一步

- **CQ0**：工具矩阵固定、缺失工具显式 BLOCKED；范围与风险分层登记。
- **CQ1**：全量自动扫描完成，P0/P1=0；P2/P3 进 `docs/QUALITY_DEBT.md`。
- **未做**：CQ2 人工高危审查（信任/治理/生产/密钥/路径/MCP）、CQ3 测试质量（覆盖/变异/负例/flaky）、CQ4 跨语言 parity、CQ5 文档/供应链、CQ6 评分卡与复审签署。
- **不声称**：本报告不是「全仓质量全绿」结论；cosign/gitleaks/dotnet 缺失与未跑面（cargo/dotnet 构建）明确挂账。

## 复核命令

```bash
python scripts/cq_scan.py --run      # 重算 results/cq/*（约 15 s）
python scripts/cq_scan.py --check    # 指纹新鲜（HEAD/工作树/工具版本）
python -m pytest desktop/tests/test_cq_scan_contract.py -q
```
