package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import dev.ninfenz.mobile.ui.screens.InboxScreen
import dev.ninfenz.mobile.ui.screens.LibraryHomeScreen
import dev.ninfenz.mobile.ui.screens.PackBuilderScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** DoD：字体 200% 下库页主要文案仍可见、不崩溃。 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi", fontScale = 2.0f)
class LargeFontComposeTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun libraryAt200PercentStillShowsPrimaryActions() {
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
        compose.onNodeWithText("内容库").assertIsDisplayed()
        compose.onNodeWithText("导入内容").assertIsDisplayed()
    }

    @Test
    fun inboxAt200PercentStillShowsEmptyState() {
        compose.setContent { NfTheme { InboxScreen(onBack = {}, onImport = {}) } }
        compose.onNodeWithText("还没有分享内容").assertIsDisplayed()
    }

    @Test
    fun packBuilderAt200PercentStillShowsEmptyState() {
        compose.setContent { NfTheme { PackBuilderScreen("missing", onBack = {}, onInstalled = {}) } }
        compose.onNodeWithText("Pack draft not found").assertIsDisplayed()
    }
}
