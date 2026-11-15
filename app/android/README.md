# NF Mobile（app/android）

NF APP 的 Android 控制面：本地处理、无账号、无遥测、**未声明 INTERNET 权限**；所有格式/操作语义/错误码按
app/docs/CONTRACT.md + app/docs/CLI.md + app/schema/error_codes.json（A0 冻结层）。

## 工程结构

~~~text
app/android/
  settings.gradle.kts        # rootProject nf-mobile；仓库 aliyun 镜像前置（本网络 dl.google 大文件会 reset）
  build.gradle.kts           # AGP 8.10.1 + Kotlin 2.1.20 + compose compiler plugin 2.1.20
  gradle/wrapper/            # gradle-8.11.1，huaweicloud 镜像 + sha256 钉住（f397b287…）
  gradlew / gradlew.bat
  .gitignore                 # 排除 .gradle/build/local.properties/jniLibs 下 .so
  app/
    build.gradle.kts         # namespace dev.ninfenz.mobile；compileSdk/targetSdk 36、minSdk 26
                             # ABI arm64-v8a + x86_64；useLegacyPackaging=false（16KB page）
    src/main/AndroidManifest.xml
    src/main/java/dev/ninfenz/mobile/
      core/                  # CoreBridge 接口 / CoreResponse 信封 / JNA 原生桥 / 错误码表
      model/                 # nf-import、nf-protocol-pack、nf-pipeline-graph、nf-md-spec、
                             # nf-assembly-plan、nf-validate-report、nf-pack-update、ccos-*、nf-project
      state/                 # NavState（返回栈，纯逻辑可单测）
      share/                 # ShareReceiverActivity（透明）+ SharePayload 解析 + FileProvider 导出
      ui/                    # Compose Material3 屏幕（card/edge-to-edge/预测返回）
    src/main/res/            # strings/styles（透明分享主题）/xml/file_paths.xml
    src/test/java/...        # JVM 单测（CoreResponse / 桥契约 / 模型解析 / 状态机 / 契约夹具）
~~~

## 工具链与环境（本机已验证组合）

- JDK 21：Microsoft OpenJDK 21.0.8；只要求 JAVA_HOME，AGP 目标 Java 17。
- Gradle 8.11.1：wrapper 从 huaweicloud 镜像下载并校验 sha256（distributionSha256Sum 已写入 wrapper properties）。
- Android SDK：platforms;android-36、build-tools;36.0.0、platform-tools；env 脚本把 ANDROID_HOME 指向 SDK。
- GRADLE_USER_HOME 复用已下载依赖（不要清）。
- 网络：系统可能配置失效 127.0.0.1 代理；构建前清空 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY，仓库顺序 aliyun → google → mavenCentral。
- 仓库**不写本机绝对路径**：local.properties 不入库，SDK 位置由 ANDROID_HOME/ANDROID_SDK_ROOT 提供。

~~~bash
# 本机工具链（按机器改路径；等价于导出 JAVA_HOME/ANDROID_HOME/GRADLE_USER_HOME 并清代理）
source D:/tmp/app-toolchain/env.sh
~~~

## 构建与复跑

~~~bash
source D:/tmp/app-toolchain/env.sh
cd app/android
./gradlew :app:assembleDebug          # -> app/build/outputs/apk/debug/app-debug.apk
./gradlew :app:testDebugUnitTest      # JVM 单测（见下方条数）
bash ../scripts/build_core_android.sh # 交叉编译 libnf_app_core.so（需要 NDK + rustup target；缺则 exit 4）
./gradlew :app:assembleDebug          # 重新打包（此时 APK 内含 jniLibs/{arm64-v8a,x86_64}/libnf_app_core.so）
~~~

产物：app/android/app/build/outputs/apk/debug/app-debug.apk（不入库：.gitignore 已排除 build/）。

## 屏幕与入口

