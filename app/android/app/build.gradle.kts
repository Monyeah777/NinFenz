plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "dev.ninfenz.mobile"
    compileSdk = 36
    buildToolsVersion = "36.0.0"

    defaultConfig {
        applicationId = "dev.ninfenz.mobile"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        // ABI 与 Rust 交叉编译目标一致（app/scripts/build_core_android.sh）
        ndk {
            abiFilters.addAll(listOf("arm64-v8a", "x86_64"))
        }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    // 16KB page：native lib 以未压缩、页对齐方式打包（AGP 8.10 起 useLegacyPackaging=false 为默认，仍显式钉住）
    packaging {
        jniLibs {
            useLegacyPackaging = false
        }
        resources {
            excludes.addAll(listOf("META-INF/AL2.0", "META-INF/LGPL2.1", "META-INF/LICENSE*", "META-INF/NOTICE*"))
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }

    // 错误码单一真源：构建时复制 app/schema/error_codes.json 为 Java resource（Settings 诊断页用）
    sourceSets {
        getByName("main") {
            resources.srcDir(layout.buildDirectory.dir("generated/schema-resources"))
        }
    }
}

// 原生核心缺席时不阻断构建（APK 仍产出），但构建日志明确提示——UI 运行时给出 NF-E-005 指引，不静默假数据。
tasks.named("preBuild") {
    doFirst {
        val arm = file("src/main/jniLibs/arm64-v8a/libnf_app_core.so").exists()
        val x86 = file("src/main/jniLibs/x86_64/libnf_app_core.so").exists()
        if (!arm || !x86) {
            logger.warn("[nf-mobile] jniLibs 缺 libnf_app_core.so（arm64-v8a=" + arm + ", x86_64=" + x86 + "）。APK 可构建；运行时 CoreBridge 报 NF-E-005。修复：bash app/scripts/build_core_android.sh")
        }
    }
}

// 错误码单一真源：把 app/schema/error_codes.json 复制进 build/generated（android.sourceSets.main.resources 已登记该目录）
val errorCodeFile = rootProject.projectDir.toPath().resolve("../schema/error_codes.json").normalize().toFile()
val copyErrorCatalog = tasks.register<Copy>("copyErrorCatalog") {
    from(errorCodeFile)
    into(layout.buildDirectory.dir("generated/schema-resources/schema"))
}
tasks.matching { it.name.startsWith("process") && it.name.endsWith("JavaRes") }.configureEach {
    dependsOn(copyErrorCatalog)
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.05.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.ui:ui-text-google-fonts")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    // JNA aar：内含 Android ABI 的 libjnidispatch.so（Android 上 JNA 必须用 aar 变体）
    implementation("net.java.dev.jna:jna:5.17.0@aar")

    debugImplementation("androidx.compose.ui:ui-tooling")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
}
