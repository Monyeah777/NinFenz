package dev.ninfenz.mobile.ui.screens
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.TextButton
import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AiRunStore
import dev.ninfenz.mobile.data.AuthorArtifactStore
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.ContractIrStore
import dev.ninfenz.mobile.data.GraphSnapshotStore
import dev.ninfenz.mobile.data.SourceStore
import dev.ninfenz.mobile.data.SpecSnapshotStore
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.SaveArtifactResult
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.AuthorOverlayStore
import dev.ninfenz.mobile.data.ProtocolDraftStore
import dev.ninfenz.mobile.data.ProtocolSnapshotStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.SaveOverlayResult
import dev.ninfenz.mobile.model.CcosModel
import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.ContextBudget
import dev.ninfenz.mobile.model.GraphEdge
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.GraphNode
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.SpecSection
import dev.ninfenz.mobile.model.SpecSlot
import dev.ninfenz.mobile.model.ProtocolModel
import dev.ninfenz.mobile.model.ProtocolPack
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.FormTextField
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfLoadingState
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

@Composable
internal fun SpecSourcesDialog(
    sources: List<SourceStore.Source>,
    sourceStore: SourceStore,
    onSourcesChange: (List<SourceStore.Source>) -> Unit,
    onNote: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_sources)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                TextButton(onClick = {
                    val text = clipboard.getText()?.text.orEmpty()
                    if (text.isNotBlank()) {
                        val title = text.lineSequence().firstOrNull { it.isNotBlank() }?.trim()?.take(80).orEmpty()
                        sourceStore.add(title, text)
                        onSourcesChange(sourceStore.list())
                        onNote(context.getString(dev.ninfenz.mobile.R.string.author_source_added))
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_source_add)) }
                SourceChainInfo(sourceStore, onNote)
                if (sources.isEmpty()) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.author_source_empty),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                sources.forEach { source ->
                    SourceRow(source, sourceStore, clipboard, onSourcesChange, onNote)
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } }
    )
}

internal data class SpecAiRunsDialogArgs(
    val aiRuns: List<AiRunStore.Run>,
    val aiRunStore: AiRunStore,
    val spec: MdSpec,
    val sources: List<SourceStore.Source>,
    val project: Project,
    val busy: Boolean,
    val onBusyChange: (Boolean) -> Unit,
    val onAiRunsChange: (List<AiRunStore.Run>) -> Unit,
    val onNote: (String?) -> Unit,
    val onImportResult: () -> Unit,
    val onDismiss: () -> Unit,
)

@Composable
internal fun SpecAiRunsDialog(args: SpecAiRunsDialogArgs) = with(args) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_ai_plan)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                val aiContext = remember(spec.sections, sources) {
                    ContextBudget.pack(
                        sections = spec.sections.map { it.id to it.title },
                        sources = sources.map { it.excerpt },
                        budgetTokens = 2000
                    )
                }
                Text(
                    stringResource(
                        dev.ninfenz.mobile.R.string.author_ai_budget,
                        aiContext.usedTokens,
                        aiContext.budgetTokens
                    ),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                TextButton(enabled = !busy, onClick = {
                    scope.launch {
                        generateAiPlan(context, project, spec, aiContext, aiRunStore, onBusyChange, onAiRunsChange, onNote)
                    }
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_ai_generate)) }
                TextButton(onClick = onImportResult) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_ai_import_result))
                }
                if (aiRuns.isEmpty()) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.author_ai_empty),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                aiRuns.forEach { run ->
                    AiRunRow(run, aiRunStore, onAiRunsChange)
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } }
    )
}

@Composable
internal fun rememberSpecAuthorState(artifacts: AuthorArtifacts, project: Project): SpecAuthorUiState {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { AuthorArtifactStore(context.filesDir) }
    val snippets = remember { ExtensionStore(context.filesDir).contributions(setOf("spec_snippet")) }
    val snapshotStore = remember { SpecSnapshotStore(context.filesDir, project.id) }
    val contractStore = remember { ContractIrStore(context.filesDir, project.id) }
    val sourceStore = remember { SourceStore(context.filesDir, project.id) }
    val aiRunStore = remember { AiRunStore(context.filesDir) }
    return remember(artifacts.specJson) {
        SpecAuthorUiState(context, project, scope, store, snippets, snapshotStore, contractStore,
            sourceStore, aiRunStore, artifacts.spec)
    }
}

internal suspend fun importAiResult(
    context: Context,
    uri: Uri,
    aiRunStore: AiRunStore,
    aiRuns: List<AiRunStore.Run>,
    onRuns: (List<AiRunStore.Run>) -> Unit,
    onNote: (String?) -> Unit
) {
    runCatching {
        val text = FileAccess.readText(context, uri)
        val result = CcosModel.parseResult(text)
        val latest = aiRuns.firstOrNull()
            ?: throw IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.author_ai_no_run))
        aiRunStore.save(aiRunStore.applyResult(latest.json, result))
        onRuns(aiRunStore.list())
        onNote(context.getString(dev.ninfenz.mobile.R.string.author_ai_result_applied))
    }.onFailure {
        onNote(context.getString(
            dev.ninfenz.mobile.R.string.author_ai_result_failed,
            it.message ?: it.javaClass.simpleName
        ))
    }
}

