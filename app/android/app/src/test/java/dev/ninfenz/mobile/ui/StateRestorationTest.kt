package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performTextInput
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.ui.screens.NewProjectScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import java.io.File
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class StateRestorationTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun newProjectTitleSurvivesStateRestore() {
        val pack = PackEntry("demo", "1.0.0", "示例", "", 1, "tree", File("/tmp"), 0L)
        val tester = StateRestorationTester(compose)
        tester.setContent {
            NfTheme {
                NewProjectScreen(
                    packs = listOf(pack),
                    creating = false,
                    error = null,
                    onBack = {},
                    onLoadSample = {},
                    onCreate = { _, _ -> }
                )
            }
        }
        compose.onNode(hasSetTextAction()).performTextInput("我的项目")
        tester.emulateSavedInstanceStateRestore()
        compose.onNodeWithText("我的项目").assertExists()
    }
}
