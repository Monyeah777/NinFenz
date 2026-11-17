# NF APP 真机结果（DEVICE_RESULTS）

> 设备：OnePlus PLF110，Android 16（SDK 36），1080×2392 / 480dpi；serial 3B65AR0183V00000。
> **2026-11-17 真机已连接**：本轮新增安装/冷启动、WebView PDF、杀进程路由与槽位恢复实测（见第 6 节）；其余未跑项仍标 OPEN。
> APK：0.2.0 / versionCode 2，minSdk 26 / target 36。本件只记实际跑过的项目；未跑项标 OPEN，不写成 pass。
> 当前本机验证总览：Android JVM **373/373**、Rust core **198/198**、app Python **498 passed**、APP 门禁 QA0–QA6 PASS/gap=0、lint **0 warnings**、`verify.sh --checks-only` PASS=107/WARN=2/FAIL=0。

## 1. 已实测（2026-11-15）

| 项目 | 结果 | 证据 |
|---|---|---|
| 全仓门报复核（2026-11-17） | pass（本机）：app/gates QA0–QA6 7/7 PASS、gap=0；pytest **498 passed**；`verify.sh --checks-only` PASS=107/WARN=2/FAIL=0。 | 本机命令输出 |
| 全新安装 + 冷启动 | pass：LaunchState COLD，TotalTime 438ms（修复前）/471ms | adb am start -W |
| 首启 3 步引导 | pass：跳过/上一步/下一步/开始使用可用；示例 Pack 载入显示 demo-pack · 1.0.0（9 个文件） | 截图 02–05 |
| 库首页 | pass：示例 Pack、演示项目、状态草稿、管理入口均显示 | 截图 05 |
| 项目详情 | pass：状态/项目 ID/Pack/协议/历史/创作台/装配与交付 | 截图 06 |
| 创作台协议 | pass（保存）：编辑 F-002、切换 C-002、保存后 files/projects/demo-project/overlay/nf-overlay.json 写入，项目 status=authoring、history=overlay:save | run-as 读文件 |
| 装配计划 | pass：graph-compile 返回 steps 2 · slots 4 | 截图 13 |
| 装配 | pass：填 4 个槽位后 assemble 返回 markdown（开篇/正文/收束） | 截图 19 |
| L1 校验 | pass：L1 pass（error=0 warn=0 info=3）；状态 assembled→validated 写回 | run-as 读项目 |
| 导出 md/zip | pass：files/exports/delivery/result.md + result.zip + manifest；状态 validated→exported 写回 | run-as 读文件 |
| 桌面快捷方式（构建） | pass（构建）：静态 shortcuts（导入/新建/搜索）+ MainActivity 冷启动/onNewIntent 路由；未真机长按图标验证（adb 无设备） |
| Lint 收尾（JVM） | pass（本机）：抑制预期 UnusedAttribute；import_project_package_done 改 plurals；warnings 4→3（仅剩 GradleDependency2/ObsoleteSdkInt1）。真机未复测（adb 无设备） |
| 错误码复制反馈（JVM） | pass（本机）：点击错误码复制并 Toast「已复制 code」；真机未复测（adb 无设备） |
| 门禁/ lint 复核（round143） | pass（本机）：QA0–QA6 全 PASS，FAIL=0，covered=14 gap=0 open=2 p0=0；lint warnings=1（仅 Paparazzi 版本，Kotlin 2.1 阻塞）。 |
| 备份未列条目拒绝（JVM） | pass（本机）：manifest 未列出的 zip 条目导致 inspect 失败；BackupRestoreServiceTest 5 条。真机未复测（adb 无设备） |
| 全量复核（round161） | pass（本机）：verify.sh PASS=107 WARN=2 FAIL=0；app gates QA0–QA6 PASS，gap=0，P0=0；lint 0 warnings。 |
| 全量复核（round15） | pass（本机）：verify PASS=107 WARN=2 FAIL=0；app gates QA0–QA6 PASS，gap=0，P0=0。 |
| EPUB 表格对齐（JVM） | pass（本机）：EPUB 表格支持 :---/::/---: 对齐；测试 11 条。真机未复测（adb 无设备） |
| HTML 表格对齐（JVM） | pass（本机）：:---/::/---: → style text-align；测试 12 条。真机未复测（adb 无设备） |
| EPUB 导出 data URI 图片（JVM） | pass（本机）：Markdown data:image 渲染为 img；测试 10 条。真机未复测（adb 无设备） |
| EPUB 图片内嵌（JVM） | pass（本机）：EPUB img 转 data URI（单图 ≤2MiB、总量 ≤20MiB）；测试 6 条。真机未复测（adb 无设备） |
| 全量复核（round53） | pass（本机）：verify PASS=107/WARN=2/FAIL=0；gates PASS/gap=0；rust 186；pytest 493。 |
| Python 全量复核（round61） | pass（本机）：schema 变更后 `pytest app/tests` 493 passed / 0 failed（126s）。 |
| 全量复核（round60） | pass（本机）：verify 107/2/0；gates PASS/gap=0；rust 186；JVM 317。 |
| 新建项目选择 SavedState（JVM） | pass（本机）：Pack 选择改 selectedKey rememberSaveable；340 tests。 |
| PDF 表格/代码/引用/行内强调（JVM）：表格列宽加权、代码等宽+浅底、引用斜体+竖线、行内 bold/italic/code span；7 条测试。 |
| PDF data URI 图片（JVM） | pass（本机）：解析 data:image/*;base64，按内容宽/页高缩放、居中、按高度权重分页；9 条测试。 |
| DOCX 强调/表格/代码块（Rust）：表格列宽加权、表头重复、嵌套强调、代码浅底；Rust 198。 |
| WebView PDF 安全/页脚（JVM）：JS/文件/内容/网络全关；每页页码；3 条 WebPdf 测试。 |
| a11y CI 门禁（JVM） | pass（本机）：`app/scripts/a11y_gate.sh` 跑 A11yComposeTest；新增溢出菜单 48dp 检查并修到 48dp。 |
| 目录导入大小预算（JVM） | pass（本机）：单文件 128 MiB、总量 512 MiB；失败清空目标目录；copyLimited 测试。 |
| 文本导入 64 MiB 限额（JVM） | pass（本机）：readText 走 readLimited，超限拒绝；2 条测试。 |
| DOCX/EPUB 导入 zip 预检（JVM） | pass（本机）：条目数 ≤1000、总量 ≤256MiB、单条压缩比 ≤120；3 条测试。 |
| PDF 表头跨页重复（JVM） | pass（本机）：repeatTableHeaders 纯函数测试 + 续页重插。 |
| PDF 表头跨页重复（JVM） | pass（本机）：表格续页自动重插表头行（按当前表头定位）。 |
| WebView PDF 页数计算（JVM） | pass（本机）：A4 缩放页数、空/极小宽度边界；2 条测试。 |
| PDF HTML/CSS 渲染（JVM 构建） | code-complete（本机）：WebView 离线渲染 HTML/CSS 到 PdfDocument；HtmlExporter.html 与文件一致测试；空白/异常回退。**真机未验证**。 |
| DOCX 引用/分隔线（Rust） | pass（本机）：引用 Quote 样式、水平线 pBdr；Rust 195。 |
| DOCX Markdown 表格（Rust） | pass（本机）：生成 w:tbl/w:tr/w:tc、表头加粗、全边框；Rust 194。 |
| DOCX 参考编号 numId（Rust） | pass（本机）：从 numbering.xml 解析首个 numId，列表 numPr 使用该 ID；Rust 193。 |
| DOCX 参考页眉/页脚（Rust+JVM） | pass（本机）：继承 header1/footer1 并写关系；Rust 193。 |
| DOCX 悬空页眉页脚引用清理（Rust+JVM） | pass（本机）：sectPr 中的 header/footerReference 在未继承对应部件时移除。 |
| DOCX 参考编号（Rust+JVM） | pass（本机）：继承 word/numbering.xml，列表段落写 numPr；Rust 191。 |
| DOCX 参考主题（Rust+JVM） | pass（本机）：继承 word/theme/theme1.xml 并写主题关系；Rust 190。 |
| DOCX 参考页面设置（Rust+JVM） | pass（本机）：继承 word/document.xml 的 sectPr（页边距/纸张）；3 条 JVM 测试。 |
| 迁移前自动备份/回滚（JVM） | pass（本机）：Pack 更新应用前自动备份并显示路径；新增确认对话框一键恢复该备份，调用 BackupRestoreService.restore。 |
| PDF 标题/粗体样式（JVM） | pass（本机）：标题按 level 字号加粗，正文/项目符号分样式绘制。 |
| SavedState 恢复测试（JVM） | pass（本机）：StateRestorationTester 验证新建项目标题与 Pack 选择进程恢复；345 tests。 |
| CCOS 评审字段 SavedState（JVM） | pass（本机）：reviewer/note 改 rememberSaveable；337 tests。 |
| Assembly 双跑检查（JVM） | pass（本机）：AssemblyScreen assemble/validate 各两次比较结果 JSON。 |
| graph-compile 双跑检查（JVM） | pass（本机）：graph-compile 两次调用比较结果 JSON；图屏显示稳定/差异。 |
| PDF Markdown 预处理（JVM） | pass（本机）：标题/粗体/代码/链接/图片标记清理，代码围栏保留内容；4 条测试。 |
| validate 双跑检查（JVM） | pass（本机）：validate 两次调用比较报告 JSON，交付台显示稳定/差异。 |
| CCOS 结果导入预检（JVM） | pass（本机）：task_id/回钉摘要/artifact 路径与 sha/evidence 结构预检；3 条测试。 |
| assemble 双跑检查（JVM） | pass（本机）：交付台 assemble 两次调用比较 markdown 字节并显示首个差异；330 tests。 |
| DOCX 参考样式（Rust+JVM） | pass（本机）：选择参考 DOCX 提取 word/styles.xml 注入导出；2 条 JVM 测试。 |
| Pack zip 特殊文件拒绝（JVM） | pass（本机）：Unix fifo/device/socket mode 拒绝；PackZipLoaderTest 10 条。 |
| Pack zip symlink 拒绝（JVM） | pass（本机）：解析 central directory external attrs，Unix symlink mode 0xA000 拒绝；PackZipLoaderTest 9 条。 |
| Pack zip 保留名拒绝（JVM） | pass（本机）：CON/PRN/AUX/NUL/COM1-9/LPT1-9 与尾点/尾空格拒绝；PackZipLoaderTest 8 条。 |
| 协议规则 explain（Rust+JVM） | pass（本机）：protocol-render explain 返回每个规则/子表达式轨迹；协议屏可勾选显示；cargo 187。 |
| 表单字段 SavedState（JVM） | pass（本机）：新建项目标题、评审人/意见改 rememberSaveable；路由已由 ShellStateCodec 覆盖。 |
| 核心 export 双跑检查（JVM） | pass（本机）：md/zip/docx/json/skill 导出后二次导出比较；325 tests。 |
| PDF 双跑复现检查（JVM） | pass（本机）：PDF 导出后二次导出逐字节比较；325 tests。 |
| EPUB/HTML 双跑复现检查（JVM） | pass（本机）：导出后二次导出逐字节比较并显示首个差异偏移；ReproCheckerTest 3 条。 |
| 有界撤销栈（JVM） | pass（本机）：Author 台撤销栈上限 100；UndoStackTest 3 条。 |
| 重复导入三选（JVM） | pass（本机）：同 digest 弹窗提供跳过/新建/更新现有草稿；更新复用 DraftLibrary.findByDigest。 |
| Pack 注册表独立于 Pack tree（JVM） | pass（本机）：SQLite 主库 + JSON 镜像均在 library/，不进入 Pack 目录；首次建库迁移 JSON。 |
| Pack 安装注册表元数据（JVM） | pass（本机）：安装写 library/pack-registry.db + JSON 镜像；PackStore 索引含 installed_at；PackCenter 显示安装时间。 |
| UI 中文硬编码守卫（Python） | pass（本机）：扫描 ui/**/*.kt 字符串字面量，仅豁免 CoreCall 无 Context 回退；pytest 498。 |
| 纯函数标签清理（JVM） | pass（本机）：移除仅测试用的 screenLabel 中文映射；UI 中文硬编码仅剩 CoreCall 无 Context 回退。 |
| 全量复核（round104） | pass（本机）：pytest 496；verify 107/2/0；gates PASS/gap=0；rust 186；JVM 319。 |
| CoreCall 异常文案 i18n（JVM） | pass（本机）：安装 applicationContext，异常/修复建议取资源；无 Context 时回退中文。 |
| PackUpdate 标签 i18n（JVM） | pass（本机）：打开更新计划/影响项目/overlay 键改资源。 |
| Settings/存储/新建项目/作者 i18n（JVM） | pass（本机）：核心缺失/未知原因/计算中/Pack 条目数/保存修复后缀改资源。 |
| Delivery 错误文案 i18n（JVM） | pass（本机）：plan/无 markdown/报告解析失败与修复建议改资源。 |
| Protocol 标签/渲染文案 i18n（JVM） | pass（本机）：条款统计/必填可选/渲染中/渲染按钮改资源。 |
| PackCenter 校验文案 i18n（JVM） | pass（本机）：Pack 条目数/校验失败/修复/诊断/重装提示改资源。 |
| TopLevel 项目/校验文案 i18n（JVM） | pass（本机）：项目流程标签/diff 读取/解析失败/未绑定/校验通过失败/诊断/Pack 校验改资源。 |
| Home 控制面/Pack/项目文案 i18n（JVM） | pass（本机）：控制面/导航/Pack 库/项目库/空态/解析失败等改资源。 |
| Graph 标签/提示 i18n（JVM） | pass（本机）：节点边/空值/权重/新节点标题/调用中/校验/保存前缀改资源。 |
| Assembly 标签/提示 i18n（JVM） | pass（本机）：未加载/本地检查/装配中/校验中/分享标题/修复后缀改资源。 |
| Import 剩余文案 i18n（JVM） | pass（本机）：核心缺 result/无建议/文件过大/读取失败/选择文件/示例内容改资源；修复英文 body 测试歧义。 |
| 导航标签资源唯一（JVM） | pass（本机）：8 个 Screen 的 string 资源 ID 两两不同；AdaptiveLayoutTest 5 条。 |
| 通用返回/更多 i18n（JVM） | pass（本机）：TopAppBar 返回与溢出菜单 contentDescription 改资源。 |
| 宽屏导航标签 i18n（JVM） | pass（本机）：AdaptiveNavigationRail 标签改 stringResource；纯函数 screenLabel 保留单测。 |
| 全量复核（round89） | pass（本机）：verify 107/2/0；gates PASS/gap=0；rust 186；JVM 318；pytest 496。 |
| 中英资源一致性测试（Python） | pass（本机）：字符串名称集合/重复名/占位符一致，2 条测试；pytest 496。 |
| 未命名管线 i18n（JVM） | pass（本机）：空白管线默认标题改资源；修复 lambda 作用域后构建通过。 |
| 未命名项目 i18n（JVM） | pass（本机）：新建项目默认标题改资源；修复 Composable lambda 作用域后构建通过。 |
| Lint 0 warnings 复核（round85） | pass（本机）：新增字符串触发 3 条 PluralsCandidate，调整格式后 lint 0 warnings/0 errors。 |
| 分享授权/草稿错误 i18n（JVM） | pass（本机）：授权失效/URI 读取/草稿读取/解析改资源；318 tests。 |
| Import 解析/分享错误 i18n（JVM） | pass（本机）：nf-import 解析/示例读取/分享空载荷改资源；318 tests。 |
| 返回库/演示项目 i18n（JVM） | pass（本机）：空态返回库、演示项目默认标题改资源；318 tests。 |
| 路由错误 i18n（JVM） | pass（本机）：项目包导入 Toast/创建错误后缀/项目与 Pack 缺失空态改资源；318 tests。 |
| Protocol 错误/提示 i18n（JVM） | pass（本机）：解析失败/占位符/缺字段提示改资源；318 tests。 |
| Pack 更新错误 i18n（JVM） | pass（本机）：diff/计划解析/解包失败改资源；318 tests。 |
| Graph 错误/提示 i18n（JVM） | pass（本机）：解析失败/local check/无 plan/摘要改资源；318 tests。 |
| 应用内语言联动系统（构建） | pass（本机）：API33+ 语言切换同步 LocaleManager.applicationLocales；启动时恢复非 SYSTEM 选择；真机未复测。 |
| 系统 per-app 语言入口（构建） | pass（本机）：manifest localeConfig + zh-CN/en 配置；系统语言设置可识别应用语言。真机未复测。 |
| 装配错误 i18n（JVM） | pass（本机）：plan/spec 解析失败与 schema 修复建议改资源；318 tests。 |
| 备份错误 i18n（JVM） | pass（本机）：校验/快照/删除/恢复失败与未知原因改资源；318 tests。 |
| 导出错误 i18n（JVM） | pass（本机）：EPUB/PDF/HTML 导出失败与修复建议改资源；318 tests。 |
| Pack 安装成功提示 i18n（JVM） | pass（本机）：安装完成/核心在场/核心缺失改资源；318 tests。 |
| Pack 安装错误 i18n（JVM） | pass（本机）：缺 manifest/缺 id/重复/移动失败/安装失败改资源；318 tests。 |
| 更多导入错误 i18n（JVM） | pass（本机）：剪贴板空/原始响应缺失/草稿重命名失败改资源；318 tests。 |
| 导入错误文案 i18n（JVM） | pass（本机）：项目包/EPUB/DOCX 导入错误改中英资源；318 tests。 |
| 重新评审刷新 stale（JVM） | pass（本机）：LaunchedEffect 纳入 subject_digest，重新评审后重算失效状态。 |
| 评审结论失效提示（JVM） | pass（本机）：项目详情比较 review.subject_digest 与当前 canonical，不一致显示“建议重新评审”；测试 3 条。 |
| 备份实际内容上限（JVM） | pass（本机）：读取时校验实际单条/总量 256MiB/512MiB，防声明值造假；317 tests 全绿。 |
| PackStore 指纹稳定（JVM） | pass（本机）：目录指纹改为子项名称+mtime，PackStoreTest 连续 3 次 --rerun-tasks 全绿。 |
| 归档恢复 data 回滚（JVM） | pass（本机）：恢复时 data 移动失败会把归档 JSON 移回；归档测试保持全绿。 |
| 复制失败清理（JVM） | pass（本机）：目标 data 目录阻塞移动时删除 staging/目标 JSON；测试 3 条。 |
| 归档回滚故障注入（JVM） | pass（本机）：预置非空 data 目标使移动失败，验证 JSON/data 回滚；归档测试 7 条。 |
| 归档部分移动回滚（JVM） | pass（本机）：JSON 已移动但 data 移动失败时回滚 JSON/data，不再用已删源文件重写；归档测试保持全绿。 |
| 表格内行内格式（JVM） | pass（本机）：表格单元格保留粗体/链接 Markdown；测试 17 条。 |
| 列表内行内格式（JVM） | pass（本机）：先做链接/粗斜/图片转换再解析列表，列表项保留 Markdown；测试 16 条。 |
| HTML 嵌套有序列表（JVM） | pass（本机）：ol 内嵌 ol 缩进编号；测试 15 条。 |
| HTML 嵌套列表（JVM） | pass（本机）：ul/ol 嵌套转缩进 Markdown；测试 14 条。真机未复测（adb 无设备） |
| 无 BOM UTF-16 启发式（JVM） | pass（本机）：按 NUL 奇偶分布识别无 BOM UTF-16LE/BE；测试 3 条。 |
| UTF-16 项目 JSON（JVM） | pass（本机）：UTF-16LE BOM 项目 JSON 可导入；项目包测试 13 条。 |
| 评审错误码补登（JVM） | pass（本机）：错误码扫描扩为全部 NF 字符串，补 NF-REV-001/002；error code 测试 2 条。 |
| 清空导出记录（JVM） | pass（本机）：交付台「清空记录」删除 history.json；测试 3 条。真机未复测（adb 无设备） |
| Lint 复核（round42） | pass（本机）：`:app:lintDebug` 0 warnings。 |
| Rust golden 同步（本轮） | pass（本机）：错误码 NF-IMP-004 fix 文案变更导致 golden 漂移；`golden-gen` 重新生成并复测 `cargo test` 186/186。 |
| Android 测试强制重跑（本轮） | pass（本机）：`:app:testDebugUnitTest --rerun-tasks` 304/304，全任务实际执行。 |
| 错误码 schema LF 守卫（pytest） | pass（本机）：新增字节级 CRLF 断言；error code 测试 2 条。 |
| 错误码 schema EOL 修复（verify） | pass（本机）：error_codes.json CRLF→LF；重新批准 conformance；verify PASS=107 WARN=2 FAIL=0。 |
| 错误码使用登记校验（pytest） | pass（本机）：扫描 Kotlin 内联 `CoreResponse.failure`/`CoreError` 码，发现并补登 NF-IMP-005；新增测试通过。 |
| 错误码目录补齐（JVM） | pass（本机）：新增 NF-IMP-006/007/008、NF-PRJ-001；NF-IMP-004 改为仅 pdf/ocr 未支持；schema negative 85 passed。 |
| EPUB 代码语言 class（JVM） | pass（本机）：EPUB 章节代码块 class=language-…；测试 9 条。真机未复测（adb 无设备） |
| HTML 代码语言 class（JVM） | pass（本机）：```kotlin → code class=language-kotlin；测试 11 条。真机未复测（adb 无设备） |
| 全量复核（round25） | pass（本机）：verify PASS=107 WARN=2 FAIL=0；gates PASS/gap=0；debug APK zipalign 16KB exit=0。 |
| HTML 导出图片（JVM） | pass（本机）：Markdown 图片安全协议转 img，危险协议保留原文；测试 10 条。真机未复测（adb 无设备） |
| DOCX 文档大小上限（JVM） | pass（本机）：document.xml >64MiB 拒绝；301 tests 全绿。真机未复测（adb 无设备） |
| 项目包深层目录（JVM） | pass（本机）：项目 JSON 深度 ≤4 的包可导入；测试 12 条。真机未复测（adb 无设备） |
| DOCX 超链接（JVM） | pass（本机）：r:id + document.xml.rels 转 Markdown 链接；测试 6 条。真机未复测（adb 无设备） |
| DOCX 粗体/斜体（JVM） | pass（本机）：w:b/w:i run 转 **/*；测试 5 条。真机未复测（adb 无设备） |
| DOCX 表格（JVM） | pass（本机）：w:tbl 行/单元格 → Markdown 表格；测试 4 条。真机未复测（adb 无设备） |
| DOCX 列表段落（JVM） | pass（本机）：w:numPr 段落转 `- `；测试 3 条。真机未复测（adb 无设备） |
| DOCX 导入（JVM） | pass（本机）：读 word/document.xml，Heading 样式转标题；测试 2 条。真机未复测（adb 无设备） |
| EPUB 容器识别（JVM） | pass（本机）：zip 内 mimetype/container.xml 可识别 EPUB 并走 EPUB 导入；测试 5 条。真机未复测（adb 无设备） |
| EPUB 标题补全（JVM） | pass（本机）：无标题章节时用 dc:title 作首行标题；测试 4 条。真机未复测（adb 无设备） |
| EPUB 章节总量上限（JVM） | pass（本机）：章节声明总量 >256MiB 拒绝；292 tests 全绿。真机未复测（adb 无设备） |
| EPUB spine 顺序（JVM） | pass（本机）：按 spine itemref 顺序输出章节；测试 3 条。真机未复测（adb 无设备） |
| EPUB 导入（JVM） | pass（本机）：按 container/OPF spine 读取 XHTML，转 Markdown 交 core；测试 2 条。真机未复测（adb 无设备） |
| HTML ol start（JVM） | pass（本机）：`<ol start="3">` 从 3 开始编号；测试 13 条。真机未复测（adb 无设备） |
| HTML 数字实体解码（JVM） | pass（本机）：`&#20320;` / `&#x597d;` → 你好；测试 12 条。真机未复测（adb 无设备） |
| HTML 删除线导入（JVM） | pass（本机）：del/s/strike → ~~；测试 11 条。真机未复测（adb 无设备） |
| HTML 粗体/斜体导入（JVM） | pass（本机）：strong/b → **、em/i → *；测试 10 条。真机未复测（adb 无设备） |
| HTML meta charset 解码（JVM） | pass（本机）：按 `<meta charset>` 解码 GBK 等页面，无 meta 回退 UTF-8；测试 9 条。真机未复测（adb 无设备） |
| 安全构建脚本 E2E（本轮） | pass（本机）：`bash app/scripts/build_android_safe.sh` 一次成功；clean/test/debug/release 全流程；284 tests；debug sha 7ff80fd1…、release sha 4554db7d…。 |
| HTML 水平线导入（JVM） | pass（本机）：hr → Markdown `---`；测试 8 条。真机未复测（adb 无设备） |
| HTML 引用块导入（JVM） | pass（本机）：blockquote → `> ` 引用；测试 7 条。真机未复测（adb 无设备） |
| HTML 代码块导入（JVM） | pass（本机）：pre/code → Markdown 代码块/行内代码；测试 6 条。真机未复测（adb 无设备） |
| HTML 图片导入（JVM） | pass（本机）：img src/alt → Markdown 图片；测试 5 条。真机未复测（adb 无设备） |
| HTML 有序列表导入（JVM） | pass（本机）：ol/li → 1./2. 有序列表；测试 4 条。真机未复测（adb 无设备） |
| HTML 表格/链接导入（JVM） | pass（本机）：table → Markdown 管道表、a href → Markdown 链接；测试 3 条。真机未复测（adb 无设备） |
| HTML 导入（JVM） | pass（本机）：html/htm 去脚本样式后转 Markdown 交 core import；测试 2 条。真机未复测（adb 无设备） |
| 备份单条上限（JVM） | pass（本机）：单条声明 >256MiB 拒绝 inspect；备份测试 9 条。真机未复测（adb 无设备） |
| 备份声明总量上限（JVM） | pass（本机）：manifest 声明总量 >512MiB 直接拒绝 inspect；备份测试 8 条。真机未复测（adb 无设备） |
| 备份 manifest BOM 兼容（JVM） | pass（本机）：带 UTF-8 BOM 的备份 manifest 可正常校验；备份测试 7 条。真机未复测（adb 无设备） |
| 项目 JSON BOM 兼容（JVM） | pass（本机）：项目包 JSON/manifest 带 BOM 仍能解析；导入测试 11 条。真机未复测（adb 无设备） |
| UTF-16/BOM 文本导入（JVM） | pass（本机）：txt/md 带 UTF-16LE/BE 或 UTF-8 BOM 时先转 UTF-8 临时文件再交给 core；测试 2 条。真机未复测（adb 无设备） |
| 备份 manifest 字段必填（JVM） | pass（本机）：缺 path/bytes/sha256 或非法值拒绝 inspect；备份测试 6 条。真机未复测（adb 无设备） |
| 项目包负例测试（JVM） | pass（本机）：缺项目 JSON、项目缺 id 均拒绝导入；导入测试 10 条。真机未复测（adb 无设备） |
| 分享导入临时文件清理（JVM） | pass（本机）：分享/SAF 项目包导入完成后删除 cache 临时 zip；267 tests 全绿。真机未复测（adb 无设备） |
| 项目包临时文件清理（JVM） | pass（本机）：命令面板导入完成后删除 cache/imports 临时 zip；267 tests 全绿。真机未复测（adb 无设备） |
| APP 门禁（round153） | pass（本机）：QA0–QA6 全 PASS，FAIL=0；covered=14 gap=0 open=2 p0=0；台账刷新到当前 HEAD。 |
| Lint 0 warnings（JVM） | pass（本机）：lint.xml 仅忽略 Paparazzi alpha05 的 GradleDependency 消息（Kotlin 2.1 读不了 stdlib 2.3）；warnings 1→0。 |
| 仓库门禁（本轮） | pass（本机）：`LANG=C.UTF-8 PYTHONUTF8=1 bash verify.sh --checks-only` → PASS=107 WARN=2 FAIL=0；conformance 27/27 conformant root d1e126…；协议回执 408f01e5…。 |
| Python app 测试（本轮） | pass（本机）：`python -m pytest app/tests -q` → **492 passed** / 1 warning / 0 failed（147s）；warning 为安全负例故意构造重复 zip 条目。 |
| 项目包未列出条目拒绝（JVM） | pass（本机）：zip 增加 manifest 未列数据文件时导入失败；测试 8 条。真机未复测（adb 无设备） |
| 交付导出防重入（JVM） | pass（本机）：导出/分享按钮在 busy 时禁用，避免并发覆盖；265 tests 全绿。真机未复测（adb 无设备） |
| 备份排除临时文件（JVM） | pass（本机）：备份 zip 排除 `.bak`/`.tmp`；测试仍 2 条（含 .bak 断言）。真机未复测（adb 无设备） |
| 分享包排除临时文件（JVM） | pass（本机）：data 下 `.bak`/`.tmp` 不进入分享包；测试 2 条。真机未复测（adb 无设备） |
| manifest 版本/项目名校验（JVM） | pass（本机）：拒绝未知 schema 或项目文件名不一致；旧包无 manifest 仍兼容。真机未复测（adb 无设备） |
| 项目包篡改拒绝（JVM） | pass（本机）：改写 data 内容但保留 manifest 后导入失败；导入测试 7 条。真机未复测（adb 无设备） |
| 项目包 manifest 校验（JVM） | pass（本机）：导出 manifest.json（project/data sha256），导入时校验项目与各数据条目；无 manifest 的旧包兼容。测试 2 条。真机未复测（adb 无设备） |
| Lint ObsoleteSdkInt 收口（JVM） | pass（本机）：新增 lint.xml 按路径忽略 mipmap-anydpi-v26（minSdk=26 下冗余但保留给 launcher 工具）；lint warnings 2→1，仅剩 Paparazzi 版本（被 Kotlin 2.1 阻塞）。 |
| 删除线（JVM） | pass（本机）：HTML/EPUB `~~旧~~` 渲染 del；各 1 条测试。真机未复测（adb 无设备） |
| 有序列表（JVM） | pass（本机）：HTML/EPUB `1.` 行渲染 ol/li 并正确闭合；各 1 条测试。真机未复测（adb 无设备） |
| 引用块（JVM） | pass（本机）：HTML/EPUB `> ` 行渲染 blockquote/p；各 1 条测试。真机未复测（adb 无设备） |
| 水平线（JVM） | pass（本机）：HTML/EPUB 的 `---` 渲染 `<hr/>`；各 1 条测试。真机未复测（adb 无设备） |
| HTML 行内代码（JVM） | pass（本机）：反引号行内代码渲染 `<code>`；测试 5 条。真机未复测（adb 无设备） |
| 安全链接（JVM） | pass（本机）：HTML/EPUB inline 仅 http/https/mailto/# 转 a 标签，javascript: 保持原文；测试各 1 条。真机未复测（adb 无设备） |
| EPUB 表格（JVM） | pass（本机）：EPUB 章节同步管道表格 table/thead/tbody；测试 3 条。真机未复测（adb 无设备） |
| HTML 表格/行内格式（JVM） | pass（本机）：管道表格渲染为 table/thead/tbody；修正 inline 正则，普通文本不再被误包 strong/em；测试 3 条。真机未复测（adb 无设备） |
| 嵌套项目包导入（JVM） | pass（本机）：支持 bundle/ 顶层目录内的项目 JSON + bundle/data/；测试 6 条。真机未复测（adb 无设备） |
| 恢复后刷新库（JVM） | pass（本机）：备份恢复成功后回调 NfMobileApp.refresh，库/项目状态立即更新；真机未复测（adb 无设备） |
| 崩溃日志分享（JVM） | pass（本机）：设置崩溃卡可把 last-crash 写入 cache/shared 并分享 text/plain；真机未复测（adb 无设备） |
| 草稿映射决策恢复（JVM） | pass（本机）：打开已保存草稿时读取 .mapping.json accepted 集合，缺失/坏 JSON 回退置信度规则；测试 5 条。真机未复测（adb 无设备） |
| RTL 外壳（JVM） | pass（本机）：RTL LayoutDirection 下库/我的目的地仍可见；测试 1 条。真机未复测（adb 无设备） |
| 快捷方式图标（构建） | pass（构建）：静态导入/新建/搜索改用三套独立 vector 图标；未真机长按验证（adb 无设备） |
| 最近项目动态快捷方式（JVM） | pass（本机）：refresh 发布最多 3 个最近项目快捷方式；MainActivity 解析 OPEN_PROJECT 并直达项目；ShortcutManager 失败静默。真机未复测（adb 无设备） |
| 分享导入缺 Pack 提示（JVM） | pass（本机）：分享/选文件导入项目包也返回 base_pack，缺 Pack 时弹同一对话框；真机未复测（adb 无设备） |
| 项目包条目预检（JVM） | pass（本机）：读 entry 前检查声明大小与总量上限，避免压缩炸弹先读入内存；测试 5 条仍绿。真机未复测（adb 无设备） |
| HTML 结构自检（JVM） | pass（本机）：导出后检查 doctype/html/head/body/title/charset；失败显示原因；测试 2 条。真机未复测（adb 无设备） |
| HTML 导出（JVM） | pass（本机）：交付台「导出 html」生成单文件 result.html（基础 Markdown、内联 CSS、转义）；测试 2 条。真机未复测（adb 无设备） |
| 关于页 i18n（JVM） | pass（本机）：About 正文改用资源（版本/versionCode 参数），中英可切换；244 tests 全绿。真机未复测（adb 无设备） |
| 永久删除项目（JVM） | pass（本机）：项目详情强确认后删除 JSON+projects/<id>/ 数据；提示建议先归档/分享；测试 6 条。真机未复测（adb 无设备） |
| Paparazzi 升级尝试（JVM） | blocked（本机）：alpha05 拉入 kotlin-stdlib 2.3.0，当前 Kotlin 编译器 2.1.0 无法读取元数据；回退 alpha02，构建/243 tests 恢复全绿。 |
| 依赖升级 coroutines（JVM） | pass（本机）：coroutines 1.9.0→1.10.2，243 tests 全绿；lint warnings 3→2；debug APK 因未压缩 dex 增至 24.7MB。真机未复测（adb 无设备） |
| Clean build（本轮） | pass（本机）：`gradlew clean` + `testDebugUnitTest --rerun-tasks` + assembleDebug；248/248 全绿；clean APK 19,032,264 B sha256 f4501bfe…；zipalign 16KB 通过。增量 APK 24.7MB 为旧构建膨胀，clean 产物为准。 |
| Rust core 单测（本轮） | pass（本机）：`cargo test` 186 passed / 0 failed；Android 端无 core 改动。 |
| Release 构建（构建） | pass（本机）：clean 后重建 `:app:assembleRelease` 成功；app-release-unsigned.apk 15,529,949 B sha256 160699b4…；zipalign 16KB 通过；apksigner 显示未签名（预期，签名 OPEN-EXTERNAL）。 |
| 16KB 页对齐（构建） | pass（本机）：`zipalign -c -P 16 4 app-debug.apk` exit=0；未真机安装验证。 |
| APP 门禁（round127） | pass（本机）：QA0–QA6 全 PASS，FAIL=0；covered=14 gap=0 open=2 p0=0；台账刷新到当前 HEAD。 |
| APP 门禁（本轮） | pass（本机）：QA0–QA6 全部 PASS，FAIL=0；自审计 covered=14 gap=0 open=2 p0=0。 |
| 备份导出后自检（JVM） | pass（本机）：导出后立即 inspect zip，显示“导出校验通过/失败原因”；真机未复测（adb 无设备） |
| 分享/文件选择导入项目包（JVM） | pass（本机）：导入流程检测 zip 内根项目 JSON，直接走 ProjectPackageImporter 并打开项目；测试识别用例。真机未复测（adb 无设备） |
| 项目包导出→导入往返（JVM） | pass（本机）：ProjectPackage 导出 zip 后 ProjectPackageImporter 导入新根，项目 JSON/assembly 内容一致；真机未复测（adb 无设备） |
| 项目包导入原子化（JVM） | pass（本机）：data 先写 staging，再移动，最后原子写项目 JSON；失败清理 staging/data/JSON；测试 3 条。真机未复测（adb 无设备） |
| 缺 Pack 跳转 Pack 中心（JVM） | pass（本机）：Toast 改对话框，可直接跳 Pack 中心；真机未复测（adb 无设备） |
| 导入缺 Pack 提示（JVM） | pass（本机）：导入返回 base_pack 引用；缺 Pack 时 Toast 提示但仍打开项目；真机未复测（adb 无设备） |
| 完整项目包导入（JVM） | pass（本机）：命令面板「导入项目包」选 zip，校验路径/总量，JSON 冲突自动 -import 改名，data/ 还原；测试 3 条。真机未复测（adb 无设备） |
| 分享完整项目包（JVM） | pass（本机）：项目详情「分享完整项目」生成 zip（JSON+data/），含 authoring/assembly；测试 2 条。真机未复测（adb 无设备） |
| 分享项目文件（JVM） | pass（本机）：项目详情「分享项目文件」写 cache/shared 后走 Sharesheet；只分享 JSON，不含项目数据目录/assembly。真机未复测（adb 无设备） |
| 项目数据目录随复制/归档（JVM） | pass（本机）：duplicate 复制 projects/<id>/ 数据；archive/restore 移动 .data 目录；删除归档清理数据；测试断言 assembly 副本往返。真机未复测（adb 无设备） |
| PDF 文案对齐（JVM） | pass（本机）：删除“PDF 未接/平台打印 OPEN”过期文案，改为本地基础文本导出；复杂排版仍 OPEN。真机未复测（adb 无设备） |
| 窗口宽度 API 迁移（JVM） | pass（本机）：screenWidthDp 改 LocalWindowInfo.containerSize + LocalDensity；三档导航/矩阵测试仍绿；lint warnings 7→4。真机未复测（adb 无设备） |
| 剩余复数资源清零（JVM） | pass（本机）：剩余 11 条英文复数改 plurals；lint warnings 18→7（仅剩 Compose 宽度/Gradle/ObsoleteSdk/UnusedAttribute）；真机未复测（adb 无设备） |
| 英文复数资源（JVM） | pass（本机）：library_errors/search_hint/settings_err_count/storage_cleaned/backup_pruned 改 plurals + pluralStringResource/getQuantityString；lint warnings 23→18。真机未复测（adb 无设备） |
| 分享授权失效指引（JVM） | pass（本机）：SecurityException 映射 NF-IMP-006，提示重新分享/改用文件选择；真机未复测（adb 无设备） |
| 恢复队列可导入当前项（JVM） | pass（本机）：恢复的单条/多条队列在预览为空时显示「导入当前项」，不会卡死；真机未复测（adb 无设备） |
| 分享队列持久化（JVM） | pass（本机）：多条目分享队列/游标存 share-queue.json，进程死亡后恢复；忽略/清空时删除；测试 2 条。真机未复测（adb 无设备） |
| 草稿转项目（JVM） | pass（本机）：草稿行选 Pack 后创建项目，并把草稿副本写入项目 authoring/import-*.json 作为来源；项目壳+来源副本，未把导入内容写入协议字段（partial）。测试 2 条。真机未复测（adb 无设备） |
| 恢复中禁止 dismiss（JVM） | pass（本机）：restoring 期间点击对话框外部不关闭；真机未复测（adb 无设备） |
| 恢复中进度/防重复（JVM） | pass（本机）：恢复确认后按钮/取消禁用并显示进度条，完成/失败复位；真机未复测（adb 无设备） |
| 评审摘要/前置校验（JVM） | pass（本机）：项目卡显示 review 状态+评审人；未 validated/exported/reviewed 时禁用通过并提示；真机未复测（adb 无设备） |
| Lint KTX 收尾（JVM） | pass（本机）：Uri.parse 改 androidx.core.net.toUri；warnings 24→23；lint/232 tests 通过。真机未复测（adb 无设备） |
| Lint 未使用资源清理（JVM） | pass（本机）：删除 14 个确认未使用字符串（中英各一份），warnings 39→24；lint/232 tests 通过。真机未复测（adb 无设备） |
| Lint 告警清理（JVM） | pass（本机）：补 fullBackupContent=false、SharedPreferences 改 KTX edit；warnings 45→39；lint 通过。真机未复测（adb 无设备） |
| 语言拆包配置（JVM） | pass（构建）：AAB bundle.language.enableSplit=false，避免运行期切 locale 缺资源；lint 通过。真机未复测（adb 无设备） |
| 归档项目删除（JVM） | pass（本机）：库页归档行可永久删除，二次确认，仅允许 projects-archive 内；测试 5 条。真机未复测（adb 无设备） |
| 最近导入重新打开（JVM） | pass（本机）：最近导入按 digest 找匹配草稿并可重新打开；草稿已删时提示；真机未复测（adb 无设备） |
| 禁止云备份/迁移（JVM） | pass（构建）：data_extraction_rules 对 cloud-backup/device-transfer 全排除；allowBackup=false；lint 通过。真机未复测（adb 无设备） |
| Android lint（JVM） | pass（本机）：:app:lintDebug 通过；修复 backup_deleted 格式参数错误与 DefaultLocale 告警；剩余 46 warnings 登记未清零。真机未复测（adb 无设备） |
| 本地项目评审（JVM） | pass（本机）：项目详情评审对话框（评审人/意见）通过写 approved+reviewed+history，驳回保留状态；project-validate 失败不写盘；测试 2 条。真机未复测（adb 无设备） |
| 偏好恢复后重启（JVM） | pass（本机）：恢复偏好后 Toast 提示并 recreate Activity，使主题/语言立即生效；真机未复测（adb 无设备） |
| 偏好备份（JVM） | pass（本机）：备份前写 app-prefs.json（主题/语言/动态色/引导/示例标记），恢复后回填 AppPrefs；主题需重启生效；测试 2 条。真机未复测（adb 无设备） |
| 对比候选修改时间（JVM） | pass（本机）：对比列表显示最近修改时间；README 测试清单修正；真机未复测（adb 无设备） |
| 偏好元数据备份（JVM） | pass（本机）：备份包含 pack-trust/search-history/search-filter/command-history/library-view；恢复白名单允许这些根文件；测试 4 条。真机未复测（adb 无设备） |
| 库页过滤/排序持久化（JVM） | pass（本机）：状态过滤与排序存 library-view.json，重进恢复；Paparazzi 无 filesDir 时安全降级；测试 2 条。真机未复测（adb 无设备） |
| 项目列表排序（JVM） | pass（本机）：库页新增排序 chips（最近修改/标题/状态），与状态过滤组合；测试 1 条。真机未复测（adb 无设备） |
| 对比状态/标题长度（JVM） | pass（本机）：对比候选显示项目状态；重命名限 120 字；测试 3 条。真机未复测（adb 无设备） |
| 备份包含归档项目（JVM） | pass（本机）：BackupService 纳入 projects-archive，恢复允许该前缀；测试归档内容往返。真机未复测（adb 无设备） |
| 打开导出文件（JVM） | pass（本机）：最近导出行新增「打开」，ACTION_VIEW + FileProvider 只读 URI；无匹配应用时 chooser 提示；真机未复测（adb 无设备） |
| 最近导入记录（JVM） | pass（本机）：导入页显示最近 5 条导入（名称/digest），可清空；用于重复导入提示；测试 3 条。真机未复测（adb 无设备） |
| 草稿重命名（JVM） | pass（本机）：草稿行重命名并同步 mapping sidecar；冲突/同名拒绝；真机未复测（adb 无设备） |
| 草稿删除（JVM） | pass（本机）：导入页草稿行可删除，二次确认，同时删除 mapping sidecar；测试 4 条。真机未复测（adb 无设备） |
| 已保存草稿列表（JVM） | pass（本机）：导入页列出最多 5 个已保存草稿，可重新打开预览；排除 mapping/import-last/import-history；测试 2 条。真机未复测（adb 无设备） |
| 项目重命名（JVM） | pass（本机）：项目详情重命名对话框，只改 title，保留 refs/status/review/history；空标题拒绝；测试 2 条。真机未复测（adb 无设备） |
| 库内对比搜索（JVM） | pass（本机）：对比选择对话框支持按项目标题/ID 搜索；真机未复测（adb 无设备） |
| 备份管理对话框（JVM） | pass（本机）：设置「全部备份」列出所有备份，可恢复或经确认删除；删除后刷新统计；真机未复测（adb 无设备） |
| 备份列表恢复（JVM） | pass（本机）：设置存储卡列出最近 3 个备份（名称/大小），可一键校验并走确认恢复；真机未复测（adb 无设备） |
| 备份清理（JVM） | pass（本机）：设置→清理旧备份保留最近 5 个，删除更早 zip；快照指针失效自动忽略；测试 3 条。真机未复测（adb 无设备） |
| 存储面板补齐 Pack/归档（JVM） | pass（本机）：StorageStats 增加 library/packs 与 projects-archive，合计覆盖全部本地数据；测试补断言。真机未复测（adb 无设备） |
| 搜索过滤持久化（JVM） | pass（本机）：kind/pack 过滤存 search-filter.json，重进恢复；已卸载 Pack 的过期 pack 过滤自动忽略；测试 2 条。真机未复测（adb 无设备） |
| 库内项目对比（JVM） | pass（本机）：项目详情「与库内项目对比」列出其它项目，直接读取 JSON 生成差异；无需文件选择器；真机未复测（adb 无设备） |
| 搜索 Pack 过滤（JVM） | pass（本机）：搜索页新增 Pack 过滤 chips，与 kind 过滤组合；测试 SearchFilter.apply 包维度。真机未复测（adb 无设备） |
| 项目对比（JVM） | pass（本机）：项目详情「对比项目」选另一项目 JSON，比较状态/refs/评审/历史；相同提示一致；测试 2 条。真机未复测（adb 无设备） |
| Pack zip 加密检测（JVM） | pass（本机）：解析 EOCD/central directory 通用位标记，含加密条目直接拒绝；测试手工构造加密 flag zip。真机未复测（adb 无设备） |
| Pack zip 压缩比预检（JVM） | pass（本机）：解包前读 central directory，拒绝声明总量/条目数超限与压缩比 >1000 的条目；测试造 20 MiB 零字节炸弹。真机未复测（adb 无设备） |
| 导出失败原因展示（JVM） | pass（本机）：最近导出失败时在记录下方显示 message；成功不显示；真机未复测（adb 无设备） |
| 导出记录校验状态（JVM） | pass（本机）：最近导出记录保存 ok/message，列表显示通过/失败；旧记录缺字段按 null 处理；测试覆盖状态持久化。真机未复测（adb 无设备） |
| 崩溃日志查看/清除（JVM） | pass（本机）：Settings 显示最近崩溃前 2000 字并可清除；处理器改为进程内只安装一次、保留原 handler/兜底终止；真机崩溃未复测（adb 无设备） |
| 崩溃日志（JVM） | pass（本机）：MainActivity 安装未捕获异常处理器写 crash/last-crash.txt，最多 64 KiB；诊断包含 crash.txt；测试 2 条。真机崩溃未复测（adb 无设备） |
| 诊断包导出（JVM） | pass（本机）：Settings 导出 zip（diagnostics.txt + README），无网络/账号/正文；Sharesheet 分享；测试 2 条。真机未复测（adb 无设备） |
| Pack 中心 trust 告警（JVM） | pass（本机）：Pack 中心列表读取本地固定 tree，发现不一致时红色提示；真机未复测（adb 无设备） |
| Pack 固定 tree 变化告警（JVM） | pass（本机）：已固定 pack 的 tree 与当前不一致时显示红色告警，可「更新固定」；测试 pinnedTree 读取。真机未复测（adb 无设备） |
| Pack 本地信任固定（JVM） | pass（本机）：Pack 详情可固定/取消固定当前 tree，按 pack@version 存 pack-trust.json；明确标注“非签名”；测试 2 条。真机未复测（adb 无设备） |
| PDF 结构自检（JVM） | pass（本机）：导出后检查 %PDF- 头、%%EOF/startxref、/Encrypt、页对象；失败显示原因；测试 3 条。真机未复测（adb 无设备） |
| PDF 导出（JVM） | pass（仅分页逻辑单测）：交付台「导出 pdf」用 Android PdfDocument 生成 A4 文本 PDF、自动折行/分页；PdfPager 2 条测试；PdfDocument 渲染未真机/仪器验证。真机未复测（adb 无设备） |
| Pack zip 解包硬化（JVM） | pass（本机）：拒绝空/控制字符条目名、重复条目、绝对路径/..、条目数/总量超限；测试补控制字符用例。真机未复测（adb 无设备） |
| 多条目分享队列（JVM） | pass（本机）：SEND_MULTIPLE 接收后保留全部条目，显示「共 N 项/当前第 X 项」，可逐项导入或忽略其余；不再只取第一项并静默丢弃。真机未复测（adb 无设备） |
| EPUB 结构自检（JVM） | pass（本机）：导出后校验 mimetype 首个/STORED、container/OPF 引用/spine/nav、XHTML 可解析、路径约束；失败显示原因；测试 3 条。真机未复测（adb 无设备） |
| EPUB 导出（JVM） | pass（本机）：交付台「导出 epub」用 EpubExporter 生成 EPUB3（mimetype STORED、container/OPF/nav/chapter），基础 Markdown→XHTML，HTML 转义；测试 2 条覆盖结构与无标题；未接 EPUBCheck。真机未复测（adb 无设备） |
| 归档列表/恢复（JVM） | pass（本机）：库页显示 projects-archive/ 归档列表，点「恢复」校验项目 JSON 后移回 projects/；坏归档拒绝；测试 4 条。真机未复测（adb 无设备） |
| 项目归档（JVM） | pass（本机）：项目详情「归档项目」确认后移动到 projects-archive/，不删除；清单刷新回库；越界文件拒绝。真机未复测（adb 无设备） |
| 项目复制（JVM） | pass（本机）：项目详情「复制项目」保留 refs，ID 生成 -copy/-copy-2，状态重置 draft、评审 pending、history 清空；测试 2 条。真机未复测（adb 无设备） |
| 项目历史分享（JVM） | pass（本机）：项目详情历史卡新增「分享历史」，生成 Markdown 表格（op/digest/at），标题/单元格转义；空历史可导出。真机未复测（adb 无设备） |
| JSON/Skill 导出（JVM） | pass（本机）：交付台新增「导出 json」「导出 skill」；json 产 result.json，skill 产 result.skill.zip；纳入校验与最近导出/重新分享；真机未复测（adb 无设备） |
| 一键回滚上次恢复（JVM） | pass（本机）：restore 写 last-restore-snapshot.txt 指针；Settings 显示「回滚上次恢复」，校验快照后走确认恢复；测试验证旧文件恢复。真机未复测（adb 无设备） |
| 恢复前自动快照（JVM） | pass（本机）：每次 restore 先 BackupService.create 生成 pre-restore 快照，再写 projects/drafts；UI 显示快照文件名；测试断言快照存在。真机未复测（adb 无设备） |
| 本地备份恢复（JVM） | pass（本机）：Settings 选 zip → inspect 校验（路径/重复/bytes/sha256）→ 确认对话框 → 恢复 projects/drafts；路径穿越/坏摘要拒绝；不可撤销提示。真机未复测（adb 无设备） |
| 本地备份导出（JVM） | pass（本机）：设置→导出本地备份，zip 含 manifest.json + projects/ + drafts/；manifest 记 sha256/bytes；空备份也有 manifest；通过 Sharesheet 导出。恢复/导入备份未实现。真机未复测（adb 无设备） |
| 项目状态历史（JVM） | pass（本机）：ProjectModel 解析 history 的 op/digest/at；项目详情展示最近 20 条；解析断言加入模型测试。真机未复测（adb 无设备） |
| 存储面板/缓存清理（JVM） | pass（本机）：设置页显示 projects/drafts/exports/cache/total；只清理 cache/imports 与 cache/shared，保留其他缓存；测试覆盖占用与清理。真机未复测（adb 无设备） |
| 命令最近使用排序（JVM） | pass（本机）：命令执行记录最近 5 个 id；命令面板最近使用前置；测试 5 条。真机未复测（adb 无设备） |
| Ctrl/Cmd+K 命令快捷键（JVM） | pass（本机）：MainActivity 捕获 Ctrl/Cmd+K → CommandBus → 打开命令面板；真机键盘未复测（adb 无设备） |
| 导出产物校验（JVM） | pass（本机）：导出后校验文件存在、manifest bytes/sha256 一致；交付页显示通过/失败原因；测试覆盖缺文件/错字节/错摘要。真机未复测（adb 无设备） |
| 命令面板（JVM） | pass（本机）：库页顶栏「命令」打开对话框；搜索导入/新建/搜索/Pack 中心/更新/CCOS/设置/错误码；空结果提示；命令过滤纯逻辑测试。真机未复测（adb 无设备） |
| 最近导出记录（JVM） | pass（本机）：导出 md/zip/docx 后记录 format/name/path/sha256/时间，最多 20 条；交付页显示最近 5 条并可重新分享；真机未复测（adb 无设备） |
| 协议未保存草稿恢复（JVM） | pass（本机）：协议字段 values/enabled 编辑 500ms 防抖存 drafts/author-protocol-<id>.json；重进提示「已恢复上次未保存的协议编辑」；保存成功清理。真机未复测（adb 无设备） |
| 项目状态过滤（JVM） | pass（本机）：库页状态 FilterChip（全部/草稿/创作中/已装配/已校验/已导出/已审阅），空状态提示；过滤状态 rememberSaveable。真机未复测（adb 无设备） |
| 错误码浏览器（JVM） | pass（本机）：设置→错误码屏；58 个错误码可按 code/message/fix 过滤，点击复制 code；路由纳入 ShellStateCodec。真机未复测（adb 无设备） |
| Author tab 恢复（JVM） | pass（本机）：AuthorScreen 三 tab 选择经 rememberSaveable 跨进程恢复；未做真机杀进程复测（adb 无设备） |
| Pack 索引缓存（JVM） | pass（本机）：library/pack-index.json 缓存 packs/errors；目录 mtime 变更重建；损坏索引回退扫描；SampleSeeder 安装后 invalidate。真机未复测（adb 无设备） |
| 搜索 kind 过滤（JVM） | pass（本机）：FilterChip 全部/项目/Pack/条款/字段/节点/章节/槽位；过滤后空态与键盘选择使用过滤结果；真机未复测（adb 无设备） |
| 导入预览恢复（JVM） | pass（本机）：最近一次 nf-import JSON 落 drafts/import-last.json；重进 Import 自动恢复预览并提示；重新导入时清理；损坏文件忽略。真机未复测（adb 无设备） |
| 搜索历史（JVM） | pass（本机）：最近搜索最多 10 条、去重、最近优先；空查询显示 chips，可点击复用/清空；真机未复测（adb 无设备） |
| Pack 原子安装（JVM） | pass（本机）：staging 全量 fsync → 旧版本 .old 备份 → rename → fsync 父目录；失败回滚；SampleSeeder 已接入。真机未复测（adb 无设备） |
| 导入幂等提示（JVM） | pass（本机）：导入历史按 digest 记录最近 100 条；同内容再次导入显示「同一内容此前已导入：name（digest）」；不阻断用户。真机未复测（adb 无设备） |
| 进程死亡路由恢复（JVM） | pass（本机）：ShellState 经 rememberSaveable + Codec 持久化四目的地/详情（项目/作者/交付/Pack id+version）；非法/缺失回退根；未做真机杀进程复测（adb 无设备） |
| 搜索键盘导航（JVM） | pass（本机）：搜索框自动聚焦，↑↓ 移动高亮，Enter 打开，Esc 清空；`SearchKeyboardTest` 覆盖边界；真机键盘未复测（adb 无设备） |
| 导入/原子写/槽位草稿（JVM/core） | pass（本机）：EPUB/OOXML 不再误判、UTF-16LE/BE+BOM 可导入、64 MiB 预检/缓存上限、草稿同名自动后缀、SEND_MULTIPLE 非首项显式提示、JSON 状态原子写+fsync+.bak；新增交付槽位草稿防抖保存/重进恢复。Rust ops_import 21/21、Android 143/143；真机未复测（adb 无设备） |
| 批量槽位导入 | pass：slot-batch.md（4 段）→ 弹窗 4 段/4 槽位预览；仅填空槽填入 4；再次仅填空槽跳过 4（已有内容不覆盖）；slot-batch-overflow.md（5 段）显示「超出 1 段」提示 |
| 槽位文本导入/适配 | pass：槽位「导入」选 slot-import.md（含 YAML/标题/粗斜体/链接/列表）→ 弹窗显示「markdown · 87 → 31 字」适配预览；替换后槽位字数 31，内容已去 frontmatter/井号/强调/链接目标 |
| 交付折叠/长文预览 | pass：长槽位输入 193 字（分 3 次输入）→ 输入框保持 maxLines=6 高度、计数实时到「已输入 193 字」；装配后预览默认 12 行，展开后限高滚动；槽位分组可收起/展开（真机点击标题折叠后 SLT-01..04 消失，再展开恢复）；槽位输入 minLines=2/maxLines=6 + 已输入字数；预览全文不再 take(4000)，默认 12 行折叠，展开后限高滚动 |
| Pack diff/apply/rollback | pass：NFTest/demo-pack-1.0.1.zip → diff（1.0.0→1.0.1，modified 1，无冲突）→ 应用（applied/nf-pack.json=1.0.1）→ 回滚（applied-rollback/nf-pack.json=1.0.0） |
| 文件导入（SAF） | pass：自建 /sdcard/NFTest 目录选 nf-file-import.md → markdown 85%、结构 2 标题/2 段落、4 条映射；全部采纳后保存 drafts/nf-file-import.md.json + mapping.json |
| 导入示例 | pass（修复后）：markdown 85%，8 条映射，全部采纳后保存 files/drafts/sample.md.json + .mapping.json | 截图 29–31 |
| 项目状态历史 | pass：overlay:save → status:authoring->assembled → status:assembled->validated → export → status:validated->exported | run-as 读项目 |

