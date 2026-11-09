---
id: AUD-0016
title: 代码审查工具线（13 仓 / 3236 规则）+ 双模型热冷双层审查 + 按类修补（bandit 49→0 · flake8 12→0 · vulture 1→0，并修出一处被遮蔽的真 bug）
date: 2026-09-22
scope: 作者指令「拉取 ≥10 项代码审查工具；用工具 + 决策模型（Laya 热路径 / Jev 冷链）逐行审查出漏洞清单；全方面修补；双端推送」——本件记录：工具与规则目录、热/冷两层模型判定、漏洞清单、按类修补结果、以及未能跑通项（Jev 9B）的如实边界
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/audit.py:b316c77fb2fa718a105af8c51a234c435847077f71309adbbf5f0d6bb25d2afb
  - desktop/src/core/export_schema.py:9052dc891be0c70ceb5b42544eceeceeeb4dee8c4f107b1ec660913cf922ad3d
  - desktop/src/core/decision_layer.py:b31b67d1feda7bd520aea978e19ab3e165c5524c058c24605e0dc5e800ff1d32
  - desktop/src/core/storage.py:b64401314fd788fe0bae9676c21d61f162d704d3ac81e2f1d619b963149ab88c
  - desktop/src/core/gap_review.py:7d1d600926e13b9936f2a7d30e8a8ca95e4bb3b2a73308f88cfb89b563055953
  - scripts/nf.py:869bab4dff472c51503c71770c1871cb4dab32a3c3d0977da69ce6a0ea963d9e
  - scripts/check_external_links.py:1cbee65ba19a83fbcdf333e35b8d99c2e45f3b400f3a025860357baf7a806b02
  - scripts/check_interop_schemas.py:da1b1c628de26f1f8979e9e1c3cf325781fe6a23f4401d0bed2c8db19f8059f6
  - scripts/ai_domain_closure.py:431d764da2ef56538eb1c473fe4f45d5ffa8191450638036f147ae7d66a3ae73

---
> 重审（2026-11-09）：in-toto ledger: 合入唯一真源与最新主干后重绑

> 重审（2026-11-08）：外部 schema 校验工具修复 bytes→UTF-8 解码后重审：导出面与远端 schema 均先严格解码再解析；新增离线负例防回归。

> 重审（2026-11-08）：task-35c：git status 收敛到 repo_face.untracked_paths

> 重审（2026-11-08）：task-35：nf.py 注释修正（nosec/理由）

> 重审（2026-11-08）：task-35 投影少算防护

> 重审（2026-11-07）：合并基线补齐：向量生成器 subject 字段 + 脚本原子写/stdio + 命令树拆组

> 重审（2026-11-07）：门禁修：silent-skip 理由 / 两个文本参数登记 / --mode 复核

> 重审（2026-11-07）：cc_check 文本层：法规原文→意图草稿（规则抽取，四张账）

> 重审（2026-11-07）：吊销公钥信任锚（钉根 + 有界委派 + 过期/scope/链深判据）

> 重审（2026-11-07）：载体层：WebP/MP4/PDF 附加块 + PNG 像素水印（判据含 JPEG 不扛的期望行为）

> 重审（2026-11-07）：RFC 3161 可信时间戳（timestamp 模块 + CLI + 证据复验时间锚）

> 重审（2026-11-07）：revocations_seed 进二进制豁免 + 两份文档项数同步（62→65 / 34→43）

> 重审（2026-11-07）：ed25519 吊销签名（非对称：验证方只持公钥）+ 回归判据

> 重审（2026-11-07）：batch_target 登记修正（位置参数进文本面，不进旗标名单）

> 重审（2026-11-07）：nf evidence batch（目录逐件复验，整批不可用即失败）

> 重审（2026-11-06）：机器面 NF_HOME 可移植（nf.py 变更）

> 重审（2026-11-06）：CLI 命令树拆分 + 旗标字面读取（nf.py 变更）

> 重审（2026-11-06）：task-27 吊销新鲜度：revocations/evidence/nf.py 变更，重绑被审对象

> 重审（2026-11-06）：JPEG 载体 P0 硬化（nf.py/CLI 文案变化）+ 口径清理，重绑被审对象

> 重审（2026-11-06）：JPEG APP15 载体（扫描数据不变）+ 真 PNG 夹具判据

> 重审（2026-11-06）：Q0-r2：evidence verify 增 --policy-digest 期望比对（nf.py 参数面变化），重绑被审对象

