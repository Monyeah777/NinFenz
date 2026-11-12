---
id: AUD-0047
title: 元认知生产驾驶舱主仓融合
date: 2026-10-30
scope: 将元原子运行时、动态驾驶、事件溯源、上下文预算、A/B 与正式协议融合进主仓；并收口桥接 Path 参数根相对/类型闸门、包入口惰性加载、生成物原子写与 manifest 可复算；不调用外部模型，不伪造 HR-001。
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/cli_bridge.py:4247ed0e73dfc1ca319f6b9881f3b73a875b01ee6b24eda3d4fe861736cadad8
  - desktop/src/core/meta_cockpit/__init__.py:f31cbadd59e3f25aab850122bbcc4ad5adcf5a65596a38c4996f264a38427fd7
  - desktop/src/core/meta_cockpit/build_atom_menu.py:1bedd2efd340114f91442a41b6319f7a9e7f962996d49f656a132e45988dbf95
  - desktop/src/core/meta_cockpit/runtime_executor.py:204a67ec93855257323887011395b0866ac8d5ae1c485362e89eb058ffe64bfb
  - desktop/src/core/meta_cockpit/cockpit_service.py:18280c6966dd618a8b09daa058b461fa43f89e99f11c797ca884338ff5c13bbf
  - desktop/src/core/meta_cockpit/cockpit_ab.py:6afcade08f2469aad4adc6f44e0e3d28a17712a85e3223f41b14c0020c2f88e7
  - desktop/src/core/terminal.py:9a86928171c71f4a2d3d324508fdafccb60fd7cc8423d52197185214a40ea30f
  - desktop/tests/test_meta_cockpit.py:cc2dc4f52729b35f400ca92aa367e685780f9f6735224e7fc0b7550b85f52662
  - desktop/tests/test_cli_error_framing.py:788460878349a907eadc21c74a1a689c9cdfe81888f5490c5a935b34fc121c8a
  - desktop/tests/test_nf_cli.py:18c407b6780205e50997d99ab9ea967e6ee066b2dca5d087e9eeea632d311804
  - scripts/nf.py:b8d793a9fcfec426276f177671af4d4f0e65d9b3b024002a9faa73b04e75d50d
  - tui/_surface.py:0845c376fd5ad601ae78b98326f1d2038b88c146d468d415efa694d8af1bb1f9
  - protocol/check12_weights.json:8294aab40577ab9b4c913550f95348a56bc03eed013181b8bdc89f224013b91a
  - protocol/coupling_baseline.json:b707d268a3bd295caade986ce6e80fd5ca1a3b24d75c60381e1d2e8bc27d1d49
  - docs/meta-cockpit/README.md:48b92addbaadc17d2bb845595bf39389269871026add1c597a8c71a0c2ca0aba
  - docs/meta-cockpit/功能解析.md:8bc9f97b3f067e11f2e3a8257e84e05845587624db8ee94de27ad10ef53a99a2
  - results/meta-cockpit-manifest.json:590418d031ab6cc8ba9cabce70968f86db4c6ed773581d87ec424b7f5083b9b4

---
> 重审（2026-11-12）：llms-install 安装面顶尖化（三条安装路线 / MCP 能力面与 mcp_package 同源 / 双时代协议常量同源 / 运行数字与 repo_stats+实时 doctor 对账 / 探针四帧修正 / fail-closed）+ 契约判据 test_llms_install_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：llms.txt 机器入口清单顶尖化（按任务选入口七行 / 入口面覆盖 34 件 / 补 WORLD_MODEL·LAYERS·NFA-L·域包协议 / 事实描述同源 / fail-closed）+ 契约判据补入口覆盖；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：ai-menu B1 菜单面顶尖化（菜单单源 / 九层与 M22/样本节号/Y5 等事实同源 / 执行前自检与停止条件）+ 契约判据 test_ai_menu_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：DEEP_DIVE 心智模型顶尖化（三正交/五条不变式与 01 §5 同源、五维纵深、六步运行表、十问逐问映射）+ 契约判据 test_deep_dive_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：ROUTES 云端导购顶尖化（入口链馆线落点 / 镜像路径可核 / 决策流 A-H / 出库前自检 / fail-closed）+ 契约判据补结构决策流与前缀分支；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：AI_ROUTING 入口路由顶尖化（三档自测证据 / 档位⇄落点⇄验收 / driver.json 同源 / fail-closed）+ 契约判据 test_ai_routing_contract；check12 权重增量实测。本轮为机械重绑。

> 重审（2026-11-12）：AGENT_START 入口顶尖化（七段分流 / DRIVER OVERRIDE 同源 / 三档可执行 / 失败即停）+ 契约判据 test_agent_start_contract（含变异自证）；check12 权重按增量实测更新。本轮为机械重绑。

> 重审（2026-11-12）：L4 塌缩守卫：五个扫描型判据补非空下限断言

> 重审（2026-11-11）：L4 判据质量：文字卫生 markdown 面收敛到 repo_face 单点扫描面（66547→370 件）+ .worktrees 静态剪枝

> 重审（2026-11-11）：L4 判据质量：test_version_map 治理面改 git 追踪面（241 件等价，14.0s→0.05s）

> 重审（2026-11-11）：L4 判据质量：test_ci_diagnostics Dockerfile 扫描面改 git 追踪面（去本地快照假红）

> 重审（2026-11-11）：llms.txt 判据修正：URL 正则反斜杠（CodeQL 高危正则漏检修复）

> 重审（2026-11-11）：L3 收官：llms.txt 卡册生成器死指针 + conformance 计数漂移修复 + 机器入口契约判据

> 重审（2026-11-11）：L3 导航面：ROUTES 死指针修复（README B2/📚 段已移出）+ 路由契约判据

> 重审（2026-11-11）：L3 文档导航面：全仓相对链接判据 + 两处伪代码坏链修复（community 资产档）

> 重审（2026-11-11）：allstar security 契约化：唯一通过条件对账 + 内容质量边界（L2 43/43 收官）

> 重审（2026-11-11）：allstar outside 契约化：权限开关显式收紧 + 组织级豁免边界 + 执行主体单点

> 重审（2026-11-11）：allstar binary_artifacts 契约化：Scorecard 判定镜像 + 全仓零二进制工件 + ignorePaths 白名单

> 重审（2026-11-11）：allstar dangerous_workflow 契约化：Scorecard 规则镜像 + 全仓工作流零命中 + branchList 全分支语义

