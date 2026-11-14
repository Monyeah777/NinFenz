# 深度逆向 R0：仓库全貌（INVENTORY）

> 状态：v1 · 2026-11-14 · 检出 `4fde4e3b5`（分支 `work/l4-floors`，工作树干净）
> 依据：`NF-Final-方案-2026-11-13.md` §4A.2（R0 仓库考古）· §4A.9（逆向 DoD）· §13B.2（分层范围）
> ⛔ 操作指令：本件是 R0 产物；每条结论附命令或 `file:line`，改本件必须重跑命令并更新数字，不得照抄旧值。
> 性质：结果/状态件（逆向审计记录）。不确定项标 `UNKNOWN`，不用推测填充。

## 0. 结论

1. **这是一个「结果形态」的大仓**：4,578 个 tracked 文件、1,598 次提交（2026-09-03 → 2026-11-14，约 10 周）、Python 1,259 文件 / 241,182 行。存量远大于方案假设的起点。
2. **真源是四层**：① 协议条款 `01/02/06/07`；② 库目录 `03_管线库/04_模块库/05_资产库`（很薄，是目录/契约层而不是内容主体）；③ 机读注册层 `protocol/`（143 件 / 218,144 行，含 schema、registry、approvals、generated）；④ 域包真源 `community/*/`（1,879 件 / 236,836 行，111 个 `protocol.yaml`、100 份 `DOMAIN_SPEC.json`）。**方案把 03/04/05 说成「内容主体」不成立**——内容主体在 `community/` 与 `02_联动注册表.md`。
3. **生成物面已经很大且已有「禁止手改」纪律**：`docs/standards/`（7 件，`scripts/geo_export.py --write`）、`docs/layers.md` 生成区（`nf layers --write`）、`docs/verification-cards.md` 生成区（`scripts/build_verification_cards.py --write`）、`protocol/generated/`（26 件）、`results/interop/`（12 面）、`protocol/RECEIPTS.json` + 回执链、`protocol/conformance_report.json`、`protocol/role_coordinates.json`、`results/ccos/`（25 件）等。**新增 Wiki/spec 生成物必须沿用同一「生成器 + 判据 + 禁止手改」范式**，否则方案 §19.3 第 2 条直接违反。
4. **死代码/草稿面很干净**：`desktop/src/core` 里 `TODO/FIXME/NotImplemented` 只有 5 处命中，且全部是扫描器规则/语义注释（非桩代码，见 §5）；tracked 的 `_legacy`/`archive/` 候选只有 `desktop/src/core/audit_legacy.py` 一件；`.rivet/`、`.worktrees/`、`.nf-logs/` 是本地未跟踪协作区（不得入仓）。
5. **入口很宽**：`nf` CLI 77 个子命令、20 个 GitHub Actions workflow、81 个带 `__main__` 的脚本、MCP 运行时 `nf serve`、5,549 条 pytest 用例。**R1/R2 不要从「找入口」开始，要从「字段-使用点」开始**。
6. **失败史以 `fix` 为主**：284 条 `fix`、57 条 `refactor`、1 条 `revert`、0 条 `hotfix`；`security` 相关 24 条。R4 用 `git log -S`/`git blame` 提失败模式，不用标题猜。

## 1. 方法与口径

```bash
git rev-parse --short HEAD; git status --porcelain | wc -l
git -c core.quotepath=false ls-files | wc -l
git log --oneline | wc -l
# 分类型/分目录统计走 Python 读 git ls-files + 文件字节计数（见 §2 表）
grep -cE '^check[0-9]+\(\)' verify.sh
python -m pytest desktop/tests --collect-only -q
```

口径说明：行数 = 文件字节里的 `\n` 计数（含末行无换行的误差 ±1/文件）；`git ls-files` 必须加 `-c core.quotepath=false`，否则非 ASCII 路径会被引号转义、统计漏计（本仓有 881 个非 ASCII 路径）。生成物判定 = 文件头/生成器声明 + 生成脚本 + 门禁判据三证齐一，不靠文件名猜。

## 2. 规模统计

| 面 | 文件 | 行数 | 备注 |
|---|---|---|---|
| tracked 总计 | 4,578 | — | `git ls-files` |
| Python | 1,259 | 241,182 | 其中 `desktop/src/core` 379 / 78,951；`desktop/tests` 671 / 109,839；`scripts` 83 / 28,056 |
| Markdown | 1,199 | 139,018 | 881 个非 ASCII 路径（中文名） |
| JSON | 1,302 | 423,080 | `protocol/` 与 `results/` 是大头 |
| YAML/YML | 144 | 7,006 | 含 111 个域包 `protocol.yaml` |
| Rust | 91 | 73,388 | `engine/` |
| C# | 110 | 41,103 | `engine/dotnet/` |
| Shell | 14 | 4,138 | `verify.sh` 单文件 183,697 字节 |
| 测试 | 671 个 `test_*.py` | 109,839 | 5,549 例（`pytest --collect-only`） |
| 域包 | 1,879（`community/`） | 236,836 | 100 域包 / 111 pipeline / 100 DOMAIN_SPEC |
| 协议层 | 143（`protocol/`） | 218,144 | schema + registry + approvals + generated |

