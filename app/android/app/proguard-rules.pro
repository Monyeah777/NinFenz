# JNA：保留动态映射入口（release 构建时 core bridge 依赖反射式接口映射）
-keep class com.sun.jna.** { *; }
-keepclassmembers class * extends com.sun.jna.Library { *; }
-keep class dev.ninfenz.mobile.core.CoreBridgeNative$CoreNativeLib { *; }
