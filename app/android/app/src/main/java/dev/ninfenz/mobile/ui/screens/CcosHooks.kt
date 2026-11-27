package dev.ninfenz.mobile.ui.screens

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.util.orNullLogged
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.CcosSessionStore
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.ProjectStatusStore
import dev.ninfenz.mobile.data.StatusAdvanceResult
import dev.ninfenz.mobile.model.CcosModel
import dev.ninfenz.mobile.model.CcosResult
import dev.ninfenz.mobile.model.CcosTask
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.ui.safeCall
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

@Composable
internal fun rememberCcosSession(context: Context): RestoredCcos =
    remember(context.filesDir) {
        val taskText = CcosSessionStore.loadTask(context.filesDir)
        val resultText = CcosSessionStore.loadResult(context.filesDir)
        val taskObj = taskText?.let { runCatching { J.parseObject(it, "ccos-task/1") }.orNullLogged("CcosScreen") }
        val parsedTask = taskObj?.let { runCatching { CcosModel.parseTask(it) }.orNullLogged("CcosScreen") }
        val parsedResult = resultText?.let { runCatching { CcosModel.parseResult(it) }.orNullLogged("CcosScreen") }
        RestoredCcos(
            task = parsedTask,
            result = parsedResult,
            rawTask = taskObj,
            findings = parsedResult?.let { dev.ninfenz.mobile.model.CcosPrecheck.check(it, parsedTask) }.orEmpty()
        )
    }

@Composable
internal fun rememberCcosPickers(
    context: Context,
    scope: CoroutineScope,
    task: CcosTask?,
    onTaskLoaded: (CcosTask, JsonObject) -> Unit,
    onResultLoaded: (CcosResult, List<dev.ninfenz.mobile.model.CcosPrecheck.Finding>) -> Unit,
    onError: (CoreError?) -> Unit
): Pair<() -> Unit, () -> Unit> {
    val taskPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "ccos-task/1")
                val parsed = CcosModel.parseTask(obj)
                withContext(Dispatchers.IO) {
                    CcosSessionStore.saveTask(context.filesDir, text)
                    CcosSessionStore.clearResult(context.filesDir)
                }
                onTaskLoaded(parsed, obj)
            } catch (e: Exception) {
                onError(CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-CCOS-001",
                    context.getString(dev.ninfenz.mobile.R.string.ccos_task_parse_error, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.ccos_task_parse_fix),
                    1
                ).error)
            }
        }
    }
    val resultPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val parsed = CcosModel.parseResult(text)
                withContext(Dispatchers.IO) { CcosSessionStore.saveResult(context.filesDir, text) }
                onResultLoaded(parsed, dev.ninfenz.mobile.model.CcosPrecheck.check(parsed, task))
            } catch (e: Exception) {
                onError(CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-CCOS-001",
                    context.getString(dev.ninfenz.mobile.R.string.ccos_result_parse_error, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.ccos_result_parse_fix),
                    1
                ).error)
            }
        }
    }
    return remember(taskPicker, resultPicker) {
        Pair(
            { taskPicker.launch(arrayOf("application/json", "text/plain")) },
            { resultPicker.launch(arrayOf("application/json", "text/plain")) }
        )
    }
}

internal data class PerformCcosReviewArgs(
    val context: Context,
    val result: CcosResult,
    val rawTask: JsonObject?,
    val task: CcosTask?,
    val reviewer: String,
    val note: String,
    val approve: Boolean,
    val onOutcome: (String?) -> Unit,
    val onBusy: (Boolean) -> Unit,
    val onError: (CoreError?) -> Unit,
    val onResult: (CcosResult) -> Unit,
)

internal suspend fun performCcosReview(args: PerformCcosReviewArgs) {
    with(args) {
    val who = reviewer.trim()
    val why = note.trim()
    val decision = CcosModel.review(result, approve, who, why)
    if (!decision.ok) {
        onOutcome(context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_not_submitted, decision.message))
        return
    }
    val reviewed = CcosModel.withReview(result, decision.state, who, why)
    if (rawTask == null) {
        onOutcome(context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_no_task))
        return
    }
    onBusy(true)
    onError(null)
    try {
        val payload = buildJsonObject {
            put("task", rawTask)
            put("result", CcosModel.resultJson(reviewed))
        }
        val response = safeCall("ccos-import-result", payload)
        if (response.ok) {
            val base = context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_accepted, response.result?.toString() ?: context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_empty))
            val extra = if (approve) advanceProjectOnReview(context, task?.projectId) else ""
            onOutcome(base + extra)
            onResult(reviewed)
            withContext(Dispatchers.IO) {
                CcosSessionStore.saveResult(context.filesDir, CcosModel.resultJson(reviewed).toString())
            }
        } else {
            onError(response.error)
        }
    } finally {
        onBusy(false)
    }

    }
}

private suspend fun advanceProjectOnReview(context: Context, projectId: String?): String {
    if (projectId.isNullOrBlank()) return ""
    val file = File(File(context.filesDir, "projects"), projectId + ".nfproject.json")
    if (!file.isFile) return ""
    return runCatching {
        val project = ProjectModel.parse(file.readText(Charsets.UTF_8))
        if (project.status != ProjectStatus.EXPORTED) {
            context.getString(dev.ninfenz.mobile.R.string.ccos_reviewed_skip, project.status.wire)
        } else {
            when (val advanced = ProjectStatusStore(context.filesDir).advance(project, ProjectStatus.REVIEWED)) {
                is StatusAdvanceResult.Advanced -> context.getString(dev.ninfenz.mobile.R.string.ccos_reviewed_ok)
                is StatusAdvanceResult.Failure -> context.getString(dev.ninfenz.mobile.R.string.ccos_reviewed_fail, advanced.message)
            }
        }
    }.getOrDefault("")
}
