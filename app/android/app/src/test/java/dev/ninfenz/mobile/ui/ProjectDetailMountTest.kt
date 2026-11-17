package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectRefs
import dev.ninfenz.mobile.model.ProjectReview
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.ui.screens.ProjectDetailScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
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
}
