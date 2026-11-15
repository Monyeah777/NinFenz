# NF APP 收口审计（FINAL DOD）

> ⛔ 操作指令：本件是 APP 收口结论的人读面；机读真源 `app/results/GATES.json`（QA0–QA6）+ `app/results/SELF_AUDIT.json`（S0–S15），判据 `app/docs/DOD.md`。**pass-with-open-items ≠ 零缺陷**：外部 OPEN 与债务不因收口消失；未跑面不得写成 pass。
> 状态：v1（2026-11-15）· 依据：计划 §13（QA0–QA6）/§15.3（自审计）/§18（DoD）。

## 1. 结论

**APP 实现面：pass-with-open-items（P0 = 0）**。依据：
- APP 门禁 `python app/gates/run_gates.py` → **7/7 门 FAIL=0**（QA0–QA6 全部 PASS；无 OPEN 阻塞），`P0=0`；
- 自审计 S0–S15 → **covered 13 / gap 1 / open 2**，全部 gap/open 带 owner+next（P1=3）；
- 核心 `cargo test` **180 断言 / 21 个测试二进制 / 0 failed**；控制面 + 契约 + 安全 + golden + E2E：**pytest 485 passed / 0 failed / 0 skipped / 0 xfailed（128s）**；
- 构建实测：Android APK（17,973,649 B，16KB 对齐通过）+ Windows MSI（66,573,406 B）均含 Rust 核心。

**发布面：未完成（OPEN-EXTERNAL）**——签名/公证/真机矩阵/Play 数据安全未执行，不得宣称「可发布」。

## 2. 门禁收口（QA0–QA6）

> **仓库层（2026-11-15 实测）**：`bash verify.sh --checks-only` → **PASS=107 WARN=2 FAIL=0**（exit 0；HEAD `f19e41660`）。APP 面**未新增/未改** check1–57；入仓提交：`8d679c726`（modeling 可复现性修复）/ `8e75a3173`（APP MVP）/ `f19e41660`（冻结链投影重算）。干净 clone 同源复现见 `results/app/BASELINE.md` 附录 A。

| 门 | 内容 | 结果 | 证据 |
|---|---|---|---|
| QA0 | 架构/数据模型/FFI 契约/威胁模型/ADR | **PASS** | schema 可解析（≥15 件）；CONTRACT/CLI/ARCHITECTURE/THREAT_MODEL 在位；ADR 11 条；正反夹具；schema 测试全绿；编码/本机路径扫描 |
| QA1 | Pack/导入/映射/搜索；负例 | **PASS** | cargo test（cwd=app/core）；E2E 导入/Pack；安全负例 + CLI 契约 |
| QA2 | 协议/管线/装配/校验/导出；golden | **PASS** | golden + oracle 对账 31 条；首闭环 E2E 6 条 |
| QA3 | 分享/回填/Pack 更新/冲突/回滚；负例 | **PASS** | 更新/冲突/回滚 E2E；分享脱敏 5 条 |
| QA4 | 桌面/TUI/CCOS 交接；跨端一致 | **PASS** | TUI selftest 全绿；CCOS 相关 E2E；Android/Desktop 工程与构建证据 |
| QA5 | 安全/性能/无障碍/16KB/设备矩阵 | **PASS（含 OPEN）** | 解析安全负例全绿；设备矩阵/性能预算文档在位（实测面 OPEN-TOOLCHAIN） |
| QA6 | 发布/签名/公证/数据安全/许可；P0=0 | **PASS（含 OPEN）** | 脚本/文档在位；签名证据 OPEN-EXTERNAL；SELF_AUDIT p0=0 |

## 3. 自审计（S0–S15）

| 结论 | 维度 |
|---|---|
| covered（13） | S0 需求覆盖、S1 代码空洞、S2 默认放行、S4 链/序、S5 类型兼容、S6 测试缺口/变异、S7 文档过度声明、S8 依赖/供应链、S9 路径/DoS、S10 隐私/秘密、S12 导入矩阵、S13 Pack diff/merge/回滚、S14 APP/CCOS 边界 |
| gap（1，带 owner+next） | S11 崩溃/进程死亡恢复未实现（owner: lead） |
| open（2，带 owner+next） | S3 密码学（仅完整性摘要，无签名/加密）、S15 红队（无 Android 运行时/真机） |

