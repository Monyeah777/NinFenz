package dev.ninfenz.mobile.ui.screens

import java.io.File

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
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
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.ErrorNotice
import dev.ninfenz.mobile.ui.components.FormTextField
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CcosScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val restored = remember(context.filesDir) {
        val taskText = CcosSessionStore.loadTask(context.filesDir)
        val resultText = CcosSessionStore.loadResult(context.filesDir)
        val taskObj = taskText?.let { runCatching { J.parseObject(it, "ccos-task/1") }.getOrNull() }
        val parsedTask = taskObj?.let { runCatching { CcosModel.parseTask(it) }.getOrNull() }
        val parsedResult = resultText?.let { runCatching { CcosModel.parseResult(it) }.getOrNull() }
        RestoredCcos(
            task = parsedTask,
            result = parsedResult,
            rawTask = taskObj,
            findings = parsedResult?.let { dev.ninfenz.mobile.model.CcosPrecheck.check(it, parsedTask) }.orEmpty()
        )
    }
    var task by remember { mutableStateOf(restored.task) }
    var result by remember { mutableStateOf(restored.result) }
    var rawTask by remember { mutableStateOf(restored.rawTask) }
    var reviewer by rememberSaveable { mutableStateOf("") }
    var note by rememberSaveable { mutableStateOf("") }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var outcome by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var precheckFindings by remember { mutableStateOf(restored.findings) }

    val taskPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "ccos-task/1")
                task = CcosModel.parseTask(obj)
                rawTask = obj
                withContext(Dispatchers.IO) {
                    CcosSessionStore.saveTask(context.filesDir, text)
                    CcosSessionStore.clearResult(context.filesDir)
                }
                result = null
                precheckFindings = emptyList()
                outcome = null
                error = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-CCOS-001",
                    context.getString(dev.ninfenz.mobile.R.string.ccos_task_parse_error, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.ccos_task_parse_fix),
                    1
                ).error
            }
        }
    }
    val resultPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                result = CcosModel.parseResult(text)
                withContext(Dispatchers.IO) { CcosSessionStore.saveResult(context.filesDir, text) }
                precheckFindings = dev.ninfenz.mobile.model.CcosPrecheck.check(result!!, task)
                error = null
                outcome = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-CCOS-001",
                    context.getString(dev.ninfenz.mobile.R.string.ccos_result_parse_error, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.ccos_result_parse_fix),
                    1
                ).error
            }
        }
    }

    fun submitReview(approve: Boolean) {
        val current = result ?: return
        val rawT = rawTask
        val who = reviewer.trim()
        val why = note.trim()
        val decision = CcosModel.review(current, approve, who, why)
        if (!decision.ok) {
            outcome = context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_not_submitted, decision.message)
            return
        }
        val reviewed = CcosModel.withReview(current, decision.state, who, why)
        if (rawT == null) {
            outcome = context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_no_task)
            return
        }
        scope.launch {
            busy = true
            error = null
            try {
                val payload = buildJsonObject {
                    put("task", rawT)
                    put("result", CcosModel.resultJson(reviewed))
                }
                val response = safeCall("ccos-import-result", payload)
                if (response.ok) {
                    val base = context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_accepted, response.result?.toString() ?: context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_empty))
                    var extra = ""
                    val projectId = task?.projectId
                    if (approve && !projectId.isNullOrBlank()) {
                        val file = File(File(context.filesDir, "projects"), projectId + ".nfproject.json")
                        if (file.isFile) {
                            extra = runCatching {
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
                    }
                    outcome = base + extra
                    result = reviewed
                    withContext(Dispatchers.IO) {
                        CcosSessionStore.saveResult(context.filesDir, CcosModel.resultJson(reviewed).toString())
                    }
                } else {
                    error = response.error
                }
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(busy) {
        if (busy) {
            delay(30_000)
            if (busy) {
                busy = false
                outcome = context.getString(dev.ninfenz.mobile.R.string.ccos_submit_timeout)
            }
        }
    }

    NfScaffold(
        title = stringResource(dev.ninfenz.mobile.R.string.ccos_title),
        onBack = onBack,
        bottomBar = {
            val r = result
            if (r != null && r.reviewState == "pending") {
                CcosReviewActions(
                    busy = busy,
                    outcome = outcome,
                    onApprove = { submitReview(true) },
                    onReject = { submitReview(false) }
                )
            }
        }
    ) {
        Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_interface_notice), Tone.INFO)
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.ccos_step1)) {
            FlowRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Button(onClick = { taskPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_open_task)) }
                OutlinedButton(onClick = { resultPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_open_result)) }
                if (task != null || result != null) {
                    OutlinedButton(enabled = !busy, onClick = {
                        scope.launch {
                            withContext(Dispatchers.IO) { CcosSessionStore.clearAll(context.filesDir) }
                            task = null
                            result = null
                            rawTask = null
                            precheckFindings = emptyList()
                            outcome = null
                            error = null
                        }
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_clear_session)) }
                }
            }
            Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_steps_notice), Tone.INFO)
        }

        error?.let { ErrorNotice(it) }

        val t = task
        if (t != null) {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.ccos_task_title, t.id)) {
                KeyValue("created_at", t.createdAt)
                KeyValue("pack", t.packId + " " + t.packVersion)
                KeyValue("protocol digest", t.protocolDigest.take(16) + "…")
                KeyValue("pipeline digest", t.pipelineDigest.take(16) + "…")
                KeyValue("spec digest", t.specDigest.take(16) + "…")
                KeyValue("inputs", t.inputsCount.toString())
                KeyValue("budget", "tokens " + t.maxTokens + " · chars " + t.maxChars + " · seconds " + t.maxSeconds)
                KeyValue("policy", "network=" + t.networkAllowed + " · secrets=" + t.secretsPolicy)
                KeyValue("provenance", t.projectId + " · " + t.projectDigest.take(16) + "…")
            }
        } else {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.ccos_no_task))
        }

        val r = result
        if (r != null) {
            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.ccos_result_title, r.taskId)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.ccos_status), style = NfType.meta)
                    NfStatusChip(r.status)
                }
                KeyValue("task_digest", r.taskDigest.take(24) + "…")
                if (precheckFindings.isEmpty()) {
                    Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_precheck_pass), Tone.INFO)
                } else {
                    Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_precheck_failed, precheckFindings.size), Tone.ERROR)
                    for (finding in precheckFindings) {
                        Notice(finding.field + "：" + finding.message, Tone.WARN)
                    }
                }
                KeyValue("artifacts", r.artifacts.size.toString())
                for (a in r.artifacts) {
                    Text(a.name + " · " + a.mime + " · " + a.bytes + " bytes", style = NfType.meta)
                    Text("  sha256=" + a.sha256.take(24) + "…", style = NfType.meta)
                }
                KeyValue("evidence", r.evidence.size.toString())
                for (e in r.evidence) {
                    Text(e.kind + " · " + e.ref + " · " + e.digest.take(16) + "…", style = NfType.meta)
                }
                KeyValue("report", r.reportSummary)
                for (issue in r.issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("human_review", style = NfType.meta)
                    NfStatusChip(r.reviewState)
                }
                KeyValue("required", r.reviewRequired.toString())
                if (r.reviewState != "pending") {
                    Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_review_done, r.reviewState, r.reviewer ?: "-"), Tone.INFO)
                }
            }

            CardBox(title = stringResource(dev.ninfenz.mobile.R.string.ccos_review_title)) {
                if (r.reviewState != "pending") {
                    EmptyState(stringResource(dev.ninfenz.mobile.R.string.ccos_review_closed))
                } else {
                    FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.ccos_reviewer_label), value = reviewer, onValueChange = { reviewer = it })
                    FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.ccos_note_field), value = note, onValueChange = { note = it }, singleLine = false)
                    Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_review_notice), Tone.INFO)
                }
                outcome?.let { MonoText(it) }
            }
        } else {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.ccos_no_result))
        }
    }
}

/** 固定底部人审操作区：与滚动列表解耦，避免按钮被输入框/滚动遮挡。 */
@Composable
fun CcosReviewActions(
    busy: Boolean,
    outcome: String?,
    onApprove: () -> Unit,
    onReject: () -> Unit
) {
    Surface(tonalElevation = 3.dp, modifier = Modifier.navigationBarsPadding()) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            outcome?.let {
                Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary)
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !busy, onClick = onApprove) {
                    Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.ccos_submitting) else stringResource(dev.ninfenz.mobile.R.string.ccos_submit))
                }
                OutlinedButton(enabled = !busy, onClick = onReject) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.ccos_reject))
                }
            }
        }
    }
}

private data class RestoredCcos(
    val task: CcosTask?,
    val result: CcosResult?,
    val rawTask: JsonObject?,
    val findings: List<dev.ninfenz.mobile.model.CcosPrecheck.Finding>
)
