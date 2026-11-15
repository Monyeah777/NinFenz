package dev.ninfenz.mobile.ui

import android.content.Context
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.test.core.app.ApplicationProvider
import dev.ninfenz.mobile.data.AppPrefs
import dev.ninfenz.mobile.data.ThemeMode
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

private fun prefsForTest(): AppPrefs {
    val context = ApplicationProvider.getApplicationContext<Context>()
    return AppPrefs(context).apply { onboardingDone = true }
}

private fun assertFourDestinations(compose: androidx.compose.ui.test.junit4.ComposeContentTestRule) {
    compose.waitForIdle()
    compose.onAllNodesWithText("库").assertCountEquals(2) // 顶部标题 + 导航标签
    compose.onNodeWithText("创作").assertIsDisplayed()
    compose.onNodeWithText("交付").assertIsDisplayed()
    compose.onNodeWithText("我的").assertIsDisplayed()
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "w360dp-h640dp-xhdpi")
class ShellCompactNavigationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun compactShowsBottomBarDestinations() {
        val prefs = prefsForTest()
        compose.setContent { NfTheme { NfMobileApp(prefs, ThemeMode.SYSTEM, {}) } }
        assertFourDestinations(compose)
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "w900dp-h640dp-xhdpi")
class ShellExpandedNavigationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun expandedShowsRailDestinations() {
        val prefs = prefsForTest()
        compose.setContent { NfTheme { NfMobileApp(prefs, ThemeMode.SYSTEM, {}) } }
        assertFourDestinations(compose)
    }
}
