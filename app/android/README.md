# NF Mobile（app/android）

NF APP 的 Android 控制面：本地处理、无账号、无遥测、**未声明 INTERNET 权限**；所有格式/操作语义/错误码按
app/docs/CONTRACT.md + app/docs/CLI.md + app/schema/error_codes.json（A0 冻结层）。

> v0.02（W1）现状：四目的地外壳（库/创作/交付/我的）+ 自适应底部栏/rail + FAB 导入 + 首启示例 Pack/3 步引导 +
> 设计 token/字体/暗色主题 + 自适应 launcher icon。旧 8 个功能页保留在详情层；W2 已接入新建项目向导、示例演示项目、本地搜索与 Pack 校验；W3 已把导入重做为产品向导；W4 已接入项目态创作台；W5 已接入项目态交付台、Pack 中心、CCOS 步骤化；Pack 更新支持应用内「选新版 Pack zip → 安全解包 → core pack-diff → 决策 → apply/回滚」；W4b 已接入创作台协议覆盖保存、管线/规格编辑+保存（撤销/重做 + 防抖自动保存）、交付状态写回；W6 已开始质量收口（heading 语义、设计 token/路由可达单测、Robolectric+Compose 语义测试 7 条、三档导航 + 9 组窗口尺寸矩阵、外壳 i18n + values-en + 英文 locale 测试）；RESULTS/FINAL_DOD 已加 v0.02 增量段；app/gates 7/7 PASS（FAIL=0）。全部屏主要文案已资源化（含 Protocol/Graph/Assembly 旧屏）；「我的」支持 zh/en/跟随系统切换与动态取色开关；库页支持下拉刷新；删除节点有 Snackbar 撤销 + 触觉；少量错误/技术提示仍内联；槽位支持单条/批量文本导入（--- 或空行分段；仅填空槽/覆盖已有）；Paparazzi 截图基线已入 app/src/test/snapshots。

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
      state/                 # 旧 NavState（保留兼容；v0.02 外壳用 ui/shell/ShellState）
      ui/shell/              # ShellState（四目的地 + 单层详情，纯逻辑可单测）
      ui/theme/              # NfTheme / NfTypography / NfSpacing / NfShapes / 动效 token
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

