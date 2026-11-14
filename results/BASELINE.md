# NF Final 基线审计（WP-00）

> 状态：v1 · 审计日 2026-11-14 · 实施机检出 `4fde4e3b5`（分支 `work/l4-floors`，工作树干净）
> 依据：`NF-Final-方案-2026-11-13.md` §12.1（只读基线）· §11.2 WP-00（基线审计 + Claim–Evidence 矩阵 + BASELINE）· §13.3/§14（claim 证据规则）· §19.2（启动提示第 1 步）
> ⛔ 操作指令：下文每条判定都附复跑命令；改本文件必须重跑命令并更新数字，不得照抄旧值。
> 性质：结果/状态件（审计记录），不是规划件。审计对象 = **本机检出**，不是方案所基于的那次检出。
> 更新（R3，2026-11-14）：WP-02/check49 收口 IN-01/IN-02（§5.5 与矩阵汇总已按实读更新；数字变化以复跑命令为准，见 §7）。
> 更新（R5，2026-11-14）：WP-01 五件生产 schema（`nf-contract/1`、`nf-wiki-page/1`、`nf-spec/1`、`nf-task/1`、`nf-assembly/1`）落 `protocol/production/`，正/反样例与变异自证在 `test_schema_reference.py`；**只有契约层、仍无编译器/页面生成器**，故 PR-02/WK 系列状态不变（见 §5）。
> 更新（R30，2026-11-14）：G2 WP-22 Output/Validation 落地——`core/output_validation.py`（adapter 契约+`nf-contract/1` schema+output form：md 标题/行宽、json 可解析、禁控制字符/占位符）+ `nf-output-report/1`（form/tier 对齐 protocol/output_forms.json、digest/contract/issues/metrics）+ 失败拒收 `OutputRejected`；Assembly Runtime K-002 改为复用本模块（拒收即 blocked、无 export），样例 `results/output/output-report.json` committed==实时重算 + `docs/output-validation.md` + `test_output_validation_contract.py`（9 例：好产物收/5 类坏产物拒/gate 联动/form 词表）。G2 余 WP-23/24。
> 更新（R29，2026-11-14）：G2 WP-21 Assembly Runtime 落地——`core/assembly_runtime.py` + `nf agent run --assembly`（P00 黄金路径：intent→spec→task→context→adapter→output 校验→gate→export；产物两层：严格 `nf-assembly/1` 计划 + `nf-assembly-run/1` 信封；失败即停 status=blocked、两 adapter 均可 E2E、记录 committed==实时重算）+ `docs/assembly-runtime.md` + `results/assembly/sample-document.assembly.json` + `test_assembly_runtime_contract.py`（8 例，含 gate 红项/失败即停/core-only）。G2 余 WP-22/23/24。
> 更新（R28，2026-11-14）：G2 WP-20 Agent Adapter 落地——`core/agent_adapter.py` + `nf agent list|run`（有界 nf-task/1 → nf-adapter-output/1：citations 子集/预算/content kind/编造引用=0；mock + local-template 两 adapter；parity 报告 `results/adapter/adapter-report.json` 提交且 == 实时重算）+ `docs/agent-adapter.md` + `test_agent_adapter_contract.py`（8 例）；终端面命令 79/索引 213（docs/terminal 三语同步 + locales 重签）。G2 余 WP-21/22/23/24。
> 更新（R27，2026-11-14）：G1 QG1 收口审计完成——`results/G1_DOD.md` + `g1_dod.json`（§14.3 八条 + §11.2 WP-10…13 + QG1 覆盖/ID/链接/contract/陈旧/引用 + L3 packer 指标；现场复算 133 页/14-13-3-100-3、spec 确定、citation 100%、SELF_AUDIT p0=0）+ `test_g1_dod.py`（4 例，6 类变异自证）；**G1 verdict=pass-with-open-items，P0=0 → 进入 G2**。G1-DEBT-01/02 与外部 OPEN 显式挂账。
> 更新（R26，2026-11-14）：G1 WP-13 门禁接入完成——`verify.sh` 新增 **check43**（LLMWiki 完整性：覆盖/ID/关系/陈旧/三入口 + 生成物逐字节）与 **check44**（Spec 编译：确定性 + nf-spec/1/nf-task/1 schema + 拒绝未知 kind）；`quality_baseline` 四常量同步为 **check1-44/45/46/47/48/49 · PASS=89**（CHECK_NUMBERS 49/EXPECTED_PASS 89）；README/EN/JA/CHANGELOG/VERSION-MATRIX/CONFORMANCE/verification-cards/llms/repo_stats/SELF_AUDIT/interop 重新生成；capability_index 给 43/44 挂能力（消除能力空洞）。G1 实现全部落地，余 QG1 收口。
> 更新（R25，2026-11-14）：G1 WP-12 Context Packer 落地——`core/context_packer.py` + `nf wiki context --role`（author/reviewer/governance 角色隔离、预算硬上限与截断、citations 100%、注入检出/清除并计数、确定性）+ `docs/context-packer.md` + `test_context_packer_contract.py`（9 例：角色/预算/注入/确定性/CLI）。G1 余 WP-13（check43/44 接入 + QG1）。
> 更新（R24，2026-11-14）：G1 WP-11 Spec Compiler 落地——`core/spec_compiler.py` + `nf spec compile --intent`（intent→nf-spec/1→nf-task/1；确定性、未知 kind/wiki id 拒绝、任务图无环、budget 必填、context_refs 带 Wiki digest）+ `spec/intents/sample-document.json` + `docs/spec-compiler.md` + `test_spec_compiler_contract.py`（9 例：schema/确定性/拒绝/环/CLI exit 2）。G1 余 WP-12 Context Packer、WP-13 测试 + check43/44。
> 更新（R23，2026-11-14）：G1 WP-10 LLMWiki 编译器落地——`core/wiki_compiler.py` + `nf wiki {build,check,get,search,related,context}` + `wiki/{pages.json,INDEX.json,GRAPH.json,llms.txt,mcp.json}`（133 页：protocol 14/module 13/pipeline 3/domain 100/asset 3；投影不复制正文、真源 digest 判陈旧、关系可解析、三入口）+ `test_wiki_compiler_contract.py`（11 例，5 类变异自证）。G1 余 WP-11/12/13（Spec Compiler/Context Packer/check43-44）。
> 更新（R21，2026-11-14）：G0 DoD 收口审计完成——`results/G0_DOD.md` + `g0_dod.json`（§14.3 八条 + Gate 级 G0-ART/BLIND/4A/QG0/RULES/TOOLS/REVIEW；DOD-06 现场核 SELF_AUDIT stop.p0=0；OPEN-PRODUCT/OPEN-EXTERNAL/BLOCKED 工具/UNOBS/CQ2 显式挂账）+ `test_g0_dod.py`（5 例，6 类变异自证）；**G0 verdict = pass-with-open-items，P0 阻断=0 → 允许进入 G1**。
> 更新（R20，2026-11-14）：§4A R6 不变量落地——`results/reverse/INVARIANTS.md` + `invariants.json`（7 层 14 条：tested 6 / covered-by-existing 4 / unobservable 4（INV-02/03/04 等 G1、INV-06 等 G2）；计划路径 `tests/invariants/` 映射 `desktop/tests/test_reverse_invariants.py`——DEV-05）+ `test_reverse_invariants.py`（11 例：6 条直接断言 + 既有测试存在性 + unobservable gate + 6 类变异自证）。§4A R0–R6 七件套齐；下一步 G0 DoD 收口审计。
> 更新（R19，2026-11-14）：§4A R5 同行差分落地——`results/reverse/PEER_DIFF.md` + `peers.json`（6 项对照：Spec Kit/OpenSpec、DeepWiki-GitMCP-Context7、ODCS-datacontract-cli、in-toto-Sigstore-CycloneDX、OPA-Cedar；借/不造边界；3 条影响设计的决策 D-PD-01…03 落 G1/G3）+ `test_reverse_peers.py`（3 例，6 类变异自证）。只作机制借鉴、不作质量背书。§4A 仍余 R6。
> 更新（R18，2026-11-14）：§4A R4 失败考古落地——`results/reverse/FAILURE_ARCHAEOLOGY.md` + `results/reverse/failures.json`（13 条失败模式：CI 假绿/required-skip 放行/隐藏件/provenance/基线松动/SAST 键级漂移/死链/路径虚假保证/生成区误改/台账造假 等；5 条文档-代码不一致；9 个缺口 R4-01…R4-09 进 R6）+ `test_reverse_failures.py`（3 例，6 类变异自证；commit 存在性 + skip 实时重算 + 固定窗口 stats）。§4A 仍余 R5–R6。
> 更新（R17，2026-11-14）：§4A R3 耦合/重复实现落地——`results/reverse/COUPLING.md` + `coupling.json`（300 模块/540 边/0 环/9 条 SDP 已进基线；fan-in/out 热点；7 项重复裁定：canonical 兼容重复、sha256/JSON/原子写共享原语、路径包含性 duplicate-suspected、覆盖率与注册表 distinct-role）+ `test_reverse_coupling.py`（3 例，6 类变异自证；实时重算图比对，图变即红）；check12 预算 2150→2175（+8.1s 模块，容量调整）。§4A 仍余 R4–R6。
> 更新（R16，2026-11-14）：§4A R2 行为重建落地——`results/reverse/BEHAVIOR.md` + `results/reverse/behavior.json`（11 条行为流：9 documented + 2 gap；状态机 S-01 冻结链/S-02 信任等级/S-03 契约生命周期；失败语义 exit 0/1/2）+ `test_reverse_behavior.py`（3 例，7 类变异自证）；§4A 仍余 R3–R6。
> 更新（R15，2026-11-14）：§4A R1 契约提取落地——`results/reverse/CONTRACT_MAP.md` + `results/reverse/contracts.json`（显式契约 11 组、隐式契约 8 组、缺口 G-01…G-05）+ `test_reverse_contracts.py`（4 例，6 类变异自证）；§4A 仍余 R2–R6（G0 收口前必做）。
> 更新（R14，2026-11-14）：WP-0A 产品发现/价值框架落地——`docs/product/{PRFAQ,GTM,INTERVIEWS}.md` + `protocol/product.json`（问题/JTBD、4 条价值假设全部 unverified、指标+反指标、MVP 做/不做、支持分级/定价假设、访谈计划 3 槽位 planned-external）+ `core/product.py` + `test_product_contract.py`（6 例，7 类变异自证）；D01 None→Partial、D14 None→Partial（BL-06 框架达成；外部访谈/试点/LOI 属外部操作，OPEN-PRODUCT 未关）。
> 更新（R13，2026-11-14）：WP-0H 全仓 CQ0/CQ1 落地——`docs/CQ_REPORT.md`（工具矩阵 13 件、3 件 BLOCKED：dotnet/cosign/gitleaks；CQ1 九维自动扫描）+ `docs/QUALITY_DEBT.md`（QD-01…08）+ `docs/REVIEW_CHECKLIST.md`（人工审查清单/记录模板）+ `results/cq/{toolchain,scan}.json` + `results/cq/findings.jsonl` + `results/cq/hotspots.md` + `core/cq_scan.py` + `scripts/cq_scan.py` + `test_cq_scan_contract.py`（10 例，6 类变异自证）；CQ1 结果 P0=0/P1=0，P2=54/P3=37，CC>15 存量 302 已棘轮冻结。
> 更新（R12，2026-11-14）：WP-0G 保证案例 + RAID + 伦理落地——`docs/assurance/ASSURANCE_CASE.md`（GSN：C0–C3 目标 / A1–A8 论证，逐条 assumption+rebuttal+真实证据）+ `results/assurance/CLAIMS.json` + `docs/RAID.md` + `protocol/raid.json`（R-01…R-08 风险 + AS-01…03 假设 + I-01…05 问题 + D-01…03 依赖 + 干系人 + 变更控制）+ `docs/ETHICS.md`（VSD/IEEE 7000 价值冲突 EV-01…06）+ `core/assurance.py` + `test_assurance_contract.py`（7 例，7 类变异自证）；D16 None→Partial（BL-12 closure）、D17 补 RAID/干系人/变更控制。
> 更新（R11，2026-11-14）：WP-0E 可访问性/i18n/人因落地——`A11Y.md` + `I18N.md` + `docs/a11y/A11Y_QA.md` + `docs/i18n/I18N_QA.md` + `protocol/{accessibility,i18n}.json` + `core/{accessibility,i18n_checks}.py` + `test_a11y_i18n_contract.py`（10 例，9 类变异自证）；WCAG 8 项/PAIR-HAX 6 条/可用性模板/违规预算 0；locale 3/入口 3/文档译件 6 组镜像 + source_sha256 + UTC/bidi 零命中 + RTL 策略；D10/D11 由 None 重估为 Partial（BL-08/BL-09 closure 条件满足）。
> 更新（R10，2026-11-14）：WP-0C 法务/许可/IP + 开源治理落地——`LEGAL.md` + `GOVERNANCE.md` + `docs/legal/{TRADEMARK,CONTRACTS,EXPORT}.md` + `protocol/legal.json` + `core/legal.py` + `scripts/legal_audit.py` + `test_legal_contract.py`（9 例，8 类变异自证）；**更正** D12 此前把 LICENSE 写成 AGPL（实为 MIT，方案 §15A.2 的 AGPL/双许可假设已作为偏差显式登记）；D12/D13 证据补强（BL-07/BL-10 closure 条件满足，仍不提供法律意见/不声称合规）。
> 更新（R9，2026-11-14）：WP-0F AI 治理 + 评测效度落地——`docs/ai/AI_GOVERNANCE.md`（影响评估/模型风险/监管映射，claim 只写 mechanism-alignment）+ `docs/eval/EVAL_PROTOCOL.md`（预注册/样本量/inter-rater/反指标/效度威胁）+ `protocol/ai_governance.json` + `protocol/eval_validity.json` + `core/{ai_governance,eval_validity}.py` + `results/eval/interrater_sample.json` + `test_ai_eval_contract.py`（9 例，8 类变异自证）；D06/D15 证据补强（均仍 Partial——不声称合规，映射仅机制对照；BL-02/BL-05 closure 条件满足）。
> 更新（R8，2026-11-14）：WP-0D 安全事件/漏洞披露/BCP/DR + 供应商登记落地——`docs/security/INCIDENT_RESPONSE.md`、`docs/sre/{SRE,BCP_DR}.md`、`docs/legal/VENDORS.md`、`SECURITY.md` 第七节入口；`protocol/ops.json`（S0–S3/runbook 7 步/披露口径/3 条 SLO/BCP 资产与场景）+ `protocol/vendors.json`（6 家供应商/退出计划/attestation）+ `core/ops.py` + `scripts/ops_drill.py` + `results/ops/drills.json`（桌面/恢复/披露/退出四类演练）+ `test_ops_contract.py`（10 例，7 类变异自证）；D09 由 None 重估为 Partial、D18 由 None 重估为 Partial、D04 补 IR/披露证据（仍 Partial——ASVS/LLM 映射缺）。
> 更新（R7，2026-11-14）：WP-0B 隐私/数据生命周期落地——`PRIVACY.md` + `docs/privacy/{DATA_MAP,DPIA,RETENTION}.md` + `docs/qa/PRIVACY_QA.md` + `protocol/privacy.json`（8 数据类/四级分类/四保留模式）+ `core/privacy_scan.py` + `test_privacy_contract.py`（8 例，含删除失败/PII 扫描/脱敏抽样/变异自证）；D05 由 None 重估为 Partial，BL-01 的 closure 条件（数据地图+DPIA+保留/删除测试通过）已满足。
> 更新（R6，2026-11-14）：WP-03 生产威胁模型落地——`protocol/boundaries.json` 六条边界（代码件+文档件在场）、`docs/production/THREAT_MODEL.md`、`results/production/threat_vectors.json`（STRIDE 8 + 失败矩阵 8，状态词表 enforced/partial/planned/UNOBSERVABLE）；D04 仍为 Partial（ASVS/LLM 映射与 IR runbook 未建），不因威胁模型存在而上调。
> 边界：本件是 `NF-Final` 方案的基线；`results/trust/BASELINE.md` 是 `NF-TrustFabric` 方案的基线。两份互不替代，数字各按各的复跑命令取用。

