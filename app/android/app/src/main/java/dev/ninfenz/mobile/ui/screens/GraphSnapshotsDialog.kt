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
internal fun GraphAddEdgeForm(
    graph: PipelineGraph,
    edgeFrom: String,
    edgeTo: String,
    edgeFromPort: String,
    edgeToPort: String,
    onEdgeFromChange: (String) -> Unit,
    onEdgeToChange: (String) -> Unit,
    onEdgeFromPortChange: (String) -> Unit,
    onEdgeToPortChange: (String) -> Unit,
    onAdd: (PipelineGraph) -> Unit
) {
    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_add_edge))
    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs), modifier = Modifier.padding(horizontal = NfSpacing.page)) {
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_from), value = edgeFrom, onValueChange = onEdgeFromChange)
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_to), value = edgeTo, onValueChange = onEdgeToChange)
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_from_port), value = edgeFromPort, onValueChange = onEdgeFromPortChange)
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_to_port), value = edgeToPort, onValueChange = onEdgeToPortChange)
        Button(onClick = {
            if (edgeFrom.isNotBlank() && edgeTo.isNotBlank()) {
                val next = (graph.edges.mapNotNull { Regex("E(\\d+)").matchEntire(it.id)?.groupValues?.get(1)?.toIntOrNull() }.maxOrNull() ?: 0) + 1
                val id = "E" + next.toString().padStart(2, '0')
                onAdd(
                    graph.copy(
                        edges = graph.edges + GraphEdge(
                            id = id, from = edgeFrom.trim(), to = edgeTo.trim(),
                            fromPort = edgeFromPort.trim(), toPort = edgeToPort.trim(), type = "data"
                        )
                    )
                )
            }
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_add_edge)) }
    }
}

@Composable
internal fun GraphUndoRedo(
    undoNotEmpty: Boolean,
    redoNotEmpty: Boolean,
    onUndo: () -> Unit,
    onRedo: () -> Unit
) {
    Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        TextButton(enabled = undoNotEmpty, onClick = onUndo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
        TextButton(enabled = redoNotEmpty, onClick = onRedo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_redo)) }
    }
}

@Composable
internal fun GraphValidateButton(
    graph: PipelineGraph,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    if (dev.ninfenz.mobile.data.FeatureGate.auditEnabled()) {
    Button(
        enabled = !busy,
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        onClick = {
            onBusyChange(true)
            onErrorChange(null)
            onReportChange(null)
            scope.launch {
                val response = safeCall("graph-validate", buildJsonObject { put("graph", GraphModel.toJson(graph)) })
                if (response.ok) onReportChange(summarizeReport(context, response)) else onErrorChange(response.error)
                onBusyChange(false)
            }
        }
    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_validating) else stringResource(dev.ninfenz.mobile.R.string.author_validate_graph)) }
    }
}

@Composable
internal fun GraphSaveButton(
    graph: PipelineGraph,
    project: Project,
    store: AuthorArtifactStore,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onSavedMsgChange: (String?) -> Unit,
    onSaved: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    Button(
        enabled = !busy,
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        onClick = {
            onBusyChange(true)
            onErrorChange(null)
            onSavedMsgChange(null)
            scope.launch {
                when (val result = store.saveGraph(project, graph)) {
                    is SaveArtifactResult.Saved -> {
                        onSavedMsgChange(context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12)))
                        onSaved()
                    }
                    is SaveArtifactResult.Failure -> onErrorChange(CoreError(result.code, result.message, result.fix, null, 1))
                }
                onBusyChange(false)
            }
        }
    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_saving_artifact) else stringResource(dev.ninfenz.mobile.R.string.author_save_graph)) }
}