## 2. 追加实测（2026-11-15 晚）

| 项目 | 结果 |
|---|---|
| 顶部大空隙 | **已修复**：Scaffold 默认 insets + Row statusBarsPadding + TopAppBar 三重叠加；改为 contentWindowInsets=0、TopAppBar 负责状态栏 |
| 搜索 | pass：索引 20 条；搜 demo 命中项目 1 + Pack 1 |
| 设置/诊断 | pass：backend=jna-native、ABI=nf-app-core/1、原生库已加载、错误码 58 条 |
| Pack 中心 | pass：已装 1，逐 Pack 校验返回 校验通过 · verdict=pass |
| 我的/深色 | pass：深色主题整体生效 |
| 我的/English | pass（修复后）：Appearance 下 System/Light/Dark、Language 选项均为英文 |
| 动态取色 | pass：Android 12+ 开关生效 |
| 分享 chooser（出站） | pass（修复后）：非 Activity Context 调用 chooser 缺 `FLAG_ACTIVITY_NEW_TASK` 导致 `AndroidRuntimeException`；修复后真机拉起系统分享面板，显示 nf-demo-project.md 59B 与目标应用，进程存活 |
| 分享接收 | **已修复**：此前确认分享会崩（No ActivityResultRegistryOwner），且 payload 未传入导入；修复后显示「已接收分享载荷」+ markdown 85% 预览 |
| 新建项目 | pass：Create→从 Pack 新建→标题 device-test→创建，生成 devicetest.nfproject.json |
| 横屏 | pass：旋转后自动切 NavigationRail（四目的地竖排） |
| 200% 字号 | pass：font_scale=2.0 重启后库页不崩、主 CTA 仍可见 |
| 冷启动/内存 | 407/409/411ms；PSS 107,589 KB（3 次 force-stop 后） |
| 分享接收 | 修复后进入 Import：显示「已接收分享载荷」+ markdown 85% 预览 |
| TalkBack 服务 | partial：TalkBack 服务可绑定、APP 启动不崩、搜索/设置等节点有 contentDescription；未做语音手势走查（ADB 无法模拟 TalkBack 手势），已关闭服务 |
| CCOS 交接 | 修复中：task/result 加载通过；提交区已移到固定底栏并加 navigationBarsPadding（原按钮落在手势导航区，点击被系统拦截）；CcosReviewActionsTest 通过，设备复测待补 |
| docx 导出 | **已修复**：根因是 jniLibs .so 还是 15:35 旧构建（core 源码 16:30 才实现 docx）；重跑 build_core_android.sh 后导出 result.docx（2754B，OOXML 条目完整，zip 校验通过） |

