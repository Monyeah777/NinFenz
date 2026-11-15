# NF Studio（app/desktop）

NF APP 的桌面作者台（Compose Multiplatform / JVM）。本地处理、无账号、无遥测；共享核心经 JNA 调
nf_app_core.dll（app/core 的 Rust cdylib，ABI nf-app-core/1）。格式/语义/错误码按 app/docs/CONTRACT.md、
app/docs/CLI.md 与 app/schema/error_codes.json。

## 工程结构

~~~text
app/desktop/
  settings.gradle.kts        # rootProject nf-studio；JetBrains compose dev 仓库 + aliyun 前置
  build.gradle.kts           # Kotlin JVM 2.1.20 + org.jetbrains.compose 1.7.3 + compose compiler 2.1.20
                             # jvmToolchain(21)；copyCoreNative 从 app/core/target/release 复制 dll 进 resources
                             # nativeDistributions: TargetFormat.Msi + 文件关联 .nfg
  gradle/wrapper/            # gradle-8.11.1（huaweicloud 镜像 + sha256 钉住）
  src/main/kotlin/dev/ninfenz/studio/
    Main.kt                  # application { Window(...) }
    core/                    # Json 助手 / CoreResponse 信封 / CoreBridgeJna（JNA 加载 dll）
    model/                   # Project / GraphModel / Dsl / ValidateReport / Ccos
    render/                  # MarkdownRenderer（打印预览用纯文本 / HTML，无第三方依赖）
    print/                   # PrintService（javax.print 分页 + HTML 生成）
    tui/                     # TuiRunner（ProcessBuilder 调 python tui/nf.py，复用不重写 TUI）
    ui/                      # 导航栏 + 7 个屏幕 + 组件 + Swing 文件对话框
  src/test/kotlin/...        # JVM 单测 + 真实 FFI 集成测试（DLL 不在场时 skip）
~~~

## 工具链与环境

- JDK 21（jvmToolchain(21)，AGP 无需在场）。
- Gradle 8.11.1 wrapper（huaweicloud 镜像 + 钉住 sha256）。
- GRADLE_USER_HOME 复用依赖缓存。
- 网络：构建前清空失效代理（HTTP_PROXY/HTTPS_PROXY/ALL_PROXY），aliyun 镜像前置。
- Rust 核心：先构建 cdylib（Windows 产物 app/core/target/release/nf_app_core.dll），构建时由 Gradle
  copyCoreNative 复制到 resources/native；找不到时不失败、不造假——UI 显示 NF-E-005 与安装指引。

~~~bash
source D:/tmp/app-toolchain/env.sh   # 按机器改路径（JAVA_HOME/GRADLE_USER_HOME 并清代理）
cd app/core && cargo build --release # -> target/release/nf_app_core.dll
~~~

## 构建与复跑

~~~bash
source D:/tmp/app-toolchain/env.sh
cd app/desktop
./gradlew test                      # JVM 单测 + FFI 集成测试
./gradlew run                       # 直接运行（开发）
./gradlew createDistributable       # app-image（不需要 WiX）
./gradlew packageMsi                # Windows MSI（jpackage 需要 WiX 工具集）
~~~

产物：
- MSI：app/desktop/build/compose/binaries/main/msi/NFStudio-0.1.0.msi
- app-image（packageMsi 同时生成）：app/desktop/build/compose/binaries/main/app/NFStudio/NFStudio.exe

### 本机 MSI 构建证据（2026-11-15）

- `./gradlew test`：20 条 JVM 单测全绿（含真实 FFI 集成测试：加载 nf_app_core.dll，ABI=nf-app-core/1，
  canonical 调用信封合法；打包资源 /native/nf_app_core.dll 的 PE 头断言）。
- `./gradlew packageMsi`：成功，MSI = 66,573,406 bytes（2026-11-15 15:39 最终产物）。
- 原生核心打包路径：copyCoreNative 把 app/core/target/release/nf_app_core.dll 复制为资源
  build/generated/core-resources/native/nf_app_core.dll → app jar 内 /native/nf_app_core.dll → MSI 内 app 目录。