@Composable
internal fun GraphStatus(
    report: String?,
    autoSaving: Boolean,
    savedMsg: String?,
    error: CoreError?,
    snackbar: SnackbarHostState,
    onRetry: () -> Unit
) {
    report?.let { text -> Text(text, style = NfType.secondary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    if (autoSaving) {
        Text(stringResource(dev.ninfenz.mobile.R.string.author_autosave_saving), style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
    savedMsg?.let { text -> Text(text, style = NfType.secondary, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    error?.let { err ->
        NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page))
        TextButton(onClick = onRetry, modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Text(stringResource(dev.ninfenz.mobile.R.string.author_retry_save))
        }
    }
    SnackbarHost(hostState = snackbar, modifier = Modifier.padding(horizontal = NfSpacing.page))
}

@Composable
internal fun GraphRecipesDialog(
    graphRecipes: List<ExtensionStore.Contribution>,
    graph: PipelineGraph,
    onApply: (PipelineGraph) -> Unit,
    onNote: (String) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_graph_recipe)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                graphRecipes.forEach { recipe ->
                    TextButton(onClick = {
                        applyGraphRecipe(recipe, graph, context, onApply, onNote, onDismiss)
                    }) { Text(recipe.id) }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
    )
}

private fun applyGraphRecipe(
    recipe: ExtensionStore.Contribution,
    graph: PipelineGraph,
    context: android.content.Context,
    onApply: (PipelineGraph) -> Unit,
    onNote: (String) -> Unit,
    onDismiss: () -> Unit
) {
    val nodes = J.optArray(recipe.config, "nodes").mapNotNull { el ->
        val o = el as? JsonObject ?: return@mapNotNull null
        val id = J.optString(o, "id").orEmpty()
        if (!GraphModel.NODE_ID.matches(id)) return@mapNotNull null
        val ports = J.optChild(o, "ports")
        val ref = J.optChild(o, "module_ref")
        GraphNode(
            id = id,
            kind = J.optString(o, "kind").orEmpty().ifBlank { "process" },
            title = J.optString(o, "title").orEmpty().ifBlank { id },
            portsIn = ports?.let { J.optStringList(it, "in") }.orEmpty(),
            portsOut = ports?.let { J.optStringList(it, "out") }.orEmpty(),
            moduleId = ref?.let { J.optString(it, "id") },
            moduleVersion = ref?.let { J.optString(it, "version") },
            moduleDigest = ref?.let { J.optString(it, "digest") }
        )
    }
    val edges = J.optArray(recipe.config, "edges").mapNotNull { el ->
        val o = el as? JsonObject ?: return@mapNotNull null
        val id = J.optString(o, "id").orEmpty()
        if (!GraphModel.EDGE_ID.matches(id)) return@mapNotNull null
        GraphEdge(
            id = id,
            from = J.optString(o, "from").orEmpty(),
            to = J.optString(o, "to").orEmpty(),
            fromPort = J.optString(o, "from_port").orEmpty(),
            toPort = J.optString(o, "to_port").orEmpty(),
            type = J.optString(o, "type").orEmpty().ifBlank { "data" }
        )
    }
    val conflict = nodes.isEmpty() || nodes.any { n -> graph.nodes.any { it.id == n.id } } ||
        edges.any { e -> graph.edges.any { it.id == e.id } } ||
        edges.any { e -> nodes.none { it.id == e.from } && graph.nodes.none { it.id == e.from } } ||
        edges.any { e -> nodes.none { it.id == e.to } && graph.nodes.none { it.id == e.to } }
    if (conflict) {
        onNote(context.getString(dev.ninfenz.mobile.R.string.author_graph_recipe_conflict))
    } else {
        onApply(graph.copy(nodes = graph.nodes + nodes, edges = graph.edges + edges))
        onNote(context.getString(dev.ninfenz.mobile.R.string.author_graph_recipe_applied, recipe.id))
        onDismiss()
    }
}

@Composable
internal fun GraphSnapshotsDialog(
    snapshots: List<GraphSnapshotStore.Snapshot>,
    graph: PipelineGraph,
    graphSnapshotStore: GraphSnapshotStore,
    onSnapshotsChange: (List<GraphSnapshotStore.Snapshot>) -> Unit,
    onRestore: (PipelineGraph) -> Unit,
    onNote: (String) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_graph_snapshot)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                TextButton(onClick = {
                    onSnapshotsChange(graphSnapshotStore.save(graph))
                    onNote(context.getString(dev.ninfenz.mobile.R.string.author_graph_snapshot_saved))
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_graph_snapshot_save)) }
                if (snapshots.isEmpty()) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.author_graph_snapshot_empty),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                snapshots.forEach { snapshot ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            stringResource(
                                dev.ninfenz.mobile.R.string.author_graph_snapshot_meta,
                                snapshot.nodes,
                                snapshot.edges
                            ),
                            style = NfType.meta,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = {
                            onRestore(graphSnapshotStore.restore(snapshot))
                            onDismiss()
                            onNote(context.getString(dev.ninfenz.mobile.R.string.author_graph_snapshot_restored))
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_graph_snapshot_restore)) }
                        TextButton(onClick = {
                            graphSnapshotStore.remove(snapshot.id)
                            onSnapshotsChange(graphSnapshotStore.list())
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_graph_snapshot_delete)) }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } }
    )
}