## 3. 真机发现并已修复

1. assembled 状态缺 refs.assembly：project-validate 拒绝；修为进入 assembled 时写 authoring/assembly.md 并补 assembly 引用（path/sha256/digest）。
2. exported 状态缺 history op=export：project-validate 拒绝；修为进入 exported 时追加 export history。
3. 示例导入 source.kind=sample 不在 schema enum：core 返回 NF-IMP-001；修为使用 file。
4. 创作台/交付页旧提示文案（保存/撤销后续接入、状态写回仍 OPEN）已改为当前行为。

## 4. 真机仍 OPEN / 未跑

- 撤销复测通过：F-002 由「冷静x」点撤销回到「冷静」；此前失败是键盘未收起时点到了键盘。
- English 主题标签已资源化（System/Light/Dark）。
- 新增盲区修复：jniLibs .so 陈旧导致 docx 被误报 NF-EXP-004；重跑 build_core_android.sh 后恢复。
- CCOS：2026-11-17 真机恢复 task/result 并通过导入前预检；人审提交未完成，仍标待复测。
- WebView PDF：2026-11-17 已在真机通过（见第 6 节）。
- 杀进程恢复：2026-11-17 已用 run-as kill -9 + 最近任务重开验证路由/槽位草稿（见第 6 节）。
- 分享 chooser 已真机通过（NEW_TASK 修复）。
- 未跑：折叠屏（本机非折叠）、TalkBack 语音走查、对比度实测。
- 本机无第二台设备/折叠屏，设备矩阵仍不完整。