internal suspend fun specAutoSave(
    spec: MdSpec,
    retrySave: Int,
    store: AuthorArtifactStore,
    project: Project,
    context: Context,
    onSaved: () -> Unit,
    isPrimed: () -> Boolean,
    onPrimed: () -> Unit,
    onAutoSaving: (Boolean) -> Unit,
    onSavedMsg: (String?) -> Unit,
    onError: (CoreError?) -> Unit
) {
    if (!isPrimed()) {
        onPrimed()
    } else {
        onAutoSaving(true)
        delay(900)
        when (val result = store.saveSpec(project, spec)) {
            is SaveArtifactResult.Saved -> {
                onSavedMsg(context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12)))
                onSaved()
            }
            is SaveArtifactResult.Failure -> onError(CoreError(result.code, result.message, result.fix, null, 1))
        }
        onAutoSaving(false)
    }
}

@Composable
private fun SourceChainInfo(sourceStore: SourceStore, onNote: (String?) -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val chain = sourceStore.chain()
    Text(
        stringResource(
            dev.ninfenz.mobile.R.string.author_source_chain,
            chain.size,
            if (sourceStore.chainOk()) stringResource(dev.ninfenz.mobile.R.string.author_source_chain_ok)
            else stringResource(dev.ninfenz.mobile.R.string.author_source_chain_bad)
        ),
        style = NfType.meta,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
    TextButton(onClick = {
        onNote(context.getString(
            if (sourceStore.chainOk()) dev.ninfenz.mobile.R.string.author_source_chain_ok
            else dev.ninfenz.mobile.R.string.author_source_chain_bad
        ))
    }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_source_chain_verify)) }
}

@Composable
private fun SourceRow(
    source: SourceStore.Source,
    sourceStore: SourceStore,
    clipboard: androidx.compose.ui.platform.ClipboardManager,
    onSourcesChange: (List<SourceStore.Source>) -> Unit,
    onNote: (String?) -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(modifier = Modifier.weight(1f)) {
            Text(source.title, style = NfType.body)
            Text(
                stringResource(dev.ninfenz.mobile.R.string.author_source_meta, source.status, source.sha256.take(12)),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        TextButton(onClick = {
            clipboard.setText(androidx.compose.ui.text.AnnotatedString(sourceStore.citation(source.id)))
            onNote(context.getString(dev.ninfenz.mobile.R.string.author_source_cited))
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_source_cite)) }
        TextButton(onClick = {
            sourceStore.remove(source.id)
            onSourcesChange(sourceStore.list())
            onNote(context.getString(dev.ninfenz.mobile.R.string.author_source_deleted))
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_source_delete)) }
    }
}

private suspend fun generateAiPlan(
    context: Context,
    project: Project,
    spec: MdSpec,
    aiContext: dev.ninfenz.mobile.model.ContextPack,
    aiRunStore: AiRunStore,
    onBusyChange: (Boolean) -> Unit,
    onAiRunsChange: (List<AiRunStore.Run>) -> Unit,
    onNote: (String?) -> Unit
) {
    onBusyChange(true)
    try {
        val response = safeCall("ai-plan", buildJsonObject {
            put("project_id", project.id)
            put("model", "ccos-task")
            put("params", buildJsonObject {
                put("budget_tokens", aiContext.budgetTokens)
                put("context_tokens", aiContext.usedTokens)
                put("trimmed", aiContext.trimmed)
            })
            put("sections", kotlinx.serialization.json.buildJsonArray {
                spec.sections.forEach { section ->
                    add(buildJsonObject { put("title", section.title) })
                }
            })
        })
        if (!response.ok) throw IllegalStateException(response.error?.message ?: "ai-plan failed")
        val run = response.resultObject() ?: throw IllegalStateException(context.getString(dev.ninfenz.mobile.R.string.author_ai_empty_result))
        aiRunStore.save(run)
        onAiRunsChange(aiRunStore.list())
        val count = (run["tasks"] as? kotlinx.serialization.json.JsonArray)?.size ?: 0
        onNote(context.getString(dev.ninfenz.mobile.R.string.author_ai_planned, count))
    } catch (t: Throwable) {
        onNote(context.getString(
            dev.ninfenz.mobile.R.string.author_ai_failed,
            t.message ?: t.javaClass.simpleName
        ))
    } finally {
        onBusyChange(false)
    }
}

@Composable
private fun AiRunRow(run: AiRunStore.Run, aiRunStore: AiRunStore, onAiRunsChange: (List<AiRunStore.Run>) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            stringResource(dev.ninfenz.mobile.R.string.author_ai_meta, run.status, run.tasks),
            style = NfType.meta,
            modifier = Modifier.weight(1f)
        )
        TextButton(onClick = {
            aiRunStore.delete(run.id)
            onAiRunsChange(aiRunStore.list())
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_source_delete)) }
    }
}