## 0. 结论（先行）

1. **方案基线 `01016908` 不在本仓**（`git cat-file -t 01016908` → `fatal: Not a valid object name`）。方案 §1.2/§3 的审计对象与本机不同源；本书以 HEAD 实读为准，方案里的路径/数字只能作意图参考。
2. **本仓已有能力大于方案 §3A 的 `None/Partial` 判定**：Trust Fabric 的契约/证据/签名/锚/类型/模型卡族已在 HEAD（`desktop/src/core/trust/` 20 个模块、14 件 schema、32 个 `test_trust_*.py`）；`02_联动注册表.md` 1190 行、`community/` 1879 件域包资产、111 个 `protocol.yaml`、100 份 `DOMAIN_SPEC.json` 都是真源存量。
3. **真实缺口集中在生产/装配平面（G1/G2）与跨域基线件（G0）**：`desktop/src/core/production/`、`desktop/src/core/governance/` 两个方案目录、11 个核心 schema 里的 8 件、CLI 的 `wiki/spec compile/assembly run/agent/production/governance` 六组命令、`scripts/check_{wiki,spec,independence,governance}.py` 四件脚本、以及 `docs/{product,privacy,legal,sre,a11y,i18n,assurance,qa,adr,governance,wiki}` 与 `results/{reverse,qa,cq}` **全部不在场**（§3）。
4. **check 编号冲突必须先对账**：方案 §14.1 的 check45–48 已被 Trust Fabric 占用（`verify.sh` 段 D）；本仓 check43/44 是 `quality_baseline.CHECK_NUMBERS` 里**显式预留的空号**（`desktop/src/core/quality_baseline.py:21-25`）。新增面按 §6 的映射落地，不得占用/覆盖 45–48。
5. **门禁基线如实**：`bash verify.sh --checks-only` → `PASS=83 WARN=2 FAIL=0`，exit 0（46 条 check 函数，编号 `check1-42/45-48`）。两条 WARN 的真实含义见 §2，不得当红也不得当绿。
6. **测试基线**：`pytest` 收集 **5,549 例 / 671 个测试文件**（8.12 s）。全量测试本轮**未跑**；按 AGENTS.md「三件套」取证（静态面全量 + 受影响面全量 + 仓库原生新鲜度命令），全量口径属 CI full 档。
7. **基线发现 1 条 P2 缺陷（F-001）**：Windows 上 `test_trust_verify.py::ScriptContractTest::test_missing_input_is_undecidable_with_guidance` 因子进程 stderr 以 GBK 解码而失败；`PYTHONUTF8=1` 下通过。属测试可移植性缺陷，不是产品判定失败；登记进 §5 缺陷表，由 §13B/§13C 的测试质量面收口。
8. **环境**：Python 3.11.9 / pytest 9.1.1 / Node 24.19 / .NET SDK 8.0.4xx 在场；`ruff/bandit/radon/mypy/coverage/vulture/shellcheck/cargo` 在场；`cosign`、`gitleaks` **不在场**（不得写成通过）。

