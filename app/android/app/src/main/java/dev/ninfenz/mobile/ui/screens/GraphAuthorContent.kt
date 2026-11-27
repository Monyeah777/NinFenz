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
internal fun rememberProtocolAuthorState(artifacts: AuthorArtifacts, project: Project): ProtocolAuthorUiState {
    val protocol = artifacts.protocol
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    val importPrefill = remember(project.id) { computeImportPrefill(context, project) }
    val zeroSlicePrefill = remember(project.id) { computeZeroSlicePrefill(context, project) }
    val mergedPrefill = importPrefill + zeroSlicePrefill
    val importPrefillByLabel = remember(mergedPrefill, artifacts.spec) {
        dev.ninfenz.mobile.data.ImportPrefill.bySlotName(mergedPrefill, artifacts.spec.slots)
    }
    val templatePrefill = remember(project.id, artifacts.protocolJson) {
        computeTemplatePrefill(context, project, protocol)
    }
    val draftStore = remember { ProtocolDraftStore(context.filesDir) }
    val draft = remember(project.id, artifacts.protocolJson) { draftStore.load(project.id) }
    val store = remember { AuthorOverlayStore(context.filesDir) }
    val clauseLibraries = remember { ExtensionStore(context.filesDir).contributions(setOf("clause_library")) }
    val protocolSnapshotStore = remember { ProtocolSnapshotStore(context.filesDir, project.id) }
    return remember(artifacts.protocolJson) {
        ProtocolAuthorUiState(
            protocol, context, mergedPrefill, importPrefillByLabel, templatePrefill,
            draftStore, draft, scope, store, clauseLibraries, protocolSnapshotStore
        )
    }
}

internal fun pushProtocolUndo(ui: ProtocolAuthorUiState) {
    ui.undo = UndoStack.push(ui.undo, Snapshot(ui.values, ui.enabled))
    ui.edited = true
}

internal fun saveProtocolOverlay(
    ui: ProtocolAuthorUiState,
    project: Project,
    pack: PackEntry,
    onSaved: () -> Unit,
    then: () -> Unit
) {
    if (ui.saving) return
    ui.saving = true
    ui.saveMessage = null
    ui.saveError = null
    ui.scope.launch {
        val result = ui.store.save(project, pack, ui.enabled, ui.values)
        when (result) {
            is SaveOverlayResult.Saved -> {
                ui.draftStore.clear(project.id)
                ui.saveMessage = ui.context.getString(dev.ninfenz.mobile.R.string.author_saved, result.status.wire, result.overlaySha256.take(12))
                onSaved()
                then()
            }
            is SaveOverlayResult.Failure -> ui.saveError = "[" + result.code + "] " + result.message + ui.context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + result.fix
        }
        ui.saving = false
    }
}

