package dev.ninfenz.mobile.ui

import android.content.Context
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.test.core.app.ApplicationProvider
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * 9 组窗口尺寸矩阵（W6）：compact/medium/expanded 宽 × compact/medium/expanded 高。
 * 语义层断言四目的地始终存在；像素级截图基线另列 OPEN。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ShellSizeMatrixTest {
    @get:Rule
    val compose = createComposeRule()

    private fun renderAndAssert(compose: ComposeContentTestRule) {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val prefs = AppPrefs(context).apply { onboardingDone = true }
        compose.setContent { NfTheme { NfMobileApp(prefs, ThemeMode.SYSTEM, {}) } }
        compose.waitForIdle()
        assertTrue(compose.onAllNodesWithText("库").fetchSemanticsNodes().isNotEmpty())
        compose.onNodeWithText("创作").assertIsDisplayed()
        compose.onNodeWithText("交付").assertIsDisplayed()
        compose.onNodeWithText("我的").assertIsDisplayed()
    }

    @Test
    @Config(qualifiers = "zh-rCN-w360dp-h400dp-xhdpi")
    fun compactWidth_compactHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
    fun compactWidth_mediumHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w360dp-h1000dp-xhdpi")
    fun compactWidth_expandedHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w700dp-h400dp-xhdpi")
    fun mediumWidth_compactHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w700dp-h640dp-xhdpi")
    fun mediumWidth_mediumHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w700dp-h1000dp-xhdpi")
    fun mediumWidth_expandedHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w900dp-h400dp-xhdpi")
    fun expandedWidth_compactHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w900dp-h640dp-xhdpi")
    fun expandedWidth_mediumHeight() = renderAndAssert(compose)

    @Test
    @Config(qualifiers = "zh-rCN-w900dp-h1000dp-xhdpi")
    fun expandedWidth_expandedHeight() = renderAndAssert(compose)
}