停止条件（计划 §15.3）：QA0–QA6 FAIL=0 ✔；P0=0 ✔；UNSUPPORTED 全带 owner+next ✔；**「连续两轮」已达成**（Round2 与 Round3 各跑一轮 run_gates.py，均 FAIL=0 / P0=0，证据见两轮 GATES 现场输出）。

## 4. DoD（计划 §18.3）

| 编号 | 判据 | 状态 | 证据 |
|---|---|---|---|
| DOD-01 | QA0–QA6 绿 | **pass** | `app/results/GATES.json`（7/7 门 FAIL=0） |
| DOD-02 | P0=0；P1 有 owner | **pass** | `SELF_AUDIT.json.summary.p0=0`；3 项 P1 全带 owner+next |
| DOD-03 | 16KB/ABI/target 36；设备矩阵 | **构建面 pass；真机矩阵 OPEN-TOOLCHAIN** | APK + `zipalign -c -P 16 4` + 双 ABI `.so`；`DEVICE_MATRIX.md` |
| DOD-04 | 无遥测/密钥不入 APP；分享/导入负例 | **pass（本机可证面）** | manifest 权限面 + PRIVACY.md + 解析/分享负例 |
| DOD-05 | 桌面签名/公证；手机发布材料 | **OPEN-EXTERNAL** | 无证书/无 macOS；`RELEASE_EVIDENCE.md` 留位 |
| DOD-06 | 文档 claims 对应代码/测试；开放项登记 | **pass** | `SELF_AUDIT.open_items` + 各文档 OPEN 段 |
| DOD-07 | 首闭环（§18.2 七步） | **pass（控制面核心面）** | `test_e2e_first_loop.py` 6 条；Android 真机交互 OPEN |
| DOD-08 | 确定性（同输入同字节） | **pass** | canonical/determinism/golden 用例 + zip 固定 mtime |

## 5. 测试与构建实测

| 面 | 数字 | 复跑 |
|---|---|---|
| Rust 核心 | 180 断言 / 21 二进制 / 0 failed | `cd app/core && cargo test` |
| Python 控制面/契约/安全/golden/E2E | **485 passed / 0 failed / 0 skipped / 0 xfailed（128s）** | `python -m pytest app/tests -q` |
| Android JVM | 38 条 | `cd app/android && ./gradlew :app:testDebugUnitTest` |
| Desktop JVM | 20 条（含真实 JNA FFI） | `cd app/desktop && ./gradlew test` |
| APK | 17,973,649 B；16KB 对齐通过；双 ABI `.so` | `bash app/scripts/build_android.sh debug` |
| MSI | 66,573,406 B；jar 内含 `native/nf_app_core.dll` | `bash app/scripts/build_desktop.sh package` |

## 6. OPEN（不因收口关闭）

| id | 内容 | owner |
|---|---|---|
| OPEN-TOOLCHAIN | 真机/模拟器 E2E、MSI 安装启动、CMP 交互运行 | lead |
| OPEN-EXTERNAL | 签名/公证/Play 数据安全/macOS | lead |
| OPEN-CHECK58 | APP 门禁未接入仓库 `verify.sh`（前置=仓库门禁可绿） | lead |
| OPEN-DOCXPDF / OPEN-L2 / OPEN-SIGN-PACK / OPEN-MAP-DECISION / OPEN-INBOX / OPEN-DEEPLINK / OPEN-A11Y / OPEN-PERF / OPEN-REPRO / OPEN-DATADIR | 见 `SELF_AUDIT.json.open_items` 与 `app/core/README.md` OPEN | 各自 owner |

## 7. claims 边界

- 「pass」只指**上面列出的判据与证据**；不指「发布就绪」「合规」「认证」「已上架」。
- 外部合作/真机/证书类面一律 OPEN；引用 APP 门禁只说 `app/gates/run_gates.py`，引用仓库门禁只说 `bash verify.sh --checks-only` 实测（本机为红，见 BASELINE §2）。
- 数字随代码/夹具变化，**以 GATES.json 现场复跑为准**；本件数字为 2026-11-15 收口快照。

## 8. 复现

```bash
python app/gates/run_gates.py            # 期望：7/7 门 FAIL=0，P0=0，exit 0
python -m pytest app/tests -q             # 期望：485 passed / 0 failed
cd app/core && cargo test                # 期望：180 断言 0 failed
bash app/scripts/build_core.sh --release --test
python tui/nf.py --selftest              # 期望：9 项全 ✔
```
