# NF APP 依赖与供应链清单

> ⛔ 操作指令：本件是依赖面的**事实登记**（名称/版本/许可/用途/是否直接依赖），不是「依赖已经审计」的声明。许可证取自**本机实际解析到的 crate 元数据**，不是记忆；未构建的平台依赖写 `OPEN`（含 owner），不得填猜测版本或许可。改本件必须同步 `app/docs/LEGAL.md`（NOTICE 口径）与 `app/docs/PERF_BUDGET.md`（包体预算）。
> 状态：v1（2026-11-15）· 性质：依赖清单 + 供应链纪律 · 取证时刻：2026-11-15 16:3x（本机实测，命令见 §8）。
> 依据：`app/core/Cargo.lock`（锁文件 = 版本真源）、`app/core/Cargo.toml`（直接依赖与精确钉版本）、`app/schema/limits.json`（依赖不参与上限）、`docs/legal/EXPORT.md`；上位：`SECURITY.md`（供应链评分口径）。

## 0. 取证方法与口径

| 项 | 方法 | 说明 |
|---|---|---|
| crate 清单与版本 | 实读 `app/core/Cargo.lock`（`version = 4` 格式） | 锁文件是版本真源；`Cargo.toml` 用 `=x.y.z` 精确钉 4 个直接依赖 |
| 许可证 | 读本机 registry 缓存的 crate `Cargo.toml` 的 `license` 字段 | 路径形如 `~/.cargo/registry/src/<index>/<crate>-<version>/Cargo.toml`；本机实测 **0 个 UNREAD**（40/40 全部取到） |
| 是否进入实际构建图 | `cd app/core && cargo tree --offline -e normal`（Windows 宿主） | 锁文件收录 ≠ 一定编译：可选依赖/目标相关依赖只在对应 feature/平台编译。注意：cargo 配置按 cwd 发现，从仓库根用 `--manifest-path` 会绕过 `.cargo/config.toml`（本机解析失败） |
| 是否直接依赖 | 实读 `app/core/Cargo.toml` 的 `[dependencies]` | 直接依赖 = regex / serde_json / sha2 / zip |

**结论（本轮实读）**：锁文件 **41** 个 package（含本 crate `nf-app-core`）= 4 个直接依赖 + 36 个传递依赖；`cargo tree -e normal` 构建图命中 **29** 个依赖（Windows 宿主），其余 **11** 个为锁文件收录（可选依赖 / 目标相关 / 未启用 feature）。许可集合全部为宽松许可：`MIT`、`MIT OR Apache-2.0`、`Apache-2.0 OR MIT`、`MIT OR Zlib OR Apache-2.0`、`0BSD OR MIT OR Apache-2.0`、`Unlicense OR MIT`、`(MIT OR Apache-2.0) AND Unicode-3.0`、`MIT/Apache-2.0`、`Apache-2.0`。**无 GPL / AGPL / SSPL 类强 copyleft 依赖。**

## 1. 直接依赖（4 个，全部精确钉版本）

| crate | 版本 | 许可证 | 进入构建图 | 用途 |
|---|---|---|---|---|
| regex | 1.13.1 | MIT / Apache-2.0 | 是 | 正则表达式（字段/路径/模式校验） |
| serde_json | 1.0.151 | MIT / Apache-2.0 | 是 | JSON 解析/序列化（响应信封、全部 JSON 产物） |
| sha2 | 0.10.9 | MIT / Apache-2.0 | 是 | SHA-256 摘要（canonical/pack/tree digest） |
| zip | 2.6.1 | MIT | 是 | zip 读写（pack/导出/解包安全） |

- 版本写法：`Cargo.toml` 使用 `=x.y.z`（不允许 `^` 漂移）；升级 = 显式改 `Cargo.toml` + 重生成 `Cargo.lock` + 重跑门禁。
- `zip` 以 `default-features = false, features = ["deflate"]` 引入（只用 DEFLATE，不启用加密/AES/其它压缩算法）。

## 2. 传递依赖（36 个；「进入构建图」列区分是否实际编译）