## 3. 真源候选表

| # | 真源 | 规模 | 承载什么 | 判据/证据 |
|---|---|---|---|---|
| S1 | `01_核心协议.md` | 415 行 | 内容契约层核心条款 | 被 `01–07` 引用链使用；`protocol/normative.json` 登记规范面 |
| S2 | `02_联动注册表.md` | 1,190 行 / 262 KB | 模块/管线/协议联动注册表（**内容主体**） | README「248 模块 / 114 管线 / 111 protocol.yaml」口径的来源（R1 复核） |
| S3 | `06_Agent执行协议.md` | 268 行 | Agent 执行契约 | 方案 PR-03 的槽位语义参考件 |
| S4 | `07_官方核心出厂与社区预设导航.md` | 97 行 | 出厂/社区导航 | 域包入口 |
| S5 | `03_管线库/` | 3 件（P00/P01/P90） | 管线抽象（目录级） | 每件带 Pipeline 契约；`core/pipeline_loader.py` 解析 |
| S6 | `04_模块库/` | 13 件（世界/事件/技术文档/通用 4 类） | 模块目录 + machine_contract | `core/machine_contract.py` 解析 |
| S7 | `05_资产库/` | 6 件（README/provenance/用户自定义等） | 资产目录 | `protocol/asset_contracts.json`、`asset_keys.json` 是机读面 |
| S8 | `protocol/` | 143 件 / 218,144 行 | schema、registry、criteria、approvals、eval、domain_packs、generated、trust | `protocol/README.md` 自述；`quality_baseline`/verify check 消费 |
| S9 | `community/*/` | 100 域包 / 1,879 件 | 域包 spec（`outputs/DOMAIN_SPEC.json` ×100）、模块、管线、资产 | 每包 `modules/ pipelines/ assets/ outputs/` 四段；`core/domain_pack.py` 读取 |
| S10 | `desktop/src/core/registry.json` | 1 件 | 运行时模块注册（含 `truth_source` 字段） | `registry.json` 头部自述真源；被 `nf spec`/`market`/`who-refers` 消费 |

> 真源与生成物边界不是按目录切的（`protocol/` 同时含真源与 generated），R1 必须按**字段级**给出「定义处/使用处/生成处」。

## 4. 生成物候选表（禁止手改）

| 生成物 | 生成器（入口） | 真源 | 判据 |
|---|---|---|---|
| `docs/standards/index.md`、`layer-{data,eng,form,gov,iface}.md`、`answer-cards.md`（7 件） | `python scripts/geo_export.py --write` | `protocol/standards_catalog.json` + `standards_binding.json` | 文件头「本页由 … 生成，禁止手改」 |
| `docs/layers.md` 生成区 | `nf layers --write` | 层模型（`core/layer_model.py`） | 生成区标记 |
| `docs/verification-cards.md` 生成区 | `python scripts/build_verification_cards.py --write` | `verify.sh` check 函数逐条抽取 | 文件头「生成方式 + 随仓库分发」 |
| `protocol/generated/`（26 件：顶层 7 + `test_vectors/` 19） | 各生成脚本（idl/receipt/asset/…） | 对应 schema/真源 | `protocol/generated/README.md` |
| `results/interop/`（12 面：a2a/asyncapi/c2pa/cid/cyclonedx/decisions/intoto/openapi/prov/sbom/slsa/vc） | 派生导出（`core/interop_export.py`） | `protocol/endpoint_contract.json` 等 | check33 断言「派生 == 实时重算」 |
| `protocol/RECEIPTS.json` + `protocol/generated/receipt_chain.json` | `nf receipts --scope protocol --write` | 协议层文件集 | check35 逐条折叠到单根 |
| `protocol/conformance_report.json` + `protocol/approvals/` | `nf conformance --write` → `nf approve` | 契约/范围/排除 | check35 报告工件 == 实时重算 |
| `protocol/role_coordinates.json` | 角色坐标生成器 | 职能面 | check35/角色门禁 |
| `protocol/code_metrics_baseline.json` | `scripts/code_metrics.py` | 代码度量 | check34 / style 棘轮 |
| `results/ccos/`（25 件） | `scripts/ccos_chain.py` 等 | 认知面证据 | 各件对应 check |
| `results/trust/`（向量/自审计/公共锚） | `scripts/trust_self_audit.py`、锚抓取等 | trust 冻结向量 | check45–48 |
| `llms.txt` / `llms-full.txt` | `python scripts/sync_llms.py`（`--write`） | README/docs 摘要面 | `test_llms_contract.py` |
| `README*.md` 数字 marker 区 | `nf stats --write` | 仓库实算 | 数字漂移门禁 |
| `packaging/npm/payload/` | stage 脚本 | 发布清单 | `npm-package-check.yml` |
| `results/*.json` 派生投影 | 各 `--write` 命令 | 各自真源 | 对应 check |

**风险**：`protocol/` 目录内真源与生成物混放（如 `RECEIPTS.json` 是生成物、`endpoint_contract.json` 是真源），方案 §4A 的「生成物候选」必须字段级标注，不能按目录整目录处置。

