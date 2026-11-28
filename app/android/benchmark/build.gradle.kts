plugins {
    id("com.android.test")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "dev.ninfenz.mobile.benchmark"
    compileSdk = 36
    buildToolsVersion = "36.0.0"

    defaultConfig {
        minSdk = 26
        targetSdk = 36
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    targetProjectPath = ":app"
    // Macrobenchmark 必须「自测」：测试 APK 在自己的进程里跑，再 kill/compile/launch 目标 app。
    // 若沿用 com.android.test 的默认 targetPackage=:app，测试会被加载进目标进程
    // （androidx.benchmark 判 NOT-SELF-INSTRUMENTING 直接报错，也是同进程类遮蔽的根源）。
    experimentalProperties["android.experimental.self-instrumenting"] = true

    buildTypes {
        create("benchmark") {
            isDebuggable = true
            matchingFallbacks += listOf("release")
            // 被测 app 的 benchmark 变体已关闭 R8/资源压缩（同进程类遮蔽收口，见 app 侧注释），
            // 测试模块同步关闭压缩，避免 AGP 的 shrink 联动约束与测试 APK 自身被裁。
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
            // 注意：AGP 8.10 对 com.android.test 模块**不会**把这里的 proguardFiles 传给 R8
            // （实测 R8 输入只有 AAR 的 consumer proguard.txt），因此真正生效的规则放在
            // libs/nf-benchmark-rules.jar 的 META-INF/proguard/nf-benchmark.pro 里。
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.test.ext:junit:1.2.1")
    implementation("androidx.test:runner:1.6.2")
    implementation("androidx.test.uiautomator:uiautomator:2.3.0")
    // 1.3.4 的 gfxinfo framestats 解析在 Android 16 上拿不到新帧（Unable to confirm
    // activity launch completion），升级到 1.5.0（2026 稳定版，支持 API 36 frame stats）。
    implementation("androidx.benchmark:benchmark-macro-junit4:1.5.0")
    // 被测 app 的 benchmark 变体开了 R8，本模块也必须压缩；压缩时 R8 需要这些
    // 依赖库引用到的运行时类可见，否则报 missing class（见 missing_rules.txt）。
    implementation("androidx.profileinstaller:profileinstaller:1.4.0")
    implementation("androidx.startup:startup-runtime:1.1.1")
    implementation("androidx.arch.core:core-runtime:2.2.0")
    compileOnly("com.google.errorprone:error_prone_annotations:2.27.0")
    // 测试 APK 自身的 R8 规则（-dontobfuscate 等）以依赖 jar 形式进入 R8 规则流；
    // 直接用 buildType.proguardFiles 会被 AGP 忽略，见上方注释。
    implementation(files("libs/nf-benchmark-rules.jar"))
}
