> 2026-11-21：当前基线见 `results/app/BASELINE-V2.md`；下方为历史 A0 审计快照。

# NF APP 基线审计（A0 · WP-A00）

> 状态：v1 · 审计日 2026-11-15 · 实施机检出 `e7855c237`（分支 `work/l4-floors`）
> 依据：`NF-APP-Final-方案-2026-11-15.md` §15.1（启动：只读基线 → `results/app/BASELINE.md`）/§14（WBS）/§18（验收）；仓库纪律 `AGENTS.md` / `STRATEGY.md`。
> ⛔ 操作指令：下文每条判定都附复跑命令；改本文件必须重跑命令并更新数字，不得照抄旧值。
> 性质：结果/状态件（审计记录），不是规划件。方案原文是作者本地输入（`C:\Users\mon_7\Downloads\NF-APP-Final-方案-2026-11-15.md`），**不入公开仓**（STRATEGY §四）。审计对象 = **本机检出**。
> 边界：本件只对 APP 实施面取证；`results/BASELINE.md` 是 NF-Final 方案基线，`results/trust/BASELINE.md` 是 TrustFabric 基线，三者互不替代。

## 0. 结论（先行）

1. **APP 面此前为零**：仓库无 `android/`、无 Kotlin/CMP 工程、无 UniFFI、无 13 个 `nf-* / ccos-*` 格式、无 `results/app/`。本方案不是「在既有 App 上补功能」，是**新建三端共享契约层 + 核心 + 两个 UI 工程**。
2. **可复用面比方案假设更大**：TUI 已是可运行的终端/检验面（`--selftest` 9 项全绿、`--list-actions --json` 34 动作/80 命令）；仓库已有 Rust 只读快线 + 跨语言对账基础设施（`engine/rust` 91 文件、`engine/dotnet` 110 文件、`clients/go`）；Python 核心已有管线/装配/校验/导出族（`desktop/src/core/{pipeline,assemble_plan,assembly_runtime,exporter,output_forms,...}.py`）。APP 侧**不重写**这些，只新增作者态/装配态/交付态格式与核心，并按 ID+digest 引用真源。
3. **门禁当前不是绿的（本机现状，非本方案引起）**：工作树 `bash verify.sh --checks-only` = **PASS=103 WARN=2 FAIL=334**；干净 clone 同 HEAD = **FAIL=1**（`conformance` 的 `modeling` 契约 root 漂移）+ WARN 2。原因见 §2.2/§2.3，全部是本地构建产物与未跟踪件，**与 `app/` 无关**（本文件写作时 `git status` 仅 `?? app/`）。不把「历史方案收口时曾 57/PASS=107」当成当前实测。
4. **工具链缺口是硬约束**：JDK 21 在场；**Gradle / Android SDK / kotlinc / Go 不在场**；crates.io 直连被失效代理拦截（需 rsproxy 镜像）；macOS 签名/公证在本机不可能执行。Android/D3 的「可安装包 / 公证」只能以 **OPEN（工具链/证书不在场）** 挂账，或以最小可构建证据补强——结论以 `app/results/TOOLCHAIN.md`（工具链勘察）为准。
5. **check 编号对账**：现有 `verify.sh` check 编号 = 1–57（`desktop/src/core/quality_baseline.py` 的显式清单）；APP 若接仓库门禁，**只能新增 check58+**，不得占用 1–57。

## 1. 实施机与检出事实

| 项 | 值（本轮实读） | 复跑命令 |
|---|---|---|
| 仓库根 | `D:\NinFenz`（origin `https://github.com/Monyeah777/NinFenz.git`） | `git config --get remote.origin.url` |
| 分支 / HEAD | `work/l4-floors` / `e7855c2372e1b07c83bc2be85d351a3401c73e3b` | `git branch --show-current; git rev-parse HEAD` |
| 脏文件 | 0（审计时；`app/` 尚未创建） | `git status --porcelain | wc -l` |
| tracked 文件 | 见 `git ls-files | wc -l`（本轮不钉数字，避免与既有基线冲突） | 同左 |
| 方案输入 | 作者本地 `Downloads/NF-APP-Final-方案-2026-11-15.md`（650 行），不入仓 | — |

## 2. 环境与门禁基线

### 2.1 工具链（本机实读）

