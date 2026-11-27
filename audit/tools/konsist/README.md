# Konsist 骨架说明

- 文件：NfArchitectureTest.kt（Kotlin 源码骨架）。
- 现状：**未接入**。离线环境缺 Konsist 依赖，且 app/android 的 Gradle 依赖无法下载；
  直接运行会失败，所以 audit/rules.json 中相应规则保持 tool / not-run。
- 接入条件：联网 CI 能执行 ./gradlew :app:testDebugUnitTest；
- 接入后：把文件放进 app/android/app/src/test/java/dev/ninfenz/mobile/audit/，
  并把运行证据（JUnit XML 摘要）写入 audit/evidence/<commit>/。
