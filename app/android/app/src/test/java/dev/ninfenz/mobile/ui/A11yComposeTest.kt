package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.screens.OnboardingScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** W6 a11y：图标 contentDescription + 最小触控目标（48dp 语义）。 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class A11yComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun libraryIconActionsHaveDescriptionsAndTargets() {
        compose.setContent {
            NfTheme {
                LibraryHomeScreen(
                    packs = emptyList(), projects = emptyList(), errors = emptyList(),
                    seedState = null, seeding = false,
                    onSeed = {}, onImport = {}, onOpenPack = {}, onOpenProject = {},
                    onSearch = {}, onPackCenter = {}, onSettings = {}
                )
            }
        }
        compose.onNodeWithContentDescription("搜索").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
        compose.onNodeWithContentDescription("设置").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
        compose.onNodeWithText("导入内容").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
        compose.onNodeWithText("载入示例 Pack").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
    }

    @Test
    fun topBarBackMeetsTarget() {
        compose.setContent { NfTheme { NfTopAppBar(title = "详情", onBack = {}) } }
        compose.onNodeWithContentDescription("返回").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
    }

    @Test
    fun onboardingActionsMeetTarget() {
        compose.setContent {
            NfTheme {
                OnboardingScreen(seedState = null, seeding = false, onSeed = {}, onDone = {}, onSkip = {})
            }
        }
        compose.onNodeWithText("跳过").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
        compose.onNodeWithText("下一步").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
    }
}
