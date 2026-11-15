package dev.ninfenz.mobile.ui.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class NfExpandableComponentsTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun longTextExpandsAndCollapses() {
        val long = (1..80).joinToString("\n") { "第 $it 行内容" }
        compose.setContent { NfTheme { NfExpandableText(long) } }
        compose.onNodeWithText("展开").assertIsDisplayed().performClick()
        compose.onNodeWithText("收起").assertIsDisplayed().performClick()
        compose.onNodeWithText("展开").assertIsDisplayed()
    }

    @Test
    fun collapsibleSectionTogglesContent() {
        compose.setContent {
            NfTheme {
                NfCollapsibleSection(title = "高级设置", initiallyExpanded = false) {
                    androidx.compose.material3.Text("内部内容")
                }
            }
        }
        compose.onNodeWithText("内部内容").assertDoesNotExist()
        compose.onNodeWithText("高级设置").performClick()
        compose.onNodeWithText("内部内容").assertIsDisplayed()
    }
}