| 入口 | 类型 | 要点 |
|---|---|---|
| 库 | 顶层 1 | 渐变 hero + 最近项目/已安装 Pack；FAB 导入；顶栏搜索/设置；空态可载入示例；扫描 library/packs 与 projects/*.nfproject.json |
| 创作 | 顶层 2 | 项目列表 + 空态（项目向导 W2 接入）；点项目进详情 |
| 交付 | 顶层 3 | 项目列表/装配入口 + Pack 更新 / CCOS 快捷入口 |
| 我的 | 顶层 4 | 主题三态（跟随系统/浅色/深色）+ 存储/诊断/关于；中文默认 |
| 详情：Import | FAB/分享/空态 | 来源（文件/剪贴板/示例/分享）→ 预览（格式/置信度/结构）→ 映射（core map-suggest，逐条采纳）→ 草稿 + 决策 sidecar |
| 详情：Protocol / Graph / Assembly / PackUpdate / Ccos / Settings | 各屏详情 | 旧功能页保留，经详情层可达（返回回顶层）；能力/负例/错误码行为不变 |
| 详情：Project / Pack / Search / Author / Delivery / PackCenter | 列表点击/顶栏 | 项目状态/引用摘要 + 创作台/交付；Pack 版本/条目/tree + core pack-verify + 更新；Search 本地索引；Author 项目态三段；Delivery 计划/槽位/装配/校验/导出/分享；PackCenter 已装列表/校验/更新 |
| ShareReceiverActivity | SEND / SEND_MULTIPLE / VIEW / PROCESS_TEXT | 透明 Activity，只做载荷预览与「去导入」，不在接收层解析/落盘 |
| 首启引导 | 首次启动 | 3 步（价值→示例 Pack→试导入），可跳过；示例载入失败可重试，不阻断 |
| Onboarding 数据 | SharedPreferences | onboarding_done / sample_seeded / theme_mode（DataStore 迁移列 W6） |

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

103 条（JVM，无需模拟器）：

- CoreResponseTest（10）：信封解析/矛盾拒绝/NF-E-005。
- CoreBridgeContractTest（5）：op+payload 原样透传、错误 exit 语义、fake 无队列 fail-closed。
- ModelParsingTest（16）：9 类格式解析 + 负例（未知版本/浮点/网络策略/人审 required）+ 图编辑纯函数/环检测/回滚反向。
- StateMachineTest（6）：导航栈、冲突决策台、项目状态机、评审留痕约束。
- FixtureFilesTest（1）：用 app/fixtures/schema/valid/* 契约夹具逐格式解析（夹具缺失时 skip，不伪造通过）。
- AdaptiveLayoutTest（4）：窗口宽 599/600/839/840 分档。
- ShellStateTest（4）：四目的地/详情栈/根返回 null。
- PackStoreTest（3）：正常 Pack 扫描/坏 manifest 入 errors/空目录。
- ProjectFactoryTest（1）：nf-project 文档形状 + ProjectModel 解析。
- ProjectCreatorTest（2）：canonical×3 + project-validate 成功写盘；核心失败不写半成品。
- SearchIndexTest（3）：Pack 条款/字段/节点/章节/槽位 + 项目索引；空查询/缺目录容错。
- PackVerifierTest（1）：pack-verify 传已安装 root；失败由错误码路径覆盖。
- AuthorArtifactsLoaderTest（2）：sample-pack 读取 protocol/graph/spec；缺文件 fail-closed。
- PackZipLoaderTest（4）：根/单层目录包、zip slip 拒绝、缺 manifest 拒绝。
- AuthorOverlayStoreTest（2）：overlay 形状；保存后 refs.overlay/status=authoring/history 更新。
- ProjectStatusStoreTest（2）：draft→validated 逐步 history；核心失败不写盘。
- DesignTokenTest（3）：间距 4 倍数、shape 梯度、7 档字号/行高。
- ShellStateTest 增补：全部 14 类 Detail 路由 open/back 可达。
- ComposeSmokeTest（7，Robolectric）：空态 CTA、TopAppBar 返回、库空态导入、section heading 语义、引导跳过、Pack 中心空态、新建项目空态。
- ShellNavigationComposeTest（3，Robolectric）：w360 底部栏、w700 rail、w900 rail 四目的地。
- ShellEnglishLocaleTest（1，Robolectric）：en-rUS 下 Library/Create/Deliver/Me 资源生效。
- ShellSizeMatrixTest（9，Robolectric）：compact/medium/expanded 宽 × 三档高，四目的地语义可达。
- EnglishBodyLocaleTest（13，Robolectric）：onboarding/new project/import/search/pack center/author/delivery/ccos/settings/pack update/protocol/graph/assembly 正文英文资源生效。
- AppPrefsTest（1）：languageMode/dynamicColor 持久化。
- CcosReviewActionsTest（1，Robolectric）：固定底部人审按钮点击回调。
- ShareExporterTest（1，Robolectric）：非 Activity Context 拉起 chooser 必须带 NEW_TASK。
- NfExpandableComponentsTest（2，Robolectric/Compose）：长文本展开收起、分组折叠切换。
- SlotTextAdapterTest（2）：Markdown/纯文本槽位导入适配、BOM/换行归一。
- SlotBatchImporterTest（7）：显式 ---/空行分段、逐段适配、仅填空槽、覆盖+溢出、段数不足。
- LibraryStoreTest（2）：草稿同名不静默覆盖、文件名清洗。
- AtomicFilesTest（2）：替换前备份、无半截文件、无 .tmp 残留。
- DeliveryDraftStoreTest（2）：槽位草稿保存/恢复、空值清理、坏 JSON 忽略。
- SearchKeyboardTest（2）：上下选择边界、空结果不越界。
- A11yComposeTest（3，Robolectric）：图标 contentDescription、返回/搜索/设置/CTA 触控目标 ≥48dp。
- LargeFontComposeTest（1，Robolectric）：fontScale 200% 下库页主文案/CTA 仍可见。
- ContrastTest（3）：明暗品牌调色板 WCAG 2.2 AA 对比度（正文 4.5、大字 3.0）。
- PaparazziScreenshotTest（1）+ PaparazziSizeMatrixTest（9）：10 张 Home 截图基线（360/700/900 × 640/800/900/1000）。

## 构建证据（本机，2026-11-15）

- v0.02 W6（2026-11-15）：`./gradlew :app:assembleDebug` 成功：app-debug.apk = 21,710,683 bytes，
  sha256 = a2167ef3db25185151b98f37965cd897b50cad8f270978db7ad211f74067b156（含双 ABI 原生库 + 9 个示例 Pack assets）。
- `./gradlew :app:testDebugUnitTest` 全绿：145 条 JVM 单测（v1 42 + v0.02 103；含 Robolectric/Compose 语义/矩阵/英文 locale/a11y/大字号/对比度/Paparazzi 截图）。
- `zipalign -c -P 16 -v 4 app-debug.apk` → Verification successful（native lib 16KB page 对齐）。
- `bash app/scripts/build_core_android.sh --clean` 成功：NDK 27.0.12077973 + rustup targets
  （aarch64-linux-android / x86_64-linux-android，经 rsproxy 镜像安装）；两个 .so 的 LOAD align 均为 0x4000。

## 未实现面（OPEN）

1. **.so 未提交入库**：按纪律 jniLibs/*.so 不进 git；干净检出需先跑 app/scripts/build_core_android.sh 再 assembleDebug。.so 缺失时 APK 仍可构建，运行时明确报 NF-E-005。
2. **map-suggest 决策回算**：采纳/未采纳只落 sidecar JSON，未再接 core map-suggest 复核（决策持久化格式待契约登记）。
3. **Pack 安装的签名校验**：当前只做 nf-pack.json schema 读取与安装位置管理；签名/来源验证未实现。
4. **真机 smoke（OnePlus PLF110 / Android 16）**：已跑首启、示例导入、创作台保存、装配/L1/导出 md+zip；发现并修复 7 个真机问题（状态引用/导出 history/示例导入 kind/顶部 insets/分享崩溃与 prefill/jniLibs 陈旧导致 docx 误报/英文主题标签）；docx、TalkBack、主题/语言、CCOS、分享等仍 OPEN。详见 results/app/DEVICE_RESULTS.md。
5. **SAF 授权差异**：PROCESS_TEXT/SEND 的 URI 读取在部分 OEM ROM 仍需实测。
6. **深链/QR 交接**：CONTRACT §5.11 标 OPEN，未实现。
7. **instrumented test**：connectedAndroidTest 未纳入本轮。
