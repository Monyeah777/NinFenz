package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class MarkdownPreviewTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun rendersHeadingsListsTablesAndCode() {
        compose.setContent {
            NfTheme {
                MarkdownPreview(
                    """
                    # 开篇
                    - 第一条
                    > 引用
                    ```
                    val x = 1
                    ```
                    | 列A | 列B |
                    | --- | --- |
                    | 1 | 2 |
                    """.trimIndent()
                )
            }
        }
        compose.onNodeWithText("开篇").assertIsDisplayed()
        compose.onNodeWithText("第一条").assertIsDisplayed()
        compose.onNodeWithText("引用").assertIsDisplayed()
        compose.onNodeWithText("val x = 1").assertIsDisplayed()
        compose.onNodeWithText("列A").assertIsDisplayed()
        compose.onNodeWithText("2").assertIsDisplayed()
    }
}
