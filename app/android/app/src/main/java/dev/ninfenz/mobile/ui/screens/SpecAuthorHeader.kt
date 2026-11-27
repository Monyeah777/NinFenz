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
internal fun ProtocolRenderSection(
    protocolJson: JsonObject,
    values: Map<String, String>,
    busy: Boolean,
    renderError: CoreError?,
    rendered: List<String>?,
    onBusyChange: (Boolean) -> Unit,
    onRenderError: (CoreError?) -> Unit,
    onRendered: (List<String>?) -> Unit
) {
    val scope = rememberCoroutineScope()
    Button(
        enabled = !busy,
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        onClick = {
            onBusyChange(true)
            onRenderError(null)
            scope.launch {
                val payload = buildJsonObject {
                    put("pack", protocolJson)
                    put("values", buildJsonObject { for ((k, v) in values) put(k, v) })
                }
                val response: CoreResponse = safeCall("protocol-render", payload)
                if (response.ok) {
                    val clauses = response.resultObject()?.get("clauses")?.jsonArray
                    onRendered(clauses?.mapNotNull { element ->
                        (element as? JsonObject)?.let { J.optString(it, "id") + "：" + J.optString(it, "text") }
                    } ?: emptyList())
                } else {
                    onRenderError(response.error)
                }
                onBusyChange(false)
            }
        }
    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_rendering) else stringResource(dev.ninfenz.mobile.R.string.author_render)) }
    renderError?.let { error ->
        NfErrorCard(error.code, error.message, error.fix, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    rendered?.let { lines ->
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_render_results, lines.size))
        for (line in lines) {
            Text(line, style = NfType.secondary, modifier = Modifier.padding(horizontal = NfSpacing.page))
        }
    }
}

@Composable
internal fun ProtocolClauseLibraryDialog(
    clauseLibraries: List<ExtensionStore.Contribution>,
    protocol: ProtocolPack,
    onApply: (List<String>, Map<String, String>) -> Unit,
    onNote: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_clause_library)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                clauseLibraries.forEach { library ->
                    TextButton(onClick = {
                        val ids = J.optArray(library.config, "clauses")
                            .mapNotNull { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }
                            .filter { id -> protocol.clauses.any { it.id == id } }
                        val presetValues = J.optChild(library.config, "values")?.let { obj ->
                            protocol.fields.mapNotNull { field ->
                                J.optString(obj, field.id)?.let { field.id to it }
                            }.toMap()
                        }.orEmpty()
                        if (ids.isEmpty() && presetValues.isEmpty()) {
                            onNote(context.getString(dev.ninfenz.mobile.R.string.author_snippet_conflict))
                        } else {
                            onApply(ids, presetValues)
                            onNote(context.getString(dev.ninfenz.mobile.R.string.author_clause_applied, library.id))
                            onDismiss()
                        }
                    }) { Text(library.id) }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
    )
}

@Composable
internal fun ProtocolSnapshotsDialog(
    snapshots: List<ProtocolSnapshotStore.Snapshot>,
    values: Map<String, String>,
    enabled: Map<String, Boolean>,
    snapshotStore: ProtocolSnapshotStore,
    onSnapshotsChange: (List<ProtocolSnapshotStore.Snapshot>) -> Unit,
    onRestore: (ProtocolSnapshotStore.Snapshot) -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_protocol_snapshot)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                TextButton(onClick = {
                    onSnapshotsChange(snapshotStore.save(values, enabled))
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_protocol_snapshot_save)) }
                if (snapshots.isEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_protocol_snapshot_empty), style = NfType.meta)
                }
                snapshots.take(10).forEach { snapshot ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            stringResource(
                                dev.ninfenz.mobile.R.string.author_protocol_snapshot_meta,
                                snapshot.values.size,
                                snapshot.enabled.count { it.value }
                            ) + " · " + java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(snapshot.at)),
                            style = NfType.meta,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = {
                            onRestore(snapshot)
                            onDismiss()
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_protocol_snapshot_restore)) }
                        TextButton(onClick = {
                            snapshotStore.remove(snapshot.id)
                            onSnapshotsChange(snapshotStore.list())
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove)) }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
    )
}

internal data class SpecAuthorHeaderArgs(
    val spec: MdSpec,
    val contractJson: JsonObject?,
    val snippetsNotEmpty: Boolean,
    val capabilityRevision: Int,
    val busy: Boolean,
    val artifacts: AuthorArtifacts,
    val contractStore: ContractIrStore,
    val snapshotNote: String?,
    val sourceNote: String?,
    val aiNote: String?,
    val contractNote: String?,
    val snippetNote: String?,
    val onShowSnippets: () -> Unit,
    val onReloadSnapshots: () -> Unit,
    val onReloadSources: () -> Unit,
    val onReloadAiRuns: () -> Unit,
    val onBusyChange: (Boolean) -> Unit,
    val onContractJsonChange: (JsonObject) -> Unit,
    val onContractValuesChange: (Map<String, String>) -> Unit,
    val onContractAssignmentsChange: (Map<String, String>) -> Unit,
    val onContractExplainChange: (List<String>) -> Unit,
    val onShowContractExplainChange: (Boolean) -> Unit,
    val onContractNoteChange: (String) -> Unit,
)