## 1. 实施机与检出事实

| 项 | 值（本轮实读） |
|---|---|
| 仓库根 | `D:\NinFenz`（origin `https://github.com/Monyeah777/NinFenz.git`） |
| 分支 / HEAD | `work/l4-floors` / `4fde4e3b542039fad3efcac297bcc7864aa066bf` |
| 脏文件 | 0（`git status --porcelain` 为空） |
| 方案基线 `01016908` | **不在本仓**（`git cat-file -t` 未知对象） |
| 提交史 | 1,598 提交，2026-09-03 → 2026-11-14；`docs` 454 / `feat` 429 / `fix` 284 / `chore` 224 / `test` 60 / `refactor` 55 / `ci` 36 / `perf` 21 / `merge` 12 / `release` 10；标题含 `security` 24、`revert` 1、`hotfix` 0 |
| tracked 文件 | 4,578 |
| Python | 1,259 文件 / 241,182 行（`desktop/src/core` 379 / 78,951；`desktop/tests` 671 / 109,839；`scripts` 83 / 28,056） |
| Markdown | 1,199 文件 / 139,018 行 |
| JSON | 1,302 文件 / 423,080 行 |
| YAML | 144 文件 / 7,006 行 |
| Rust / C# / Shell | 91 / 73,388 行；110 / 41,103 行；14 / 4,138 行 |
| 真源存量 | `01_核心协议.md` 415 行、`02_联动注册表.md` 1190 行、`06` 268 行、`07` 97 行；`03_管线库` 3 件、`04_模块库` 13 件、`05_资产库` 6 件；`protocol/` 143 件 / 218,144 行 |
| 域包存量 | `community/` 1,879 件 / 236,836 行；111 个 `protocol.yaml`；100 份 `DOMAIN_SPEC.json` |
| Python | 3.11.9；pytest 9.1.1 |
| Node.js | v24.19.0 |
| .NET | SDK 8.0.4xx（`dotnet --list-sdks` 可见） |
| 工具在场 | `ruff` `bandit` `radon` `mypy` `coverage` `vulture` `shellcheck` `cargo` |
| 工具缺失 | `cosign`、`gitleaks`（缺失即记 BLOCKED/WARN，不得「跳过 = 通过」） |