@Composable
internal fun GraphAuthorContent(artifacts: AuthorArtifacts, project: Project, onSaved: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var graph by remember(artifacts.graphJson) { mutableStateOf(artifacts.graph) }
    val undo = remember { mutableStateListOf<PipelineGraph>() }
    val redo = remember { mutableStateListOf<PipelineGraph>() }
    fun apply(next: PipelineGraph) {
        undo.add(graph)
        redo.clear()
        graph = next
    }
    val graphRecipes = remember { ExtensionStore(context.filesDir).contributions(setOf("graph_recipe")) }
    val graphSnapshotStore = remember { GraphSnapshotStore(context.filesDir, project.id) }
    var graphSnapshots by remember { mutableStateOf(graphSnapshotStore.list()) }
    var showGraphSnapshots by remember { mutableStateOf(false) }
    var graphSnapshotNote by remember { mutableStateOf<String?>(null) }
    var showGraphRecipes by remember { mutableStateOf(false) }
    var graphRecipeNote by remember { mutableStateOf<String?>(null) }
    val snackbar = remember { SnackbarHostState() }
    val haptics = LocalHapticFeedback.current
    val snackbarScope = rememberCoroutineScope()
    fun deleteNode(node: GraphNode) {
        deleteGraphNode(DeleteGraphNodeArgs(node, graph, context, haptics, snackbar, snackbarScope,
            onApply = { apply(it) }, onRestore = { graph = it }))
    }
    var report by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    var savedMsg by remember { mutableStateOf<String?>(null) }
    var nodeId by remember { mutableStateOf("") }
    var nodeTitle by remember { mutableStateOf("") }
    var nodeKind by remember { mutableStateOf("stage") }
    var nodeModule by remember { mutableStateOf("") }
    var edgeFrom by remember { mutableStateOf("") }
    var edgeTo by remember { mutableStateOf("") }
    var edgeFromPort by remember { mutableStateOf("out") }
    var edgeToPort by remember { mutableStateOf("in") }
    val scope = rememberCoroutineScope()
    val store = remember { AuthorArtifactStore(context.filesDir) }
    var autoSavePrimed by remember { mutableStateOf(false) }
    var autoSaving by remember { mutableStateOf(false) }
    var retrySave by remember { mutableIntStateOf(0) }
    LaunchedEffect(graph, retrySave) {
        graphAutoSave(graph, retrySave, store, project, context, onSaved,
            isPrimed = { autoSavePrimed }, onPrimed = { autoSavePrimed = true },
            onAutoSaving = { autoSaving = it }, onSavedMsg = { savedMsg = it }, onError = { error = it })
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        GraphNodesSection(graph, graphRecipes.isNotEmpty(), graphRecipeNote, graphSnapshotNote, onShowRecipes = { showGraphRecipes = true }, onShowSnapshots = { graphSnapshots = graphSnapshotStore.list(); showGraphSnapshots = true }, onDeleteNode = { deleteNode(it) })
        GraphEdgesSection(graph, onApply = { apply(it) })
        GraphAddNodeForm(graph, nodeId, nodeTitle, nodeKind, nodeModule, onNodeIdChange = { nodeId = it }, onNodeTitleChange = { nodeTitle = it }, onNodeKindChange = { nodeKind = it }, onNodeModuleChange = { nodeModule = it }, onAdd = { apply(it) }, onReset = { nodeId = ""; nodeTitle = ""; nodeModule = "" })
        GraphAddEdgeForm(graph, edgeFrom, edgeTo, edgeFromPort, edgeToPort, onEdgeFromChange = { edgeFrom = it }, onEdgeToChange = { edgeTo = it }, onEdgeFromPortChange = { edgeFromPort = it }, onEdgeToPortChange = { edgeToPort = it }, onAdd = { apply(it) })
        GraphUndoRedo(undo.isNotEmpty(), redo.isNotEmpty(), onUndo = { val previous = undo.removeAt(undo.lastIndex); redo.add(graph); graph = previous }, onRedo = { val next = redo.removeAt(redo.lastIndex); undo.add(graph); graph = next })
        GraphValidateButton(graph, busy, onBusyChange = { busy = it }, onErrorChange = { error = it }, onReportChange = { report = it })
        GraphSaveButton(graph, project, store, busy, onBusyChange = { busy = it }, onErrorChange = { error = it }, onSavedMsgChange = { savedMsg = it }, onSaved = onSaved)
        GraphStatus(report, autoSaving, savedMsg, error, snackbar, onRetry = { retrySave++ })
    }
    if (showGraphRecipes) GraphRecipesDialog(graphRecipes, graph, onApply = { apply(it) }, onNote = { graphRecipeNote = it }) { showGraphRecipes = false }
    if (showGraphSnapshots) GraphSnapshotsDialog(graphSnapshots, graph, graphSnapshotStore, onSnapshotsChange = { graphSnapshots = it }, onRestore = { graph = it }, onNote = { graphSnapshotNote = it }) { showGraphSnapshots = false }
}

internal data class DeleteGraphNodeArgs(
    val node: GraphNode,
    val graph: PipelineGraph,
    val context: android.content.Context,
    val haptics: androidx.compose.ui.hapticfeedback.HapticFeedback,
    val snackbar: SnackbarHostState,
    val snackbarScope: kotlinx.coroutines.CoroutineScope,
    val onApply: (PipelineGraph) -> Unit,
    val onRestore: (PipelineGraph) -> Unit,
)

