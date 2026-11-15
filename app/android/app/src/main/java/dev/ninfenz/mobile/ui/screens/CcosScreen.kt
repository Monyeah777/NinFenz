package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.model.CcosModel
import dev.ninfenz.mobile.model.CcosResult
import dev.ninfenz.mobile.model.CcosTask
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
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

@Composable
fun CcosScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var task by remember { mutableStateOf<CcosTask?>(null) }
    var result by remember { mutableStateOf<CcosResult?>(null) }
    var rawTask by remember { mutableStateOf<JsonObject?>(null) }
    var reviewer by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var outcome by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    val taskPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "ccos-task/1")
                task = CcosModel.parseTask(obj)
                rawTask = obj
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
        val decision = CcosModel.review(current, approve, reviewer, note)
        if (!decision.ok) {
            outcome = context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_not_submitted, decision.message)
            return
        }
        val reviewed = CcosModel.withReview(current, decision.state, reviewer, note)
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
                    outcome = context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_accepted, response.result?.toString() ?: context.getString(dev.ninfenz.mobile.R.string.ccos_outcome_empty))
                    result = reviewed
                } else {
                    error = response.error
                }
            } finally {
                busy = false
            }
        }
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.ccos_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.ccos_step1)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { taskPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_open_task)) }
                Button(onClick = { resultPicker.launch(arrayOf("application/json", "text/plain")) }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_open_result)) }
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
                    Text(stringResource(dev.ninfenz.mobile.R.string.ccos_status), style = MaterialTheme.typography.bodySmall)
                    NfStatusChip(r.status)
                }
                KeyValue("task_digest", r.taskDigest.take(24) + "…")
                KeyValue("artifacts", r.artifacts.size.toString())
                for (a in r.artifacts) {
                    Text(a.name + " · " + a.mime + " · " + a.bytes + " bytes", style = MaterialTheme.typography.bodySmall)
                    Text("  sha256=" + a.sha256.take(24) + "…", style = MaterialTheme.typography.labelSmall)
                }
                KeyValue("evidence", r.evidence.size.toString())
                for (e in r.evidence) {
                    Text(e.kind + " · " + e.ref + " · " + e.digest.take(16) + "…", style = MaterialTheme.typography.bodySmall)
                }
                KeyValue("report", r.reportSummary)
                for (issue in r.issues) Notice(issue.code + "：" + issue.message, Tone.WARN)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("human_review", style = MaterialTheme.typography.bodySmall)
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
                    FormTextField(label = "reviewer", value = reviewer, onValueChange = { reviewer = it })
                    FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.ccos_note_field), value = note, onValueChange = { note = it }, singleLine = false)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(enabled = !busy, onClick = { submitReview(true) }) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.ccos_submitting) else stringResource(dev.ninfenz.mobile.R.string.ccos_submit)) }
                        OutlinedButton(enabled = !busy, onClick = { submitReview(false) }) { Text(stringResource(dev.ninfenz.mobile.R.string.ccos_reject)) }
                    }
                    Notice(stringResource(dev.ninfenz.mobile.R.string.ccos_review_notice), Tone.INFO)
                }
                outcome?.let { MonoText(it) }
            }
        } else {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.ccos_no_result))
        }
    }
}