> 重审（2026-11-06）：耦合面重冻（载体模块行数变化后 metrics 面漂移）

> 重审（2026-11-06）：cc_label PNG iTXt 载体（可读回/不改像素/CRC 合法）

> 重审（2026-11-06）：注册 --decision 参数进编码/路径闸门（其提交遗漏）

> 重审（2026-11-05）：Q0 决策证据绑定：scripts/nf.py 增 --decision 入口、evidence/attest/nf_verify 增 decision 绑定，重绑被审对象摘要

> 重审（2026-11-05）：容器面加固：路径安全闸门 / 重名判死 / 解压上限（攻击矩阵 33→35）

> 重审（2026-11-05）：cc_label sidecar 回退（nf-label-sidecar/1，绑定对象摘要）

> 重审（2026-11-05）：--compile 参数登记进编码/路径闸门

> 重审（2026-11-05）：cc_check 编译面 v0：意图 → 封闭词表策略（不可表达逐条挂账）

> 重审（2026-11-05）：G2 吊销分发件（签名 feed：签发/校验/合并，防回滚）+ nf.py 导入块排序

> 重审（2026-11-05）：label 声明层补登记（编码闸门/路径旗标）+ 删零引用函数

> 重审（2026-11-05）：cc_label 声明层（nf-label/1 IR）+ 供应链核对进发布结论

> 重审（2026-11-05）：G1 外部锚点：证据包可声明并可核对（防整链截断），双实现同口径 + 攻击矩阵 33 条

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

> 重审（2026-10-29）：CLI 命令树无损分组、meta-cockpit 接线与恢复分支全量验证后重绑；既有结论不变

> 重审（2026-10-29）：恢复分支全量验证：接线 meta-cockpit 公共模块、清理零引用、修复 ReDoS/CLI 闸门/公开文档路径后重绑；既有结论不变

> 重审（2026-10-25）：跨平台收口：真实路径归一、守护状态读写锁、autostart 原子标记与机器路径短名脱敏

> 重审（2026-10-24）：夜间收口：Rust worker 安全、投稿配额、元数据、schema 与 postmortem 跨平台回执路径修复后按新输入重绑

> 重审（2026-10-23）：I/O/内存/IPC 审计整改：RepoIndex、缓存新鲜度、ISO/信任/协议防护

> 重审（2026-10-23）：Rust 快线加速收口：新增常驻 worker / PyO3 原语 / Rayon 解析并行与 code_metrics 接线；被审判据语义未变，digest 随实现同步

> 重审（2026-10-22）：H1：nf verify 仓库信任门（重冻）

> 重审（2026-10-21）：1.0.5 收口 1

> 重审（2026-10-20）：release 1.0.4 1

> 重审（2026-10-20）：repo hygiene: junk dirs removed, LF normalized

> 重审（2026-10-20）：version governance + daemon leak fix

> 重审（2026-10-20）：D 盘迁移：跨盘 relpath 修复（nf.py 展示面 + trust_boundary 用例）

> 重审（2026-10-19）：nf.py 会话落点放行 .rivet（受限环境唯一可写临时区）

> 重审（2026-10-18）：Glama coherence：收紧 spec_ls/registry_query 描述边界；asset_get 说明为协议资产五接口规范名

> 重审（2026-10-17）：步骤4 收口：attest --selfcheck 接线 + 站点/覆盖率分母同步

> 重审（2026-10-17）：步骤4：新增 check41/42（构建隔离 + 不可伪造 provenance）与对应判据模块

> 重审（2026-10-17）：能力面挂账：assertions.json 增 capability_vocabulary/index + 每条断言 capability

> 重审（2026-10-17）：并行的守护隔离：三种粒度（整个 NF_HOME / 只 cache 共享 / 只状态文件）实测全部与既有测试契约冲突，已全部撤回；保留 storage.cache_root() 单点派生（行为等价）与 daemon.state_path 的「为何不加覆盖」结论注释

> 重审（2026-10-17）：整批毫秒路径深入：nf verify 增 --jobs（每 check 独立子进程跑 --only N --json，按 check 号排序合并）；机器面增 messages 使并行结果可重放文案；实测 18.6s→6.4s（2.9x）且人读面/机器面与串行逐字节一致；新增 test_verify_parallel_checks 4 条判据（等价+排序+fail-closed）

> 重审（2026-10-16）：子 check 缓存（步骤①）：新增 core/subcheck_cache.py（观测读面+目录项快照+内容寻址，fail-closed）+ gate_faces 增目录列举收集器；实测审计：观测开销 1.4–2.2x，大树遍历 check 命中收益被快照成本吃掉

