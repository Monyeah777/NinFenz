# Macrobenchmark 测试 APK 自身压缩时的 keep 规则（被测 app 已开 R8，AGP 要求本模块同步开）
-keep class androidx.benchmark.** { *; }
-keep class androidx.test.** { *; }
-keep class org.junit.** { *; }
-keepclasseswithmembers class * {
    @org.junit.Test <methods>;
}
-keepclasseswithmembers class * {
    @org.junit.Rule <fields>;
}
-dontwarn org.junit.**
-dontwarn androidx.benchmark.**
# 测试模块自身压缩时，R8 会对依赖库的缺失传递类报错；这些类只在库的运行时分支里出现，测试 APK 不需要。
-dontwarn androidx.arch.core.**
-dontwarn androidx.profileinstaller.**
-dontwarn androidx.startup.**
-dontwarn androidx.tracing.**
-dontwarn com.google.errorprone.annotations.**
-dontwarn com.google.common.**
-dontwarn javax.annotation.**
-dontwarn org.checkerframework.**
-dontobfuscate
