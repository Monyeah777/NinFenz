# NF Mobile（app/android）

NF APP 的 Android 控制面：本地处理、无账号、无遥测、**未声明 INTERNET 权限**；所有格式/操作语义/错误码按
app/docs/CONTRACT.md + app/docs/CLI.md + app/schema/error_codes.json（A0 冻结层）。

> v0.02（W1）现状：单入口外壳（库 / 工作台+ / 我的；创作与交付在同一个工作台里按项目状态给出下一步）+ 自适应底部栏/rail + FAB 导入 + 首启示例 Pack/3 步引导 +
> 设计 token/字体/暗色主题 + 自适应 launcher icon。旧 8 个功能页保留在详情层；W2 已接入新建项目向导、示例演示项目、本地搜索与 Pack 校验；W3 已把导入重做为产品向导；W4 已接入项目态创作台；W5 已接入项目态交付台（含富文本 Markdown 预览）、Pack 中心、CCOS 接口预留（仅本地 task/result 文件交换，真实 AI OS/Agent 后续接入）；Pack 更新支持应用内「选新版 Pack zip → 安全解包 → core pack-diff → 决策 → apply/回滚」；Pack 中心支持安装 zip（安全解包→manifest 校验→原子安装）、校验/详情/卸载（项目引用时阻断并提示，卸载同时删 SQLite+JSON 注册记录）；W4b 已接入创作台协议覆盖保存、管线/规格编辑+保存（撤销/重做 + 防抖自动保存）、交付状态写回；导入端支持 md/txt/json/HTML/EPUB/DOCX/UTF-8(BOM)/UTF-16（含无 BOM 启发式），导出端支持 md/zip/json/docx/skill/EPUB/PDF/HTML（PDF 优先 WebView 离线 HTML/CSS，失败回退基础文本）；项目包与备份均带 manifest 完整性校验。W6 已开始质量收口（heading 语义、设计 token/路由可达单测、Robolectric+Compose 语义测试 7 条、三档导航 + 9 组窗口尺寸矩阵、外壳 i18n + values-en + 英文 locale 测试）；RESULTS/FINAL_DOD 已加 v0.02 增量段；app/gates 7/7 PASS（FAIL=0）。全部屏主要文案已资源化（含 Protocol/Graph/Assembly 旧屏）；「我的」支持 zh/en/跟随系统切换与动态取色开关；库页支持下拉刷新；删除节点有 Snackbar 撤销 + 触觉；UI 中文硬编码守卫通过（仅 CoreCall 无 Context 回退豁免）；槽位支持单条/批量文本导入（--- 或空行分段；仅填空槽/覆盖已有）；Paparazzi 截图基线已入 app/src/test/snapshots。

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

## a11y 门禁

