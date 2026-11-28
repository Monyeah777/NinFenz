# 仅用于 benchmark 变体（性能测量用，不随 release 发布）。
# 原因：macrobenchmark 的测试 APK 与 app 同进程运行，若两边都被混淆，测试 APK 的混淆名
# 会与 app 的混淆名冲突（真机实测 k3.j NoSuchMethodError）。AGP 8.10 对 com.android.test
# 模块忽略 proguardFiles，无法给测试 APK 单独加规则；因此改为让被测 app 的 benchmark 变体
# 不做名称混淆（R8 收缩仍开启，性能口径不受影响），消除冲突。
-dontobfuscate

# 第二层同进程类遮蔽（2026-11-27 收口）：测试 APK 与本 app 同进程，类加载解析到 app 侧
# 被 R8 优化/裁剪过的 kotlin 运行时副本，测试 APK 自带的同名副本被遮蔽；真机实测
# Intrinsics.checkNotNullParameter 抛 NoSuchMethodError。这里保住测试侧会调用的运行时
# 成员（仅 benchmark 变体，不随 release 发布；release 仍是全量 R8）。
-keep class kotlin.jvm.internal.** { *; }
-keep class kotlin.coroutines.jvm.internal.** { *; }
-keep class kotlin.collections.** { *; }
-keep class kotlin.ranges.** { *; }
-keep class kotlin.text.** { *; }
-keep class kotlin.time.** { *; }

# 第三层：androidx 共享运行时同样会被 app 侧 R8 裁剪/优化，而测试 APK（androidx.test/startup/benchmark）
# 依赖其完整成员；同进程父加载器先命中 app 副本 → NoSuchMethodError / NoClassDefFoundError。
# 仅 benchmark 变体保留完整成员，release 仍是全量 R8。
-keep class androidx.arch.core.** { *; }
-keep class androidx.startup.** { *; }
-keep class androidx.profileinstaller.** { *; }
-keep class androidx.tracing.** { *; }
-keep class androidx.concurrent.** { *; }