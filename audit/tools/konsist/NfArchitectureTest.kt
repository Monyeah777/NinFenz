// NF 审计工具：Konsist 架构规则骨架
//
// 状态：未接入。离线环境没有 Konsist 依赖，也没有 app/android 的 Gradle 可解析环境；
// 本文件只是规则骨架，接入 app/android 后才能运行。
//
// 接入步骤（需联网 CI，禁止在离线审计里声称已通过）：
// 1) app/android/gradle/libs.versions.toml 增加 konsist 版本（或 app/android/app/build.gradle.kts
//    直接 testImplementation("com.lemonappdev:konsist:<version>")）；
// 2) 把本文件复制到 app/android/app/src/test/java/dev/ninfenz/mobile/audit/NfArchitectureTest.kt；
// 3) 运行 ./gradlew :app:testDebugUnitTest --tests '*NfArchitectureTest'；
// 4) 将结果回填到 audit/rules.json 对应规则（ARCH-001/002/003/004、B-004、B-010）的 note/CI 记录，
//    并把该规则从 tool 改为 script 或保留 tool + CI 证据。
//
// 与 audit/rules.json 的对应关系：
// - ARCH-001/002/003：层间 import 边界
// - ARCH-004：包间依赖成环
// - B-004：UI 不得直接依赖 data 实现
// - B-010：state 不得依赖 UI

package dev.ninfenz.mobile.audit

import com.lemonappdev.konsist.api.Konsist
import com.lemonappdev.konsist.api.container.KoScope
import com.lemonappdev.konsist.api.declaration.KoFile
import com.lemonappdev.konsist.api.ext.list.withPackage
import com.lemonappdev.konsist.api.verify.assertFalse
import com.lemonappdev.konsist.api.verify.assertTrue
import org.junit.Test

class NfArchitectureTest {

    private val androidRoot: KoScope = Konsist.scopeFromProject()

    private fun filesUnder(segment: String): List<KoFile> =
        androidRoot.files.filter { it.path.contains(segment) }

    private fun importing(files: List<KoFile>, prefix: String): List<String> =
        files.flatMap { file ->
            file.imports.filter { it.name.startsWith(prefix) }.map { file.path + " -> " + it.name }
        }

    @Test
    fun coreMustNotImportAndroidFramework() {
        val violations = importing(filesUnder("/mobile/core/"), "android.")
        assertTrue(violations.isEmpty()) {
            "core 包 import android.* 越界: " + violations.joinToString()
        }
    }

    @Test
    fun modelMustNotImportDataLayer() {
        val violations = importing(filesUnder("/mobile/model/"), "dev.ninfenz.mobile.data.")
        assertTrue(violations.isEmpty()) {
            "model 层 import data 层: " + violations.joinToString()
        }
    }

    @Test
    fun dataMustNotImportUiOrActivity() {
        val violations = importing(filesUnder("/mobile/data/"), "dev.ninfenz.mobile.ui.") +
            importing(filesUnder("/mobile/data/"), "dev.ninfenz.mobile.MainActivity")
        assertTrue(violations.isEmpty()) {
            "data 层 import ui/MainActivity: " + violations.joinToString()
        }
    }

    @Test
    fun stateMustNotImportUi() {
        val violations = importing(filesUnder("/mobile/state/"), "dev.ninfenz.mobile.ui.")
        assertTrue(violations.isEmpty()) {
            "state 层 import ui: " + violations.joinToString()
        }
    }

    // 依赖成环：Konsist 不直接提供包图，需要与 scripts/audit_package_graph.py 或
    // tools/dependency-analysis 结合；本骨架先保留占位，接入后补实现。
    @Test
    fun packagesMustBeAcyclic() {
        // TODO(CI): 接入包依赖图后断言无环；离线未接入，禁止写成通过。
    }
}
