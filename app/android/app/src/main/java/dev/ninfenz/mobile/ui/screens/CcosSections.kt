package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import dev.ninfenz.mobile.data.CcosQueueStore
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
internal fun CcosStep1Card(
    rawTask: JsonObject?,
    task: CcosTask?,
    result: CcosResult?,
    queueSize: Int,
    busy: Boolean,
    onOpenTask: () -> Unit,
    onOpenResult: () -> Unit,
    onQueueAdd: () -> Unit,
    onShowQueue: () -> Unit,
    onClearSession: () -> Unit
) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.ccos_step1)) {
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Button(onClick = onOpenTask) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_open_task)) }
            OutlinedButton(onClick = onOpenResult) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_open_result)) }
            if (rawTask != null) {
                OutlinedButton(onClick = onQueueAdd) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_queue_add)) }
            }
            OutlinedButton(onClick = onShowQueue) {
                Text(stringResource(dev.ninfenz.mobile.R.string.ccos_queue) + " (" + queueSize + ")")
            }
            if (task != null || result != null) {
                OutlinedButton(enabled = !busy, onClick = onClearSession) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_clear_session)) }
            }
        }
        Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_steps_notice), Tone.INFO)
    }
}

@Composable
internal fun CcosTaskCard(t: CcosTask) {
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
}

@Composable
internal fun CcosResultSection(
    r: CcosResult,
    precheckFindings: List<dev.ninfenz.mobile.model.CcosPrecheck.Finding>,
    reviewer: String,
    note: String,
    outcome: String?,
    onReviewerChange: (String) -> Unit,
    onNoteChange: (String) -> Unit
) {
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
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.ccos_reviewer_label), value = reviewer, onValueChange = onReviewerChange)
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.ccos_note_field), value = note, onValueChange = onNoteChange, singleLine = false)
            Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_review_notice), Tone.INFO)
        }
        outcome?.let { MonoText(it) }
    }
}

@Composable
internal fun CcosQueueDialog(
    queue: List<CcosQueueStore.Item>,
    selectedQueue: Set<String>,
    queueNote: String?,
    queueStore: CcosQueueStore,
    onSelectedQueueChange: (Set<String>) -> Unit,
    onQueueChange: (List<CcosQueueStore.Item>) -> Unit,
    onLoadTask: (CcosTask, JsonObject) -> Unit,
    onNote: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_queue)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                if (queue.isEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.ccos_queue_empty), style = NfType.meta)
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    TextButton(onClick = {
                        onSelectedQueueChange(if (selectedQueue.size == queue.size) emptySet() else queue.map { it.id }.toSet())
                    }) { Text(stringResource(if (selectedQueue.size == queue.size) dev.ninfenz.mobile.R.string.ccos_queue_select_none else dev.ninfenz.mobile.R.string.ccos_queue_select_all)) }
                    TextButton(enabled = selectedQueue.isNotEmpty(), onClick = {
                        selectedQueue.forEach { queueStore.remove(it) }
                        onSelectedQueueChange(emptySet())
                        onQueueChange(queueStore.load())
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_queue_remove_selected)) }
                }
                queue.forEach { item ->
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(
                                checked = item.id in selectedQueue,
                                onCheckedChange = { on ->
                                    onSelectedQueueChange(if (on) selectedQueue + item.id else selectedQueue - item.id)
                                }
                            )
                            Text(item.id, style = NfType.meta)
                        }
                        Row {
                            TextButton(onClick = {
                                runCatching {
                                    val obj = item.task
                                    onLoadTask(CcosModel.parseTask(obj), obj)
                                    CcosSessionStore.saveTask(context.filesDir, obj.toString())
                                }.onFailure { onNote(it.message) }
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_queue_load)) }
                            TextButton(onClick = { queueStore.remove(item.id); onQueueChange(queueStore.load()) }) {
                                Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove))
                            }
                        }
                    }
                }
                queueNote?.let { Text(it, style = NfType.meta) }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } }
    )
}

@Composable
internal fun CcosBottomBar(
    result: CcosResult?,
    busy: Boolean,
    outcome: String?,
    onApprove: () -> Unit,
    onReject: () -> Unit
) {
    val r = result
    if (r != null && r.reviewState == "pending") {
        CcosReviewActions(busy = busy, outcome = outcome, onApprove = onApprove, onReject = onReject)
    }
}

@Composable
internal fun CcosBusyTimeout(
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onOutcome: (String) -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    LaunchedEffect(busy) {
        if (busy) {
            delay(30_000)
            if (busy) {
                onBusyChange(false)
                onOutcome(context.getString(dev.ninfenz.mobile.R.string.ccos_submit_timeout))
            }
        }
    }
}