@Composable
internal fun SpecAuthorHeader(args: SpecAuthorHeaderArgs) = with(args) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_sections, spec.sections.size))
        if (snippetsNotEmpty) {
            TextButton(onClick = onShowSnippets) {
                Text(stringResource(dev.ninfenz.mobile.R.string.author_snippet))
            }
        }
        TextButton(onClick = onReloadSnapshots) {
            Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot))
        }
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.CONTRACT)) TextButton(enabled = !busy, onClick = {
            scope.launch {
                compileContract(context, contractStore, artifacts, onBusyChange, onContractJsonChange, onContractNoteChange)
            }
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_contract)) }
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.CONTRACT)) TextButton(enabled = !busy, onClick = {
            scope.launch {
                solveContract(
                    context, contractStore, contractJson, onBusyChange,
                    onContractAssignmentsChange, onContractValuesChange, onContractNoteChange,
                    onContractExplainChange, onShowContractExplainChange
                )
            }
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_solve)) }
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.SOURCES)) TextButton(onClick = onReloadSources) { Text(stringResource(dev.ninfenz.mobile.R.string.author_sources)) }
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.AI)) TextButton(onClick = onReloadAiRuns) { Text(stringResource(dev.ninfenz.mobile.R.string.author_ai_plan)) }
    }
    SpecAuthorNotes(snapshotNote, sourceNote, aiNote, contractNote, snippetNote)
}

@Composable
private fun SpecAuthorNotes(
    snapshotNote: String?,
    sourceNote: String?,
    aiNote: String?,
    contractNote: String?,
    snippetNote: String?
) {
    snapshotNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    sourceNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    aiNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    contractNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    snippetNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
}

private suspend fun compileContract(
    context: Context,
    contractStore: ContractIrStore,
    artifacts: AuthorArtifacts,
    onBusyChange: (Boolean) -> Unit,
    onContractJsonChange: (JsonObject) -> Unit,
    onContractNoteChange: (String) -> Unit
) {
    onBusyChange(true)
    contractStore.compile(artifacts.specJson, artifacts.protocolJson)
        .onSuccess { compiled ->
            onContractJsonChange(compiled.contract)
            val slots = compiled.contract["slots"]?.let { element ->
                (element as? kotlinx.serialization.json.JsonArray)?.size ?: 0
            } ?: 0
            onContractNoteChange(context.getString(dev.ninfenz.mobile.R.string.author_contract_done, slots))
        }
        .onFailure {
            onContractNoteChange(context.getString(
                dev.ninfenz.mobile.R.string.author_contract_failed,
                it.message ?: it.javaClass.simpleName
            ))
        }
    onBusyChange(false)
}

private suspend fun solveContract(
    context: Context,
    contractStore: ContractIrStore,
    contractJson: JsonObject?,
    onBusyChange: (Boolean) -> Unit,
    onContractAssignmentsChange: (Map<String, String>) -> Unit,
    onContractValuesChange: (Map<String, String>) -> Unit,
    onContractNoteChange: (String) -> Unit,
    onContractExplainChange: (List<String>) -> Unit,
    onShowContractExplainChange: (Boolean) -> Unit
) {
    onBusyChange(true)
    val contract = contractJson ?: contractStore.load()
    if (contract == null) {
        onContractNoteChange(context.getString(dev.ninfenz.mobile.R.string.author_contract_missing))
    } else {
        val solved = safeCall("contract-solve", buildJsonObject { put("contract", contract) })
        val result = solved.resultObject()
        if (!solved.ok || result == null) {
            onContractNoteChange(context.getString(
                dev.ninfenz.mobile.R.string.author_contract_failed,
                solved.error?.message ?: "contract-solve failed"
            ))
        } else {
            contractStore.saveSolve(result)
            val assignments = (result["assignments"] as? JsonObject)?.mapValues { (_, value) -> value.jsonPrimitive.content }.orEmpty()
            onContractAssignmentsChange(assignments)
            if (assignments.isNotEmpty()) {
                contractStore.saveValues(assignments)
                onContractValuesChange(contractStore.loadValues())
            }
            onContractNoteChange(context.getString(dev.ninfenz.mobile.R.string.author_contract_solved))
            val explained = safeCall("contract-explain", buildJsonObject { put("result", result) })
            onContractExplainChange(explained.resultObject()?.get("lines")?.jsonArray
                ?.map { it.jsonPrimitive.content }
                .orEmpty())
            onShowContractExplainChange(true)
        }
    }
    onBusyChange(false)
}
