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

    buildTypes {
        create("benchmark") {
            isDebuggable = true
            matchingFallbacks += listOf("release")
            // 被测 app 的 benchmark 变体开了 R8/资源压缩，AGP 要求测试模块同步开启，
            // 否则 assemble 直接报 "shrinking enabled ... enable shrinking in this test project"。
            isMinifyEnabled = true
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
    implementation("androidx.benchmark:benchmark-macro-junit4:1.3.4")
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