## 6. 2026-11-17 真机复核（OnePlus PLF110 / Android 16）

| 项目 | 结果 | 证据 |
|---|---|---|
| 安装/冷启动 | pass：adb install -r 成功；冷启动 LaunchState=COLD，TotalTime=525ms，WaitTime=530ms；logcat 无 FATAL EXCEPTION | device_smoke.sh |
| WebView PDF | pass：交付台导出 result.pdf 31,067 B；界面显示“PDF 结构校验通过（1 页）”“复现检查：两次导出一致”；经 FileProvider 分享到 Edge，页面可见“演示项目 / 开篇 / 正文 / 收束” | result.pdf、pdf-share-edge2.png |
| 杀进程路由/槽位恢复 | pass：Home 后 run-as kill -9；最近任务重开；交付台路由保留，SLT-01 显示“已恢复上次槽位草稿”且内容恢复 | form-restored.png |
| TalkBack 服务 | partial/pass（服务层）：开启 TalkBack 后服务已 Bound，APP 前台运行、无 FATAL；未做语音手势逐项走查 | talkback-back.png |
| SQLite 注册表 | pass：预置旧 JSON 后 force-stop/启动，生成 pack-registry.db，查询到 demo-pack/1.0.0/123456/device-migrate-test；随后清理种子数据 | pack-registry.db |
| CCOS 会话/预检 | partial：run-as 预置 task/result 后，CCOS 屏恢复 task-demo-0001、result succeeded、显示“导入前预检通过”；人审提交未完成 | ui-ccos5.xml |
| 横屏自适应 | pass：旋转到横屏后 NavigationRail 竖排四目的地，内容区重排 | landscape.png |
| Release 结构 | partial：zipalign 16KB 通过；apksigner 报 Missing META-INF/MANIFEST.MF（未签名，签名仍 OPEN-EXTERNAL） | zipalign/apksigner 输出 |
| device_smoke 脚本 | 已修复：原 echo 中的 ADB 命令被 bash 当成算术展开，真机首跑报 unbound variable；改为普通命令替换 | app/scripts/device_smoke.sh |

## 5. 复跑入口

    adb install -r app/android/app/build/outputs/apk/debug/app-debug.apk
    adb shell am start -W -n dev.ninfenz.mobile/.MainActivity
    adb exec-out screencap -p > shot.png
    adb shell run-as dev.ninfenz.mobile find files -maxdepth 4 -type f