| 面 | 结果 | 复跑 |
|---|---|---|
| Python | 3.11.9；pytest 9.1.1；jsonschema 4.26；PyYAML 在场 | `python -V; python -m pytest --version` |
| Node | v24.19.0 | `node -v` |
| Rust | cargo 1.99.1 / rustc 1.99.1 | `cargo -V; rustc -V` |
| JDK | openjdk 21.0.8 (Microsoft) | `java -version` |
| Gradle / Android SDK / kotlinc | **不在场**（`gradle`/`kotlinc` command not found；`ANDROID_HOME` 空、`%LOCALAPPDATA%\Android\Sdk` 无） | `gradle -v; kotlinc -version` |
| Go | **不在场** | `go version` |
| .NET | CLI 存在但 `dotnet --version` 报 SDK 解析失败（不冒充在场） | `dotnet --version` |
| crates.io | 直连被失效代理 `127.0.0.1` 拦截；`https://rsproxy.cn` 可达 | `cargo fetch`（默认）/镜像配置见 §2.4 |
| TUI | `python tui/nf.py --selftest` 9 项全 ✔；`--list-actions --json` = 34 动作 / 80 命令 / 区 9 / 表单 13 | 同左 |

### 2.2 工作树门禁（本机现状，红）

`bash verify.sh --checks-only` → **PASS=103 WARN=2 FAIL=334**（exit 1）。逐条归类：

- **332 条** = 编码卫生扫描命中**本地构建产物**：`engine/dotnet/**/{bin,obj}/**`（BOM/CRLF/路径键）与 `.nf-logs/*.json`（CRLF）。`text_hygiene` 只看文件系统、不看 `.gitignore`；`.gitignore` 第 58–60 行已显式记录该现象。
- **1 条** = check30「扩展策略/bump 迁移扫描异常」——`FileNotFoundError: [WinError 2]`（子进程工具缺失，未逐项定位）。
- **1 条** = check35 汇总（由上述 check30 子面触发）。
- 结论：**不是提交树的问题**；是工作树里历史会话留下的构建产物。处置 = 清理本地产物后复跑（本方案不改这些面）。
- 复跑：`bash verify.sh --checks-only > .nf-logs/verify.log 2>&1; grep -c '\[FAIL\]' .nf-logs/verify.log`

### 2.3 干净 clone 门禁（历史：曾红 1 条；**2026-11-15 已修复并复绿**）

`git clone --local D:\NinFenz D:\tmp\nf-baseline-clean` → `bash verify.sh --checks-only` → **FAIL=1**：

```
[FAIL] 一致性报告：报告过期或被改：root 记录=67eaf83536d46ae4 实测=2768d0a5e97602da（修复指引：nf conformance --write）
```

**2026-11-15 修复（BASELINE-F-001）**：根因是 modeling.verify_normative 的说明件计数把**未跟踪件**也算进去；已改为只认 git 追踪面（desktop/src/core/modeling.py::_tracked，UTF-8 surrogateescape 解码，git 不可用时保持旧行为），并加单测（desktop/tests/test_modeling.py::TestTrackedOnlyInformative）。修复后同一 commit 在干净 clone 与工作树算出同一 root；conformance 报告随冻结链重算。

原始根因实读：只差 `modeling` 一个契约（`informative_files` 2560 vs 2561）。工作树多出的文件 = `results/trust/rekor-public-key.pem`（**未跟踪**，被 `.gitignore` 吸收；干净 clone 没有）。即：**入仓的 conformance root 依赖工作树未跟踪件，干净 clone 不可复现**。

- 判定：**既有可复现性缺陷**（不是 APP 引入）；登记为 `BASELINE-F-001`（不阻断 APP 实施，APP 侧交付不得依赖它）。
- 复跑：见上；逐契约差分脚本见 `results/app/BASELINE-F-001.md`（附录 A）。

### 2.4 Rust 构建网络（本机）

crates.io 直连失败（系统代理 `127.0.0.1` 不可用）。已验证可用路径：`~/.cargo/registry` 已有 281 个 crate 缓存 + `rsproxy.cn` sparse 镜像可达。

```toml
# app/core/.cargo/config.toml（仅本机开发用；README 说明 CI 走默认 crates.io）
[source.crates-io]
replace-with = "rsproxy-sparse"
[source.rsproxy-sparse]
registry = "sparse+https://rsproxy.cn/index/"
```

复跑：`cd app/core && CARGO_HTTP_PROXY= HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= cargo fetch`

### 2.5 测试基线

`python -m pytest desktop/tests --collect-only -q` → **5894 tests collected in 7.96s**。全量 `pytest` 与 `bash verify.sh --full` **本轮未跑**（按 AGENTS.md 三件套口径：静态面全量 + 受影响面全量 + 仓库原生新鲜度命令；全量属 CI full 档）。APP 侧测试（`app/tests`）另行统计，不与 5894 混算。


### 2.6 本地验证约束 ENV-01（工具沙箱写盘面）