复跑：

```bash
git rev-parse --short HEAD; git status --porcelain | wc -l
git cat-file -t 01016908 || echo ABSENT
git -c core.quotepath=false ls-files | wc -l
git log --oneline | wc -l
python -V; node -v; dotnet --list-sdks | head -1
```

## 2. 门禁与测试基线

| 面 | 命令 | 本轮结果 |
|---|---|---|
| 静态门禁 | `bash verify.sh --checks-only` | **PASS=83 WARN=2 FAIL=0**，exit 0 |
| check 函数 | `grep -cE '^check[0-9]+\(\)' verify.sh` | **46**（编号 1–42、45–48；43/44 预留空号） |
| 声明基线 | `desktop/src/core/quality_baseline.py:23-26` | `CHECK_NUMBERS = tuple(range(1,43)) + (45,46,47,48)`；`EXPECTED_CHECKS=46`；`EXPECTED_PASS=83`；`CHECK_LABEL="check1-42/45/46/47/48"` |
| 测试收集 | `python -m pytest desktop/tests --collect-only -q` | **5,549 例**，8.12 s；671 个测试文件 |
| 代表测试 | `python -m pytest desktop/tests/test_trust_{process,bundle,verify}.py -q` | **49 passed, 1 failed**（F-001，见 §5） |
| 全量测试 | `bash verify.sh --full` | **本轮未跑**（口径见下） |

两条 WARN 的真实含义（不得当红，也不得当绿）：

1. check12 的 `--checks-only` 分支按设计不跑 unittest，提示文案「desktop/tests 不在场」是该分支固定文案，目录实测在场（671 个 `test_*.py`）。
2. check42「仓库自身 provenance 缺签名外锚（`cosign` 不在场）」——只证明外部验签机制可用且对篡改敏感，**不等于**本仓 provenance 已不可伪造。

**全量测试口径**：本报告按 AGENTS.md「三件套」取证（静态面全量 + 受影响面全量 + 仓库原生新鲜度命令），`bash verify.sh --full`（3,000+ 测试）属 CI full 档，未跑就写「未跑」。任何「全绿」字样只指上表静态门禁那一行。

## 3. 方案锚点复验（对照本机 HEAD）

判定口径：**命中** = 语义在且路径/接口可核；**漂移** = 能力在但落点/命名不同；**不成立** = 方案所引模块/位置在本仓不存在；**缺** = 方案要求、本仓无对应件。

### 3.1 组件目录（§4.3 / §4.4）

