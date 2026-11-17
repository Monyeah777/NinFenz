package dev.ninfenz.mobile.ui

import android.content.Context
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
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

private fun prefsForTest(): AppPrefs {
    val context = ApplicationProvider.getApplicationContext<Context>()
    return AppPrefs(context).apply { onboardingDone = true }
}

private fun assertThreeDestinations(compose: androidx.compose.ui.test.junit4.ComposeContentTestRule) {
    compose.waitForIdle()
    assertTrue(compose.onAllNodesWithText("库").fetchSemanticsNodes().isNotEmpty())
    compose.onNodeWithText("工作台").assertExists()
    compose.onNodeWithText("我的").assertExists()
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class ShellCompactNavigationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun compactShowsBottomBarDestinations() {
        val prefs = prefsForTest()
        compose.setContent { NfTheme { NfMobileApp(prefs, ThemeMode.SYSTEM, {}) } }
        assertThreeDestinations(compose)
        compose.onNodeWithText("工作台").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("一个入口，继续内容").assertExists()
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w900dp-h640dp-xhdpi")
class ShellExpandedNavigationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun expandedShowsRailDestinations() {
        val prefs = prefsForTest()
        compose.setContent { NfTheme { NfMobileApp(prefs, ThemeMode.SYSTEM, {}) } }
        assertThreeDestinations(compose)
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w700dp-h900dp-xhdpi")
class ShellMediumNavigationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun mediumShowsRailDestinations() {
        val prefs = prefsForTest()
        compose.setContent { NfTheme { NfMobileApp(prefs, ThemeMode.SYSTEM, {}) } }
        assertThreeDestinations(compose)
    }
}