**现象**：仓库内可执行文件（`app/core/target/release/nf-app-core.exe`）调用 `std::fs::write` 写 `out_dir` 时返回 `os error 5（拒绝访问）`；同一二进制复制到 `D:/tmp` 运行即成功。逐项实测（2026-11-15）：

| # | 可执行文件位置 | 目标路径 | 结果 |
|---|---|---|---|
| 1 | 仓库内 | `D:/tmp/new_a.txt` | **拒绝（error 5）** |
| 2 | `D:/tmp` | `D:/tmp/new_b.txt` | 成功 |
| 3 | `D:/tmp` | `D:/NinFenz/.rivet/new_c.txt` | 成功 |
| 4 | 仓库内 | `D:/NinFenz/.rivet/new_d.txt` | **拒绝（error 5）** |
| 5 | 仓库内 | `D:/NinFenz/app/core/target/new_e.txt` | 成功 |

**判定**：本机 DSH 工具沙箱对**工作区内可执行文件**的写盘限制（白名单含构建输出面），**不是 APP 核心缺陷**，也不影响真实 APP（Android 进程/JVM 端壳不在该沙箱内）。**处置**：APP 测试/E2E 如需核心写盘，用临时目录内的二进制副本（`NF_APP_CORE` 指向它）或在允许面内写；CI 与真实运行不受此限。此约束同时解释「本机 `verify.sh` 有 300+ 编码卫生 FAIL」中的历史构建产物面——同一沙箱/工作树形态，不冒充仓库绿。


### 2.7 构建面实测（A0 后补，2026-11-15）

| 产物 | 实测 | 命令 |
|---|---|---|
| Android APK | 17,973,649 B；含 `lib/{arm64-v8a,x86_64}/{libnf_app_core.so,libjnidispatch.so}`；`zipalign -c -P 16 4` 通过 | `bash app/scripts/build_android.sh debug` |
| Rust Android `.so` | arm64 4,478,824 B / x86_64 4,645,976 B（NDK r27，LOAD align 0x4000） | `bash app/scripts/build_core_android.sh` |
| Windows MSI | 66,573,406 B；`build/libs/nf-studio.jar` 内含 `native/nf_app_core.dll` | `bash app/scripts/build_desktop.sh package` |
| Rust CLI / cdylib | `app/core/target/release/{nf-app-core.exe,nf_app_core.dll}` | `bash app/scripts/build_core.sh --release` |

工具链定版与坑见 `app/results/TOOLCHAIN.md`；`OPEN-TOOLCHAIN`（真机/模拟器/安装启动）不因构建成功而关闭。

## 3. 方案锚点复验（对照本机 HEAD）

判定口径：**命中** = 语义在且路径/接口可核；**漂移** = 能力在但落点/命名不同；**缺** = 方案要求、本仓无对应件。

| 方案锚点 | 方案用途 | 本机实读 | 判定 |
|---|---|---|---|
| §18.1 Android 工程（Kotlin/CMP + Rust） | 移动控制面 | 无 `android/`、无 `*.kt/*.gradle`、无 Android SDK | **缺**（A0–A6 新建） |
| §18.1 Desktop 工程（CMP + Rust） | 桌面作者台 | 无 CMP 工程；`desktop/src` 是 Python 核心（非 GUI 端壳，L3 端壳已退役见 `docs/L3_FROZEN.md`） | **缺**（D0–D3 新建） |
| §5.2 Rust + UniFFI 核心 | 共享核心 | `engine/rust` 91 文件是**只读快线**（ABI 版本号 cdylib；不写盘）；无 UniFFI | **漂移**：可复用对账/ABI 范式，APP 核心新写；UniFFI 依赖本机不可得 → JSON-C ABI（ADR-APP-011） |
| §11.3 TUI 集成 | 终端/检验一等公民 | `tui/nf.py` 76 KB、`_surface.py` 31 KB、`build_exe.ps1/.sh`；`--selftest` 9 ✔、`--list-actions --json` 34 动作/80 命令 | **命中**（D2 = 集成不重写） |
| §6 13 个数据模型 | 三端共享格式 | `protocol/schema/*.json`（9 件）+ `protocol/production/*.schema.json`（5 件）覆盖仓库生产平面；**无** `nf-import/1`、`nf-protocol-pack/1`、`nf-pipeline-graph/1`、`nf-md-spec/1`、`nf-assembly-plan/1`、`nf-validate-report/1`、`nf-template/1`、`nf-pack-update/1`、`nf-overlay/1`、`nf-project/1`、`ccos-task/1`、`ccos-result/1` | **缺**（A0 新建；边界见 `app/docs/CONTRACT.md` §9） |
| §10 CCOS 交接 | 执行面边界 | 无 `ccos-task/1`/`ccos-result/1`；`results/ccos/` 是旧方案的数据目录（非本方案格式） | **缺**（A6 新建） |
| §12 安全 | STRIDE/解析硬化 | 仓库有 `SECURITY.md`、威胁模型范式（`docs/production/THREAT_MODEL.md`）；APP 解析面（zip/YAML/PDF/DOCX）无实现 | **漂移**（A0 新建 + 复用范式） |
| §13 质量门 QA0–QA6 / S0–S15 | APP 自审 | 仓库有 S0–S15 自审计先例（`results/self_audit/S0-S15.json`）与 check55 聚合范式 | **命中**（复用格式，APP 自建门禁） |
| §14 WBS A0–A6/D0–D3/Q/R | 实施分解 | `results/app/` 不存在 | **缺**（本轮起建） |
| §15.2 不绕过 TUI 写盘 `yes` | 纪律 | TUI 已内建写盘确认（selftest「交互语义」项） | **命中** |
| §18.3 桌面签名/公证 | 发布门 | 无证书/无 macOS 环境 | **不可执行 → OPEN-EXTERNAL**（不阻断实现，阻断发布结论） |