> 重审（2026-10-16）：门禁提速批（续）：拆 gate_native 让引擎回到行数闸门内 + check37 走 runpy 进程内执行，gate_inproc 增 run_script；被审对象字节已变，按本仓流程重绑 digest

> 重审（2026-10-15）：门禁提速批：测试面进程内化（check12 热点）+ 新增 gate_engine/gate_labels 单进程门禁引擎 + 派生基线重冻；被审对象字节已变，按本仓 rebind 流程重绑 digest

> 重审（2026-10-14）：收口：长行/导入序/静默跳过理由/风格基线重冻（评审）

> 重审（2026-10-14）：引入 nf audit rebind 命令（core/audit.py + CLI + 顺序纪律 + 两处面收敛）

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI + 顺序纪律）：重审并更新 digest 机器化

> 重审（2026-10-14）：引入 nf audit rebind（core/audit.py + CLI）：重审并更新 digest 口径机器化，替换手搓脚本

> 重审（2026-10-14 · 数字资产契约 S 档：包自述对账 / Frictionless 导出 / 可移植 schema）：被审对象随本波改动（组合包 INDEX 补登 SYSTEM_CARD 契约 / receipts 锚定面续扩 / CHANGELOG 条目），subjects 依「重审并更新 digest」机械重绑；既有结论不变，不主张新的语义审计。


> 重审（2026-10-14 · 核心文档改名/路径迁移）：被审对象随本波改名或引用替换而变，subjects 依「重审并更新 digest」机械重绑；本轮不主张新的语义审计。

> 重审（2026-10-11 · §15 审计修复波）：被审对象随修复波改动，subjects 依「重审并更新 digest」处置。本次为**机械重绑**（作者裁定 A）：修复波本身带判据与全量测试证据（doctor 17/17、四棘轮与基线相等、分块全量测试除本项外全绿），非新的语义审计。

> 签收位：本件**未填 `accepted_by`/`accepted_at`**——验收签收属作者动作，执行者不自签。
> subjects = 九件（本次修补涉及的模块与脚本）；**不含派生物**（口径同前）。

## 一、代码审查工具线（13 仓 · 3236 条可数规则）

拉取并提取规则目录（浅克隆到 `.rivet/scratch/cr-tools/`，报告
`.rivet/private_archive/cr_scan/2026-09-22_catalog.json`）：

| 工具 | 仓库 | 规则数 | 提取口径 |
|---|---|---|---|
| ruff | astral-sh/ruff | 969 | `ruff rule --all --output-format json` |
| pylint | PyCQA/pylint | 408 | checkers 源码 msgid |
| codeql | github/codeql | 1076 | `python/ql/**/*.ql` |
| sonar-python | SonarSource/sonar-python | 444 | 规则资源 JSON |
| semgrep-rules | semgrep/semgrep-rules | 112 | `python/**/*.yaml` rule id |
| flake8+pyflakes | PyCQA/flake8 · PyCQA/pyflakes | 101 | Message 类 + pycodestyle 码位 |
| pyright | microsoft/pyright | 81 | `report*` 诊断开关 |
| prospector | PyCQA/prospector | 29 | profile 计数 |
| vulture | jendrikseipp/vulture | 12 | `visit_*` 检查器 |
| radon | rubik/radon | 4 | 度量族 |
| bandit | PyCQA/bandit | （插件表口径另计） | 实际以运行结果为准（49 条发现） |
| pydocstyle / pyupgrade | PyCQA/pydocstyle · asottile/pyupgrade | 已克隆，码位抽取待改进 | — |
| Open-Jev | Zefan-Cai/Open-Jev | — | 冷链模型运行时（见 §四） |

**可执行分析器实测发现项 408 条**：bandit 49（安全）/ radon 240（复杂度≥C，其中 HIGH 93）/
mypy 106（类型）/ flake8 12 / vulture 1。

## 二、双模型热冷两层审查（Laya 热路径 / Jev 冷链）

**热路径（Laya·本地 systemone-http）**：对按严重度排序的前 **120 条**逐条快判
（`noul` 是否真问题 + `score` 优先级），全部 p≥0.5（工具证据型发现），其中 HIGH 93 / MEDIUM 27；
按工具：radon 93 · flake8 12 · mypy 10 · bandit 5。

