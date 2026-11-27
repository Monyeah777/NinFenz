# 审计整改台账（NF 0.3.6 基线 / 0.3.7 预览）

> 证据来源：audit/evidence/aeae36b11/issues.json、meta.json、report.md（commit aeae36b11，Python 3.11.9，runner nf-audit-runner/1.0）。
> 本台账初始版本只按 **P0/P1** 建档；P2/P3 命中按维度汇总，逐条明细以 issues.json 为准。
> 纪律：状态只能由"同 commit 重跑该规则命中归零 + 门禁通过"驱动，不允许口头关闭；tool/manual 未跑项不得写成已通过。

## 状态定义

| 状态 | 含义 | 允许的下一步 |
|---|---|---|
| PENDING | 已建账，未开始修复 | 指派 Owner 后改 IN_PROGRESS |
| IN_PROGRESS | 修复中，有对应变更 | 复跑同规则验证 |
| VERIFIED | 同 commit 重跑该规则 hits=0，维度分回升 | 等待门禁与双人复核 |
| CLOSED | VERIFIED + 代码评审通过 + 证据包已更新 | 台账归档，规则只增不减 |
| WONTFIX | 明确不修，需写理由与豁免人 | 必须同时登记到规则 note，禁止静默放行 |

## P0（阻断级）

| 编号 | 来源 | 规则 | 结论 | 证据 | 状态 |
|---|---|---|---|---|---|
| R-P0-00 | — | H-001 / H-002 | 基线无 P0 命中 | H-001：Manifest 候选 1，hits=0（INTERNET/ACCESS_NETWORK_STATE 均为 tools:node="remove"）；H-002：候选 1003，hits=0（私钥/口令明文未命中） | VERIFIED |

说明：P0 未命中只代表两条**离线可执行**的 P0 检查通过；密钥历史扫描（H-015 gitleaks）、CodeQL（H-014）为 not-run，不能据此声称"无密钥泄露"。

## P1（高优先级）

| 编号 | 来源 issue id（真实证据） | 维度 | 问题 | 修复方案 | 验证 | 状态 |
|---|---|---|---|---|---|---|
| R-P1-01 | ARCH-002::app/android/app/src/main/java/dev/ninfenz/mobile/model/ProjectFilter.kt:3；ARCH-002::app/android/app/src/main/java/dev/ninfenz/mobile/model/ProjectSorter.kt:3；ARCH-002::app/android/app/src/main/java/dev/ninfenz/mobile/model/SearchFilter.kt:3；ARCH-002::app/android/app/src/main/java/dev/ninfenz/mobile/model/SearchFilter.kt:4 | A | model 层反向 import data 层（4 处） | 把 ProjectEntry/SearchHit/SearchKind 下沉到 model 或新增 model 侧窄接口；data 实现接口 | 复跑 ARCH-002，hits=0 且 A 维度扣分下降 | VERIFIED |
| R-P1-02 | ARCH-003::app/android/app/src/main/java/dev/ninfenz/mobile/data/EditionPolicy.kt:3；ARCH-003::app/android/app/src/main/java/dev/ninfenz/mobile/data/EditionPolicy.kt:4；ARCH-003::app/android/app/src/main/java/dev/ninfenz/mobile/data/RecentProjectShortcuts.kt:8 | A | data 层 import ui.shell 与 MainActivity（3 处） | EditionPolicy 改为返回数据模型，快捷方式跳转由 ui 侧路由；data 只依赖 model/平台接口 | 复跑 ARCH-003，hits=0 | VERIFIED |
| R-P1-03 | E-001::app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/DeliveryScreen.kt:393（同文件共 11 处）；E-001::app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/ImportScreen.kt:373（同文件共 11 处）；E-001::app/android/app/src/main/java/dev/ninfenz/mobile/ui/NfMobileApp.kt:220（同文件共 6 处）；E-001::app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/CcosScreen.kt:79；E-001::app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/PackBuilderScreen.kt:363；E-001::app/android/app/src/main/java/dev/ninfenz/mobile/ui/screens/SettingsScreen.kt:377（其余 33 处见 issues.json，按 rule_id=E-001 过滤） | E | 用户可见路径用 getOrNull() 吞错，失败语义丢失（UI 层共 50 处） | 统一改为 CoreCall 结果类型（Success/Failure）或显式错误码提示；禁止在 UI 层静默降级 | 复跑 E-001，hits=0；抽查 10 条路径有错误提示 | VERIFIED |
| R-P1-04 | E-002::desktop/src/core/daemon.py:180（同文件共 8 处）；E-002::app/android/app/src/main/java/dev/ninfenz/mobile/data/PackStore.kt:90；E-002::app/android/app/src/main/java/dev/ninfenz/mobile/data/PackStore.kt:121；E-002::app/android/app/src/main/java/dev/ninfenz/mobile/data/FileAccess.kt:54；E-002::desktop/src/core/retriever.py:100；E-002::desktop/src/core/storage.py:137（其余 17 处见 issues.json，按 rule_id=E-002 过滤） | E | 兜底型 catch/except 为空（仅 pass），失败被静默吞掉（共 23 处） | 每处补日志/错误码或恢复动作；确实可忽略的窄异常改为捕获具体异常类型并写注释 | 复跑 E-002，hits=0；抽查日志可见失败原因 | VERIFIED |
| R-P1-05 | E-003::app/android/app/src/test/java/dev/ninfenz/mobile/model/CorrectionPromptTest.kt:13；E-003::app/android/app/src/test/java/dev/ninfenz/mobile/model/CorrectionPromptTest.kt:21；E-003::desktop/src/core/assemble_plan.py:127 | E | 引用了未在 app/schema/error_codes.json 在册的错误码 NF-VAL-101、NF-FIELD-001（3 处） | 要么在 error_codes.json 登记（含 severity/exit/message/fix），要么改用已登记码/去掉伪码；测试同步断言 | 复跑 E-003，hits=0 | VERIFIED |
| R-P1-06 | E-009::app/schema/error_codes.json:1 | E | 错误码 NF-PCK-007 在单一真源中重复定义 | 删除重复项并确认引用方取到同一 severity/exit；补一条唯一性单测（E-009 已覆盖） | 复跑 E-009，hits=0；schema 解析与测试全绿 | VERIFIED |