| 方案锚点 | 方案用途 | 本机实读 | 判定 |
|---|---|---|---|
| `desktop/src/core/production/`（wiki/spec/context/agent/assembly/output/delivery/assets） | 生产平面 | 目录不存在；等价件散在 `core/{pipeline,pipelinerun,assemble_plan,assemble_build,exporter,output_forms,output_envelope,composer,retriever,injection_budget,domain_pack,library,asset_ledger}.py` 等 | **漂移**（需映射，不重写） |
| `desktop/src/core/governance/`（contract/obligation/evidence/verify/trust/policy/report/anchor） | 治理平面 | 目录不存在；等价件在 `core/trust/{bundle,dsse,keys,anchor,verify,model_card,human_review,entity,process,trust_store,public_anchor,canonical}.py` + `core/{attest,receipts,transparency_log,evidence,revocations,trust_anchor,key_transparency,contract_history,policy_snapshot,approval}.py` | **漂移**（G3 只补缺口，不重建） |
| `results/SELF_AUDIT.json`、`docs/SELF_AUDIT.md` | 自审计 | 根级不存在；现件为 `results/trust/SELF_AUDIT.json`、`docs/trust/SELF_AUDIT.md` | **缺**（G5 新建方案级自审计） |
| `results/reverse/`、`results/qa/`、`results/cq/` | 逆向/分层 QA/CQ | 三者均不存在 | **缺**（G0/WP-0H 起建） |
| `docs/{product,privacy,legal,sre,a11y,i18n,assurance,qa,adr,governance,wiki}` | 跨域基线 | 目录均不存在；现有方向/治理文档为 `STRATEGY.md`、`SECURITY.md`、`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`MAINTAINERS.md`、`SUPPORT.md`、`THIRD-PARTY-NOTICES.md`、`decisions/`（3 件，示例为主）、`docs/{en,ja,ccos,meta,standards,trust}` | **缺**（WP-0A…0G 新建） |

### 3.2 核心 schema（§6.2）

| 方案 schema | 本机实读 | 判定 |
|---|---|---|
| `nf-verify/1` | `protocol/trust/verify.schema.json`；`core/trust/verify.py` | 命中 |
| `nf-model-card/1` | `protocol/trust/model-card.schema.json`；`core/trust/model_card.py` | 命中 |
| `nf-abstention/1` | 已有引用（`meta_cockpit/abstention.py:121` 等 2 处） | 命中（需核 schema 件，R1） |
| `nf-contract/1` | 无 | 缺 |
| `nf-wiki-page/1` | 无 | 缺 |
| `nf-spec/1` | 无 | 缺 |
| `nf-task/1` | 无（现有 `nf-task-profile/1`、`nf-task-handoff/1`，语义不同） | 缺 |
| `nf-assembly/1` | 无（现有 `nf-graphspec/1`、`nf-pipeline-advisory/1`） | 缺 |
| `nf-production-event/1` | 无（现有 `nf-job-event/1`、`nf-external-events/1`、`nf-event_registry`） | 缺 |
| `nf-evidence-card/1` | 无（现有 `nf-evidence/1`、`nf-evidence-roles/1`、`nf-claim-bundle/1`） | 缺 |
| `nf-eval-evidence/1` | 无（现有 `nf-eval-protocol/1`、`nf-eval-run/1`、`nf-eval-compare/1`） | 缺 |

已存在的 `nf-*/1` 标识共 200+ 个（`protocol/` + `desktop/src/core/` 实读枚举，见 `results/reverse/INVENTORY.md` §2），所以新增 schema 必须查重、不得与既有 id 撞语义。

### 3.3 CLI / 脚本 / 关键词（§7.1 / §7.3 / §17.3）

| 方案接口 | 本机实读 | 判定 |
|---|---|---|
| `nf wiki build\|check\|get\|search\|related\|context` | 无 `wiki` 子命令；`nf --help` 77 个子命令中无此项 | 缺 |
| `nf spec compile` | `nf spec` 仅 `ls`（Spec Registry 查询，`scripts/nf.py spec`） | 缺 |
| `nf assembly run` | 无 `assembly` 组；等价 `nf assemble`（需求 → 装配计划/成品，`--check/--build`） | 漂移 |
| `nf agent list\|run --adapter` | 无 `agent` 组；adapter 以库件+导出格式存在（7 个 `*adapter*` 模块，`test_*adapter*.py`） | 缺 |
| `nf production deliver` | 无 `production` 组 | 缺 |
| `nf governance verify\|anchor\|sign\|policy` | 无 `governance` 组；等价 `nf evidence/check/conformance/transparency/receipts` + `scripts/trust_verify.py` | 漂移 |
| `scripts/check_wiki.py` / `check_spec.py` / `check_independence.py` / `check_governance.py` | 四件均不存在 | 缺 |
| `protocol/keywords.json` + `nf keywords --check` | 均不存在 | 缺 |
| 退出码 0/1/2 | `core/trust/verify.py:1-12` 明确 0/1/2；`scripts/trust_verify.py` 已实现 | 命中（trust 面；生产面待接） |

### 3.4 §13.3 Claim–Evidence 锚点（方案示例表）

方案 §13.3 六条 claim 的代码锚点全部是「待建路径」：`production/wiki/compiler.py`、`production/spec/compiler.py`、`production/agent/adapter.py`、`scripts/check_independence.py`、`governance/verify.py`、`test_wiki_single_source`、`test_spec_deterministic`、`test_agent_portability`、`test_core_only`、`test_external_artifact` —— 本机均不存在，方案表把它们标为 `TODO` 与实情一致。本报告 §5 按「实仓等价锚点」给出可执行矩阵。

### 3.5 §13C 重点人工审查区（已在场，可直接用）

| 高风险面 | 实仓落点 | 判据 |
|---|---|---|
| `exec(compile(...))` | `core/gate_inproc.py` | 有 `repo_trust` 守护（方案 §13C.4 点名） |
| MCP 参数校验 | `core/trust_boundary.py`、`core/mcp_*.py` | `unknown_policy.py` fail-closed |
| 路径/写入 | `core/paths.py::validate_path`；`desktop/tests/test_paths.py`、`test_output_path_escape.py` | 方案 §13C.4 点名区已有单测 |
| 密钥/TSA | `core/timestamp.py`、`core/trust/key_material.py`、`scripts/trust_keygen.py` | RFC3161 + 0600 语义 |

## 4. §3A 覆盖重估（18 领域）

| # | 领域 | 方案判定 | 本机实读证据 | 重估 | closure（方案） |
|---|---|---|---|---|---|
| D01 | 产品发现/价值 | Partial | `docs/product/{PRFAQ,GTM,INTERVIEWS}.md` + `protocol/product.json`（3 JTBD、4 价值假设 unverified、指标/反指标、MVP、机会解决树、访谈计划/同意/问题脚本）+ `core/product.py` + `test_product_contract.py`；**3 次访谈与试点/LOI 属外部操作未执行（OPEN-PRODUCT）** | **重估为 Partial**（BL-06 框架达成；外部验证挂 OPEN） | WP-0A ✅/外部 |
| D02 | 需求工程 | Partial | `01_核心协议.md` 415 行、`protocol/normative.json`、`nf-requirements/1`；无 RTM、无 ISO 25010 NFR 表 | **Partial 成立** | WP-01/0A |
| D03 | 架构 | Partial | `docs/ccos/` 20 件、`decisions/` 3 件（含 2 件示例）；无质量属性场景/ATAM-lite、无 arc42 视图件 | **Partial 成立** | WP-02/04 |
| D04 | 安全 | Partial | `SECURITY.md`（含私密披露通道与处理口径）、`docs/security/INCIDENT_RESPONSE.md`（IR runbook/分级/披露衔接）、`docs/trust/THREAT_MODEL.md`、`docs/production/THREAT_MODEL.md` + `protocol/boundaries.json`、`results/production/threat_vectors.json`、`protocol/ops.json`、`scripts/sast_check.py`、`core/trust_boundary.py`；仍无 ASVS/LLM Top10 映射 | **Partial 成立**（IR/披露面补齐；ASVS/LLM 映射仍缺） | WP-0D ✅/WP-0F |
| D05 | 隐私 | Partial | `PRIVACY.md`、`docs/privacy/{DATA_MAP,DPIA,RETENTION}.md`、`docs/qa/PRIVACY_QA.md`、`protocol/privacy.json`（8 类数据/四级分类/四保留模式/删除证据）、`core/privacy_scan.py` + `secret_guard`（PII/凭据扫描与脱敏）、`test_privacy_contract.py`；无跨境/委托处理与法律审核（本地优先不适用；不提供合规结论） | **重估为 Partial**（BL-01 数据地图+DPIA+保留/删除测试已过；法律审核不提供） | WP-0B ✅ |
| D06 | AI 治理 | Partial | `docs/ai/AI_GOVERNANCE.md` + `protocol/ai_governance.json`（影响评估 IA-01…04、模型风险 MR-01…05、监管映射 6 框架、人类监督/透明度/救济、claim 仅 mechanism-alignment）+ `core/ai_governance.py` + `test_ai_eval_contract.py`；不声称合规/认证（映射非法律意见） | **Partial 成立**（BL-02 closure：影响评估+模型风险+监管映射齐；仍不做合规结论） | WP-0F ✅ |
| D07 | 数据治理 | Partial | `protocol/{data_contracts,asset_contracts,asset_keys}.json`、`core/data_quality.py`（`scripts/data_quality.py`）；无数据分类/所有权/血缘图 | **Partial 成立** | WP-0B |
| D08 | 质量管理 | Partial | `verify.sh` 46 条 check、`quality_baseline`、`docs/st-quality-checklist.md` + **CQ0/CQ1**：`docs/CQ_REPORT.md`（工具矩阵/九维自动扫描/P0=0,P1=0,P2=54,P3=37）、`docs/QUALITY_DEBT.md`（QD-01…08）、`docs/REVIEW_CHECKLIST.md`、`results/cq/*`、`core/{cq_scan,code_metrics,quality_gate}.py`；CQ2–CQ6（人工高危/测试质量/跨语言/评分卡）未做 | **Partial 成立**（自动扫描与债/清单齐；人工审查阶段未做） | §13A/CQ2 |
| D09 | 可靠性/SRE/BCP | Partial | `docs/sre/{SRE,BCP_DR}.md`（SLO 三条/错误预算逻辑口径/资产备份 RTO·RPO/三类故障场景）、`docs/security/INCIDENT_RESPONSE.md`（S0–S3 + IR-01…07）、`protocol/ops.json`、恢复演练（DR-02）；无 on-call/日历级 RTO（本地优先不适用） | **重估为 Partial**（BL-03 closure：IR runbook + BCP/恢复演练通过） | WP-0D ✅ |
| D10 | 可访问性/UX/人因 | Partial | `A11Y.md` + `protocol/accessibility.json`（WCAG 2.2 八项：6 enforced/1 partial/1 n-a-with-reason、PAIR/HAX 6 条、可用性测试模板 UT-01/02、违规预算 0）+ `core/accessibility.py` + `docs/a11y/A11Y_QA.md` + `test_a11y_i18n_contract.py`；TUI 键盘/无色/限长/self_check 机检 | **重估为 Partial**（BL-08 closure：WCAG 清单+PAIR/HAX；可用性实测/读屏实测属外部操作未做） | WP-0E ✅ |
| D11 | 本地化/i18n | Partial | `I18N.md` + `protocol/i18n.json`（locale 覆盖下限/locale 清单/UTC 时区口径/RTL 策略/bidi+零宽闸门/NFC）+ `protocol/locales.json`（3 locale、6 组译件、source_sha256）+ `core/i18n_checks.py` + `docs/i18n/I18N_QA.md`；当前无 RTL locale（不声称） | **重估为 Partial**（BL-09 closure：locale 清单+RTL/bidi 测试；RTL 渲染/外部语言服务属外部/planned） | WP-0E ✅ |
| D12 | 法务/许可/IP | Partial | **实际许可 = MIT（非方案假设的 AGPL/双许可）**：`LICENSE`/`LICENSES/{MIT,LicenseRef-Community-Submission}.txt`、`REUSE.toml`（3 annotations）、`LEGAL.md` + `docs/legal/{TRADEMARK,CONTRACTS,EXPORT}.md`、`protocol/legal.json`、`THIRD-PARTY-NOTICES.md`（44 行）+ 生成器/requirements/SBOM 可核、`scripts/legal_audit.py` + `test_legal_contract.py`；合同为模板（未签署）、不提供法律意见 | **Partial 成立**（BL-07 closure：许可审计+NOTICE+合同/出口检查；无正式法律审核/商标注册） | WP-0C ✅ |
| D13 | 开源治理/社区 | Partial | `GOVERNANCE.md`（角色/决策/发布/废弃/SemVer/Scorecard 登记）+ `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`MAINTAINERS.md`、`SECURITY.md`、`SUPPORT.md`、`CHANGELOG.md`、`docs/release.md`、`module_lifecycle` deprecate/restore、`.github/workflows/{release-gate,scorecard}.yml`；单维护者、无社区规模/SLA 承诺 | **Partial 成立**（BL-10 closure：贡献/发布/废弃/披露流程齐；社区治理仍单人事实） | WP-0C ✅ |
| D14 | 商业/GTM/支持 | None | `SUPPORT.md` 在（支持分级雏形）；无定价假设/LOI/试点 | **Weak→None 成立**（仅支持面有雏形） | WP-0A/0C |
| D15 | 测量/实验效度 | Partial | `docs/eval/EVAL_PROTOCOL.md` + `protocol/eval_validity.json`（预注册字段/冻结规则、样本量 ≥3、Cohen kappa ≥0.6 现算、反指标 CM-01…03、效度威胁 VT-01…05）+ `results/eval/interrater_sample.json` + `core/eval_validity.py`；具体预注册协议 `protocol/eval/protocol.json` 过 `eval_harness` 校验 | **Partial 成立**（BL-05 closure：预注册+inter-rater+反指标齐；真实外部盲评仍属外部操作） | WP-0F ✅ |
| D16 | 伦理/保证 | Partial | `docs/assurance/ASSURANCE_CASE.md` + `results/assurance/CLAIMS.json`（GSN/CAE：C0–C3→A1–A8→证据；supported 须 ≥2 件含测试证据；缺口有 owner 并进 RAID）+ `docs/ETHICS.md`（IEEE 7000/VSD：干系人/价值冲突 EV-01…06/设计回应/残余风险）+ `core/assurance.py` + `test_assurance_contract.py`；不声称伦理认证/合规 | **重估为 Partial**（BL-12 closure：保证案例+伦理评审；外部伦理审查未做） | WP-0G ✅ |
| D17 | 项目/项目群 | Partial | `docs/RAID.md` + `protocol/raid.json`（R-01…R-08 / AS-01…03 / I-01…05（link 保证案例缺口）/ D-01…03 / 4 类干系人 / 变更控制）+ `decisions/`、`handovers/`、`postmortems/`；单维护者/无正式 PMO | **Partial 成立**（RAID/干系人/变更控制齐；项目群治理仍单人） | WP-0G ✅ |
| D18 | 供应商/第三方 | Partial | `docs/legal/VENDORS.md` + `protocol/vendors.json`（6 家：模型/TSA/公共日志/托管/包源/部署；used_by/attestation/退出计划/不得处理用户数据）+ 退出就绪演练（DR-04）；不签 DPA（本地优先不委托处理） | **重估为 Partial**（BL-04 closure：vendor register+exit plan+SBOM/attestation） | WP-0D ✅ |

重估结论（R10 更新）：18 领域里 1 项被方案低估（D11）；D12 事实更正为 MIT（方案假设 AGPL/双许可，已登记偏差）。**P0 盲区 BL-01…BL-05 已全部 closure**（R7–R9）；P1 中 BL-07（法务）/BL-10（开源治理）达 closure 条件（R10）；BL-08（a11y）/BL-09（i18n）达 closure 条件（R11）；BL-06（产品）/BL-11（商业）仍缺；BL-12（伦理/保证案例，P2）达 closure 条件（R12）。

## 5. FR/NFR Claim–Evidence 矩阵（方案 §5.1–§5.5，共 34 条）

状态口径：**SUPPORTED** = 代码 + 测试/机检可证；**PARTIAL** = 能力部分在场、缺方案要求的验收面；**ABSENT** = 方案要求的实现/锚点不在场。矩阵只登记**本机实读**，不抄方案判词。

### 5.1 生产/装配 PR

| ID | 级别 | 状态 | 本机等价锚点 | 测试/证据 | 缺口 → WP |
|---|---|---|---|---|---|
| PR-01 无治理完成交付 | MUST | PARTIAL | `scripts/nf.py run`（retrieve→compose→gate→export）、`core/pipeline.py`、`core/exporter.py` | `test_pipeline.py`、`test_exporter.py` | 无 core-only 安装矩阵；无交付事件；G2 |
| PR-02 spec→task/assembly | MUST | ABSENT | **五件 schema 已落地**（`protocol/production/`：nf-contract/nf-wiki-page/nf-spec/nf-task/nf-assembly）；`nf spec` 仍仅 registry 查询，无 intent→spec→task 编译器 | `test_schema_reference.py`（13 例，含 5 类变异自证） | G1（WP-11 编译器） |
| PR-03 有界任务槽位 | MUST | PARTIAL | `06_Agent执行协议.md`、`nf-task-profile/1`、`nf-task-handoff/1`、`core/injection_budget.py` | `test_agent_start_contract.py`、`test_injection_budget.py` | 无槽位越界拒绝测试；G1/G2 |
| PR-04 生产事件（纯数据） | MUST | PARTIAL | 事件族 `nf-job-event/1`、`nf-external-events/1`、`protocol/event_registry.json` | 无专项测试 | 无 `nf-production-event/1`；G2 |
| PR-05 2 Adapter 同 spec 可移植 | MUST | ABSENT | 7 个 `*adapter*` 模块（import/skill/mcp/mvu/ccv3/agent_rules/driver） | 各 adapter 单测在场 | 无「同 spec 双 adapter parity」判据；G2 |
| PR-06 上下文打包/引用/预算 | MUST | PARTIAL | `core/composer.py`、`retriever.py`、`injection_budget.py`、`protocol/injection_profiles.json` | `test_composer.py`、`test_retriever.py`、`test_injection_budget.py` | 无 citation 强制；G1 |
| PR-07 输出校验 | MUST | PARTIAL | `core/output_forms.py`、`output_envelope.py`、`validator.py`、`protocol/output_forms.json` | `test_output_forms.py` | 无 contract/output form 统一拒收面；G2 |
| PR-08 生产指标 | SHOULD | PARTIAL | `docs/45_执行遥测规范.md`、`core/telemetry_semconv.py`、`nf-timings/1` | 无导出判据 | 指标不可导出对账；G2 |

### 5.2 LLMWiki/规范 WK

| ID | 级别 | 状态 | 本机等价锚点 | 测试/证据 | 缺口 → WP |
|---|---|---|---|---|---|
| WK-01 Wiki 由真源编译 | MUST | ABSENT | 无 wiki 编译器；`llms.txt` 由 `scripts/sync_llms.py` 同步，`docs/standards/*` 由 `scripts/geo_export.py --write` 生成（标准目录，非协议 Wiki） | `docs/standards/index.md` 首行「禁止手改」 | G1 |
| WK-02 每类对象有页 | MUST | ABSENT | 04/03/05 与 protocol 无页面投影 | — | G1 |
| WK-03 页面 ID 唯一/relations 可解析 | MUST | ABSENT | 无 wiki id 体系 | — | G1 |
| WK-04 machine_contract/Pipeline/asset schema 可解析 | MUST | PARTIAL | `core/machine_contract.py`、`docs/machine_contract.md`、`core/pipeline_loader.py`、`protocol/asset_contracts.json` | `test_machine_contract*`、`test_pipeline_loader.py` | 无 Wiki 页级 contract 检查；G1 |
| WK-05 源变更触发陈旧检查 | MUST | PARTIAL | `scripts/freshness_check.py`、check37（文档新鲜度）、docs 生成物 digest 钉法 | `test_freshness_check.py` | 无 wiki 页 digest；G1 |
| WK-06 三入口 llms.txt/MCP/CLI | MUST | PARTIAL | `llms.txt`、`nf serve`（MCP stdio）、`nf --help` | `test_llms_contract.py`、`test_llms_full_contract.py`、`test_mcp_adapter.py` | 无 `nf wiki` CLI；G1 |
| WK-07 citations + 输出引用 wiki id | MUST | ABSENT | 无 wiki id 引用校验 | — | G1 |
| WK-08 不复制正文/第二真源 | MUST | PARTIAL | docs 生成物「禁止手改」纪律已在（`docs/layers.md`、`docs/verification-cards.md`） | check37/38 | 无 Wiki 重复正文检查；G1 |

### 5.3 治理 GV

| ID | 级别 | 状态 | 本机等价锚点 | 测试/证据 | 缺口 → WP |
|---|---|---|---|---|---|
| GV-01 独立验证非 NF 产物 | MUST | PARTIAL | `core/trust/verify.py`（bundle+policy，任意 artifact digest）、`scripts/trust_verify.py` | `test_trust_verify.py` | 无非 NF 产物 fixture + 独立性端到端；G3 |
| GV-02 契约生命周期 | MUST | PARTIAL | `core/contract_history.py`（`nf-contract-history/1`）、`protocol/adr/registry.json` | `test_contract_history*` | 无 `nf-contract/1` 状态机（版本/审批/废弃）；G3 |
| GV-03 义务→证据要求 | MUST | PARTIAL | `nf-method-obligations/1`、`nf-bridge-obligation/1`、`core/trust/bundle.py` | 无 obligation→evidence 编译测试 | G3 |
| GV-04 离线复算/缺锚 exit 2 | MUST | SUPPORTED | `core/trust/verify.py:1-12`、`scripts/trust_verify.py` | `test_trust_verify.py`（exit 0/1/2）、`test_trust_public_anchor.py`（离线） | — |
| GV-05 复用 in-toto/Sigstore/RFC3161 | MUST | PARTIAL | `core/timestamp.py`（RFC3161）、`core/attest.py`（sigstore 外挂）、`core/interop_export.py`（in-toto）、`trust/public_anchor.py`（Rekor） | `test_timestamp.py`、`test_trust_public_anchor*.py` | `cosign` 不在场（check42 WARN）；公共日志提交未执行；G3/G4 |
| GV-06 策略编译 OPA/Cedar | MUST | ABSENT | 无 OPA/Cedar 适配器；仅 `nf-trust-policy/1`、`nf-check-policy/1` 判定 schema | — | G3 |
| GV-07 none/observe/require | MUST | ABSENT | 无附件模式实现（`protocol/geo_export.json` 里的 `policy-attachment` 是标准目录词条，非运行时语义） | — | G3 |
| GV-08 治理不阻塞生产 | MUST | PARTIAL | trust 验证是独立进程/可选调用，未进入 `nf run` 主链 | 无「治理禁用时生产输出逐字节一致」测试 | G3 |

### 5.4 AI 信任 AI

| ID | 级别 | 状态 | 本机等价锚点 | 测试/证据 | 缺口 → WP |
|---|---|---|---|---|---|
| AI-01 model card/eval 绑定 | MUST | PARTIAL | `core/trust/model_card.py`（`nf-model-card/1`）；eval 仅 `nf-eval-protocol/1`/`nf-eval-run/1` | `test_trust_model_card.py` | 无 `nf-eval-evidence/1`；G4 |
| AI-02 prompt/context lineage | SHOULD | SUPPORTED | `core/trust/context_lineage.py`（`nf-context-lineage/1`） | `test_trust_context_lineage.py` | — |
| AI-03 人类复核可签名/未签=PENDING | MUST | SUPPORTED | `core/trust/human_review.py`（`nf-human-review/1`） | `test_trust_human_review.py` | — |
| AI-04 AIGC 标识证据接入 | SHOULD | PARTIAL | `core/label_*.py` 族（`nf-label/1`、sidecar/watermark）、`labeling/` 已迁出 | `test_label_*.py`（5 件） | 未接入 bundle；G4 |
| AI-05 运行时无质量评分 | MUST | SUPPORTED | `core/meta_cockpit/abstention.py:121`（`no_scoring: True`）、`cockpit_handoff.schema.json`（`no_scoring` const true） | `test_meta_cockpit.py` | — |

### 5.5 独立性 IN

| ID | 级别 | 状态 | 本机等价锚点 | 测试/证据 | 缺口 → WP |
|---|---|---|---|---|---|
| IN-01 生产不 import 治理 | MUST | SUPPORTED | `protocol/independence.json`（三平面归属）+ `core/independence.py`（全 core 模块静态闭包）+ `scripts/check_independence.py`；check49 | `desktop/tests/test_independence.py`（11 例，6 类变异自证） | —（R3 收口） |
| IN-02 治理不 import 生产运行时 | MUST | SUPPORTED | 同上（三平面互斥 + 禁止边 production↛governance / governance↛production / shared↛任一平面）；check49 | 同上；`results/independence.json` 在盘 == 实时重算 | —（R3 收口） |
| IN-03 core-only 安装通过核心测试 | MUST | ABSENT | 无 core-only CI matrix（20 workflows 无此项）；静态边界已证但安装矩阵未建 | — | G2/WP-02 余项 |
| IN-04 治理关闭不影响生产 | MUST | PARTIAL | 静态面无生产→治理 import（check49 已证）；运行面开关/逐字节一致未测 | 无开关测试 | G3 |
| IN-05 契约 schema 双方共同评审 | MUST | PARTIAL | `decisions/` 3 件 ADR（含模板/示例），`protocol/adr/registry.json` | `test_trust_adr_contract.py` | 无双平面契约评审记录；G0 |

**矩阵汇总（本机，R3 更新）**：SUPPORTED 6 / PARTIAL 19 / ABSENT 9（共 34）。IN-01/IN-02 由 check49（`protocol/independence.json` + 全 core 模块闭包）收口；其余缺口按表内 WP 列推进。方案 §1.3 总 DoD 的 8 条本机仍未达成，矩阵里没有任何一条被写成「已通过」。

## 6. check 编号对账（方案 §14.1 与本仓基线）

方案名称 → 本仓可用编号（建议；最终以 `quality_baseline.CHECK_NUMBERS` 实改为准）：

| 方案 check | 内容 | 本仓编号（建议） | 理由 |
|---|---|---|---|
| check45 | Wiki 完整性 | **check43** | 43 是 `quality_baseline.py:21` 显式预留空号（「留给其它线」），先占先用 |
| check46 | Spec 编译 + 黄金路径 + 2 Adapter | **check44** | 同上；且与 check43 成对落在 G1 |
| check47 | 治理独立性 + 非 NF 产物 + 附件模式 | **check49（已落地 IN-01/IN-02 部分；非 NF 产物验证/附件模式属 G3）** | 45–48 已被 Trust Fabric 占用，49 起顺延 |
| check48 | AI 证据 + 生态导出 + 自审计 | **check50** | 同上 |
| check49 | 全仓代码质量棘轮 | **check51** | 同上 |
| check50 | 文档 claims 一致性 | **check52** | 同上 |
| （§13C.12 候选） | 审查过程/AI provenance | **check53** | G5 时再定 |
| （§13C.12 候选） | 架构一致性 | **check54** | G5 时再定 |

落地约束（任一新增 check 必做）：`quality_baseline.CHECK_NUMBERS/EXPECTED_CHECKS/EXPECTED_PASS/CHECK_LABEL` 同步 → `CHANGELOG.md` 最新节、`docs/meta/VERSION-MATRIX.md`、`README.md` 版本块的 `PASS=` 声明同步 → `verify.sh` 段位计数注释同步 → 旧基线可红（注入反例）→ 冻结链重跑（§7）。**不得**挪动/复用 check45–48。

## 7. 冻结链与复现

冻结链顺序（`docs/release.md:21-31`，不可颠倒）：内容定稿 → `python scripts/nf.py conformance --write` → `nf approve protocol/conformance_report.json --by <批准人> --note <说明>` → `python scripts/nf.py receipts --scope protocol --write`。

本件只新增 `results/` 状态件；是否触发 check35 以实跑为准（若红，按上链重跑，不弱化 check）。

```bash
bash verify.sh --checks-only                          # 46 条静态 check（含 trust 4 条）
python -m pytest desktop/tests --collect-only -q      # 5,549 例
python -m pytest desktop/tests/test_trust_{process,bundle,verify}.py -q
python -m pytest desktop/tests/test_trust_verify.py::ScriptContractTest -q          # F-001 复现（无 PYTHONUTF8 时）
PYTHONUTF8=1 python -m pytest desktop/tests/test_trust_verify.py::ScriptContractTest -q  # F-001 消失
```

## 8. 缺陷登记

| ID | 维度 | 级别 | 位置 | 证据 | 根因 | 处置 |
|---|---|---|---|---|---|---|
| F-001 | S6 测试质量 / 可移植性 | P2 | `desktop/tests/test_trust_verify.py:148`（`_run` 用子进程文本输出） | 无 `PYTHONUTF8` 时 stderr 被 GBK 解码成 mojibake，断言 `不可判定` 失败；`PYTHONUTF8=1` 下 4/4 通过 | 子进程 `text=True` 未钉 `encoding="utf-8"`，受本机 locale 影响 | 测试质量面修复（补 `encoding=errors=` 显式钉死），回归测试须能在两种 locale 下稳定 |

## 9. 本报告的边界

- 本件只做只读审计 + claim 矩阵，不改代码/不建 schema/不加 check；方案 G0 其余交付物（§4A 七件套、§3A 盲区 closure、L0/L1 QA 计划、WP-01 schema）不在本件范围。
- §3A/§5 的「本机等价锚点」是初判；R1（契约提取）/R2（行为重建）/R3（耦合）会用 file:line 逐条复验，发现不一致以 R1–R6 结果为准并回写本件（改则重跑命令、更新数字）。
- 环境受限项（`cosign`/`gitleaks` 缺失、全量测试未跑、公共日志提交未执行）按「不得写成通过」处理，逐条显式登记，不并入绿面。
