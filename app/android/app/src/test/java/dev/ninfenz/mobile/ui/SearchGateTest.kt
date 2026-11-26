package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.ModuleToggles
import dev.ninfenz.mobile.data.NfPrefs
import dev.ninfenz.mobile.ui.screens.SearchScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.After
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class SearchGateTest {
    @get:Rule
    val compose = createComposeRule()

    @After
    fun tearDown() {
        CapabilityRegistry.resetForTest()
    }

    @Test
    fun disabledSearchShowsModuleNotice() {
        CapabilityRegistry.install(NfPrefs(modules = ModuleToggles.allOff()))
        compose.setContent {
            NfTheme {
                SearchScreen(onBack = {}, onOpenPack = { _, _ -> }, onOpenProject = {})
            }
        }
        compose.onNodeWithText("搜索模块未启用，请先在设置中打开。").assertIsDisplayed()
    }
}