## 5. 草稿候选/死代码候选表

| # | 候选 | 实读 | 判定 |
|---|---|---|---|
| D1 | `desktop/src/core` 的 TODO/FIXME/NotImplemented | 5 处：`evidence.py:404`（异常元组里的 `NotImplementedError`）、`host_projection.py:11`（占位符正则）、`purity_scan.py:8/58`（扫描器规则）、`telemetry_semconv.py:16`（官方站点 TODO 注释） | **非桩代码**，5 处全是规则/注释；无「未实现函数」 |
| D2 | `desktop/src/core/audit_legacy.py` | 唯一 tracked 的 `legacy` 命名模块 | 待 R3 判是否死代码（引用面为零即登记） |
| D3 | `.rivet/`（含 `scratch/` `plan/`） | 本地未跟踪协作区（`.gitignore:32`） | 不得入仓；计划/过程件留此处 |
| D4 | `.worktrees/` | 本地 worktree 残留（含 `w-agent/` 旧分支文件） | 未跟踪；不入仓 |
| D5 | `.nf-logs/` | 本地门禁日志/脚本残留（`patch-*.py`、`commit-msg-*.txt`） | 未跟踪；不入仓 |
| D6 | 生成物被手改的历史残留 | 43 个文件含「自动生成/DO NOT EDIT」标记（`docs/`、`protocol/`） | 由 check 判据兜底；R3 查漂移 |

## 6. 入口清单

**CLI**：`python scripts/nf.py --help` → 77 个子命令。主要族：`run / demo / pipeline / module / asset / market / register / spec / render / serve / design / who-refers / impact / rename / import / sig / attest / cog / label / evidence / check / resolve / score / lint / assertions / model / decisions / handover / postmortem / audit / cognition / lsp / license / telemetry / conformance / events / receipts / driver / rfc / patterns / preset / bench / endpoint / interop / transparency / output / domain / combine / decide / workloop / review / knowledge / approve / library / diff / explain / related / doctor / assemble / release / changelog / locales / toolface / worldmodel / shell / terminal / layers / daemon / verify / nfal`。

**脚本入口**：81 个 `scripts/*.py` 带 `__main__`（`grep -rln "__main__" scripts`）。

**CI**：20 个 workflow（`.github/workflows/`）：`ci-health / ci-verify / codeql / coverage / cross-lang / cross-platform / dependency-audit / docker-nfal / dotnet-build / e2e-desktop / external-links / gitee-poll / library-ingest / lint / linux-parity-refresh / net-probes / npm-package-check / npm-publish / release-gate / rust-crate`。

**MCP**：`nf serve`（stdio JSON-RPC，`protocol/mcp_package.json` 是打包面）。

**测试入口**：`python -m pytest desktop/tests`（5,549 例）；`bash verify.sh`（全量）/ `--checks-only`（46 条静态 check）。

## 7. 历史与失败面初判（交 R4）

| 指标 | 实读 |
|---|---|
| 提交数 / 跨度 | 1,598 / 2026-09-03 → 2026-11-14 |
| 类型分布 | docs 454 · feat 429 · fix 284 · chore 224 · test 60 · refactor 55 · ci 36 · perf 21 · merge 12 · release 10 · security 3 · Delete 2 |
| 搜索命中 | 标题含 `security` 24、`revert` 1、`refreeze` 2、`refactor` 57、`hotfix` 0 |
| 复盘/接力件 | `postmortems/` 2 件（模板 + README）、`handovers/` 2 件（模板 + README）——**没有已归档的真实失败复盘**，R4 只能从 git log/diff 重建 |
| 已知重复实现候选 | `canonical`（`core/trust/canonical.py` + `scripts/jcs.py` + `core/json_doc.py`）、`path validate`（`core/paths.py`）、`coverage`（`core/requirement_coverage.py` + `judgement_coverage.py` + `scripts/coverage_summary.sh`）→ R3 用调用点/逐字节 diff 判是否真重复 |

## 8. 三表汇总与 R1 交接

- **真源候选 10 组**（S1–S10）→ R1 做字段级 CONTRACT_MAP：`machine_contract`、Pipeline YAML、asset keys、`protocol/*.json`、`DOMAIN_SPEC.json` 的「定义处 → 读取处 → 缺口」。
- **生成物候选 15 组**（§4 表）→ R2/R3 只审「生成一致性/来源」，不审生成物正文；手改禁令清单可直接进 §13B CQ。
- **草稿/死代码候选 6 组**（D1–D6）→ D1 已判否（非桩）、D2 待 R3、D3–D5 是本地未跟踪区（不入仓）、D6 交 R3 查漂移。
- **R0 的 DoD 自检**：每条结论有命令/`file:line`；规模数字可复跑（§1）；生成物判定三证齐一；未解决只留 `UNKNOWN` 一处（S2 的 248/114 数字待 R1 复核，见 §3 备注）。

> 下一件：R1 `CONTRACT_MAP.md`（显式+隐式契约）；R3 `COUPLING.md` 与 R6 `INVARIANTS.md` 可在 R1 后并行；R2/R4/R5 依赖 R1 的字段表。