private fun deleteGraphNode(args: DeleteGraphNodeArgs) = with(args) {
    val previous = graph
    haptics.performHapticFeedback(HapticFeedbackType.LongPress)
    onApply(
        graph.copy(
            nodes = graph.nodes.filter { it.id != node.id },
            edges = graph.edges.filter { it.from != node.id && it.to != node.id },
            weights = graph.weights - node.id
        )
    )
    snackbarScope.launch {
        val outcome = snackbar.showSnackbar(
            message = context.getString(dev.ninfenz.mobile.R.string.author_deleted),
            actionLabel = context.getString(dev.ninfenz.mobile.R.string.author_undo),
            duration = androidx.compose.material3.SnackbarDuration.Short
        )
        if (outcome == SnackbarResult.ActionPerformed) {
            onRestore(previous)
        }
    }
}

private suspend fun graphAutoSave(
    graph: PipelineGraph,
    retrySave: Int,
    store: AuthorArtifactStore,
    project: Project,
    context: android.content.Context,
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
        when (val result = store.saveGraph(project, graph)) {
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
private fun GraphNodesSection(
    graph: PipelineGraph,
    recipesNotEmpty: Boolean,
    recipeNote: String?,
    snapshotNote: String?,
    onShowRecipes: () -> Unit,
    onShowSnapshots: () -> Unit,
    onDeleteNode: (GraphNode) -> Unit
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_nodes, graph.nodes.size))
        if (recipesNotEmpty) {
            TextButton(onClick = onShowRecipes) {
                Text(stringResource(dev.ninfenz.mobile.R.string.author_graph_recipe))
            }
        }
        TextButton(onClick = onShowSnapshots) { Text(stringResource(dev.ninfenz.mobile.R.string.author_graph_snapshot)) }
    }
    recipeNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    snapshotNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    for (node in graph.nodes) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(node.id + " · " + node.title, style = NfType.itemTitle, modifier = Modifier.weight(1f))
                    NfStatusChip(node.kind)
                    TextButton(onClick = { onDeleteNode(node) }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_delete)) }
                }
                Text(
                    stringResource(
                        dev.ninfenz.mobile.R.string.author_module,
                        node.moduleId ?: stringResource(dev.ninfenz.mobile.R.string.author_not_bound),
                        node.portsIn.joinToString(","),
                        node.portsOut.joinToString(",")
                    ),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                graph.weights[node.id]?.let { Text(stringResource(dev.ninfenz.mobile.R.string.author_weight, it), style = NfType.meta) }
            }
        }
    }
}

@Composable
private fun GraphEdgesSection(graph: PipelineGraph, onApply: (PipelineGraph) -> Unit) {
    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_edges, graph.edges.size))
    for (edge in graph.edges) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Text(
                edge.from + "." + edge.fromPort + " → " + edge.to + "." + edge.toPort + "（" + edge.type + "）",
                style = NfType.meta,
                modifier = Modifier.weight(1f)
            )
            TextButton(onClick = { onApply(graph.copy(edges = graph.edges.filter { it.id != edge.id })) }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.author_delete))
            }
        }
    }
}

@Composable
private fun GraphAddNodeForm(
    graph: PipelineGraph,
    nodeId: String,
    nodeTitle: String,
    nodeKind: String,
    nodeModule: String,
    onNodeIdChange: (String) -> Unit,
    onNodeTitleChange: (String) -> Unit,
    onNodeKindChange: (String) -> Unit,
    onNodeModuleChange: (String) -> Unit,
    onAdd: (PipelineGraph) -> Unit,
    onReset: () -> Unit
) {
    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_add_node))
    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs), modifier = Modifier.padding(horizontal = NfSpacing.page)) {
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_id), value = nodeId, onValueChange = onNodeIdChange)
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_title), value = nodeTitle, onValueChange = onNodeTitleChange)
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_kind), value = nodeKind, onValueChange = onNodeKindChange)
        FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_module), value = nodeModule, onValueChange = onNodeModuleChange)
        Button(onClick = {
            if (nodeId.isNotBlank()) {
                val module = nodeModule.trim().ifBlank { null }
                onAdd(
                    graph.copy(
                        nodes = graph.nodes + GraphNode(
                            id = nodeId.trim(), kind = nodeKind.trim().ifBlank { "stage" },
                            title = nodeTitle.trim().ifBlank { nodeId.trim() },
                            portsIn = emptyList(), portsOut = listOf("out"),
                            moduleId = module, moduleVersion = null, moduleDigest = null
                        )
                    )
                )
            onReset()
            }
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_add_node)) }
    }
}
