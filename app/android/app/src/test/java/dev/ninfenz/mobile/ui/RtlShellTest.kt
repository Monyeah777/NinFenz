package dev.ninfenz.mobile.ui

import android.content.Context
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.LayoutDirection
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

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class RtlShellTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun rtlStillShowsDestinations() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val prefs = AppPrefs(context).apply { onboardingDone = true }
        compose.setContent {
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                NfTheme { NfMobileApp(prefs, ThemeMode.SYSTEM, {}) }
            }
        }
        compose.waitForIdle()
        assertTrue(compose.onAllNodesWithText("库").fetchSemanticsNodes().isNotEmpty())
        assertTrue(compose.onAllNodesWithText("我的").fetchSemanticsNodes().isNotEmpty())
    }
}