| crate | 版本 | 许可证 | 进入构建图 | 用途 |
|---|---|---|---|---|
| adler2 | 2.0.1 | 0BSD / MIT / Apache-2.0 | 是 | Adler-32 校验和（flate2/miniz_oxide 解压校验） |
| aho-corasick | 1.1.5 | Unlicense / MIT | 是 | 多模式字符串匹配（regex 引擎内部） |
| arbitrary | 1.5.0 | MIT / Apache-2.0 | 否（仅锁文件） | 结构化 fuzz 输入类型（zip 可选依赖；锁文件收录，未进 normal 构建图） |
| block-buffer | 0.10.4 | MIT / Apache-2.0 | 是 | 分组哈希缓冲区（sha2 → digest） |
| bumpalo | 3.20.4 | MIT / Apache-2.0 | 是 | bump 分配器（zopfli 压缩器） |
| cfg-if | 1.0.5 | MIT / Apache-2.0 | 是 | 编译期条件宏（跨平台分支） |
| cpufeatures | 0.2.17 | MIT / Apache-2.0 | 是 | CPU 特性探测（sha2 加速路径） |
| crc32fast | 1.5.5 | MIT / Apache-2.0 | 是 | CRC-32 校验（zip 条目完整性） |
| crossbeam-utils | 0.8.23 | MIT / Apache-2.0 | 否（仅锁文件） | 并发工具（zip 可选依赖；锁文件收录） |
| crypto-common | 0.1.7 | MIT / Apache-2.0 | 是 | 哈希 trait 公共定义（digest 依赖） |
| derive_arbitrary | 1.5.0 | MIT / Apache-2.0 | 否（仅锁文件） | arbitrary 派生宏（未进 normal 构建图） |
| digest | 0.10.7 | MIT / Apache-2.0 | 是 | 哈希抽象接口（sha2 依赖） |
| equivalent | 1.0.3 | Apache-2.0 / MIT | 是 | HashMap 键等价判定（indexmap 依赖） |
| flate2 | 1.1.11 | MIT / Apache-2.0 | 是 | DEFLATE 压缩/解压（zip 的 deflate 特性） |
| generic-array | 0.14.7 | MIT | 是 | 定长数组（digest/crypto-common 依赖） |
| hashbrown | 0.17.1 | MIT / Apache-2.0 | 是 | HashMap 实现（indexmap 依赖） |
| indexmap | 2.14.2 | Apache-2.0 / MIT | 是 | 保持插入序的 map（zip 中央目录） |
| itoa | 1.0.19 | MIT / Apache-2.0 | 是 | 整数转字符串（serde_json 依赖） |
| libc | 0.2.191 | MIT / Apache-2.0 | 否（仅锁文件） | Unix 平台系统调用绑定（cpufeatures 目标相关） |
| log | 0.4.35 | MIT / Apache-2.0 | 是 | 日志门面（zopfli 依赖；核心本身不记录日志） |
| memchr | 2.8.3 | Unlicense / MIT | 是 | 字节搜索（serde_json / regex / memchr） |
| miniz_oxide | 0.9.1 | MIT / Zlib / Apache-2.0 | 是 | DEFLATE 纯 Rust 实现（flate2 后端） |
| proc-macro2 | 1.0.107 | MIT / Apache-2.0 | 否（仅锁文件） | 过程宏基础设施（serde_derive/syn 依赖） |
| quote | 1.0.47 | MIT / Apache-2.0 | 否（仅锁文件） | 过程宏 token 生成（serde_derive/syn 依赖） |
| regex-automata | 0.4.18 | MIT / Apache-2.0 | 是 | regex 引擎实现（regex 依赖） |
| regex-syntax | 0.8.11 | MIT / Apache-2.0 | 是 | 正则语法解析（regex 依赖） |
| serde | 1.0.229 | MIT / Apache-2.0 | 否（仅锁文件） | 序列化框架（serde_json 依赖；锁文件收录） |
| serde_core | 1.0.229 | MIT / Apache-2.0 | 是 | serde 核心 trait（serde_json 直接使用） |
| serde_derive | 1.0.229 | MIT / Apache-2.0 | 否（仅锁文件） | serde 派生宏（serde 依赖） |
| simd-adler32 | 0.3.10 | MIT | 是 | SIMD Adler-32（miniz_oxide/zopfli 依赖） |
| syn | 3.0.10 | MIT / Apache-2.0 | 否（仅锁文件） | Rust 语法解析（派生宏依赖） |
| typenum | 1.20.1 | MIT / Apache-2.0 | 是 | 类型级整数（generic-array 依赖） |
| unicode-ident | 1.0.27 | (MIT / Apache-2.0) + Unicode-3.0 | 否（仅锁文件） | Unicode 标识符判定（proc-macro2/syn 依赖） |
| version_check | 0.9.5 | MIT/Apache-2.0 | 否（仅锁文件） | 编译器版本检测（generic-array 依赖） |
| zmij | 1.0.23 | MIT | 是 | 数字格式化（serde_json 依赖） |
| zopfli | 0.8.4 | Apache-2.0 | 是 | 高压缩比 DEFLATE（zip 可选特性） |

> 「否（仅锁文件）」不等于「永不编译」：在其它平台（如 Unix 目标会引入 `libc`）或启用对应 feature 时会进入构建图；发布构建必须对**实际目标**重跑 `cargo tree`，不能只看本表。

