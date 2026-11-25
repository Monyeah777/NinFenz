package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import dev.ninfenz.mobile.data.FeatureGate
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectRefs
import dev.ninfenz.mobile.model.ProjectReview
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.ui.screens.ProjectDetailScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.After
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class ProjectDetailMountTest {
    @get:Rule
    val compose = createComposeRule()

    @After
    fun resetTier() {
        FeatureGate.resetForTest()
    }

    @Test
    fun projectDetailMounts() {
        val project = Project(
            id = "p1",
            title = "演示项目",
            refs = ProjectRefs("pack", "1.0.0", "tree", "proto", "digest", "graph", "spec", null),
            status = ProjectStatus.EXPORTED,
            review = ProjectReview("pending", null, null, null),
            historyCount = 0
        )
        compose.setContent {
            NfTheme {
                ProjectDetailScreen(project = project, onBack = {}, onAuthor = {}, onAssembly = {})
            }
        }
        compose.onNodeWithText("演示项目").assertExists()
    }

    @Test
    fun projectDetailOffersOverflowActions() {
        val project = Project(
            id = "p1",
            title = "演示项目",
            refs = ProjectRefs("pack", "1.0.0", "tree", "proto", "digest", "graph", "spec", null),
            status = ProjectStatus.EXPORTED,
            review = ProjectReview("pending", null, null, null),
            historyCount = 0
        )
        compose.setContent {
            NfTheme {
                ProjectDetailScreen(project = project, onBack = {}, onAuthor = {}, onAssembly = {})
            }
        }
        compose.onNodeWithContentDescription("更多").performClick()
        compose.onNodeWithText("复制项目").assertExists()
        compose.onNodeWithText("项目工作流").assertExists()
    }

    @Test
    fun dailyHidesReviewSurfaces() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.FREE)
        compose.setContent { NfTheme { ProjectDetailScreen(probeProject(), {}, {}, {}) } }
        compose.onNodeWithContentDescription("更多").performClick()
        compose.onNodeWithText("评审").assertDoesNotExist()
        compose.onNodeWithText("逐块评审").assertDoesNotExist()
    }

    @Test
    fun proShowsReviewSurfaces() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.PRO)
        compose.setContent { NfTheme { ProjectDetailScreen(probeProject(), {}, {}, {}) } }
        compose.onNodeWithContentDescription("更多").performClick()
        compose.onAllNodesWithText("评审").onFirst().assertExists()
        compose.onNodeWithText("逐块评审").assertExists()
    }

    private fun probeProject() = Project(
        id = "p1",
        title = "演示项目",
        refs = ProjectRefs("pack", "1.0.0", "tree", "proto", "digest", "graph", "spec", null),
        status = ProjectStatus.EXPORTED,
        review = ProjectReview("approved", "a", "ok", "d"),
        historyCount = 3
    )
}