`bash app/scripts/a11y_gate.sh`：运行 `A11yComposeTest`（图标 contentDescription + 48dp 触控目标）；任一失败即非零退出。

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
| 库 | 顶层 1 | 紧凑页头（标题/项目数/Pack 数/主操作）+ 最近项目/已安装 Pack；顶栏搜索/设置；空态可载入示例；扫描 library/packs 与 projects/*.nfproject.json |
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
- AdaptiveLayoutTest（4）：窗口宽 599/600/839/840 分档、导航标签资源唯一。
- ShellStateTest（4）：四目的地/详情栈/根返回 null。
- PackStoreTest（4）：正常 Pack 扫描/坏 manifest 入 errors/空目录/安装时间注册表。
- UndoStackTest（3）：有界撤销栈保留最近 100 条、顺序、零上限。
- ReproCheckerTest（3）：两次字节一致、首个差异偏移、长度差异。
- ProjectFactoryTest（1）：nf-project 文档形状 + ProjectModel 解析。
- ProjectCreatorTest（2）：canonical×3 + project-validate 成功写盘；核心失败不写半成品。
- SearchIndexTest（3）：Pack 条款/字段/节点/章节/槽位 + 项目索引；空查询/缺目录容错。
- PackVerifierTest（1）：pack-verify 传已安装 root；失败由错误码路径覆盖。
- AuthorArtifactsLoaderTest（2）：sample-pack 读取 protocol/graph/spec；缺文件 fail-closed。
- PackZipLoaderTest（10）：根/单层目录包、zip slip、缺 manifest、控制字符、压缩炸弹、加密条目、Windows 保留名、symlink、特殊文件拒绝。
- DocxReferenceStylesTest（7）：读取 word/styles.xml、sectPr、theme、numbering、header/footer、清理引用、缺 styles 拒绝。
- CcosPrecheckTest（3）：结果完整通过、task_id 不一致、危险路径/摘要。
- PdfMarkdownTest（9）：标题/行内标记、链接图片、代码围栏、项目符号、表格行、引用/分隔线、强调 span、data URI 图片、畸形输入不崩。
- StateRestorationTest（2，Robolectric）：新建项目标题、Pack 选择 SavedState 恢复。
- ProjectDiffTest（2）：状态/历史差异、相同项目无差异。
- SearchFilterStoreTest（2）：kind/pack 过滤存取与清空、坏 JSON 容错。
- ProjectRenamerTest（3）：重命名保留其它字段、空标题/超 120 字拒绝且不改文件。
- ProjectSorterTest（1）：按最近修改/标题/状态排序。
- LibraryViewStoreTest（2）：状态过滤/排序存取清空、坏 JSON 容错。
- DraftLibraryTest（5）：只列真实草稿、缺目录为空、删除含 mapping、重命名/冲突拒绝、读取 accepted sidecar。
- DraftProjectBinderTest（2）：草稿副本写入项目 authoring；缺项目/草稿拒绝。
- ShareQueueStoreTest（2）：多条目队列/游标存取、空/坏 JSON 容错。
- ProjectPackageTest（2）：完整项目 zip 含 JSON+data、缺项目拒绝。
- ProjectPackageImporterTest（13）：JSON+data 导入、嵌套目录包、ID 冲突改名、路径穿越拒绝、导出→导入往返、项目包识别、manifest 篡改拒绝、未列出条目拒绝、缺项目 JSON、缺 id、项目 JSON BOM、深层目录、UTF-16 项目 JSON。
- FileAccessLimitTest（4）：文本限额、目录单文件/总预算。
- ImportPreflightTest（3）：小 zip 通过、条目过多、压缩比过高。
- PackRegistrySqliteTest（4，Robolectric）：SQLite 写入/读取、旧 JSON 迁移、scan 自动迁移、remove 删除。
- ProjectDetailMountTest（1，Robolectric）：项目详情页可挂载并显示标题。
- CcosSessionRestoreTest（2，Robolectric）：恢复 task/result、恢复 approved 状态。
- CcosSessionStoreTest（4）：task/result 落盘恢复、清结果保留 task、清全部、缺文件回 null。
- WebPdfExporterTest（3）：A4 缩放页数、空/极小宽度、WebView 安全开关。
- A11yComposeTest（4）：库页图标/触控目标、返回、引导按钮、溢出菜单 48dp。
- HtmlExporterTest（13）：单文件 HTML/转义/列表、代码块、管道表格、安全链接、行内代码、水平线、引用块、有序列表、删除线、安全图片、代码语言 class、表格对齐、html() 与导出文件一致。
- HtmlValidatorTest（2）：导出物结构通过、坏/缺 HTML 拒绝。
- RtlShellTest（1）：RTL 下四目的地文本仍可见。
- AuthorOverlayStoreTest（2）：overlay 形状；保存后 refs.overlay/status=authoring/history 更新。
- ProjectStatusStoreTest（2）：draft→validated 逐步 history；核心失败不写盘。
- DesignTokenTest（3）：间距 4 倍数、shape 梯度、7 档字号/行高。
- ShellStateTest 增补：全部 14 类 Detail 路由 open/back 可达。
- ComposeSmokeTest（7，Robolectric）：空态 CTA、TopAppBar 返回、库空态导入、section heading 语义、引导跳过、Pack 中心空态、新建项目空态。
- ShellNavigationComposeTest（3，Robolectric）：w360 底部栏、w700 rail、w900 rail 四目的地。
- ShellEnglishLocaleTest（1，Robolectric）：en-rUS 下 Library/Create/Deliver/Me 资源生效。
- ShellSizeMatrixTest（9，Robolectric）：compact/medium/expanded 宽 × 三档高，四目的地语义可达。
- EnglishBodyLocaleTest（13，Robolectric）：onboarding/new project/import/search/pack center/author/delivery/ccos/settings/pack update/protocol/graph/assembly 正文英文资源生效。
- AppPrefsTest（2）：languageMode/dynamicColor 持久化、snapshot/restore 主题语言标记。
- ProjectReviewStoreTest（3）：通过写 approved/reviewed/history、驳回保留状态且空字段拒绝、评审摘要失效检测。
- CcosReviewActionsTest（1，Robolectric）：固定底部人审按钮点击回调。
- ShareExporterTest（1，Robolectric）：非 Activity Context 拉起 chooser 必须带 NEW_TASK。
- NfExpandableComponentsTest（2，Robolectric/Compose）：长文本展开收起、分组折叠切换。
- SlotTextAdapterTest（2）：Markdown/纯文本槽位导入适配、BOM/换行归一。
- SlotBatchImporterTest（7）：显式 ---/空行分段、逐段适配、仅填空槽、覆盖+溢出、段数不足。
- LibraryStoreTest（2）：草稿同名不静默覆盖、文件名清洗。
- AtomicFilesTest（2）：替换前备份、无半截文件、无 .tmp 残留。
- DeliveryDraftStoreTest（2）：槽位草稿保存/恢复、空值清理、坏 JSON 忽略。
- SearchKeyboardTest（2）：上下选择边界、空结果不越界。
- ShellStateCodecTest（2）：四目的地/全部详情类型的进程死亡编码与非法输入回退。
- ImportHistoryStoreTest（3）：digest 去重、重复记录更新。
- PackInstallerTest（4）：staging→fsync→rename、替换旧版本、卸载移动/删记录、越界路径拒绝。
- PackZipInstallerTest（3）：zip 安装、同 id+version 拒绝、缺 manifest 拒绝。
- PackCenterUninstallTest（1，Compose）：卸载按钮→确认弹窗→回调。
- MarkdownPreviewTest（1，Compose）：标题/列表/引用/代码/表格渲染。
- FlowUiTest（2，Compose）：工作台单入口/下一步、项目五阶段工作流。
- ProjectDetailMountTest（2，Compose）：项目详情挂载、overflow 更多操作。
- SearchHistoryStoreTest（2）：最近优先/去重、最多 10 条、清空。
- ImportDraftStoreTest（2）：最近导入预览保存/恢复、空白/损坏容错。
- SearchFilterTest（3）：kind=null 全量、按 kind 过滤。
- PackStoreTest 扩展（3）：索引缓存写入/损坏回退、目录变更重建、invalidate。
- ErrorCodeFilterTest（2）：空查询全量、code/message/fix 大小写不敏感过滤。
- ProjectFilterTest（2）：项目按状态过滤，null 全量。
- ProtocolDraftStoreTest（2）：协议未保存 values/enabled 存取、清空/坏 JSON 容错。
- ExportHistoryStoreTest（3）：最近导出/路径去重、最多 20 条、坏 JSON 容错、清空记录。
- CommandPaletteTest（3）：空查询全量、标题/id 过滤、最近使用排序。
- CommandHistoryStoreTest（2）：最近命令去重/上限 5。
- StorageStatsTest（2）：目录占用汇总、只清 imports/shared 缓存、缺失目录为 0。
- BackupServiceTest（4）：备份 zip 含 manifest/projects/drafts、空备份仍有 manifest、列表/裁剪旧备份、偏好元数据。
- BackupRestoreServiceTest（9）：合法备份恢复、回滚快照、路径穿越拒绝、sha256 不匹配拒绝、未列条目拒绝、缺 sha256 拒绝、manifest BOM、声明总量超限、单条过大。
- TextEncodingTest（3）：UTF-16LE/UTF-8 BOM 识别、无 BOM 不处理、无 BOM UTF-16 启发式。
- HtmlImporterTest（17）：标题/列表/实体转换、脚本/样式剔除、表格/链接、有序列表、图片、代码块、引用块、水平线、meta charset、粗体/斜体、删除线、数字实体、ol start、嵌套列表、嵌套有序列表、列表内行内格式、表格内行内格式。
- EpubImporterTest（6）：按 OPF spine 提取章节、缺 container 拒绝、spine 顺序、dc:title 补标题、容器识别、图片 data URI。
- DocxImporterTest（6）：Heading/正文提取、缺 document.xml 拒绝、列表段落、表格、粗体/斜体 run、超链接。
- ProjectHistoryExportTest（2）：历史 Markdown 表格/标题转义、空历史。
- ProjectDuplicatorTest（3）：复制保留 refs、重置状态/评审/历史、避免 id 冲突、目标 data 目录阻塞时清理。
- ProjectArchiverTest（7）：归档移出 projects/、列表/恢复、删除仅在归档目录、永久删除项目+数据、坏归档拒绝、越界拒绝、data 移动失败回滚。
- EpubExporterTest（11）：EPUB3 结构（mimetype STORED/OPF/nav/chapter、HTML 转义）、无标题单章、管道表格、安全链接、水平线、引用块、有序列表、删除线、代码语言 class、data URI 图片、表格对齐。
- EpubValidatorTest（3）：导出物通过、缺 EPUB 结构拒绝、缺文件拒绝。
- PdfPagerTest（4）：折行、分页/空输入、图片权重分页、表格表头续页。
- PdfValidatorTest（3）：最小 PDF 通过、坏/加密 PDF 拒绝、缺文件拒绝。
- PackTrustStoreTest（2）：按 pack@version 固定 tree、取消固定、坏 JSON 容错。
- DiagnosticsBundleTest（2）：诊断包仅含 diagnostics/README、文件名唯一。
- CrashLogStoreTest（2）：最近崩溃写入/清空、栈限制 64 KiB。
- ExportVerifierTest（2）：manifest bytes/sha256 一致通过；缺文件/错字节/错摘要/manifest 缺失失败。
- A11yComposeTest（4，Robolectric）：图标 contentDescription、返回/搜索/设置/CTA/溢出菜单触控目标 ≥48dp。
- LargeFontComposeTest（1，Robolectric）：fontScale 200% 下库页主文案/CTA 仍可见。
- ContrastTest（3）：明暗品牌调色板 WCAG 2.2 AA 对比度（正文 4.5、大字 3.0）。
- PaparazziScreenshotTest（1）+ PaparazziSizeMatrixTest（9）：10 张 Home 截图基线（360/700/900 × 640/800/900/1000）。

## 构建证据（本机，2026-11-15）

> Windows 下 clean/assembleRelease 若报 `lintVitalAnalyzeRelease` 的 lint jar 被占用，先 `./gradlew --stop` 再重试；也可直接用 `bash app/scripts/build_android_safe.sh`（失败自动 stop+重试一次）。
- 真机 smoke：连接并授权后运行 `bash app/scripts/device_smoke.sh`（安装 debug APK、冷启动、前台 Activity、最近崩溃日志）；设 `CAPTURE_DIR=…` 额外拉取 `home.png` 与 `ui.xml`。

- 2026-11-16 当前：`./gradlew :app:assembleDebug` 成功：app-debug.apk = 19,049,108 bytes，
  sha256 = 0ab152ad7787e1fffe722df9a7bf967e140b08e4c3b443f544ffe19125d01942（含双 ABI 原生库 + 9 个示例 Pack assets）。
- 仓库级门禁在 UTF-8 locale 下运行：`LANG=C.UTF-8 PYTHONUTF8=1 bash verify.sh --checks-only`（GBK 控制台会让 `git ls-files` 解码失败，触发 modeling 检查异常）。
- `./gradlew :app:testDebugUnitTest` 全绿：408 条 JVM 单测（v1 42 + v0.02 342；含 Robolectric/Compose 语义/矩阵/英文 locale/a11y/大字号/对比度/Paparazzi 截图）。
- `zipalign -c -P 16 -v 4 app-debug.apk` → Verification successful（native lib 16KB page 对齐）。
- `bash app/scripts/build_core_android.sh --clean` 成功：NDK 27.0.12077973 + rustup targets
  （aarch64-linux-android / x86_64-linux-android，经 rsproxy 镜像安装）；两个 .so 的 LOAD align 均为 0x4000。

## 未实现面（OPEN）

1. **.so 未提交入库**：按纪律 jniLibs/*.so 不进 git；干净检出需先跑 app/scripts/build_core_android.sh 再 assembleDebug。.so 缺失时 APK 仍可构建，运行时明确报 NF-E-005。
2. **map-suggest 决策回算**：采纳/未采纳只落 sidecar JSON，未再接 core map-suggest 复核（决策持久化格式待契约登记）。
3. **Pack 安装的签名校验**：当前只做 nf-pack.json schema 读取与安装位置管理；签名/来源验证未实现。
4. **真机 smoke（OnePlus PLF110 / Android 16）**：已跑首启、示例导入、创作台保存、装配/L1/导出 md+zip；发现并修复 7 个真机问题（状态引用/导出 history/示例导入 kind/顶部 insets/分享崩溃与 prefill/jniLibs 陈旧导致 docx 误报/英文主题标签）；docx/HTML/EPUB 导入、TalkBack、主题/语言、CCOS、分享等仍只有本机验证，真机未复测。详见 results/app/DEVICE_RESULTS.md。
5. **SAF 授权差异**：PROCESS_TEXT/SEND 的 URI 读取在部分 OEM ROM 仍需实测。
6. **深链/QR 交接**：CONTRACT §5.11 标 OPEN，未实现。
7. **instrumented test**：connectedAndroidTest 未纳入本轮。
