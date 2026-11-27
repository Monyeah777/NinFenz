# JNA：保留动态映射入口（release 构建时 core bridge 依赖反射式接口映射）
-keep class com.sun.jna.** { *; }
-keepclassmembers class * extends com.sun.jna.Library { *; }
-keep class dev.ninfenz.mobile.core.CoreBridgeNative$CoreNativeLib { *; }

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