## 3. Python 控制面/测试依赖（APP 侧）

| 依赖 | 版本（仓库 pin） | 许可证 | 用途 | 引入位置 | 状态 |
|---|---|---|---|---|---|
| `jsonschema` | 4.26.0 | MIT | schema 结构 pre-flight（语义权威仍在 Rust 核心） | `app/cli/nf_app/schemas.py` | 实读（`.github/requirements-ci.txt` pin） |
| `jsonschema-specifications` | 2025.9.1 | MIT | jsonschema 依赖 | 传递依赖 | 实读 |
| `PyYAML` | 6.0.3 | MIT | YAML 安全加载（别名/深度上限在 `security.py` 内实现） | `app/cli/nf_app/security.py`（函数内懒加载 `loads_yaml_secure`） | 实读（`.github/requirements-ci.txt` pin） |
| `pytest` | 9.1.1（本机实测） | MIT | 测试执行（开发/门禁，不随产品分发） | `app/tests/` | 实读（本机 `python -m pytest --version`） |

- 控制面**不引入** HTTP/网络/SDK 类依赖（`PRIVACY.md` §3 有判据）；`jsonschema`/`PyYAML` 是纯本地解析库。
- 依赖版本来自仓库既有固定清单 `.github/requirements-ci.txt`（本仓既有供应链纪律），APP 不自建第二套 pin 文件。

## 4. 端壳构建依赖（Android / Desktop；**未构建 → 以下均未核验**）

| 平台 | 组件 | 声明版本（源码实读） | 许可（待核） | 落点 | 状态 |
|---|---|---|---|---|---|
| Android | Android Gradle Plugin | 8.10.1 | Apache-2.0（待 POM 核验） | `app/android/build.gradle.kts` | OPEN-TOOLCHAIN |
| Android | Kotlin / Compose 编译器插件 | 2.1.20 | Apache-2.0（待核） | 同上 | OPEN-TOOLCHAIN |
| Android | Gradle Wrapper 发行版 | 8.11.1（`distributionSha256Sum` 已钉） | Apache-2.0（待核） | `app/android/gradle/wrapper/gradle-wrapper.properties` | OPEN-TOOLCHAIN |
| Android | AndroidX test runner | 未声明具体版本（由 BOM/AGP 决定） | Apache-2.0（待核） | `app/android/app/build.gradle.kts` | OPEN-TOOLCHAIN |
| Desktop | Kotlin JVM 插件 | 2.1.20 | Apache-2.0（待核） | `app/desktop/build.gradle.kts` | OPEN-TOOLCHAIN |
| Desktop | Compose Multiplatform | 1.7.3 | Apache-2.0（待核） | 同上 | OPEN-TOOLCHAIN |
| Desktop | kotlinx-serialization-json | 1.8.1 | Apache-2.0（待核） | 同上 | OPEN-TOOLCHAIN |
| Desktop | JNA | 5.17.0 | **双许可（Apache-2.0 / LGPL-2.1）→ 分发时须按其一并随附声明**（待 POM 核验） | 同上 | OPEN-TOOLCHAIN |
| Desktop | JUnit | 4.13.2 | EPL-1.0（测试期依赖，不随产品分发；待核） | 同上 | OPEN-TOOLCHAIN |

**为什么是 OPEN**：本机无 Gradle/Android SDK（`app/docs/DEVICE_MATRIX.md` §0 实测），端壳从未构建 → 没有依赖解析结果（无 Gradle 依赖清单），许可证只能标注「待核」。端壳构建落地后必须：导出依赖清单（Gradle `dependencies`/SBOM）、逐项核许可、生成 APP 侧 NOTICE（`LEGAL.md` OPEN-LEGAL-01）。

**已注意到的供应链面（如实登记）**：Gradle wrapper 的 `distributionUrl` 指向第三方镜像（huaweicloud），已用 `distributionSha256Sum` 钉住发行版摘要——镜像被投毒时可被摘要校验发现，但镜像可用性成为构建前置。

## 5. 供应链纪律（现状 × 判据）

