package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithText
import dev.ninfenz.mobile.data.FeatureGate
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectRefs
import dev.ninfenz.mobile.model.ProjectReview
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.ui.screens.ProjectFlowScreen
import dev.ninfenz.mobile.ui.screens.WorkflowHubScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import java.io.File
import org.junit.After
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class FlowUiTest {
    @get:Rule
    val compose = createComposeRule()

    @After
    fun resetTier() {
        FeatureGate.resetForTest()
    }

    private fun project(status: ProjectStatus) = Project(
        id = "p1",
        title = "演示项目",
        refs = ProjectRefs("pack", "1.0.0", "tree", "proto", "digest", "graph", "spec", null),
        status = status,
        review = ProjectReview("pending", null, null, null),
        historyCount = 0
    )

    @Test
    fun workflowHubShowsSingleEntryAndNextAction() {
        compose.setContent {
            NfTheme {
                WorkflowHubScreen(
                    projects = listOf(ProjectEntry(project(ProjectStatus.AUTHORING), File("p1.json"))),
                    onOpenProject = {},
                    onAuthor = {},
                    onDelivery = {},
                    onNewProject = {},
                    onImport = {}
                )
            }
        }
        compose.onNodeWithText("新建项目").assertIsDisplayed()
        compose.onNodeWithText("演示项目").assertIsDisplayed()
        compose.onAllNodesWithText("继续创作").onFirst().assertIsDisplayed()
    }

    @Test
    fun projectFlowShowsStagesAndNextStep() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.PRO)
        compose.setContent {
            NfTheme {
                ProjectFlowScreen(
                    project = project(ProjectStatus.ASSEMBLED),
                    onBack = {},
                    onAuthor = {},
                    onDelivery = {}
                )
            }
        }
        compose.onNodeWithText("项目工作流").assertIsDisplayed()
        compose.onNodeWithText("创作").assertIsDisplayed()
        compose.onNodeWithText("评审").assertIsDisplayed()
        compose.onNodeWithText("装配与交付").assertIsDisplayed()
    }

    @Test
    fun dailyFlowHasThreeStagesAndNoReview() {
        FeatureGate.setTierForDebug(FeatureGate.Tier.FREE)
        compose.setContent {
            NfTheme {
                ProjectFlowScreen(
                    project = project(ProjectStatus.ASSEMBLED),
                    onBack = {},
                    onAuthor = {},
                    onDelivery = {}
                )
            }
        }
        compose.onNodeWithText("创作").assertIsDisplayed()
        compose.onNodeWithText("装配与交付").assertIsDisplayed()
        compose.onNodeWithText("校验").assertDoesNotExist()
        compose.onNodeWithText("评审").assertDoesNotExist()
    }
}
