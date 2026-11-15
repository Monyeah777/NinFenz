# NF APP 真机结果（DEVICE_RESULTS）

> 设备：OnePlus PLF110，Android 16（SDK 36），1080×2392 / 480dpi；ADB 已授权（3B65AR0183V00000）。
> APK：0.2.0 / versionCode 2，minSdk 26 / target 36。本件只记实际跑过的项目；未跑项标 OPEN，不写成 pass。

## 1. 已实测（2026-11-15）

| 项目 | 结果 | 证据 |
|---|---|---|
| 全新安装 + 冷启动 | pass：LaunchState COLD，TotalTime 438ms（修复前）/471ms | adb am start -W |
| 首启 3 步引导 | pass：跳过/上一步/下一步/开始使用可用；示例 Pack 载入显示 demo-pack · 1.0.0（9 个文件） | 截图 02–05 |
| 库首页 | pass：示例 Pack、演示项目、状态草稿、管理入口均显示 | 截图 05 |
| 项目详情 | pass：状态/项目 ID/Pack/协议/历史/创作台/装配与交付 | 截图 06 |
| 创作台协议 | pass（保存）：编辑 F-002、切换 C-002、保存后 files/projects/demo-project/overlay/nf-overlay.json 写入，项目 status=authoring、history=overlay:save | run-as 读文件 |
| 装配计划 | pass：graph-compile 返回 steps 2 · slots 4 | 截图 13 |
| 装配 | pass：填 4 个槽位后 assemble 返回 markdown（开篇/正文/收束） | 截图 19 |
| L1 校验 | pass：L1 pass（error=0 warn=0 info=3）；状态 assembled→validated 写回 | run-as 读项目 |
| 导出 md/zip | pass：files/exports/delivery/result.md + result.zip + manifest；状态 validated→exported 写回 | run-as 读文件 |
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
- CCOS：task/result 能加载；提交区已改固定底栏 + navigationBarsPadding，设备端最终复测仍待补。
- 分享 chooser 已真机通过（NEW_TASK 修复）。
- 未跑：折叠屏（本机非折叠）、TalkBack 语音走查、对比度实测。
- 本机无第二台设备/折叠屏，设备矩阵仍不完整。

## 5. 复跑入口

    adb install -r app/android/app/build/outputs/apk/debug/app-debug.apk
    adb shell am start -W -n dev.ninfenz.mobile/.MainActivity
    adb exec-out screencap -p > shot.png
    adb shell run-as dev.ninfenz.mobile find files -maxdepth 4 -type f