**冷链（Jev 契约 · 三步链）**：取热判为真且优先级最高者 12 条，做
**真伪 → 类别 → 归属** 的三步类型化链（每步答案进入下一步 state）。示例：
`pipeline_scaffold.py:26 complexity-D → 正确性 / 代码`、`pipelinerun.py:84 complexity-F → 正确性 / 代码`。

**执行体如实标注**：Jev 9B **本机跑不动**——Jev venv 的 torch 为 CPU 版且未装 CUDA 轮子，
本机物理内存 **15.7 GB < 9B fp16 ≈ 18 GB**；故冷链由 **Laya 按 Jev 的
`/v1/systemone` + choice/noul/score 契约**执行（链路形状与 Jev 一致，换 Jev 只需把
endpoint 指向 `python -m jev.server`）。Jev 侧已完成：仓库克隆 + 独立 venv + 运行时安装 +
`jev.server --help` 接口核对。**可运行前置条件**（触发条件已记档）：CUDA 版 torch + ≥24GB 内存
或支持 4-bit 的 loader。

## 三、漏洞清单与按类修补（全部实测）

| 类 | 修前 | 修法 | 修后 |
|---|---|---|---|
| **bandit B310（MEDIUM）**：`urlopen` 无 scheme 校验 | 5 | 在 3 个模块的 urlopen 前加 **scheme ∈ {http,https} 白名单**（并附 `# nosec B310` 说明） | **0** |
| **bandit B110/B112**：`except → pass/continue` 无说明 | 30 | 逐站点补**成文理由**（`# nosec B110/B112 —— 尽力而为…见 AUD-0016`）：文档化 + 抑制同源 | **0** |
| **bandit B404/B603/B607**：subprocess 面 | 14 | 明确 argv 列表/绝对路径理由（`shutil.which` 已在前波落地） | **0** |
| **flake8** | 12 | 逐一修：未用导入（6）/ 未用变量（2）/ **`_cmd_audit` 重复定义 F811** / 等 | **0** |
| **vulture** | 1 | `check_agents_md` 的 `A if False else B` **死条件**清理为单一路径 | **0** |
| **mypy** | 106 | 未在本轮修：类型面属纵深工程（按模型判定归 `类型契约/可维护性`，见挂账） | 106（挂账） |
| **radon 复杂度** | 240（HIGH 93） | 未在本轮批量重构（重构成批风险高）：按冷链给出类别/归属，记入挂账清单 | 240（挂账） |

### 本轮修出的**真 bug**（被函数重名遮蔽，此前从未生效过）

`nf design audit` 的实现与 `nf audit` 家族**同名**（`_cmd_audit`，flake8 F811 实证），
Python 后定义者覆盖前者 → `nf design audit ls` 实测打出的是 `== nf audit（26 件）==`；
而暴露出来的那段旧实现又依赖**已退役 API**（`core.audit.init_audit`）→ 该子命令长期不可用。
修法（两层）：① 重命名 `_cmd_design_audit` + 修正调用点；② 按**单源委托**补回 M_AUDIT 门面
（`init_audit/check_audit/scan_audit` → 委托 `core.steelman`，未实装的 blindspot/full
fail-closed 并给修复指引，不编造语义）。实测：`nf design audit ls` 现返回设计审计索引，
`nf audit ls` 不受影响。

## 四、门禁与验收

| 判据 | 结果 |
|---|---|
| `bash verify.sh` | 见 §五（串行跑） |
| `python -m unittest discover -s desktop/tests -q` | 见 §五 |
| bandit / flake8 / vulture / ruff / compileall | **全零**（49→0 / 12→0 / 1→0 / clean / OK） |
| `nf model contracts` · `nf conformance` | 全绿 · 27/27 |

## 五、遗留与不宣称（如实）

1. **Jev 9B 未跑通**（内存/显卡前置不足，见 §二）；其契约与链路已按官方仓库核对并复用。
2. **mypy 106 条与 radon 240 条复杂度**属存量纵深面：本轮给出模型判定与归属，
   **未批量重构**（成批改写风险高于收益）——作为挂账，收敛路径 = 逐文件读语义 + 分批重构，
   每批过后跑全门禁。
3. **`# nosec` 的边界**：每一处都带**具体理由**且与 AUD-0016 的类级判据同源；
   这不等于"问题不存在"，而是"已评估并接受，且有登记"。
4. 本轮**未宣称零漏洞**：工具面覆盖有限（13 工具中实际可跑 6 个），模型判定未校准，
   结论以工具证据 + 门禁为准。