| # | 纪律 | 现状 | 判据 |
|---|---|---|---|
| SC-01 | 锁文件入库 | `app/core/Cargo.lock` 在场（version 4） | `git ls-files app/core/Cargo.lock` |
| SC-02 | 版本精确钉死 | `Cargo.toml` 4 个直接依赖全部 `=x.y.z` | `grep -n "=" app/core/Cargo.toml` |
| SC-03 | 无 git/路径依赖 | 锁文件所有 `source` 均为 crates.io index；无 `git+`/`path+` | `grep -n "source = " app/core/Cargo.lock` |
| SC-04 | 无 vendored 依赖 | 无 `vendor/` 目录；依赖只在 registry 缓存 | `ls app/core/vendor`（不存在） |
| SC-05 | 构建脚本不取网 | `app/scripts/build_core.sh` 不取网（注释明示）；`build_android.sh`/`build_desktop.sh` 只调 wrapper | `grep -rniE "curl|wget|pip install|npm install" app/scripts`（仅提示文案命中） |
| SC-06 | 离线可构建 | `cargo build --offline`（依赖缓存就绪时）可构建；`CARGO_NET_OFFLINE=true` 可强制 | `cd app/core && CARGO_NET_OFFLINE=true cargo build` |
| SC-07 | crates.io 源 | **偏差**：`app/core/.cargo/config.toml` 把 crates-io 替换为 `sparse+https://rsproxy.cn/index/`（第三方镜像，本机网络约束下的临时方案） | `cat app/core/.cargo/config.toml` → OPEN-SUPPLY-001 |
| SC-08 | 依赖漏洞审计 | **未做**：`cargo audit`/`cargo deny` 不在场，Dependabot 仅覆盖仓库既有面 | OPEN-SUPPLY-002 |
| SC-09 | 许可证合规检查 | 本表为手工+缓存元数据；无自动化（`cargo-deny`/`cargo-about` 不在场） | OPEN-SUPPLY-003（与 LEGAL OPEN-LEGAL-01 合并处理） |
| SC-10 | 构建可复现 | 锁文件 + 固定工具链可接近可复现；未做二进制比对（`cargo build` 两次产物摘要） | OPEN-SUPPLY-004 |

## 6. OPEN 登记

| id | 内容 | owner | 下一步 |
|---|---|---|---|
| OPEN-SUPPLY-001 | `.cargo/config.toml` 使用 rsproxy 第三方镜像（替换 crates-io） | lead | 决定是否入库/删除；CI 用官方源或自建 mirror + checksum；文档不得暗示官方源可用 |
| OPEN-SUPPLY-002 | 无依赖漏洞审计（cargo audit / dependabot 覆盖） | lead | 接入 `cargo audit`（或 CI 步骤），把结果进 `app/results/` |
| OPEN-SUPPLY-003 | 无自动化许可证检查与 APP NOTICE 生成 | lead | 接入 `cargo-deny` 或等价脚本；生成 `app/THIRD-PARTY-NOTICES.md`（见 `LEGAL.md` OPEN-LEGAL-01） |
| OPEN-SUPPLY-004 | 未做构建可复现性验证（同输入两次产物摘要比对） | rust-core | 核心稳定后做两次构建摘要比对并登记 |
| OPEN-TOOLCHAIN | 端壳依赖未解析（无 Gradle/SDK） | kotlin-ui | 端壳可构建后导出依赖清单 + 许可核验，回填 §4 |

## 7. 判据命令（复跑本表）

```bash
# 锁文件包数（41 = 1 本 crate + 40 依赖）
grep -c "^name = " app/core/Cargo.lock
# 直接依赖与精确钉版本
sed -n "/\[dependencies\]/,/^$/p" app/core/Cargo.toml
# 实际构建图（Windows 宿主；必须 cd 到 app/core：cargo 配置按 cwd 发现）
cd app/core && cargo tree --offline -e normal
# 目标平台的构建图（需先装对应 Rust target；同样 cd 到 app/core）
cd app/core && cargo tree --offline --target aarch64-linux-android -e normal
# 许可证逐包核对（读本机 registry 缓存元数据）
python - <<PY
import re, pathlib
lock = pathlib.Path("app/core/Cargo.lock").read_text(encoding="utf-8")
for b in lock.split("[[package]]")[1:]:
    n = re.search(r"name = \"([^\"]+)\"", b).group(1)
    v = re.search(r"version = \"([^\"]+)\"", b).group(1)
    for base in pathlib.Path.home().joinpath(".cargo/registry/src").glob("*"):
        p = base / f"{n}-{v}" / "Cargo.toml"
        if p.is_file():
            m = re.search(r"^license\\s*=\\s*\"([^\"]*)\"", p.read_text(encoding="utf-8", errors="replace"), re.M)
            print(n, v, m.group(1) if m else "UNREAD")
            break
PY
# 端壳依赖清单（端壳可构建后）
cd app/android && ./gradlew :app:dependencies --configuration releaseRuntimeClasspath
```

> 本件是依赖事实登记：许可证信息来自本机缓存元数据（取证时刻），实际分发前必须以发布构建的依赖解析结果复核；`OPEN-*` 未关闭前不得声称「供应链已审计」。

