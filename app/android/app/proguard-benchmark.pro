# 仅用于 benchmark 变体（性能测量用，不随 release 发布）。
# 原因：macrobenchmark 的测试 APK 与 app 同进程运行，若两边都被混淆，测试 APK 的混淆名
# 会与 app 的混淆名冲突（真机实测 k3.j NoSuchMethodError）。AGP 8.10 对 com.android.test
# 模块忽略 proguardFiles，无法给测试 APK 单独加规则；因此改为让被测 app 的 benchmark 变体
# 不做名称混淆（R8 收缩仍开启，性能口径不受影响），消除冲突。
-dontobfuscate
