# JNA：保留动态映射入口（release 构建时 core bridge 依赖反射式接口映射）
-keep class com.sun.jna.** { *; }
-keepclassmembers class * extends com.sun.jna.Library { *; }
# CoreNativeLib 是文件级 private interface（JVM 名 dev.ninfenz.mobile.core.CoreNativeLib，不是 CoreBridgeNative$…）。
# 0.3.7 真机实测：旧规则写错名 → 接口被 R8 改名且方法被裁 → Native.load 抛 ClassCastException → 所有核心 op 报 NF-E-005。
-keep class dev.ninfenz.mobile.core.CoreNativeLib { *; }
-keep interface dev.ninfenz.mobile.core.CoreNativeLib { *; }

# PDFBox Android：资源加载与反射字体/解析入口；release 冒烟覆盖 PDF 导入/样式
-keep class dev.ninfenz.mobile.ocr.OcrFeature { *; }

-keep class com.tom_roush.** { *; }
-dontwarn com.tom_roush.**

# ML Kit OCR：consumer rules 之外保留入口与模型回调
-keep class com.google.mlkit.** { *; }
-dontwarn com.google.mlkit.**

# JNA 可选 AWT 辅助类：Android 无 java.awt
-dontwarn java.awt.Component
-dontwarn java.awt.GraphicsEnvironment
-dontwarn java.awt.HeadlessException
-dontwarn java.awt.Window