| 屏幕 | 入口 | 要点 |
|---|---|---|
| Home | 启动 | Pack 库（library/packs）+ 项目扫描（projects/*.nfproject.json）+ 核心诊断；安装 Pack 走 SAF 目录树复制（只写 app 私有目录） |
| Import | Home / 分享 / SAF / 剪贴板 | 核心 import 产出 nf-import/1 → 嗅探/结构/映射建议预览；低置信（<60）必须人工确认；草稿+映射决策 sidecar 落盘 |
| Protocol | Home | 条款表单（开关 / 字段值 / 必填与占位符本地预检）→ 核心 protocol-render 权威渲染 |
| Graph | Home | 节点/边/权重编辑（本地表单检查：dup/dangling/weight/cycle）→ 核心 graph-validate / graph-compile |
| Assembly | Home | plan+spec+inputs → 核心 assemble → validate L1 → export md/zip → FileProvider 分享 |
| PackUpdate | Home | diff/impact/breaking 展示 + 冲突决策（keep_mine/take_new/defer，NF-PCK-006：未裁决不得应用）→ 核心 pack-merge；回滚=反向 update 走同一 op |
| Ccos | Home | ccos-task/ccos-result 人审（reviewer+note 必填，required 恒 true）→ 核心 ccos-import-result 回钉 task_digest |
| Settings | Home | 核心桥诊断（backend/ABI/原生库就绪/错误码登记条数）+ 隐私说明 + 诊断复制；无遥测 |
| ShareReceiverActivity | SEND / SEND_MULTIPLE / VIEW / PROCESS_TEXT | 透明 Activity，只做载荷预览与「去导入」，不在接收层解析/落盘 |

## 核心桥（CLI.md §5）

- 接口：suspend fun call(op: String, payload: JsonObject): CoreResponse；CoreResponse 严格解析 CLI.md §2 信封。
- 不变式：ok == (exit == 0)；失败响应必须带 code/message/fix；自相矛盾响应收敛为 NF-E-002 并 exit 4（fail-closed）。
- CoreBridgeNative：JNA 加载 libnf_app_core.so（ABI nf-app-core/1）；调用 nf_app_core_call，返回值必须 nf_app_core_free。
- 原生库缺席：**每次调用**返回 NF-E-005（exit 4）+ 安装指引（app/scripts/build_core_android.sh）；UI 明确显示错误，绝不回退假数据。
- FakeCoreBridge 只存在于 src/test（回放显式入队响应）。
- 错误码单一真源：构建时把 app/schema/error_codes.json 复制为 Java resource（copyErrorCatalog → process*JavaRes），Settings 页显示登记条数。

## 16KB page / ABI

- abiFilters = arm64-v8a + x86_64；packaging.jniLibs.useLegacyPackaging = false（native lib 不压缩、按页对齐打包）。
- 交叉编译脚本额外传 -Wl,-z,max-page-size=16384，并用 llvm-readelf 校验 LOAD align 含 0x4000（警告不静默）。

## 单测

38 条（JVM，无需模拟器）：

- CoreResponseTest（10）：信封解析/矛盾拒绝/NF-E-005。
- CoreBridgeContractTest（5）：op+payload 原样透传、错误 exit 语义、fake 无队列 fail-closed。
- ModelParsingTest（16）：9 类格式解析 + 负例（未知版本/浮点/网络策略/人审 required）+ 图编辑纯函数/环检测/回滚反向。
- StateMachineTest（6）：导航栈、冲突决策台、项目状态机、评审留痕约束。
- FixtureFilesTest（1）：用 app/fixtures/schema/valid/* 契约夹具逐格式解析（夹具缺失时 skip，不伪造通过）。

## 构建证据（本机，2026-11-15）

- `./gradlew :app:assembleDebug` 成功：app-debug.apk = 17,973,649 bytes（含 lib/arm64-v8a + lib/x86_64 的
  libnf_app_core.so 与 libjnidispatch.so）。
- `./gradlew :app:testDebugUnitTest` 全绿：38 条 JVM 单测。
- `zipalign -c -P 16 -v 4 app-debug.apk` → Verification successful（native lib 16KB page 对齐）。
- `bash app/scripts/build_core_android.sh --clean` 成功：NDK 27.0.12077973 + rustup targets
  （aarch64-linux-android / x86_64-linux-android，经 rsproxy 镜像安装）；两个 .so 的 LOAD align 均为 0x4000。

## 未实现面（OPEN）

1. **.so 未提交入库**：按纪律 jniLibs/*.so 不进 git；干净检出需先跑 app/scripts/build_core_android.sh 再 assembleDebug。.so 缺失时 APK 仍可构建，运行时明确报 NF-E-005。
2. **map-suggest 决策回算**：采纳/未采纳只落 sidecar JSON，未再接 core map-suggest 复核（决策持久化格式待契约登记）。
3. **Pack 安装的签名校验**：当前只做 nf-pack.json schema 读取与安装位置管理；签名/来源验证未实现。
4. **真机/设备矩阵 E2E**：未跑（无模拟器/真机证据）；本项目只提供 JVM 单测与构建证据。
5. **SAF 授权差异**：PROCESS_TEXT/SEND 的 URI 读取在部分 OEM ROM 仍需实测。
6. **深链/QR 交接**：CONTRACT §5.11 标 OPEN，未实现。
7. **instrumented test**：connectedAndroidTest 未纳入本轮。
