package dev.ninfenz.mobile.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import dev.ninfenz.mobile.data.SeedResult
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.screens.NewProjectScreen
import dev.ninfenz.mobile.ui.screens.OnboardingScreen
import dev.ninfenz.mobile.ui.screens.PackCenterScreen
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** W6：Robolectric + Compose 语义测试（无需模拟器）。 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class ComposeSmokeTest {

    @get:Rule
    val compose = createComposeRule()

    @Test
    fun emptyStateShowsActionAndInvokesCallback() {
        var clicked = false
        compose.setContent {
            NfTheme {
                NfEmptyState(
                    icon = Icons.Filled.Home,
                    title = "还没有内容",
                    message = "载入示例或导入",
                    actionLabel = "载入示例",
                    onAction = { clicked = true }
                )
            }
        }
        compose.onNodeWithText("还没有内容").assertIsDisplayed()
        compose.onNodeWithText("载入示例").performClick()
        assertTrue(clicked)
    }

    @Test
    fun sectionHeaderHasHeadingSemantics() {
        compose.setContent { NfTheme { NfSectionHeader("最近项目") } }
        compose.onNodeWithText("最近项目").assertIsDisplayed()
        compose.onNode(SemanticsMatcher.keyIsDefined(androidx.compose.ui.semantics.SemanticsProperties.Heading)).assertIsDisplayed()
    }

    @Test
    fun onboardingSkipInvokesCallback() {
        var skipped = false
        compose.setContent {
            NfTheme {
                OnboardingScreen(seedState = null, seeding = false, onSeed = {}, onDone = {}, onSkip = { skipped = true })
            }
        }
        compose.onNodeWithText("跳过").performClick()
        assertTrue(skipped)
    }

    @Test
    fun packCenterEmptyStateHasLoadAction() {
        var loaded = false
        compose.setContent {
            NfTheme {
                PackCenterScreen(packs = emptyList(), onBack = {}, onOpenPack = {}, onUpdatePlan = {}, onLoadSample = { loaded = true })
            }
        }
        compose.onNodeWithText("还没有 Pack").assertIsDisplayed()
        compose.onNodeWithText("载入示例 Pack").performClick()
        assertTrue(loaded)
    }

    @Test
    fun newProjectEmptyStateHasLoadAction() {
        var loaded = false
        compose.setContent {
            NfTheme {
                NewProjectScreen(packs = emptyList(), creating = false, error = null, onBack = {}, onLoadSample = { loaded = true }, onCreate = { _, _ -> })
            }
        }
        compose.onNodeWithText("还没有可用的 Pack").assertIsDisplayed()
        compose.onNodeWithText("载入示例 Pack").performClick()
        assertTrue(loaded)
    }

    @Test
    fun topAppBarBackHasContentDescriptionAndInvokes() {
        var back = false
        compose.setContent {
            NfTheme {
                NfTopAppBar(title = "详情", onBack = { back = true })
            }
        }
        compose.onNodeWithContentDescription("返回").performClick()
        assertTrue(back)
    }

    @Test
    fun libraryEmptyStateShowsSeedAndImportActions() {
        var imported = false
        compose.setContent {
            NfTheme {
                LibraryHomeScreen(
                    packs = emptyList(),
                    projects = emptyList(),
                    errors = emptyList(),
                    seedState = null,
                    seeding = false,
                    onSeed = {},
                    onImport = { imported = true },
                    onOpenPack = {},
                    onOpenProject = {},
                    onSearch = {},
                    onPackCenter = {},
                    onSettings = {}
                )
            }
        }
        compose.onNodeWithText("内容库").assertIsDisplayed()
        compose.onNodeWithText("还没有内容").assertIsDisplayed()
        compose.onNodeWithText("导入内容").performClick()
        assertTrue(imported)
    }
}