> 重审（2026-11-11）：allstar branch_protection 契约化：平台保护设置镜像 + required 检查作业名对账 + 平台独有缺口

> 重审（2026-11-11）：allstar 根配置契约化：仓库级/组织级字段口径 + fail-open 边界 + label 前置条件判据

> 重审（2026-11-11）：requirements-lint/sast/audit 三份固定集契约化（同族机械同步）：生成头改为仓库内可复现命令（--extra lint/sast/audit pyproject.toml；audit 保留 --allow-unsafe），hash 完备/自包含/ASCII/禁重复与 extras 纳入判据，并新增跨文件版本一致性对账（含 ci，cross-platform 同时装全部）；lock_digest 变化 → 重生成 THIRD-PARTY-NOTICES.md；新增 test_requirements_pins_contract（3 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：requirements-ci 契约化：每钉版 hash 完备（sha256 64hex、无重复）、直钉与 pyproject ci extra 镜像一致、生成命令改为仓库内可复现（--extra ci pyproject.toml，去掉不存在的外部输入）、自包含（禁 -r/-c/-e）、ASCII/CRLF/结尾换行、禁重复/extras；编辑头部后 lock_digest 变化 → 用生成器重写 THIRD-PARTY-NOTICES.md（44 组件）并同步判据。新增 test_requirements_ci_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：gitee_ingest 脚本契约化：**推送顺序修为先 origin（真源）后 Gitee（镜像）**（原顺序会让镜像领先真源、下一次非快进永久卡死镜像），两处推送都加 pull --rebase 重试；幂等（来源：Gitee Issue #N 认账）、令牌仅从 env + secret=TOKEN 回显脱敏、API 响应有界、issue 分页上限、gitee 通道闸门/配额/超长/密钥/注入/frontmatter 闸门、原子写、36 进制编号；新增 test_gitee_ingest_script_contract（3 项含五类变异自证 + 幂等功能测试）。本轮为机械重绑。

> 重审（2026-11-11）：library_ingest 脚本契约化：标准库+core 白名单、正文真源优先级（文件>env>API）、超长/密钥形状/空壳/frontmatter 形状/白名单/配额六道拒收闸门、注入记档、36 进制编号、原子写、日志脱敏、禁执行面；新增推送韧性（push 失败 pull --rebase 重试一次，仍失败在 Issue 留可执行提示——workflow 仅 issues:opened 触发，静默丢失不可接受）；新增 test_library_ingest_script_contract（3 项含五类变异自证 + 真源优先级功能测试）。本轮为机械重绑。

> 重审（2026-11-11）：net-probes 契约化（workflow 家族收官）：仅手动触发（禁 schedule/push/PR，历史重写后金标缺失只会每周假红）、金标未前移期间 continue-on-error=true（诊断信号，须写明理由）、快照 ref 参数化 + git archive + Python tarfile 解包 + 不可用 fail-fast、树外构建、双 RID 交付形态、跑批 7 个占位符全解析、探针清单在场、失败证据工件（failure-only）保留 7 天；新增 test_net_probes_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：external-links 契约化：非门禁定位（禁 push/PR 触发、独立并发组、禁调 verify.sh）、离线扫描步永远绿 + 联网步 fail-closed（禁兜底写法、pipefail、tee 落盘）、联网硬预算 --max-seconds 600（防慢站点拖到 job 超时）、报告只传 .artifacts/ 本 run 副本（禁受跟踪路径）、工件保留 7 天；新增 test_external_links_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：ci-health 看门狗契约化：只读（禁 checkout / 写仓库）、权限恰为三 read、4 次/天 schedule + push main + dispatch、最新一次口径（排除自身 / cancelled/skipped 不算失败 / pending 跳过）、schedule 面补分页（长期不跑的 workflow 会滑出窗口假绿）、失败必须 ::error + exit 1、安全面快照 continue-on-error 与 NA 兜底；新增 test_ci_health_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：dotnet-build 契约化：树外构建铁律（RUNNER_TEMP + Copy-Item engine/dotnet，树内不留 bin/obj）、.NET 8 主版本守卫、三处 build 都检查  + =Stop、两平台矩阵 fail-fast false、三个 csproj 在场对账、只读、工件含 matrix.os 与日志且保留 7 天；新增 test_dotnet_build_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：rust-crate 契约化：三处 cargo 调用都必须 --locked（test/bin/pyo3）、两平台矩阵 fail-fast false、Linux 专属面（bin parity 34 判据 + PyO3 cdylib 构建）必须显式 runner.os 门控、只读（禁写仓库）、Cargo.toml/lock 四件输入在场对账、失败日志工件含 matrix.os 且保留 7 天；新增 test_rust_crate_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：cross-lang 契约化：full 模式（正负例都 --require-full，UNKNOWN=0）、正例 --digest 逐字节、覆盖棘轮 --coverage、只读铁律（禁 git commit/push/--write/nf.py）与分工铁律（禁调 verify.sh，基线门只在 ci-verify）、.NET 8 主版本守卫、退化证据工件保留 7 天；新增 test_cross_lang_workflow_contract（4 项含五类变异自证，注释豁免）。本轮为机械重绑。

