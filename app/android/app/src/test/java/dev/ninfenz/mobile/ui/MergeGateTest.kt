package dev.ninfenz.mobile.ui

import android.content.Context
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.core.app.ApplicationProvider
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.ModuleToggles
import dev.ninfenz.mobile.data.NfPrefs
import dev.ninfenz.mobile.ui.screens.NfDocMergeScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.After
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class MergeGateTest {
    @get:Rule
    val compose = createComposeRule()

    @After
    fun tearDown() {
        CapabilityRegistry.resetForTest()
    }

    @Test
    fun disabledMergeShowsModuleNotice() {
        CapabilityRegistry.install(NfPrefs(modules = ModuleToggles.allOff()))
        val context = ApplicationProvider.getApplicationContext<Context>()
        compose.setContent {
            NfTheme {
                NfDocMergeScreen(filesDir = context.filesDir, onBack = {})
            }
        }
        compose.onNodeWithText("合并模块未启用，请先在设置中打开。").assertIsDisplayed()
    }
}