- **WiX 说明（本机特有）**：jpackage 需要 WiX 3.11（candle/light）。Compose 插件会自动下载 wix311-binaries.zip
  到 GRADLE_USER_HOME/compose-jb/wix311.zip；本机网络下该下载曾截断，改用镜像重下后解压到 build/wix311。
  又因本机 DSH 沙箱拒绝「workspace 内 exe」写入系统临时目录（light.exe 报 LGHT0001 UnauthorizedAccessException），
  需要把 WiX 放到 workspace 之外（如 D:/tmp/app-toolchain/wix/wix311）再用 junction 指向 build/wix311，
  并 `./gradlew packageMsi -x unzipWix`。普通 Windows 机器不需要这些绕行（插件自动下载 WiX 即可）。

## 屏幕

| 屏幕 | 要点 |
|---|---|
| 项目（ProjectManager） | 扫描/打开 nf-project/1；状态机迁移（draft→…→reviewed；回退/跳跃必须 force）+ 评审留痕约束 |
| 作者（Author） | 左：GraphEditor（节点/边/权重编辑 + 本地检查）；右：DslEditor（文本 DSL，解析出图并给行级错误）；核心 graph-validate / graph-compile |
| Pack（PackManager） | 目录列表 + nf-pack.json 摘要显示；核心 pack-verify（报告）/ pack-hash（tree digest） |
| 评审（Review） | 导入 ccos-result + ccos-task；人审 reviewer+note 必填、required 恒 true；核心 ccos-import-result 回钉 task_digest |
| 校验（ValidationPanel） | 打开既有 nf-validate-report/1；或 trio（markdown+spec+plan）调核心 validate L1 |
| TUI（TuiTerminal） | ProcessBuilder 跑 python tui/nf.py --selftest / --list-actions --json / 自定义命令，回放输出与退出码 |
| 打印（Print） | Markdown → MarkdownRenderer 纯文本预览；javax.print 分页打印；或生成 HTML 交系统打印 |

## Author DSL（与图编辑等价）

~~~text
# 行首 # 为注释
graph demo-pipeline 1.0.0
mode pro
node N01 stage "阶段"
node N02 module "模块" module=mod-outline
edge E01 N01:out -> N02:in
weight N01 30
required N01
~~~

解析产物即 nf-pipeline-graph/1；语义问题（悬空边/环/权重越界/未知节点类型）给出 line + code + fix。

## 核心桥与错误语义

- CoreBridgeJna 查找顺序：-Dnf.core.dll 显式路径 → classpath 资源 /native/nf_app_core.dll（构建时复制）→ 仓库相对路径
  ../core/target/release/nf_app_core.dll（开发期）。
- JNA 接口：nf_app_core_abi_version / nf_app_core_call / nf_app_core_free；调用后必须 free。
- 响应按 CLI.md §2 信封严格解析；ok == (exit==0)；矛盾收敛 NF-E-002；异常与缺库一律 NF-E-005（exit 4），不显示假数据。
- 集成测试 BridgeIntegrationTest 会真实加载 nf_app_core.dll 并断言 ABI = nf-app-core/1；DLL 不在场时 skip。

## 单测

app/desktop/src/test 下：
- CoreResponseTest：信封解析/矛盾拒绝/NF-E-005。
- BridgeIntegrationTest：真实 FFI（ABI + canonical 调用信封）。
- ModelAndDslTest：DSL 解析/往返/行级错误；契约夹具（nf-project、nf-validate-report、ccos-result）。
- RenderAndTuiTest：Markdown 渲染（纯文本/HTML 转义）、HTML 临时文件、TUI 仓库根探测。

## 未实现面（OPEN）

1. **代码签名/公证**：无证书与 macOS 环境，签名面挂 OPEN（不阻断实现）；MSI 未签名。
3. **文件关联 OS 级验证**：nativeDistributions 已声明 .nfg 关联；实际注册效果需在安装后的 Windows 上验证。
4. **评审写回项目文件**：Review 屏只回传核心判定，未改写 nf-project.json（项目写回属控制面 CLI 职责）。
5. **真机/跨平台验证**：只在 Windows 本机构建与测试；Linux/macOS 打包未跑。
