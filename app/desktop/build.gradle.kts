import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    kotlin("jvm") version "2.1.20"
    id("org.jetbrains.compose") version "1.7.3"
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.20"
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    implementation("net.java.dev.jna:jna:5.17.0")
    testImplementation("junit:junit:4.13.2")
}

// 原生核心（Windows cdylib）在构建时从 app/core/target/release 复制进 resources；
// 找不到时不失败、不造假：UI 显示 NF-E-005 与安装指引。
val coreResourceDir = layout.buildDirectory.dir("generated/core-resources")

val copyCoreNative = tasks.register<Copy>("copyCoreNative") {
    val release = rootProject.projectDir.toPath().resolve("../core/target/release/nf_app_core.dll").normalize().toFile()
    val debug = rootProject.projectDir.toPath().resolve("../core/target/debug/nf_app_core.dll").normalize().toFile()
    val src = when {
        release.exists() -> release
        debug.exists() -> debug
        else -> null
    }
    if (src != null) {
        from(src)
    }
    // 资源路径固定为 /native/nf_app_core.dll（CoreBridgeJna 先按此查找）
    into(coreResourceDir.map { dir -> dir.dir("native") })
    doFirst {
        if (src == null) {
            logger.warn("[nf-studio] 未找到 nf_app_core.dll（app/core/target/release）：Studio 可启动，但 CoreBridge 显示 NF-E-005。修复：cd app/core && cargo build --release")
        } else {
            logger.lifecycle("[nf-studio] 打包原生核心：" + src.absolutePath)
        }
    }
}

sourceSets {
    main {
        resources.srcDir(coreResourceDir)
    }
}

tasks.named("processResources") {
    dependsOn(copyCoreNative)
}

tasks.withType<Test>().configureEach {
    useJUnit()
}

compose.desktop {
    application {
        mainClass = "dev.ninfenz.studio.MainKt"
        nativeDistributions {
            targetFormats(TargetFormat.Msi)
            packageName = "NFStudio"
            packageVersion = "0.1.0"
            description = "NF Studio - local authoring control plane"
            vendor = "NinFenz"
            modules("java.desktop", "java.logging", "java.naming", "jdk.unsupported")
            // 文件关联（Windows 安装包注册 .nfg 双击打开；OS 级验证见 README OPEN）
            fileAssociation(
                extension = "nfg",
                description = "NF pipeline graph (nf-pipeline-graph/1)",
                mimeType = "application/json"
            )
        }
    }
}
