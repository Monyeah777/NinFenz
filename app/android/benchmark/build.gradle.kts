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
}
