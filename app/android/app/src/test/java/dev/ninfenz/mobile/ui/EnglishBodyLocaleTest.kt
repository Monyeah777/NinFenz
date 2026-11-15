package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.ProjectFactory
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.ui.screens.AuthorScreen
import dev.ninfenz.mobile.ui.screens.ImportScreen
import dev.ninfenz.mobile.ui.screens.NewProjectScreen
import dev.ninfenz.mobile.ui.screens.PackCenterScreen
import dev.ninfenz.mobile.ui.screens.SearchScreen
import dev.ninfenz.mobile.ui.screens.OnboardingScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "en-rUS-w360dp-h640dp-xhdpi")
class EnglishBodyLocaleTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun onboardingUsesEnglishBody() {
        compose.setContent {
            NfTheme {
                OnboardingScreen(seedState = null, seeding = false, onSeed = {}, onDone = {}, onSkip = {})
            }
        }
        compose.onNodeWithText("Skip").assertIsDisplayed()
        compose.onNodeWithText("Put content into a protocol").assertIsDisplayed()
        compose.onNodeWithText("Next").performClick()
        compose.onNodeWithText("Start with a sample").assertIsDisplayed()
    }

    @Test
    fun importUsesEnglishBody() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val store = LibraryStore(context.filesDir)
        compose.setContent { NfTheme { ImportScreen(prefill = null, store = store, onBack = {}) } }
        compose.onNodeWithText("Import").assertIsDisplayed()
        compose.onNodeWithText("Choose a source").assertIsDisplayed()
        compose.onNodeWithText("Choose file").assertIsDisplayed()
        compose.onNodeWithText("Clipboard").assertIsDisplayed()
        compose.onNodeWithText("Nothing imported yet").assertIsDisplayed()
    }

    @Test
    fun searchUsesEnglishBody() {
        compose.setContent { NfTheme { SearchScreen(onBack = {}, onOpenPack = { _, _ -> }, onOpenProject = {}) } }
        compose.onNodeWithText("Search").assertIsDisplayed()
        compose.onNodeWithText("Type a keyword", substring = true).assertIsDisplayed()
    }

    @Test
    fun packCenterUsesEnglishBody() {
        compose.setContent { NfTheme { PackCenterScreen(packs = emptyList(), onBack = {}, onOpenPack = {}, onUpdatePlan = {}, onLoadSample = {}) } }
        compose.onNodeWithText("Pack center").assertIsDisplayed()
        compose.onNodeWithText("No packs yet").assertIsDisplayed()
    }

    @Test
    fun authorMissingPackUsesEnglishBody() {
        val hex = "0123456789abcdef".repeat(4)
        val project = ProjectModel.parse(
            ProjectFactory.build(
                id = "p", title = "P", packId = "demo-pack", packVersion = "1.0.0", packTree = hex,
                protocolId = "proto", protocolVersion = "1.0.0", protocolDigest = hex,
                graphId = "graph", graphVersion = "1.0.0", graphDigest = hex, graphSha256 = hex,
                specId = "spec", specVersion = "1.0.0", specDigest = hex, specSha256 = hex
            ).toString()
        )
        compose.setContent { NfTheme { AuthorScreen(project = project, pack = null, onBack = {}, onAssembly = {}) } }
        compose.onNodeWithText("Bound pack is not on this device").assertIsDisplayed()
    }

    @Test
    fun newProjectUsesEnglishBody() {
        var loaded = false
        compose.setContent {
            NfTheme {
                NewProjectScreen(packs = emptyList(), creating = false, error = null, onBack = {}, onLoadSample = { loaded = true }, onCreate = { _, _ -> })
            }
        }
        compose.onNodeWithText("New project").assertIsDisplayed()
        compose.onNodeWithText("No packs available yet").assertIsDisplayed()
        compose.onNodeWithText("Load sample pack").performClick()
        assertTrue(loaded)
    }
}
