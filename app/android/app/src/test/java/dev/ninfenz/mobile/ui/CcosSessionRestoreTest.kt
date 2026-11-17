package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.test.core.app.ApplicationProvider
import android.content.Context
import dev.ninfenz.mobile.data.CcosSessionStore
import dev.ninfenz.mobile.ui.screens.CcosScreen
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class CcosSessionRestoreTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun restoresImportedTaskAndResult() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        CcosSessionStore.saveTask(context.filesDir, TASK)
        CcosSessionStore.saveResult(context.filesDir, RESULT)
        compose.setContent { NfTheme { CcosScreen(onBack = {}) } }
        compose.waitUntil(5_000) {
            compose.onAllNodes(androidx.compose.ui.test.hasText("task-demo-0001", substring = true))
                .fetchSemanticsNodes().isNotEmpty()
        }
        compose.onAllNodesWithText("task-demo-0001", substring = true)[0].assertExists()
        compose.onAllNodesWithText("succeeded", substring = true)[0].assertExists()
    }

    private companion object {
        const val TASK = "{\n  \"schema\": \"ccos-task/1\", \"id\": \"task-demo-0001\", \"created_at\": \"2026-11-15T00:00:00Z\",\n  \"pack\": {\"id\": \"demo-pack\", \"version\": \"1.0.0\", \"tree\": \"1a6562590ef19d1045d06c4055742d38288e9e6dcd71ccde5cee80f1d5a774eb\"},\n  \"protocol\": {\"id\": \"demo-protocol\", \"version\": \"1.0.0\", \"digest\": \"031b4af5197ec30a926f48cf40e11a7dbc470048a21e4003b7a3c07c5dab1baa\"},\n  \"pipeline\": {\"id\": \"demo-pipeline\", \"version\": \"1.0.0\", \"digest\": \"41cfc0d1f2d127b04555b7246d84019b4d27710a3f3aff6e7764375b1e06e05d\"},\n  \"md_spec\": {\"id\": \"demo-spec\", \"version\": \"1.0.0\", \"digest\": \"2858dcd1057d3eae7f7d5f782167e24b61153c01551450a628cee722509f6529\"},\n  \"inputs\": [{\"slot\": \"SLT-01\", \"value\": \"开头\"}],\n  \"budget\": {\"max_tokens\": 1000, \"max_chars\": 4000, \"max_seconds\": 600},\n  \"policy\": {\"network\": false, \"tools\": [\"write\"], \"secrets\": \"ccos-only\"},\n  \"provenance\": {\"project_id\": \"demo-project\", \"project_digest\": \"2fca346db656187102ce806ac732e06a62df0dbb2829e511a770556d398e1a6e\"}\n}"
        const val RESULT = "{\n  \"schema\": \"ccos-result/1\", \"task_id\": \"task-demo-0001\",\n  \"task_digest\": \"02d20bbd7e394ad5999a4cebabac9619732c343a4cac99470c03e23ba2bdc2bc\",\n  \"status\": \"succeeded\",\n  \"artifacts\": [{\"name\": \"result.md\", \"mime\": \"text/markdown\", \"path\": \"artifacts/result.md\", \"sha256\": \"7688b6ef52555962d008fff894223582c484517cea7da49ee67800adc7fc8866\", \"bytes\": 100}],\n  \"evidence\": [{\"kind\": \"log\", \"ref\": \"evidence/run.log\", \"digest\": \"c837649cce43f2729138e72cc315207057ac82599a59be72765a477f22d14a54\"}],\n  \"report\": {\"summary\": \"完成\", \"issues\": []},\n  \"provenance\": {\"engine\": \"ccos-demo\", \"model\": \"demo-model\", \"started_at\": \"2026-11-15T00:00:00Z\", \"finished_at\": \"2026-11-15T00:01:00Z\"},\n  \"human_review\": {\"required\": true, \"state\": \"pending\"}\n}"
    }
}
