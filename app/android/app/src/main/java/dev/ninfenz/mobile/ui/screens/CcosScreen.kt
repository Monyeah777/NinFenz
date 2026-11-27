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
fun CcosScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val restored = rememberCcosSession(context)
    val ui = rememberCcosUiState(context, restored)
    var reviewer by rememberSaveable { mutableStateOf("") }
    var note by rememberSaveable { mutableStateOf("") }

    val (openTask, openResult) = rememberCcosPickers(
        context, scope, ui.task,
        onTaskLoaded = ui::onDraftLoaded,
        onResultLoaded = ui::onResultLoaded,
        onError = { ui.error = it }
    )

    CcosBusyTimeout(ui.busy, onBusyChange = { ui.busy = it }, onOutcome = { ui.outcome = it })

    NfScaffold(
        title = stringResource(dev.ninfenz.mobile.R.string.ccos_title),
        onBack = onBack,
        bottomBar = {
            CcosBottomBar(ui.result, ui.busy, ui.outcome,
                onApprove = { ui.submitReview(scope, context, reviewer, note, true) },
                onReject = { ui.submitReview(scope, context, reviewer, note, false) })
        }
    ) {
        Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_interface_notice), Tone.INFO)
        CcosStep1Card(ui.rawTask, ui.task, ui.result, ui.queue.size, ui.busy,
            onOpenTask = openTask, onOpenResult = openResult,
            onQueueAdd = { ui.enqueue() },
            onShowQueue = { ui.openQueue() },
            onClearSession = { scope.launch { ui.clearSession(context) } })

        ui.error?.let { ErrorNotice(it) }

        val t = ui.task
        if (t != null) CcosTaskCard(t) else EmptyState(stringResource(dev.ninfenz.mobile.R.string.ccos_no_task))

        val r = ui.result
        if (r != null) CcosResultSection(r, ui.precheckFindings, reviewer, note, ui.outcome, onReviewerChange = { reviewer = it }, onNoteChange = { note = it })
        else EmptyState(stringResource(dev.ninfenz.mobile.R.string.ccos_no_result))
    }
    CcosQueueHost(ui)
}

internal class CcosUiState(context: android.content.Context, restored: RestoredCcos) {
    val queueStore = CcosQueueStore(context.filesDir)
    var task by mutableStateOf(restored.task)
    var result by mutableStateOf(restored.result)
    var rawTask by mutableStateOf(restored.rawTask)
    var error by mutableStateOf<CoreError?>(null)
    var outcome by mutableStateOf<String?>(null)
    var busy by mutableStateOf(false)
    var precheckFindings by mutableStateOf(restored.findings)
    var queue by mutableStateOf(queueStore.load())
    var showQueue by mutableStateOf(false)
    var queueNote by mutableStateOf<String?>(null)
    var selectedQueue by mutableStateOf<Set<String>>(emptySet())

    fun onDraftLoaded(parsed: CcosTask, obj: JsonObject) {
        task = parsed
        rawTask = obj
        result = null
        precheckFindings = emptyList()
        outcome = null
        error = null
    }

    fun onResultLoaded(parsed: CcosResult, findings: List<dev.ninfenz.mobile.model.CcosPrecheck.Finding>) {
        result = parsed
        precheckFindings = findings
        error = null
        outcome = null
    }

    fun enqueue() {
        queue = queueStore.add(rawTask!!)
        queueNote = "queued"
    }

    fun openQueue() {
        queue = queueStore.load()
        showQueue = true
    }

    fun loadFromQueue(parsed: CcosTask, obj: JsonObject) {
        task = parsed
        rawTask = obj
        result = null
        precheckFindings = emptyList()
        showQueue = false
    }

    suspend fun clearSession(context: android.content.Context) {
        withContext(Dispatchers.IO) { CcosSessionStore.clearAll(context.filesDir) }
        task = null
        result = null
        rawTask = null
        precheckFindings = emptyList()
        outcome = null
        error = null
    }

    fun submitReview(
        scope: kotlinx.coroutines.CoroutineScope,
        context: android.content.Context,
        reviewer: String,
        note: String,
        approve: Boolean
    ) {
        val current = result ?: return
        scope.launch {
            performCcosReview(context, current, rawTask, task, reviewer, note, approve,
                onOutcome = { outcome = it }, onBusy = { busy = it }, onError = { error = it }, onResult = { result = it })
        }
    }
}

@Composable
internal fun rememberCcosUiState(context: android.content.Context, restored: RestoredCcos): CcosUiState =
    remember(restored) { CcosUiState(context, restored) }

@Composable
private fun CcosQueueHost(ui: CcosUiState) {
    if (ui.showQueue) {
        CcosQueueDialog(ui.queue, ui.selectedQueue, ui.queueNote, ui.queueStore,
            onSelectedQueueChange = { ui.selectedQueue = it }, onQueueChange = { ui.queue = it },
            onLoadTask = ui::loadFromQueue,
            onNote = { ui.queueNote = it }) { ui.showQueue = false }
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

internal data class RestoredCcos(
    val task: CcosTask?,
    val result: CcosResult?,
    val rawTask: JsonObject?,
    val findings: List<dev.ninfenz.mobile.model.CcosPrecheck.Finding>
)
