package dev.ninfenz.mobile.ui

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.LayoutDirection
import dev.ninfenz.mobile.ui.screens.SettingsMacroSection
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** 新宏 UI 在 RTL + 200% 字号下仍可见，不替代真机 TalkBack。 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "ar-rSA-w360dp-h640dp-xhdpi", fontScale = 2.0f)
class MacroA11yTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun macroSectionRtlAt200PercentShowsActions() {
        compose.setContent {
            NfTheme {
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    SettingsMacroSection()
                }
            }
        }
        compose.onNodeWithText("语义宏").assertIsDisplayed()
        compose.onNodeWithText("还没有宏。").assertIsDisplayed()
        compose.onNodeWithText("导入宏").assertIsDisplayed()
    }
}
