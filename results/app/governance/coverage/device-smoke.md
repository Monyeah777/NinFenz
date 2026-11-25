# Android 真机冒烟（PLF110）

- 设备：PLF110，Android 16 / SDK 36
- APK：app-debug.apk（65MB，含 Noto 字体与 cmap）
- 安装：`adb install -r` Success，package dev.ninfenz.mobile 存在
- 启动：MainActivity 前台，内容库显示 6 个项目 / 1 个 Pack
- 交互：打开"演示项目" → 装配与交付 → 槽位页，SLT-02/03 可输入
- 4 面板验证：step1 仅计划，step2 仅槽位；step3/4 仅装配/导出
- 完成：装配 -> 导出 PDF/UA -> 拉回桌面 veraPDF PASS（C6-10-device.pdf）
- 真机产物：result-ua.pdf 12,982 B；sha256 a9745ba177151995e295a4dc48a98b3672bd83c4fe6e396897931ec70fb03823
- 未发现应用崩溃日志（logcat 仅系统 Osense EBUSY）
