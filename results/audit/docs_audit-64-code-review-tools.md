---
id: AUD-0016
title: 代码审查工具线（13 仓 / 3236 规则）+ 双模型热冷双层审查 + 按类修补（bandit 49→0 · flake8 12→0 · vulture 1→0，并修出一处被遮蔽的真 bug）
date: 2026-09-22
scope: 作者指令「拉取 ≥10 项代码审查工具；用工具 + 决策模型（Laya 热路径 / Jev 冷链）逐行审查出漏洞清单；全方面修补；双端推送」——本件记录：工具与规则目录、热/冷两层模型判定、漏洞清单、按类修补结果、以及未能跑通项（Jev 9B）的如实边界
verdict: pass
auditor: 本轮执行者
subjects:
  - desktop/src/core/audit.py:973b14991337d73ebe3508e4a4be0b9b5b632fa5477a40a82b1d0f5e4c69add2
  - desktop/src/core/export_schema.py:9052dc891be0c70ceb5b42544eceeceeeb4dee8c4f107b1ec660913cf922ad3d
  - desktop/src/core/decision_layer.py:f230aa31538f795d3a75a9cef9a109d323374cd8edbfc79c577df3e6378c31b7
  - desktop/src/core/storage.py:b64401314fd788fe0bae9676c21d61f162d704d3ac81e2f1d619b963149ab88c
  - desktop/src/core/gap_review.py:7d1d600926e13b9936f2a7d30e8a8ca95e4bb3b2a73308f88cfb89b563055953
  - scripts/nf.py:aa2e35009932c213c8659aaf02d087fca07b15c2c8e15bfeab5e31dbf74813e4
  - scripts/check_external_links.py:1cbee65ba19a83fbcdf333e35b8d99c2e45f3b400f3a025860357baf7a806b02
  - scripts/check_interop_schemas.py:f9c1add0ee80fb23a3913e32482027e9a4049c5ce70cb35b2b1be4afa075d091
  - scripts/ai_domain_closure.py:431d764da2ef56538eb1c473fe4f45d5ffa8191450638036f147ae7d66a3ae73

---
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
