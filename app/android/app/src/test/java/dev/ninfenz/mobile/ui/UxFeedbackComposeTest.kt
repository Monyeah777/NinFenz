package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.onNodeWithText
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfStepStrip
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class UxFeedbackComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun errorCardShowsHumanHintAndRawDetail() {
        compose.setContent {
            NfTheme {
                NfErrorCard("NF-E-004", "open failed: /x", "重新选择")
            }
        }
        compose.onNodeWithText("无法读取这个文件，请重新选择文件。", substring = true).assertIsDisplayed()
        compose.onNodeWithText("open failed: /x", substring = true).assertIsDisplayed()
    }

    @Test
    fun stepStripShowsProgress() {
        compose.setContent {
            NfTheme {
                NfStepStrip(steps = listOf("来源", "预览", "映射", "草稿"), current = 1)
            }
        }
        compose.onNodeWithText("第 2/4 步", substring = true).assertIsDisplayed()
        compose.onNode(
            SemanticsMatcher.expectValue(SemanticsProperties.StateDescription, "第 2/4 步")
        ).assertExists()
    }
}
