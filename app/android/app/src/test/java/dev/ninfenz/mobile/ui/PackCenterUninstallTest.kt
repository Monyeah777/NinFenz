package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.ui.screens.PackCenterScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class PackCenterUninstallTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun uninstallButtonConfirmsAndInvokesCallback() {
        var uninstalled = false
        val pack = PackEntry(
            id = "demo",
            version = "1.0.0",
            title = "演示 Pack",
            description = "demo",
            itemCount = 1,
            tree = "tree",
            dir = File("demo/1.0.0")
        )
        compose.setContent {
            NfTheme {
                PackCenterScreen(
                    packs = listOf(pack),
                    onUninstall = { uninstalled = true },
                    onBack = {},
                    onOpenPack = {},
                    onUpdatePlan = {},
                    onLoadSample = {}
                )
            }
        }
        compose.onNodeWithText("卸载").performClick()
        compose.onNodeWithText("卸载 Pack？").assertIsDisplayed()
        compose.onNodeWithTag("packcenter_uninstall_confirm").performClick()
        assertTrue(uninstalled)
    }
}