## 4. 差距清单 → WBS 映射（开工依据）

| # | 差距（可核） | WBS | 本方案处置 |
|---|---|---|---|
| G-01 | 13 个共享格式 + 错误码/上限登记缺失 | A0 | `app/schema/`（已落） |
| G-02 | 共享核心（pack/import/protocol/graph/assemble/md/validate/export/update）缺失 | A0–A5 | `app/core/` Rust 参考实现 + CLI/FFI |
| G-03 | 控制面（项目/作者/分享/CCOS 人审）缺失 | A1–A6 | `app/cli/` Python 控制面 |
| G-04 | Android APP 工程缺失 | A1–A6 | `app/android/`（构建受工具链约束，见 §2.1） |
| G-05 | Desktop Studio 工程缺失 | D0–D1 | `app/desktop/`（同上） |
| G-06 | TUI 集成（Repo/命令面板/验证面板）只在 TUI 自身 | D2 | Studio 侧集成 + 复用 `--list-actions/--selftest` |
| G-07 | 签名/公证/发布脚本缺失 | D3 | 脚本 + 发布清单；证书/平台不在场 → OPEN |
| G-08 | APP 质量门/自审计缺失 | Q/R | `app/gates/` + `app/results/SELF_AUDIT.json` |
| G-09 | 仓库门禁无 APP 面 | Q | **本波决策：APP 面用自有门禁 `python app/gates/run_gates.py`（QA0–QA6 + S0–S15），**不改** `verify.sh` check1–57——理由：APP 面未收口前接入会把未稳定判据写进仓库基线，且冻结链（conformance/approve/receipts/layers/verify_report + 派生文档）在本地工作树（既有 334 FAIL）无法完成绿验证。接入 `check58` 列为 OPEN（owner: lead），前置 = 仓库本机/干净 clone 门禁先可绿（BASELINE-F-001 + 本地产物清理） |

## 5. 基线判定

- **可以开工**：G-01…G-09 是真缺口，且都有可核落点；无 P0 阻断（工具链缺口已识别为 OPEN，不阻断契约层与可验证核心）。
- **不可声称**：当前仓库门禁全绿（§2.2/§2.3 红）、Android APK 可安装、桌面签名/公证完成——这些要么未跑、要么环境不允许，按 `[HONESTY]` 口径挂 OPEN。

## 6. 复跑入口

```bash
git rev-parse --short HEAD; git status --porcelain
python -V; cargo -V; java -version
python -m pytest desktop/tests --collect-only -q | tail -1
python tui/nf.py --selftest
bash verify.sh --checks-only            # 期望本机现状：FAIL=334（见 §2.2），不是全绿
# 干净 clone：见 §2.3
```

## 附录 A：BASELINE-F-001 差分复现

```bash
git clone --local D:/NinFenz D:/tmp/nf-baseline-clean
cd D:/tmp/nf-baseline-clean && python scripts/nf.py conformance --json > D:/tmp/conf_clone.json
cd D:/NinFenz && python scripts/nf.py conformance --json > D:/tmp/conf_orig.json
python - <<'PY'
import json
a=json.load(open('D:/tmp/conf_clone.json',encoding='utf-8'))['report']
b=json.load(open('D:/tmp/conf_orig.json',encoding='utf-8'))['report']
print('root', a['root'][:16], b['root'][:16])
ca={c['id']:c['digest'] for c in a['contracts']}; cb={c['id']:c['digest'] for c in b['contracts']}
print([k for k in ca if ca[k]!=cb.get(k)])
PY
# 实测：仅 'modeling' 不同；工作树多出未跟踪文件 results/trust/rekor-public-key.pem
```