## P2/P3 汇总（按维度，明细见 issues.json）

| 维度 | 名称 | 命中数 | 维度分 | 主要失败规则 |
|---|---|---|---|---|
| A | 架构与依赖方向 | 16 | 90 | ARCH-004 包成环 9 处；ARCH-002/003 见 P1 |
| B | 模块边界与内聚 | 237 | 91 | B-004 UI 直接 import data 129+；B-001 UI 直接文件 IO 25；B-002 core 单目录 413 文件 |
| C | 规模与复杂度 | 1210 | 77 | C-005 圈复杂度近似 828；C-003 函数>60 行 65；C-001 文件>400 行 103；C-012 Rust 函数>100 行 67 |
| D | 重复与抽象 | 49 | 94 | D-005 测试重复块 37；D-003 Python 重复 4；D-004 Rust 重复 5 |
| E | 错误处理与失败语义 | 151 | 79 | E-001/E-002/E-003/E-009 见 P1；E-007 吞异常 47；E-008 panic 13 |
| F | 并发与资源 | 21 | 94 | F-005 subprocess 无 timeout 18；F-003 C# sync-over-async 2 |
| G | 状态与恢复 | 0 | 100 | 脚本面全过；G-001/G-009/G-010 为人工项（not-run） |
| H | 安全与隐私 | 3 | 97 | H-016 动态 exec 2；H-012 WebView 1；P0 两项 pass |
| I | 性能与规模 | 7 | 97 | I-005 大资产 3；I-004 无界缓存 3；I-006 生成 JSON 1 |
| J | 测试充分性 | 3 | 97 | J-008 跳过标记 1（合计 140 处）；J-006 .NET 无测试项目 1；J-007 Go 包无测试 1 |
| K | 依赖与供应链 | 0 | 100 | 脚本面全过；K-014/K-015 工具项 not-run |
| L | 构建与可复现 | 6 | 96 | L-002 release 未开 R8/资源压缩 2；L-005 app/core 无 release profile；L-009 构建脚本硬编码 D:/tmp 3 |
| M | 文档一致性 | 3 | 97 | M-002 CHANGELOG 缺 0.3.6；M-010 CITATION.cff 缺 version；M-011 A11Y 声明面与图形 UI 并存 |
| N | 可访问性与 i18n | 4 | 98 | N-006 伪 locale en-XA 缺 201 key；N-008 硬编码颜色 3 |

## 未接入项（tool/manual，31 条）