> 重审（2026-11-11）：docker-nfal 契约化：只 build 不推送（禁 docker push/login/secrets/REGISTRY）、push 与 PR 的 paths 同一锚点、两作业各自恰一个诊断工件（修复 nfal 工件错放进 hf-space 作业的真问题）、工件保留 7 天、Dockerfile FROM 必须 @sha256（纯函数对账）；新增 test_docker_nfal_workflow_contract（5 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：e2e-desktop 契约化：无 GUI 不变量（禁 PySide6/QT_QPA_PLATFORM/pyside6/xvfb）、PR 全量触发（禁 paths）、python3 调 scripts/e2e_desktop_headless.py + pipefail + tee、禁兜底假绿、工件 always + 保留 7 天、与 release-gate 同脚本交叉对账；新增 test_e2e_desktop_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：coverage 契约化：覆盖率门槛 --fail-under=80 与 --include=desktop/src/core/* 与 release-gate 交叉对账、NF_COVERAGE=1 + verify_tests --jobs + coverage combine、pipefail + exit rc fail-closed、冷启动 3 目录、诊断工件 always + 保留 7 天；新增 test_coverage_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：cross-platform 三平台依赖口径修复：非 Windows 平台此前只装 requirements-ci，而 --full 的 check12 与 ci-verify unit-tests 同套测试（需要 ruff/bandit）→ style/sast 棘轮 fail-closed 长期红；现三平台统一安装 ci/lint/sast 三份固定集，Windows SAST 步骤只跑基线。判据新增三份固定集必装 + 缺件变异自证。本轮为机械重绑。

> 重审（2026-11-11）：cross-platform 契约化：修复 **报告新鲜度 fail-open**（原顺序 --write → --check，写入后 check 永远通过；改为先 check 再 write，并把顺序钉进判据）、三平台矩阵 fail-fast false、显式 --full 档位、Windows SAST nt 段、冷启动前置 3 目录、Linux 库 RUNNER_OS 守卫、两工件保留 7 天、checkout fetch-depth/tags；新增 test_cross_platform_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：npm-package-check 契约化：只读（禁 npm publish / 令牌 / secrets）、PR 全量触发（禁 paths）、stage→verify→冒烟→pack→tarball 同口径、站点数字对账、stage 后受跟踪改动必须为零（带修复指引）、stage 输出落盘并进工件（保留 7 天）；新增 test_npm_package_check_workflow_contract（5 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：gitee-poll 契约化：跨端入库共用 library-write 写锁（与 library-ingest 交叉对账）、无 GITEE_TOKEN 时显式 skip 不假红（2026-11-07 实测 144 次/天教训）、checkout 凭据保留显式说明（origin 推送依赖）、子令牌只从 env 取且日志脱敏、双端推送/Gitee API v5 对账、诊断工件保留 7 天；新增 test_gitee_poll_workflow_contract（5 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：linux-parity-refresh 契约化：只读不变量（禁 contents: write / git push / git commit）、dispatch+周 schedule、漂移判定双 diff 非空 + 键级 SAST 比对、证据件（sast-posix/vectors.diff/projections.diff）always 上传且保留 7 天；新增 test_linux_parity_refresh_workflow_contract（4 项含五类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：dependency-audit 契约化：四份固定集全审（ci/lint/sast/audit）、审计器 --require-hashes、fail-closed（禁兜底假绿）、审计输出 tee 落盘并进工件（保留 7 天）、PR 路径面与周 schedule；新增 test_dependency_audit_workflow_contract（4 项含五类变异自证 + 固定集在场/ASCII 对账）。本轮为机械重绑。

> 重审（2026-11-11）：library-ingest 契约化：issues 触发仅 opened、写权限仅 contents+issues、标题守卫、编号并发串行且不可取消、正文强制走 API（E2BIG 事故口径）、checkout 凭据保留显式说明（push 依赖，与其它 workflow 相反）、诊断工件保留 7 天；新增 test_library_ingest_workflow_contract（5 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：scorecard 契约化：顶层 read-all + analysis 权限（security-events/id-token/contents/actions 各只读或仅需）、评分不可取消、四类触发面、publish_results=true 与 sarif 格式、SARIF/摘要工件保留期、摘要可追溯字段（run_id/commit/sha256/empty_results_are_not_clean）；清理过期 v2.4.3 叙述与 upload-sarif 的 v3/v4 注释错位；新增 test_scorecard_workflow_contract（4 项含六类变异自证 + 与 codeql.yml 同 SHA 交叉对账）。本轮为机械重绑。

> 重审（2026-11-11）：codeql 契约化：PR 路径过滤补 packaging/**（含公网 hf-space server.py 与 js/ts 工具链）、init/analyze 必须同 SHA（删过期 v3 SHA 注释）、SARIF category 按语言区分；新增 test_codeql_workflow_contract（4 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：CI 真红修复（分片 12）：test_pipeline_loader 的「缺 YAML 回退」夹具只还原 sys.modules，未还原 lazy_yaml 的 (_TRIED,_YAML) 缓存——同进程后续用例永久看到缺 PyYAML（world_model / quant 域包 setUpClass 报 ClosureError）；补缓存还原后本地 shard 12 rc=0。本轮为机械重绑。

> 重审（2026-11-11）：npm-publish 双通道契约化：per-job 最小权限（id-token 仅 npmjs / packages:write 仅 GitHub Packages）、发布永不取消、tag-版本一致性（两条通道同口径）、OIDC provenance、幂等跳过、证据工件 always + 保留 30 天；修正 tag 不一致提示里的过期版本线表述；新增 test_npm_publish_workflow_contract（4 项含六类变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：release-gate 发布闸门契约化：最小权限 / **永不取消**（cancel-in-progress false，发布体检不许被取消）/ tag-only 触发 / fetch-depth+tags / nf release 体检 + e2e 落盘 + 覆盖率门槛 ≥80 / 证据工件 always + 保留 30 天；新增 test_release_gate_workflow_contract（4 项含变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：lint 工作流契约化：required check 名稳定（ruff-check-e9-f63-f7-f82 / ruff-style-ratchet）、棘轮 fail-closed、规则集与 ruff.toml select 同源、检查面为 style_check 扫描面子集；硬化 PR 限 main、ruff 输出 github 注释、工件含 style-counts.json 且保留 7 天；新增 test_lint_workflow_contract（5 项含变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：sast 工作流契约化：最小权限/并发取消/触发限 main/超时/工具 --require-hashes 固定/棘轮 fail-closed（禁 || true）/工件 always + 保留 7 天；SECURITY.md 的 SAST 行改为与脚本 SCAN_TARGETS 同源（去掉不存在的 sast-extra 与非阻塞声明）；新增 test_sast_workflow_contract（5 项，含写权限/PR 不设限/|| true/无保留期/扫描面缺 tui/基线缺平台段变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：ci-verify 主门禁契约化：顶层最小权限/并发取消/触发面限 main/每作业超时/32 片矩阵连续性/gate 对 needs 显式判红/工件 always 上传与 7 天保留；新增强化项（pull_request 限 main、工件 retention 7 天）；新增 test_ci_verify_contract（4 项，含写权限/去超时/gate 非 always/矩阵缺片/工件无保留期变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：dependabot 覆盖补齐：新增 pyproject extras 镜像（pip /）、Rust 引擎 5 个 crate（含 wasm 组件的 wit-bindgen）、容器 digest 3 处 docker 面；分组纪律（major 不分组）与 license/标签/前缀纳入契约；新增 test_dependabot_contract（4 项，含删面/非法节奏/不存在目录/major 入组/重复面变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：CODEOWNERS 顶尖化：承重面显式归人（协议件/门禁本体/判据/治理件/核心库/CI/投稿面/分发站点）、catch-all 置首、owner 与 MAINTAINERS 同源；新增 test_codeowners_contract（5 项：死规则/承重面覆盖/owner 同源/顺序/变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：STRATEGY 可核化：新增 test_strategy_contract（5 项：五段/政策内核/五维在场 + 内部链四载体在场 + 发布边界事实（根层无方案文档、agent 入口在场）+ 引用可解析 + 变异自证）。STRATEGY 本体零改动（作者政策面），本轮只做可核化。

> 重审（2026-11-11）：AGENTS.md 可核化：修正一处退役事实（删除「桌面端显示环境缺失横幅」——桌面 GUI 端壳 2026-09-09 已永久退役，见 docs/L3_FROZEN.md）；新增 test_agents_contract（4 项：闸门段/破坏性命令清单/引用可解析/事实对账 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：许可链总闸：新增 test_license_chain（LICENSE 是唯一真源；canonical MIT 文本完整性 + LICENSES/MIT.txt 逐字节一致 + pyproject/REUSE/CITATION/Zenodo/codemeta/notices 六处声明全等 + 入口文档不宣称 copyleft + 变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：THIRD-PARTY-NOTICES 顶尖化（连带生成器修复）：生成器改为 fail-closed（查询失败不写盘、返回 2）；notices 从「44 行中 34 行查询失败占位」重生成为 44 个组件的真实 SPDX 清单（pin 真源 + 锁摘要新鲜度锚 + 归属声明/分发边界/零依赖可证/双许可表态/人工核对段）；新增 test_third_party_notices_contract（6 项，含 fail-closed 打桩与变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：REUSE 判据按一手调研补强：override 顺序（宽表在前）、投稿面逐文件覆盖（git 追踪面，白名单外必须命中 override）、LicenseRef 命名规则、包级元数据标注为「非 REUSE 3.3 字段」；同步修掉 test_governance_docs 里恒真的 reuse gap 判据。本轮为机械重绑。

> 重审（2026-11-11）：REUSE.toml 顶尖化：三级许可声明结构（全仓 MIT 聚合 + 投稿面 override 拆为 library 与 community 两条）+ 投稿面口径注释（作者自投/第三方投稿同按投稿条款）+ 许可文本自身不声明；新增 test_reuse_contract（5 项：TOML 结构/聚合许可与 LICENSE 一致/override 不空转/许可文本双向闭合/变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：CITATION.cff 顶尖化：作者从 entity 的 name 改为 person（family-names），避免被当机构；补「不钉 version/date-released」策略注释与两源并存说明；与 .zenodo.json 的 title/license/作者双源一致；新增 test_citation_contract（5 项：schema 必填/无未知键 + person 判定 + 双源一致 + 版本策略 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-11）：.zenodo.json 修复：许可从 AGPL-3.0-only（与 LICENSE/REUSE/pyproject/CITATION 的 MIT 矛盾）改回 MIT，删除三个不存在文件的引用（LICENSING.md/COMMERCIAL.md/TRADEMARK.md）与失效的「v1.1.0 许可分层」段；新增 test_zenodo_contract（4 项，许可四源一致 + 双源 title/creators + 失效引用 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：SUPPORT 口径回归修复：申诉复核主体改指 MAINTAINERS 的回避路径（涉 Owner 由外部第三方，无第三方记「未复核」），去掉「未参与原处置的维护者」这一单人仓不存在的角色；判据 test_support_contract 扩到 7 项（新增复核主体同源 + 变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：MAINTAINERS 维护者文档顶尖化：执行主体真源（Owner 具名 + 职责与不可代行面 + 安全/行为双经办）、单维护者三条硬约束（涉己外部第三方回避 / 可复核性代替双人复核 / 90 天失能只读预案）、晋升四硬条件、响应与 SLA 边界；新增 test_maintainers_contract（4 项，含删 Owner/删回避/删天数/悬空链接变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：SECURITY 安全策略顶尖化：通道分工（漏洞→本件 / 行为→COC / 使用→SUPPORT，互不代收）、六项报告模板、7 天确认 + 90 天协调披露、CVE/致谢/无赏金边界、修掉两处悬空引用（tests/test_repo_trust.py、core/gate_inproc.py）；新增 test_security_contract（4 项，含删段/删时限/悬空链接变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：CODE_OF_CONDUCT 顶尖化：通道分工（行为举报受理归属在本件、SECURITY 只界定漏洞）、四档处置（可跳档）、7 天确认 / 14 天申诉 / 30 天复核目标、利益冲突回避与外部第三方复核、报复与恶意举报独立违规；新增 test_coc_contract（4 项，含删段/删时限/悬空链接变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：SUPPORT 入口面顶尖化（含调研补强：私密直达 URL / 状态位承诺 / 复现三件套 / Markdown 相对链接可解析判据）；新增 test_support_contract 6 项，含配置放开、悬空路径、悬空链接变异自证。本轮为机械重绑。

> 重审（2026-11-10）：SUPPORT 入口面顶尖化：先自查 → 去哪问（五类通道 ⇄ config.yml/表单/声明件）→ 提 Issue 前自检四项（与 bug_report checklist 同源）→ 怎么问（最小复现/一次一件）→ 之后会发生什么（不静默丢弃）→ 支持边界；新增 test_support_contract（4 项，含配置放开与悬空路径变异自证）。本轮为机械重绑。

> 重审（2026-11-10）：CONTRIBUTING 入口面顶尖化：§5 重写为「入口分流（空白 Issue 已关 + 四条分流 ⇄ config.yml）/ 改动域四类（代码面清单照抄 library/intake.json 声明）/ 三个模板各自守什么 / 一次一件事 / 提 PR 前自检」；新增 test_contributing_contract（5 项，含配置放开与悬空路径变异自证）；§4.2 补代码面清单真源注记。本轮为机械重绑。

> 重审（2026-11-10）：PR 模板与两个 Issue 表单同构化（改动域/问题→做法→影响面/可核验收命令+期望/门禁自检四项/Closes-Refs+只做一件事声明）；新增 test_pr_template_contract（4 项，含删段与悬空路径变异自证）；本轮为机械重绑，不主张新的语义审计。

> 重审（2026-11-10）：config.yml 入投稿面声明

> 重审（2026-11-10）：权重件随表单契约更新

> 重审（2026-11-10）：新增 issue 表单契约判据后重绑

> 重审（2026-11-10）：merge 后重绑

> 重审（2026-11-10）：论文台账系统化 + 方法包深度判据

> 重审（2026-11-09）：冻结链

> 重审（2026-11-09）：台账表内自洽判据（序号连续 + 红绿不交叠 + 解析拒绝畸形输入）

> 重审（2026-11-09）：方法包文档「N 种用法」与列举条数/命令存在性绑定判据

> 重审（2026-11-09）：包可跑入口真跑判据（11 域 14 命令，退出码 0/2 合规）

> 重审（2026-11-09）：红证据棘轮改比例口径（绝对数会惩罚新增测试）

> 重审（2026-11-09）：core 引用面映射（355 模块 / 未引用 34，棘轮只减不增）

> 重审（2026-11-09）：红证据加 negative_assertion 档（assertRaises）：硬证据 20→99，无 149→139

> 重审（2026-11-09）：红证据登记（硬证据 20 / 疑似 221 / 无 149，棘轮只减不增）

> 重审（2026-11-09）：矩阵文档点名每层变异测试（一致性绑定第二条）

> 重审（2026-11-09）：文档入口列与包 runnable 绑定判据（消灭第二真源）

> 重审（2026-11-09）：方法包声明可跑入口 runnable，清单与文档共用（含入口存在性判据）

> 重审（2026-11-09）：脚本孤儿棘轮（6 个冻结 + 文档点名 + 自指排除）

> 重审（2026-11-09）：能力清单（静态 AST 扫描 scripts/*，可查而非猜）

> 重审（2026-11-09）：方法包补「可跑入口」列 + 入口命令存在性判据

> 重审（2026-11-09）：文档引用的探针数字判据（判据数/变异体数/覆盖率绑定结果件）

> 重审（2026-11-09）：文档仓库路径存在性判据（引用面第四条，59 处全命中）

> 重审（2026-11-09）：maps_to 词表判据（引用面第三条）

> 重审（2026-11-09）：判据族谱 v0 收入 docs/ccos（7 族 + 每族失效方式）

> 重审（2026-11-09）：文档相对链接存在性判据（14 条全部解析）

> 重审（2026-11-09）：criteria_refs 悬空修复（5 包）+ 引用存在性判据

> 重审（2026-11-09）：结论可落盘 --out（配合 verifier_status 复核）

> 重审（2026-11-09）：路径旗标覆盖棘轮（22 个已知缺口冻结，禁止新增未覆盖）

> 重审（2026-11-09）：第十一个域 operations（运维可观测性）：6 动作 3 证据类

> 重审（2026-11-09）：补 --threshold CLI 真跑覆盖（trigger 块与计数自洽）

> 重审（2026-11-09）：供应链对象 v0 收入 docs/ccos

> 重审（2026-11-09）：发布结论记录材料清单摘要（供应链闭环）

> 重审（2026-11-09）：json_doc 统一 + 耦合重算（材料清单入仓）

> 重审（2026-11-09）：材料清单对象（nf-sbom/1：显式范围 + 摘要折叠 + 篡改必红）

> 重审（2026-11-09）：CLI 输出确定性判据（两条只读命令逐字节比对）

> 重审（2026-11-09）：第十个域 supply-chain（供应链安全）：6 动作 3 证据类，锚点落 packaging/静态扫描/溯源

> 重审（2026-11-09）：文档判据变异测试（层数/门数/域数/动作数/类目数）

> 重审（2026-11-09）：变异探针扩到三判据（9 变异体 / 7 合法变体，杀死率 1.0 误报 0.0）

> 重审（2026-11-09）：方法包例子路径补全 + 引用存在性判据

> 重审（2026-11-09）：第九个域 privacy（隐私工程）：6 动作 3 证据类，锚点落 ingress/到期/吊销面

> 重审（2026-11-09）：判据接线：resource 核入 verify_commitment，authority 核入 replay

> 重审（2026-11-09）：修重放回归：authority 必须随记录回放（含回归判据）

> 重审（2026-11-09）：证人核对接入生产路径：session.step(root=) + CLI 传 ROOT

> 重审（2026-11-09）：文档数字漂移判据（层数 / precheck 门数）

> 重审（2026-11-09）：结论可复用性查询（verifier_status：current/stale/unknown）

> 重审（2026-11-09）：双核不变量 v0 收入 docs/ccos（九层 + 自省闭环）

> 重审（2026-11-09）：发布结论记录验证器摘要（自省层闭环）

> 重审（2026-11-09）：耦合面重算（288 模块）

> 重审（2026-11-09）：自省层对象：验证器摘要（判定面脚本内容摘要）+ 探针 + 判据

> 重审（2026-11-09）：对抗+资源入矩阵（8/9）：证人文件核验 + 两本账；文档同步

> 重审（2026-11-09）：对抗层：counterexample 必须带可复算证人（file+case）

> 重审（2026-11-09）：资源层同构判据 #7：两本账（cog_steps/cc_cost_ms）并列记、不合并

> 重审（2026-11-09）：资源层记账起点：证据判定附 cost_ms（只记耗时，不参与判定）

> 重审（2026-11-09）：同构矩阵数据搬到 fixtures（单源），测试只留反射查证

> 重审（2026-11-09）：授权层对象：control 记录 authority（终态算子必填）+ 同构判据 #6 + 变异测试

> 重审（2026-11-09）：两种导入风格判据（包路径 + 裸名）

> 重审（2026-11-09）：快照25 两处红：--pack-checklist 进编码闸 + 矩阵判据支持裸模块名

> 重审（2026-11-09）：证据图结果新鲜度判据（陈旧即红）

> 重审（2026-11-09）：探针结果新鲜度：--check + 判据（结果陈旧即红）

> 重审（2026-11-09）：precheck 名单拆成数据件（precheck_gates）+ 探针改原子写

> 重审（2026-11-09）：判据变异探针：两条判据 × 3 变异体，杀死率/误报率入 results

> 重审（2026-11-09）：同构矩阵反射查证抽函数 + 变异测试（指向不存在方法必须 False）

> 重审（2026-11-09）：时钟纯度负向用例 + 探针代理扩词（19/22）

> 重审（2026-11-09）：门禁负向用例探针（命名代理，只出比率与缺口清单）

> 重审（2026-11-09）：同构矩阵加变异测试列（每层必须能被改坏打死）

> 重审（2026-11-09）：观测同构判据 #3 变异测试（改来源/改序/改证人必红）

> 重审（2026-11-09）：桥信封守卫变异测试（第三类信封必须被抓）

> 重审（2026-11-09）：判据 #4 变异测试：词表核对接出独立函数，故意改坏必红

> 重审（2026-11-09）：方法包文档 v0（八域）+ 文档计数判据

> 重审（2026-11-09）：precheck 20 闸门：补时钟纯度 + 报告确定性（快照24 漏检面）

> 重审（2026-11-09）：方法包可执行化：checklist 投影 + nf cognition --pack-checklist

> 重审（2026-11-09）：第八个域 handoff（协作交接）：可接续帧/承诺落证/角色分离/分歧留档/第三方复验/版本钉定

> 重审（2026-11-09）：第七个域 resilience（韧性工程）：6 动作 3 证据类，锚点落既有隔离/变异/回滚面

> 重审（2026-11-09）：判据时钟纯度闸门（读此刻必须登记理由）

> 重审（2026-11-09）：判定判据日期稳定：同树同基准日重算（跨午夜不再假红）

> 重审（2026-11-08）：反模式守卫：桥只允许两类信封

> 重审（2026-11-08）：同构矩阵：缺失理由必须点名具体对象（新判据）

> 重审（2026-11-08）：九双生层同构矩阵（覆盖项必须有真实测试）

> 重审（2026-11-08）：同构判据 #5（负空间层）：abstain 必带检索边界

> 重审（2026-11-08）：同构判据 #4（语义层）：claim_kind 单一词表

> 重审（2026-11-08）：文档锚点：生成物前缀兜底（git 不可用时也能判）

> 重审（2026-11-08）：同构判据 #3（观测层）：回灌记录与契约失败集逐项对应

> 重审（2026-11-08）：precheck 快车道扩到 16 闸门（补 calibration/grouped/evidence_graph/atom_catalog）

> 重审（2026-11-08）：提交前自查快车道（precheck：按名单跑既有横向门禁）

> 重审（2026-11-08）：快照20 红修复：--pairs 入闸/json_doc/分组表接入探针/耦合重算

> 重审（2026-11-08）：同构判据 #1：commitment 绑定时点引用（ts_digest）

> 重审（2026-11-08）：桥线格式守卫（commitment/obligation 字段集钉死）

> 重审（2026-11-08）：证据图探针（陈述⇄证据二部图，H=悬挂比）

> 重审（2026-11-08）：第六个域 data-provenance（数据溯源：说明书/字段溯源/缺失语义/许可/版本钉定/泄漏）

> 重审（2026-11-08）：文档锚点：忽略生成物路径（payload/dist）+ 修 62 项计数

> 重审（2026-11-08）：分组报告模块（先分组再汇总；n<2 不能谈方差）

> 重审（2026-11-08）：口头置信触发策略（触发器非证据）+ CLI --threshold

> 重审（2026-11-08）：calibrate 文案收口

> 重审（2026-11-08）：cog calibrate CLI（可靠性表出口）

> 重审（2026-11-08）：校准度量 core/calibration.py（分箱/ECE/可靠性表，只计数不评分）

> 重审（2026-11-08）：快照现场体检（--status：锁/运行目录/最近结论一份看全）

> 重审（2026-11-08）：快照墙钟上限（--max-wall-s，超时判红留证）

> 重审（2026-11-08）：Ingress 启动自检（四道闸探针，非空转判据）

> 重审（2026-11-08）：MCP 红队用例集（8 条，逐条核闸门）

> 重审（2026-11-08）：文档锚点判据（docs/ccos 每篇必须指到真实实现）

> 重审（2026-11-08）：所有方法包动作：锚点或显式概念声明（判据）

> 重审（2026-11-08）：锁拒绝的集成判据（退出码 2 + 指引）+ 锁目录 env 钩子

> 重审（2026-11-08）：快照锁：json_doc/atomic_write/sink 登记/文档计数/编码闸门

> 重审（2026-11-08）：快照锁等待模式（--lock-wait，死锁立刻接管）

> 重审（2026-11-08）：锁存活探测走受控进程原子（S603/S607 收口）

> 重审（2026-11-08）：--sheet 入确认闸（(cog, --sheet)）

> 重审（2026-11-08）：快照锁 + sink 登记（lock 自清）

> 重审（2026-11-08）：快照互斥锁（并发会话互清 worktree 的实测对策）

> 重审（2026-11-08）：claim-check 直吃作业单（免手抄 evidence）

> 重审（2026-11-08）：主张→证据作业单（每个 required 一条 unknown 槽）

> 重审（2026-11-08）：采集单：半填必须点名「采集未完成」

> 重审（2026-11-08）：五包组合判据（并集去重/逆序不丢/同序可复现）

> 重审（2026-11-08）：采集单校验器（协议绑定/状态机/维度完整/盲评负对照）

> 重审（2026-11-08）：耦合面重算（eval_harness→method_pack 边）

> 重审（2026-11-08）：eval harness 采集检查单（D-06 作业面）

> 重审（2026-11-08）：注入防御包动作加代码锚点判据

> 重审（2026-11-08）：新增方法包 prompt-injection-defense（注入防御域）

> 重审（2026-11-08）：方法包引用还清 k.standard 原子债；A4 判据改为合成死码

> 重审（2026-11-08）：评测设计包接主张编译（efficacy/cost/reliability 三态）

> 重审（2026-11-08）：新增方法包 evaluation-design（评测设计域）

> 重审（2026-11-08）：拍屏探针第五轮（10 配置全扫描，负结果锁死）

> 重审（2026-11-08）：快照红修复：job 描述/面信封/权重/耦合面

> 重审（2026-11-08）：全量门禁收口：json_doc/atomic_write/面判别键/dead-code/静默跳过/路径旗标/ingress 接线

> 重审（2026-11-08）：terminal 族登记 cog + 终端投影刷新 + CRLF 归一

> 重审（2026-11-08）：Ingress 网关（认证/白名单/限流/同意/回执）

> 重审（2026-11-08）：工具清单派生自真实 TOOL_DEFS（D-04 关账）

> 重审（2026-11-08）：预注册评测协议 + harness（D-05 关账，新增 D-06 真实测量债）

> 重审（2026-11-08）：原子组合覆盖层（13 复合原子）+ 死码 12→1（D-01/D-02 关账）

> 重审（2026-11-08）：桥接真实证据包（D-03 关账）

> 重审（2026-11-08）：闭包台账（21 条断言 → 真实判据 → 反例 → 状态）+ 审计脚本

> 重审（2026-11-08）：K1 作业账本 + K4 事件流 + K8 启动自检（P6 第二件）

> 重审（2026-11-08）：MCP 兼容头（工具清单 _meta 增强 + 签名钉根 + 吊销 + 调用回执）

> 重审（2026-11-08）：ADR 注册表 + 16 份文档台账 + 分层依赖判据（P0 补账）

> 重审（2026-11-08）：双核桥（commitment + 回灌 + 闭环）

> 重审（2026-11-08）：原子目录 v2 + 不变量 A1–A5 + 候选健康 B1–B5

> 重审（2026-11-08）：判据注册表 + 主张编译（证据义务清单/三态核对）

> 重审（2026-11-08）：元算子层（11 ops + 触发引擎 + 双 trace + 反仪式化）

> 重审（2026-11-08）：认知工作台 L0（discourse/15 moves/records/replay + nf cog）

> 重审（2026-11-08）：几何提示同步探针（尺寸反解 + 双假设 + 偏移搜索；谱峰不变反例）

> 重审（2026-11-08）：同步层探针（同步字平铺 + 网格搜索，负结果可复算）

> 重审（2026-11-08）：DCT 水印探针（QIM vs 关系嵌入，q70/q50 实测）

> 重审（2026-11-08）：密钥透明目录 v0（版本根/追加链/包含证明/分叉见证）

> 重审（2026-11-08）：水印鲁棒性基准（16 攻击 × BER）+ 文档实测表

> 重审（2026-11-07）：方法包 v0 收尾（风格/度量重冻）

> 重审（2026-11-07）：方法包 v0（3 个领域包 + 组合 + 研究计划接线）

> 重审（2026-11-07）：认知核研究层：方法库 + 切片计划器 + CLI（切片检索词/方法论路径/证据台账）

> 重审（2026-11-07）：向量面收口：三形态跨实现同判 + 信封 subject 三摘要面

> 重审（2026-11-07）：命令树拆分（production 321→117 行 + 新组 evidence_face 207 行）

> 重审（2026-11-07）：门禁修：silent-skip 理由 / 两个文本参数登记 / --mode 复核

> 重审（2026-11-07）：Go 客户端补齐 cc_check/cc_label/cc_attest/cc_replay/cc_diff/cc_resolve（6 份向量集）

> 重审（2026-11-07）：Go 客户端补 receipts/attest 两形态；向量集扩到 28 条（三形态）

> 重审（2026-11-07）：cc_check 文本层：法规原文→意图草稿（规则抽取，四张账）

> 重审（2026-11-07）：吊销公钥信任锚（钉根 + 有界委派 + 过期/scope/链深判据）

> 重审（2026-11-07）：载体层：WebP/MP4/PDF 附加块 + PNG 像素水印（判据含 JPEG 不扛的期望行为）

> 重审（2026-11-07）：RFC 3161 可信时间戳（timestamp 模块 + CLI + 证据复验时间锚）

> 重审（2026-11-07）：快照落点纯函数化 + 3 条隔离判据（同盘/出树/日志）

> 重审（2026-11-07）：revocations_seed 进二进制豁免 + 两份文档项数同步（62→65 / 34→43）

> 重审（2026-11-07）：ed25519 吊销签名（非对称：验证方只持公钥）+ 回归判据

> 重审（2026-11-07）：batch_target 登记修正（位置参数进文本面，不进旗标名单）

> 重审（2026-11-07）：口径同步 3022 件 / 23.92 MB

> 重审（2026-11-07）：nf evidence batch（目录逐件复验，整批不可用即失败）

> 重审（2026-11-07）：instruction_evidence 临近过期提前 7 天 WARN + 重录 verify/release

> 重审（2026-11-06）：快照模式：内层日志边跑边落盘 + 陈旧快照自动清理

> 重审（2026-11-06）：机器面 NF_HOME 可移植（nf.py 变更）

> 重审（2026-11-06）：bash 身份守卫（WSL 空输出不再冒充判据红）+ Windows 两坑入文档

> 重审（2026-11-06）：CLI 命令树拆分 + 旗标字面读取（nf.py 变更）

> 重审（2026-11-06）：Rust 侧 SINK_ALLOW 同步 + 陈旧二进制守卫 + 漂移判据

> 重审（2026-11-06）：task-27 吊销新鲜度：revocations/evidence/nf.py 变更，重绑被审对象

> 重审（2026-11-06）：快照落点改仓库同盘 + TEMP 重定向（防满盘 ENOSPC）

> 重审（2026-11-06）：发布结论器加 --snapshot（HEAD 快照里跑，免疫并发改动）

> 重审（2026-11-06）：JPEG 载体 P0 硬化（nf.py/CLI 文案变化）+ 口径清理，重绑被审对象

> 重审（2026-11-06）：JPEG APP15 载体（扫描数据不变）+ 真 PNG 夹具判据

> 重审（2026-11-06）：Q0-r2：evidence verify 增 --policy-digest 期望比对（nf.py 参数面变化），重绑被审对象

> 重审（2026-11-06）：耦合面重冻（载体模块行数变化后 metrics 面漂移）

> 重审（2026-11-06）：cc_label PNG iTXt 载体（可读回/不改像素/CRC 合法）

> 重审（2026-11-06）：注册 --decision 参数进编码/路径闸门（其提交遗漏）

> 重审（2026-11-05）：Q0 决策证据绑定：scripts/nf.py 增 --decision 入口、evidence/attest/nf_verify 增 decision 绑定，重绑被审对象摘要

> 重审（2026-11-05）：M2：证据面双实现 parity（三形态+仓外单文件）与 CLI↔HTTP 同证据判据落地；重绑 check12 权重摘要

> 重审（2026-11-05）：M1：ABI 错误面登记 + docs/ccos 一致性判据落地，重绑被审对象摘要

> 重审（2026-11-05）：容器面加固：路径安全闸门 / 重名判死 / 解压上限（攻击矩阵 33→35）

> 重审（2026-11-05）：cc_label sidecar 回退（nf-label-sidecar/1，绑定对象摘要）

> 重审（2026-11-05）：隔离静态判据（打桩面）+ 三个机器判据进常驻集

> 重审（2026-11-05）：证据判定向量集（跨语言一致性锚点）+ 文档

> 重审（2026-11-05）：--compile 参数登记进编码/路径闸门

> 重审（2026-11-05）：cc_check 编译面 v0：意图 → 封闭词表策略（不可表达逐条挂账）

> 重审（2026-11-05）：权重实测后重冻（报告须最后写）

> 重审（2026-11-05）：新鲜度步：修 UP031 + 前置测试改结构断言

> 重审（2026-11-05）：受影响选片 v2（四类规则 + 文档目录前缀 + 硬兜底面）+ 纯函数判据

> 重审（2026-11-05）：G2 吊销分发件（签名 feed：签发/校验/合并，防回滚）+ nf.py 导入块排序

> 重审（2026-11-05）：label 声明层补登记（编码闸门/路径旗标）+ 删零引用函数

> 重审（2026-11-05）：cc_label 声明层（nf-label/1 IR）+ 供应链核对进发布结论

> 重审（2026-11-05）：G1 外部锚点：证据包可声明并可核对（防整链截断），双实现同口径 + 攻击矩阵 33 条

> 重审（2026-11-04）：H1 修复：--trust-repo 环境变量不再泄漏（信任门不再被绕过）+ 新增回归判据

> 重审（2026-11-04）：分片 1/8 抽检修复：编码闸门/路径旗标名单补全、删零引用常量与函数、耦合基线重冻

> 重审（2026-11-04）：证据线 fail-closed 加固：chain 段必填 / 吊销表坏件判 invalid（攻击矩阵 25→29）

> 重审（2026-11-04）：抽检第二个分片：原子写纪律（包/报告走 atomic_write，临时写例外登记）

> 重审（2026-11-04）：check12 修复波：JSON 面登记 / json_doc 收敛 / Rust 回执去重同步 / 基准 JSON 纯净

> 重审（2026-11-04）：本地 HTTP 面 v0（nf serve --http 三端点）落地 + 端点契约登记 local.*

> 重审（2026-11-04）：cc_resolve（契约面反查）+ 一条链复现脚本落地

> 重审（2026-11-04）：cc_replay 轨迹 + cc_check 单对象策略体检落地（新模块 check_policy）+ 回执去重

> 重审（2026-11-04）：证据复验器扩三种形态 + 攻击矩阵基准（26 项校验路径与基准落地）

> 重审（2026-11-04）：证据包缺省落点改到临时目录（不往仓库落盘）+ CCOS ABI v0 收口

> 重审（2026-11-04）：CCOS ABI v0 + 证据包校验器落地（scripts/nf.py 与 core/terminal.py 摘要变更；并修复本分支既有漂移）

> 重审（2026-10-30）：新增契约级 Git 演进时间线；结构化 Markdown YAML 字段与 JSON schema 差异纳入影响度

> 重审（2026-10-30）：全仓审计口径复核：显式 legacy 清单、subjects 根内解析、Path 参数闸门、惰性导入与 manifest 可复算

> 重审（2026-10-30）：桥接 Path 参数统一根相对与类型闸门；公共子模块惰性加载；生成菜单原子写；入仓 manifest 增加实时复算判据

> 重审（2026-10-29）：CLI 命令树无损分组、meta-cockpit 接线与恢复分支全量验证后重绑；既有结论不变

> 重审（2026-10-29）：恢复分支全量验证：纯度修复、零引用清理、public API 接线、ReDoS/CLI 闸门/文档路径与模板示例修复

> 重审（2026-10-29）：恢复分支全量验证：接线 meta-cockpit 公共模块、清理零引用、修复 ReDoS/CLI 闸门/公开文档路径后重绑；既有结论不变


# 元认知生产驾驶舱主仓融合审计

> 日期：2026-10-30
> 范围：`desktop/src/core/meta_cockpit/`、CLI 桥、终端命令族与自动化测试
> Machine digest：`59357b7056a68bfbd64cdd85333aadfb95c34fdf06f1216563cee56f5e01ce5c`
> Manifest digest：`c9469a7f54041e7c041e353a768bad98054b72bcb4775639f7463754b985abfc`

## 结果

- 33/33 原子执行器在场，14 个方法节点、10 节点内容管线与 5 节点元管线可加载执行。
- 元管线好样本 PASS：5 节点、17 个原子轨迹全部 PASS。
- 六类 fail-closed 突变均被抓：缺执行器、无效方法路由、预算耗尽、缺判据、未知任务类型、输出类型不匹配。
- 动态驾驶验证：不同任务/注入产生不同 need 序列，状态完成且轨迹无 `score`。
- 事件账本验证：提交后可加载、哈希链校验通过、确定性重放与当前状态一致。
- A/B 验证：预注册、盲包、功效分析、强效应、重复 ballot 拒绝、bundle/store 往返均通过。
- 发布清单验证：运行代码、契约、协议与正式说明纳入统一 digest；HR-001 保持 `PENDING`。
- CLI 入口验证：`nf cockpit` 与 `nf cockpit-ab` 可发现、可帮助、可执行；终端能力族与生成投影同步。

## 验证证据

| 检查 | 结果 |
|---|---|
| `tests.test_meta_cockpit` | 11/11 PASS |
| 最终受影响合并集 | 292/292 PASS |
| 终端/TUI/代码度量/权重/文本卫生受影响集 | 233/233 PASS |
| CLI/JSON 形状/耦合/模块命名受影响集 | 79/79 PASS |
| Ruff | PASS |
| 风格棘轮 | 10022 ≤ 基线 10032 |
| 代码规模 | 310 文件；最大行数 7643；最长函数 1262；最大复杂度 116 |
| 耦合 | 0 未登记环；258 模块；SDP 10/10 登记 |
| 元管线运行 | `PENDING-REVIEW`，机器层 PASS |

## 遗留边界

- HR-001 必须由作者或指定复核人签字，本审计未生成 approve 记录。
- 真实跨模型、多 seed A/B 未运行；不宣称已测得质量增量。
- 语义真伪仍由人工复核兜底。
- 工作区存在本次任务前已有的并发修改；本轮未执行 stash、reset、restore 或清理。

## 设计偏差

- 内部原型使用扁平模块导入与 `D:\\NinFenz` 绝对路径；主仓版本改为 `core.meta_cockpit` 包、相对导入和仓库根推导。
- 内部一次性 spike 脚本未直接入库；高价值断言已转为主仓 unittest 契约。
- `jsonschema` 作为可选标准实现使用；缺失时退回主仓确定性 JSON Schema 子集并 fail-closed。
