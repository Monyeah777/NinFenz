package dev.ninfenz.mobile.ui

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.components.NfOverflowButton
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.screens.InboxScreen
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.screens.PackBuilderScreen
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
    }

    @Test
    fun inboxEmptyStateIsReadable() {
        compose.setContent { NfTheme { InboxScreen(onBack = {}, onImport = {}) } }
        compose.onNodeWithText("还没有分享内容").assertIsDisplayed()
    }

    @Test
    fun inboxRtlRenders() {
        compose.setContent {
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                NfTheme { InboxScreen(onBack = {}, onImport = {}) }
            }
        }
        compose.onNodeWithText("还没有分享内容").assertIsDisplayed()
    }

    @Test
    fun packBuilderMissingDraftIsReadable() {
        compose.setContent { NfTheme { PackBuilderScreen("missing", onBack = {}, onInstalled = {}) } }
        compose.onNodeWithText("Pack draft not found").assertIsDisplayed()
    }

    @Test
    fun scaffoldTitleIsHeading() {
        compose.setContent { NfTheme { NfScaffold(title = "标题", onBack = {}) { } } }
        compose.onNodeWithText("标题").assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.Heading))
    }

    @Test
    fun scaffoldAnnouncesPaneTitle() {
        compose.setContent { NfTheme { NfScaffold(title = "标题", onBack = {}) { } } }
        compose.onNode(
            SemanticsMatcher.expectValue(SemanticsProperties.PaneTitle, "标题"),
            useUnmergedTree = true
        ).assertExists()
    }

    @Test
    fun scaffoldHasStableTraversalIndex() {
        compose.setContent { NfTheme { NfScaffold(title = "标题", onBack = {}) { } } }
        compose.onNode(
            SemanticsMatcher.expectValue(SemanticsProperties.TraversalIndex, 0f),
            useUnmergedTree = true
        ).assertExists()
        compose.onNode(
            SemanticsMatcher.expectValue(SemanticsProperties.TraversalIndex, 1f),
            useUnmergedTree = true
        ).assertExists()
    }

    @Test
    fun noticeIsPoliteLiveRegion() {
        compose.setContent { NfTheme { Notice("已保存", Tone.INFO) } }
        compose.onNode(
            SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Polite),
            useUnmergedTree = true
        ).assertExists()
    }

    @Test
    fun topBarBackMeetsTarget() {
        compose.setContent { NfTheme { NfTopAppBar(title = "详情", onBack = {}) } }
        compose.onNodeWithContentDescription("返回").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
    }

    @Test
    fun overflowButtonHasDescriptionAndTarget() {
        compose.setContent { NfTheme { NfOverflowButton(onClick = {}) } }
        compose.onNodeWithContentDescription("更多").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
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