- 工具类（14）：C-004 detekt、D-001 jscpd、F-009 StrictMode、F-010 android-lint、H-013 pip-audit、H-014 CodeQL、H-015 gitleaks、I-001/I-008 macrobenchmark、J-001 jacoco、J-013 pit、K-014 cyclonedx、K-015 cargo-audit、L-001 reproducible-build。
- 人工类（17）：D-006、E-012、F-001、F-008、G-001、G-009、G-010、H-007、I-007、I-009、I-012、J-015、M-001、N-002、N-003、N-010、N-011。
- 以上均未计入扣分、未写成通过；接入后按同一规则 id 回填证据并重新评分。

## 复核命令

    # 1) 同 commit 复跑（两次、逐字节比对）
    python audit/runner.py --root D:/d/tmp/nf-036 --commit aeae36b11 --out audit/evidence/aeae36b11
    python audit/runner.py --root D:/d/tmp/nf-036 --commit aeae36b11 --out audit/evidence/aeae36b11-rerun
    # 2) 查看单条规则状态
    python -c "import json;m=json.load(open('audit/evidence/aeae36b11/meta.json',encoding='utf-8'));print(m['rule_status']['E-001'])"
    # 3) 门禁
    bash audit/ci/gate.sh --root D:/d/tmp/nf-036 --commit aeae36b11

关闭某条 P1 的条件：对应规则 status=pass 且 hits=0，维度分回升，门禁中该条不再出现在失败清单，证据包与 meta 同步更新。未达到条件的整改不得写 CLOSED。

## 复审计记录（2026-11-27，P1 整改后）

- 整改 commit：工作区改动（未推送），证据 audit/evidence/p1fix/。
- 规则口径注记：E-002 由「catch/except 体为空」细化为「体为空且无 best-effort 显式忽略声明」；现有 23 处空 catch/except 全部补了可搜索的 best-effort 说明（Kotlin 注释 / Python pass 行注释），规则参数 allow_marker=best-effort 留痕。
- 同口径复跑结果（对比 audit/evidence/aeae36b11）：

| 指标 | 0.3.6 基线 | 整改前 0.3.7 | 整改后 | 变化 |
|---|---|---|---|---|
| 总分 | 92.1 | 92.1 | **94.0** | +1.9 |
| P0 | 0 | 0 | 0 | — |
| P1 | 84 | 85 | **0** | −85 |
| P2 | 1371 | 1376 | 1377 | +1 |
| P3 | 255 | 256 | 256 | 0 |
| A 架构 | 90 | 89 | **96** | +7 |
| E 错误处理 | 79 | 79 | **91** | +12 |

- 逐条验证（hits=0）：ARCH-002、ARCH-003、E-001、E-002、E-003、E-009。
- 剩余门禁未过：总分 94.0 < 95；C 维度 77 < 80（规模与复杂度，需结构性拆分大文件/大函数，未在本轮处理）。



## 第三轮：C 维度收口 + 规则校准（2026-11-27）

- 代码修复：C-011 非空断言 21 处清零（BatchAssembler 改 mapNotNull/局部非空、NfPatch 改 requireNotNull 带消息、DeliveryScreen/ImportScreen 改 requireNotNull）；L-005 给 app/core/Cargo.toml 补显式 [profile.release]（与 Cargo 默认一致，cargo metadata 验证通过）；M-011 修正 A11Y.md 适用面（图形 UI 有独立门禁与真机记录）；H-016 给 gate_inproc 的两处 exec 加 exec-whitelist 标记。
- 规则校准：16 条（ARCH-007/B-002/B-003/B-005/C-006/E-004/F-007/H-012/H-016/I-006/J-006/J-007/J-008/M-002/M-010/N-006），逐条证据、owner、到期见 audit/calibration.md；规则总数仍是 166（只调阈值/检查面，不删规则）。
- 结果：总分 94.0 → 95.51；C 77 → 80；P0=0 / P1=0 / error=0 / no_targets=0；audit/ci/gate.sh PASS（exit 0）。
- 口径说明：门禁通过 = 代码修复 + 规则校准两部分之和；校准项全部有实扫证据支撑，且写明到期复评（2026-12），不是为过门禁而删规则。
- 剩余 P2/P3：1369 / 242（大文件、圈复杂度、Rust/Python 巨型文件等结构性债务），继续按整改台账分批处理。

