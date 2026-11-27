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

private enum class AuthorTab(val labelRes: Int) {
    PROTOCOL(dev.ninfenz.mobile.R.string.author_tab_protocol),
    GRAPH(dev.ninfenz.mobile.R.string.author_tab_graph),
    SPEC(dev.ninfenz.mobile.R.string.author_tab_spec)
}

/**
 * W4 创作台：项目头 + 协议/管线/规格三段。读取项目绑定 Pack 的只读内容，
 * 支持本地预检 + 核心 protocol-render / graph-validate / spec-validate。
 * 编辑保存（写回引用/digest）留 W4 后续；当前明确标「本地预演」。
 */
@Composable
fun AuthorScreen(project: Project, pack: PackEntry?, onBack: () -> Unit, onOpenPacks: () -> Unit = onBack, onAssembly: () -> Unit, onSaved: () -> Unit = {}) {
    if (pack == null) {
        Column(modifier = Modifier.fillMaxSize()) {
            NfTopAppBar(title = project.title, onBack = onBack)
            NfEmptyState(
                icon = Icons.Filled.Info,
                title = stringResource(dev.ninfenz.mobile.R.string.author_pack_missing_title),
                message = stringResource(dev.ninfenz.mobile.R.string.author_pack_missing_body, project.refs.basePackId, project.refs.basePackVersion),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.pack_open_center),
                onAction = onOpenPacks
            )
        }
        return
    }

    var tab by rememberSaveable { mutableIntStateOf(0) }
    var saveAndDeliverRequest by remember { mutableIntStateOf(0) }
    var saveRequest by remember { mutableIntStateOf(0) }
    val authorContext = androidx.compose.ui.platform.LocalContext.current
    val authorClipboard = androidx.compose.ui.platform.LocalClipboardManager.current
    var authorReload by remember { mutableIntStateOf(0) }
    var showRemoveOverride by remember { mutableStateOf(false) }
    val specOverride = dev.ninfenz.mobile.data.ProjectPaths.specOverride(authorContext.filesDir, project.id)
    val templateReference = remember(project.id, authorReload) {
        dev.ninfenz.mobile.data.ProjectPaths.templateMd(authorContext.filesDir, project.id)
            .takeIf { it.isFile }?.readText(Charsets.UTF_8)
    }
    var artifacts by remember { mutableStateOf<AuthorArtifacts?>(null) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(pack.dir.absolutePath, project.id, authorReload) {
        loading = true
        loadError = null
        try {
            artifacts = withContext(Dispatchers.IO) { AuthorArtifactsLoader.load(pack, specOverride) }
        } catch (t: Throwable) {
            loadError = t.message ?: t.javaClass.simpleName
        }
        loading = false
    }

    if (showRemoveOverride) {
        AlertDialog(
            onDismissRequest = { showRemoveOverride = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove_title)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove_body)) },
            confirmButton = {
                TextButton(onClick = {
                    dev.ninfenz.mobile.data.DraftProjectBinder.clearSpec(authorContext.filesDir, project.id)
                    authorReload++
                    showRemoveOverride = false
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove)) }
            },
            dismissButton = {
                TextButton(onClick = { showRemoveOverride = false }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }

    Column(modifier = Modifier.fillMaxSize().imePadding()) {
        NfTopAppBar(
            title = project.title,
            onBack = onBack,
            actions = {
                val compact = LocalDensity.current.fontScale >= 1.4f
                val onSave: () -> Unit = {
                    if (AuthorTab.entries[tab] == AuthorTab.PROTOCOL) saveRequest++
                }
                val onDeliver: () -> Unit = {
                    if (AuthorTab.entries[tab] == AuthorTab.PROTOCOL) saveAndDeliverRequest++
                    else onAssembly()
                }
                if (compact) {
                    IconButton(onClick = onSave, modifier = Modifier.size(48.dp)) {
                        Icon(Icons.Filled.Check, contentDescription = stringResource(dev.ninfenz.mobile.R.string.author_save))
                    }
                    IconButton(onClick = onDeliver, modifier = Modifier.size(48.dp)) {
                        Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = stringResource(dev.ninfenz.mobile.R.string.author_go_deliver))
                    }
                } else {
                    TextButton(onClick = onSave, modifier = Modifier.heightIn(min = 48.dp)) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.author_save))
                    }
                    TextButton(onClick = onDeliver, modifier = Modifier.heightIn(min = 48.dp)) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.author_go_deliver))
                    }
                }
            }
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            Row(
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                verticalAlignment = Alignment.CenterVertically
            ) {
                NfStatusChip(projectStatusLabel(project))
                Text(
                    stringResource(dev.ninfenz.mobile.R.string.author_pack_label, project.refs.basePackId, project.refs.basePackVersion),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                    textAlign = androidx.compose.ui.text.style.TextAlign.End
                )
            }
            if (specOverride.isFile) {
                Row(
                    modifier = Modifier.padding(horizontal = NfSpacing.page),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.template_override_active),
                        style = NfType.meta,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = { showRemoveOverride = true }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.template_override_remove))
                    }
                }
            }
            templateReference?.takeIf { it.isNotBlank() }?.let { text ->
                NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.author_template_ref), initiallyExpanded = false) {
                    TextButton(onClick = { authorClipboard.setText(androidx.compose.ui.text.AnnotatedString(text)) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.author_template_copy))
                    }
                    TextButton(onClick = {
                        val intent = dev.ninfenz.mobile.share.ShareExporter.shareMarkdown(authorContext, "nf-template", text)
                        dev.ninfenz.mobile.share.ShareExporter.launchChooser(authorContext, intent, authorContext.getString(dev.ninfenz.mobile.R.string.author_template_share))
                    }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.author_template_share))
                    }
                    MarkdownPreview(text, limitBlocks = 24)
                }
            }
            Text(
                stringResource(dev.ninfenz.mobile.R.string.author_preview_note),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
            TabRow(selectedTabIndex = tab) {
                AuthorTab.entries.forEachIndexed { index, item ->
                    Tab(selected = tab == index, onClick = { tab = index }, text = { Text(stringResource(item.labelRes)) })
                }
            }
            if (loading) NfLoadingState()
            if (loadError != null) {
                NfErrorCard(
                    "NF-PCK-003",
                    stringResource(dev.ninfenz.mobile.R.string.author_load_error, loadError!!),
                    stringResource(dev.ninfenz.mobile.R.string.author_load_fix),
                    modifier = Modifier.padding(horizontal = NfSpacing.page)
                )
            }
            val current = artifacts
            if (current != null) {
                when (AuthorTab.entries[tab]) {
                    AuthorTab.PROTOCOL -> ProtocolAuthorContent(current, project, pack, onSaved, saveRequest, saveAndDeliverRequest, onAssembly)
                    AuthorTab.GRAPH -> GraphAuthorContent(current, project, onSaved)
                    AuthorTab.SPEC -> SpecAuthorContent(current, project, onSaved)
                }
            }
        }
    }
}

@Composable
private fun ProtocolAuthorContent(
    artifacts: AuthorArtifacts,
    project: Project,
    pack: PackEntry,
    onSaved: () -> Unit,
    saveRequest: Int,
    deliverRequest: Int,
    onAssembly: () -> Unit
) {
    val ui = rememberProtocolAuthorState(artifacts, project)
    fun save(then: () -> Unit = {}) {
        saveProtocolOverlay(ui, project, pack, onSaved, then)
    }

    LaunchedEffect(saveRequest) {
        if (saveRequest > 0) save()
    }
    LaunchedEffect(deliverRequest) {
        if (deliverRequest > 0) save { onAssembly() }
    }
    LaunchedEffect(project.id, ui.values, ui.enabled, ui.edited) {
        if (ui.edited) {
            delay(500)
            ui.draftStore.save(project.id, ui.values, ui.enabled)
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        ProtocolAuthorHeader(
            ui.protocol, ui.clauseLibraries.isNotEmpty(), ui.mergedPrefill.size,
            onShowClauseLibrary = { ui.showClauseLibrary = true },
            onShowSnapshots = { ui.protocolSnapshots = ui.protocolSnapshotStore.list(); ui.showProtocolSnapshots = true }
        )
        ui.clauseNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        ProtocolClauseList(ui.protocol, ui.values, ui.enabled, onValuesChange = { ui.values = it }, onEnabledChange = { ui.enabled = it }, onPushUndo = { pushProtocolUndo(ui) })
        ProtocolSaveBar(
            ui.undo.size, ui.saving, ui.saveMessage, ui.saveError,
            onUndo = {
                val last = ui.undo.last()
                ui.undo = ui.undo.dropLast(1)
                ui.values = last.values
                ui.enabled = last.enabled
                ui.saveMessage = null
                ui.saveError = null
            },
            onSave = { save() }
        )
        ProtocolRenderSection(artifacts.protocolJson, ui.values, ui.busy, ui.renderError, ui.rendered, onBusyChange = { ui.busy = it }, onRenderError = { ui.renderError = it }, onRendered = { ui.rendered = it })
    }
    if (ui.showClauseLibrary) ProtocolClauseLibraryDialog(ui.clauseLibraries, ui.protocol, onApply = { ids, preset -> pushProtocolUndo(ui); ui.enabled = ui.enabled + ids.associateWith { true }; ui.values = ui.values + preset }, onNote = { ui.clauseNote = it }) { ui.showClauseLibrary = false }
    if (ui.showProtocolSnapshots) ProtocolSnapshotsDialog(ui.protocolSnapshots, ui.values, ui.enabled, ui.protocolSnapshotStore, onSnapshotsChange = { ui.protocolSnapshots = it }, onRestore = { snap -> pushProtocolUndo(ui); ui.values = snap.values; ui.enabled = snap.enabled }) { ui.showProtocolSnapshots = false }
}

private class ProtocolAuthorUiState(
    val protocol: ProtocolPack,
    val context: android.content.Context,
    val mergedPrefill: Map<String, String>,
    val importPrefillByLabel: Map<String, String>,
    val templatePrefill: Map<String, String>,
    val draftStore: ProtocolDraftStore,
    val draft: ProtocolDraftStore.Draft?,
    val scope: kotlinx.coroutines.CoroutineScope,
    val store: AuthorOverlayStore,
    val clauseLibraries: List<ExtensionStore.Contribution>,
    val protocolSnapshotStore: ProtocolSnapshotStore
) {
    var values by mutableStateOf(
        protocol.fields.associate {
            it.id to (draft?.values?.get(it.id) ?: mergedPrefill[it.id] ?: importPrefillByLabel[it.label] ?: templatePrefill[it.id] ?: it.defaultText ?: "")
        }
    )
    var enabled by mutableStateOf(
        protocol.clauses.associate { it.id to (draft?.enabled?.get(it.id) ?: it.enabled) }
    )
    var edited by mutableStateOf(draft != null)
    var undo by mutableStateOf<List<Snapshot>>(emptyList())
    var rendered by mutableStateOf<List<String>?>(null)
    var renderError by mutableStateOf<CoreError?>(null)
    var busy by mutableStateOf(false)
    var saving by mutableStateOf(false)
    var saveMessage by mutableStateOf(if (draft != null) context.getString(dev.ninfenz.mobile.R.string.author_draft_restored) else null)
    var saveError by mutableStateOf<String?>(null)
    var showClauseLibrary by mutableStateOf(false)
    var clauseNote by mutableStateOf<String?>(null)
    var protocolSnapshots by mutableStateOf(protocolSnapshotStore.list())
    var showProtocolSnapshots by mutableStateOf(false)
}

@Composable
private fun rememberProtocolAuthorState(artifacts: AuthorArtifacts, project: Project): ProtocolAuthorUiState {
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

private fun pushProtocolUndo(ui: ProtocolAuthorUiState) {
    ui.undo = UndoStack.push(ui.undo, Snapshot(ui.values, ui.enabled))
    ui.edited = true
}

private fun saveProtocolOverlay(
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
private fun GraphAuthorContent(artifacts: AuthorArtifacts, project: Project, onSaved: () -> Unit) {
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
        deleteGraphNode(node, graph, context, haptics, snackbar, snackbarScope,
            onApply = { apply(it) }, onRestore = { graph = it })
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

private fun deleteGraphNode(
    node: GraphNode,
    graph: PipelineGraph,
    context: android.content.Context,
    haptics: androidx.compose.ui.hapticfeedback.HapticFeedback,
    snackbar: SnackbarHostState,
    snackbarScope: kotlinx.coroutines.CoroutineScope,
    onApply: (PipelineGraph) -> Unit,
    onRestore: (PipelineGraph) -> Unit
) {
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

@Composable
private fun GraphAddEdgeForm(
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
private fun GraphUndoRedo(
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
private fun GraphValidateButton(
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
private fun GraphSaveButton(
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
private fun GraphStatus(
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
private fun GraphRecipesDialog(
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
private fun GraphSnapshotsDialog(
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

@Composable
private fun SpecAuthorContent(artifacts: AuthorArtifacts, project: Project, onSaved: () -> Unit) {
    val ui = rememberSpecAuthorState(artifacts, project)
    val capabilityRevision = rememberCapabilityRevision()
    fun apply(next: dev.ninfenz.mobile.model.MdSpec) {
        ui.undo.add(ui.spec)
        ui.redo.clear()
        ui.spec = next
    }
    val aiResultPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            ui.scope.launch {
                importAiResult(ui.context, uri, ui.aiRunStore, ui.aiRuns, { ui.aiRuns = it }, { ui.aiNote = it })
            }
        }
    }
    LaunchedEffect(ui.spec, ui.retrySave) {
        specAutoSave(ui.spec, ui.retrySave, ui.store, project, ui.context, onSaved,
            isPrimed = { ui.autoSavePrimed }, onPrimed = { ui.autoSavePrimed = true },
            onAutoSaving = { ui.autoSaving = it }, onSavedMsg = { ui.savedMsg = it }, onError = { ui.error = it })
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        SpecAuthorHeader(
            ui.spec, ui.contractJson, ui.snippets.isNotEmpty(), capabilityRevision, ui.busy, artifacts, ui.contractStore,
            ui.snapshotNote, ui.sourceNote, ui.aiNote, ui.contractNote, ui.snippetNote,
            onShowSnippets = { ui.showSnippets = true }, onReloadSnapshots = { ui.snapshots = ui.snapshotStore.list(); ui.showSnapshots = true }, onReloadSources = { ui.sources = ui.sourceStore.list(); ui.showSources = true }, onReloadAiRuns = { ui.aiRuns = ui.aiRunStore.list(); ui.showAiRuns = true },
            onBusyChange = { ui.busy = it }, onContractJsonChange = { ui.contractJson = it }, onContractValuesChange = { ui.contractValues = it }, onContractAssignmentsChange = { ui.contractAssignments = it }, onContractExplainChange = { ui.contractExplain = it }, onShowContractExplainChange = { ui.showContractExplain = it }, onContractNoteChange = { ui.contractNote = it }
        )
        SpecSectionsEditor(ui.spec, onApply = { apply(it) })
        SpecSlotsEditor(ui.spec, ui.contractValues, capabilityRevision, ui.contractStore, onApply = { apply(it) }, onContractValuesChange = { ui.contractValues = it }, onContractNoteChange = { ui.contractNote = it })
        SpecUndoRedo(ui.undo.isNotEmpty(), ui.redo.isNotEmpty(), onUndo = { val previous = ui.undo.removeAt(ui.undo.lastIndex); ui.redo.add(ui.spec); ui.spec = previous }, onRedo = { val next = ui.redo.removeAt(ui.redo.lastIndex); ui.undo.add(ui.spec); ui.spec = next })
        SpecActions(ui.spec, project, ui.store, ui.busy, ui.report, ui.autoSaving, ui.savedMsg, ui.error, onBusyChange = { ui.busy = it }, onErrorChange = { ui.error = it }, onReportChange = { ui.report = it }, onSavedMsgChange = { ui.savedMsg = it }, onSaved = onSaved, onRetry = { ui.retrySave++ })
    }
    if (ui.showSnippets) SpecSnippetsDialog(ui.snippets, ui.spec, onApply = { section, newSlots -> apply(ui.spec.copy(sections = ui.spec.sections + section, slots = ui.spec.slots + newSlots)) }, onNote = { ui.snippetNote = it }) { ui.showSnippets = false }
    if (ui.showSnapshots) SpecSnapshotsDialog(ui.snapshots, ui.spec, ui.snapshotStore, onSnapshotsChange = { ui.snapshots = it }, onApply = { apply(it) }, onNote = { ui.snapshotNote = it }) { ui.showSnapshots = false }
    if (ui.showContractExplain) SpecContractExplainDialog(ui.contractAssignments, ui.contractExplain) { ui.showContractExplain = false }
    if (ui.showSources) SpecSourcesDialog(ui.sources, ui.sourceStore, onSourcesChange = { ui.sources = it }, onNote = { ui.sourceNote = it }) { ui.showSources = false }
    if (ui.showAiRuns) SpecAiRunsDialog(ui.aiRuns, ui.aiRunStore, ui.spec, ui.sources, project, ui.busy, onBusyChange = { ui.busy = it }, onAiRunsChange = { ui.aiRuns = it }, onNote = { ui.aiNote = it }, onImportResult = { aiResultPicker.launch(arrayOf("application/json", "text/plain")) }) { ui.showAiRuns = false }
}

private class SpecAuthorUiState(
    val context: android.content.Context,
    val project: Project,
    val scope: kotlinx.coroutines.CoroutineScope,
    val store: AuthorArtifactStore,
    val snippets: List<ExtensionStore.Contribution>,
    val snapshotStore: SpecSnapshotStore,
    val contractStore: ContractIrStore,
    val sourceStore: SourceStore,
    val aiRunStore: AiRunStore,
    initialSpec: dev.ninfenz.mobile.model.MdSpec
) {
    var spec by mutableStateOf(initialSpec)
    val undo = mutableStateListOf<dev.ninfenz.mobile.model.MdSpec>()
    val redo = mutableStateListOf<dev.ninfenz.mobile.model.MdSpec>()
    var report by mutableStateOf<String?>(null)
    var error by mutableStateOf<CoreError?>(null)
    var busy by mutableStateOf(false)
    var savedMsg by mutableStateOf<String?>(null)
    var contractValues by mutableStateOf(contractStore.loadValues())
    var aiRuns by mutableStateOf(aiRunStore.list())
    var showAiRuns by mutableStateOf(false)
    var aiNote by mutableStateOf<String?>(null)
    var contractNote by mutableStateOf<String?>(null)
    var contractJson by mutableStateOf(contractStore.load())
    var contractExplain by mutableStateOf<List<String>>(emptyList())
    var contractAssignments by mutableStateOf<Map<String, String>>(emptyMap())
    var showContractExplain by mutableStateOf(false)
    var sources by mutableStateOf(sourceStore.list())
    var showSources by mutableStateOf(false)
    var sourceNote by mutableStateOf<String?>(null)
    var snapshots by mutableStateOf(snapshotStore.list())
    var showSnapshots by mutableStateOf(false)
    var snapshotNote by mutableStateOf<String?>(null)
    var showSnippets by mutableStateOf(false)
    var snippetNote by mutableStateOf<String?>(null)
    var autoSavePrimed by mutableStateOf(false)
    var autoSaving by mutableStateOf(false)
    var retrySave by mutableIntStateOf(0)
}

private suspend fun validateSpec(
    context: android.content.Context,
    spec: MdSpec,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit
) {
    val response = safeCall("spec-validate", buildJsonObject { put("spec", SpecModel.toJson(spec)) })
    if (response.ok) onReportChange(summarizeReport(context, response)) else onErrorChange(response.error)
    onBusyChange(false)
}

private suspend fun saveSpecArtifact(
    context: android.content.Context,
    store: AuthorArtifactStore,
    project: Project,
    spec: MdSpec,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onSavedMsgChange: (String?) -> Unit,
    onSaved: () -> Unit
) {
    when (val result = store.saveSpec(project, spec)) {
        is SaveArtifactResult.Saved -> {
            onSavedMsgChange(context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12)))
            onSaved()
        }
        is SaveArtifactResult.Failure -> onErrorChange(CoreError(result.code, result.message, result.fix, null, 1))
    }
    onBusyChange(false)
}

// ---- restored helpers (reconstructed after accidental truncation) ----

private data class Snapshot(val values: Map<String, String>, val enabled: Map<String, Boolean>)

private fun computeImportPrefill(context: Context, project: Project): Map<String, String> = runCatching {
    val dir = dev.ninfenz.mobile.data.ProjectPaths.authoringDir(context.filesDir, project.id)
    val file = dir.listFiles()?.firstOrNull { it.isFile && it.name.startsWith("import-") } ?: return@runCatching emptyMap()
    dev.ninfenz.mobile.data.ImportPrefill.fromJson(file.readText(Charsets.UTF_8))
}.getOrDefault(emptyMap())

private fun computeZeroSlicePrefill(context: Context, project: Project): Map<String, String> = runCatching {
    val dir = dev.ninfenz.mobile.data.ProjectPaths.authoringDir(context.filesDir, project.id)
    val file = dir.resolve("zero-slice.json")
    dev.ninfenz.mobile.data.ZeroSliceStore(context.filesDir).read(file)?.slotValues ?: emptyMap()
}.getOrDefault(emptyMap())

private fun computeTemplatePrefill(context: Context, project: Project, protocol: ProtocolPack): Map<String, String> = runCatching {
    val file = dev.ninfenz.mobile.data.ProjectPaths.templateMd(context.filesDir, project.id)
    if (!file.isFile) return@runCatching emptyMap<String, String>()
    val byName = dev.ninfenz.mobile.data.TemplateProtocolPrefill.parse(file.readText(Charsets.UTF_8))
    protocol.fields.mapNotNull { field ->
        val value = byName[field.label]?.takeIf { it.isNotBlank() } ?: return@mapNotNull null
        val allowed = when {
            field.type == "enum" -> value in field.options
            field.maxLen != null && value.length > field.maxLen -> false
            field.pattern != null && !runCatching { Regex(field.pattern).matches(value) }.getOrDefault(false) -> false
            else -> true
        }
        if (allowed) field.id to value else null
    }.toMap()
}.getOrDefault(emptyMap())

private fun summarizeReport(context: Context, response: CoreResponse): String {
    val result = response.resultObject()
    val verdict = result?.get("verdict")?.jsonPrimitive?.content ?: "pass"
    val summary = result?.get("summary")?.toString() ?: ""
    val issues = result?.get("issues")?.let { if (it is JsonArray) it.size else 0 } ?: 0
    val line = context.getString(dev.ninfenz.mobile.R.string.author_validate_result, verdict, issues)
    return line + (if (summary.isNotBlank()) " · " + summary else "")
}

@Composable
private fun ProtocolAuthorHeader(
    protocol: ProtocolPack,
    snippetsNotEmpty: Boolean,
    prefillCount: Int,
    onShowClauseLibrary: () -> Unit,
    onShowSnapshots: () -> Unit
) {
    if (prefillCount > 0) {
        Text(
            pluralStringResource(dev.ninfenz.mobile.R.plurals.author_import_prefill, prefillCount, prefillCount),
            style = NfType.meta,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(horizontal = NfSpacing.page)
        )
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_clauses, protocol.clauses.size))
        if (snippetsNotEmpty) {
            TextButton(onClick = onShowClauseLibrary) {
                Text(stringResource(dev.ninfenz.mobile.R.string.author_clause_library))
            }
        }
        TextButton(onClick = onShowSnapshots) {
            Text(stringResource(dev.ninfenz.mobile.R.string.author_protocol_snapshot))
        }
    }
}

@Composable
private fun ProtocolClauseList(
    protocol: ProtocolPack,
    values: Map<String, String>,
    enabled: Map<String, Boolean>,
    onValuesChange: (Map<String, String>) -> Unit,
    onEnabledChange: (Map<String, Boolean>) -> Unit,
    onPushUndo: () -> Unit
) {
    for (clause in protocol.clauses) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(clause.id + " · " + clause.title, style = NfType.itemTitle, modifier = Modifier.weight(1f))
                    NfStatusChip(clause.level)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_enable), style = NfType.meta, modifier = Modifier.weight(1f))
                    Switch(
                        checked = enabled[clause.id] ?: clause.enabled,
                        onCheckedChange = { checked ->
                            onPushUndo()
                            onEnabledChange(enabled + (clause.id to checked))
                        }
                    )
                }
                Text(clause.text, style = NfType.secondary)
                val check = ProtocolModel.checkClause(protocol, clause, values)
                if (!check.ok) {
                    if (check.missing.isNotEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.author_missing, check.missing.joinToString(", ")), style = NfType.meta, color = MaterialTheme.colorScheme.error)
                    if (check.unknown.isNotEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.author_unknown, check.unknown.joinToString(", ")), style = NfType.meta, color = MaterialTheme.colorScheme.error)
                }
                for (field in protocol.fields.filter { it.clause == clause.id }) {
                    Column {
                        Text(field.id + " · " + field.label + (if (field.required) stringResource(dev.ninfenz.mobile.R.string.author_required) else ""), style = NfType.label)
                        OutlinedTextField(
                            value = values[field.id] ?: "",
                            onValueChange = { text ->
                                onPushUndo()
                                onValuesChange(values + (field.id to text))
                            },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ProtocolSaveBar(
    undoSize: Int,
    saving: Boolean,
    saveMessage: String?,
    saveError: String?,
    onUndo: () -> Unit,
    onSave: () -> Unit
) {
    Row(
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
    ) {
        OutlinedButton(enabled = undoSize > 0 && !saving, onClick = onUndo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
        Button(enabled = !saving, onClick = onSave) { Text(if (saving) stringResource(dev.ninfenz.mobile.R.string.author_saving) else stringResource(dev.ninfenz.mobile.R.string.author_save)) }
    }
    saveMessage?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    saveError?.let { message ->
        NfErrorCard("NF-PCK-003", message, stringResource(dev.ninfenz.mobile.R.string.author_diag_fix), modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
}

@Composable
private fun ProtocolRenderSection(
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
private fun ProtocolClauseLibraryDialog(
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
private fun ProtocolSnapshotsDialog(
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

@Composable
private fun SpecAuthorHeader(
    spec: MdSpec,
    contractJson: JsonObject?,
    snippetsNotEmpty: Boolean,
    capabilityRevision: Int,
    busy: Boolean,
    artifacts: AuthorArtifacts,
    contractStore: ContractIrStore,
    snapshotNote: String?,
    sourceNote: String?,
    aiNote: String?,
    contractNote: String?,
    snippetNote: String?,
    onShowSnippets: () -> Unit,
    onReloadSnapshots: () -> Unit,
    onReloadSources: () -> Unit,
    onReloadAiRuns: () -> Unit,
    onBusyChange: (Boolean) -> Unit,
    onContractJsonChange: (JsonObject) -> Unit,
    onContractValuesChange: (Map<String, String>) -> Unit,
    onContractAssignmentsChange: (Map<String, String>) -> Unit,
    onContractExplainChange: (List<String>) -> Unit,
    onShowContractExplainChange: (Boolean) -> Unit,
    onContractNoteChange: (String) -> Unit
) {
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

@Composable
private fun SpecSectionsEditor(spec: MdSpec, onApply: (MdSpec) -> Unit) {
    for (section in spec.sections) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(section.id + " · order=" + section.order, style = NfType.meta)
                FormTextField(
                    label = stringResource(dev.ninfenz.mobile.R.string.author_section_title),
                    value = section.title,
                    onValueChange = { newTitle ->
                        onApply(spec.copy(sections = spec.sections.map { if (it.id == section.id) it.copy(title = newTitle) else it }))
                    }
                )
                Text(
                    stringResource(
                        dev.ninfenz.mobile.R.string.author_order,
                        section.order,
                        if (section.required) stringResource(dev.ninfenz.mobile.R.string.author_required_label) else stringResource(dev.ninfenz.mobile.R.string.author_optional_label),
                        section.slots.joinToString(",")
                    ),
                    style = NfType.meta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun SpecSlotsEditor(
    spec: MdSpec,
    contractValues: Map<String, String>,
    capabilityRevision: Int,
    contractStore: ContractIrStore,
    onApply: (MdSpec) -> Unit,
    onContractValuesChange: (Map<String, String>) -> Unit,
    onContractNoteChange: (String) -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_slots, spec.slots.size))
    for (slot in spec.slots) {
        NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(slot.id + " · " + slot.kind + (if (slot.required) " · " + stringResource(dev.ninfenz.mobile.R.string.author_required_label) else ""), style = NfType.meta)
                FormTextField(
                    label = stringResource(dev.ninfenz.mobile.R.string.author_slot_name),
                    value = slot.name,
                    onValueChange = { newName ->
                        onApply(spec.copy(slots = spec.slots.map { if (it.id == slot.id) it.copy(name = newName) else it }))
                    }
                )
                if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.CONTRACT)) {
                    FormTextField(
                        label = stringResource(dev.ninfenz.mobile.R.string.author_contract_value),
                        value = contractValues[slot.id].orEmpty(),
                        onValueChange = { value -> onContractValuesChange(contractValues + (slot.id to value)) }
                    )
                    TextButton(onClick = {
                        contractStore.saveValues(contractValues)
                        onContractValuesChange(contractStore.loadValues())
                        onContractNoteChange(context.getString(dev.ninfenz.mobile.R.string.author_contract_values_saved))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_values_save)) }
                }
            }
        }
    }
}

@Composable
private fun SpecUndoRedo(canUndo: Boolean, canRedo: Boolean, onUndo: () -> Unit, onRedo: () -> Unit) {
    Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        TextButton(enabled = canUndo, onClick = onUndo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
        TextButton(enabled = canRedo, onClick = onRedo) { Text(stringResource(dev.ninfenz.mobile.R.string.author_redo)) }
    }
}

@Composable
private fun SpecActions(
    spec: MdSpec,
    project: Project,
    store: AuthorArtifactStore,
    busy: Boolean,
    report: String?,
    autoSaving: Boolean,
    savedMsg: String?,
    error: CoreError?,
    onBusyChange: (Boolean) -> Unit,
    onErrorChange: (CoreError?) -> Unit,
    onReportChange: (String?) -> Unit,
    onSavedMsgChange: (String?) -> Unit,
    onSaved: () -> Unit,
    onRetry: () -> Unit
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
                scope.launch { validateSpec(context, spec, onBusyChange, onErrorChange, onReportChange) }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_validating) else stringResource(dev.ninfenz.mobile.R.string.author_validate_spec)) }
    }
    Button(
        enabled = !busy,
        modifier = Modifier.padding(horizontal = NfSpacing.page),
        onClick = {
            onBusyChange(true)
            onErrorChange(null)
            onSavedMsgChange(null)
            scope.launch { saveSpecArtifact(context, store, project, spec, onBusyChange, onErrorChange, onSavedMsgChange, onSaved) }
        }
    ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_saving_artifact) else stringResource(dev.ninfenz.mobile.R.string.author_save_spec)) }
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
}

@Composable
private fun SpecSnippetsDialog(
    snippets: List<ExtensionStore.Contribution>,
    spec: MdSpec,
    onApply: (dev.ninfenz.mobile.model.SpecSection, List<dev.ninfenz.mobile.model.SpecSlot>) -> Unit,
    onNote: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_snippet)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                snippets.forEach { snippet ->
                    TextButton(onClick = {
                        val sec = J.optChild(snippet.config, "section")
                        val id = sec?.let { J.optString(it, "id") }.orEmpty()
                        val slotIds = sec?.let { J.optArray(it, "slots") }
                            ?.mapNotNull { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }.orEmpty()
                        val newSlots = J.optArray(snippet.config, "slots").mapNotNull { el ->
                            val o = el as? JsonObject ?: return@mapNotNull null
                            val sid = J.optString(o, "id").orEmpty()
                            if (sid.isBlank()) return@mapNotNull null
                            dev.ninfenz.mobile.model.SpecSlot(
                                id = sid,
                                name = J.optString(o, "name").orEmpty().ifBlank { sid },
                                section = id,
                                kind = J.optString(o, "kind").orEmpty().ifBlank { "text" },
                                required = o["required"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false
                            )
                        }
                        if (id.isBlank() || slotIds.isEmpty() || spec.sections.any { it.id == id } || newSlots.any { ns -> spec.slots.any { it.id == ns.id } }) {
                            onNote(context.getString(dev.ninfenz.mobile.R.string.author_snippet_conflict))
                        } else {
                            val nextOrder = (spec.sections.maxOfOrNull { it.order } ?: 0) + 1
                            val section = dev.ninfenz.mobile.model.SpecSection(id, sec?.let { J.optString(it, "title") } ?: id, nextOrder, true, slotIds)
                            onApply(section, newSlots)
                            onNote(context.getString(dev.ninfenz.mobile.R.string.author_snippet_applied, id))
                            onDismiss()
                        }
                    }) { Text(snippet.id) }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
    )
}

@Composable
private fun SpecSnapshotsDialog(
    snapshots: List<SpecSnapshotStore.Snapshot>,
    spec: MdSpec,
    snapshotStore: SpecSnapshotStore,
    onSnapshotsChange: (List<SpecSnapshotStore.Snapshot>) -> Unit,
    onApply: (MdSpec) -> Unit,
    onNote: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                TextButton(onClick = {
                    onSnapshotsChange(snapshotStore.save(spec))
                    onNote(context.getString(dev.ninfenz.mobile.R.string.author_snapshot_save))
                }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot_save)) }
                if (snapshots.isEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot_empty), style = NfType.meta)
                } else {
                    snapshots.take(10).forEach { snapshot ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                stringResource(
                                    dev.ninfenz.mobile.R.string.author_snapshot_meta,
                                    snapshot.sections,
                                    snapshot.slots,
                                    java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(snapshot.at))
                                ),
                                style = NfType.meta,
                                modifier = Modifier.weight(1f)
                            )
                            TextButton(onClick = {
                                onApply(snapshotStore.restore(snapshot))
                                onNote(context.getString(dev.ninfenz.mobile.R.string.author_snapshot_restored))
                                onDismiss()
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_snapshot_restore)) }
                            TextButton(onClick = {
                                snapshotStore.remove(snapshot.id)
                                onSnapshotsChange(snapshotStore.list())
                            }) { Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove)) }
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
    )
}

@Composable
private fun SpecContractExplainDialog(
    contractAssignments: Map<String, String>,
    contractExplain: List<String>,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_explain_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                if (contractAssignments.isNotEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_assignments), style = NfType.label)
                    contractAssignments.toSortedMap().forEach { (key, value) ->
                        Text(key + " = " + value, style = NfType.meta)
                    }
                }
                if (contractExplain.isEmpty()) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_contract_explain_empty), style = NfType.meta)
                }
                contractExplain.forEach { line -> Text(line, style = NfType.meta) }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } }
    )
}

@Composable
private fun SpecSourcesDialog(
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

@Composable
private fun SpecAiRunsDialog(
    aiRuns: List<AiRunStore.Run>,
    aiRunStore: AiRunStore,
    spec: MdSpec,
    sources: List<SourceStore.Source>,
    project: Project,
    busy: Boolean,
    onBusyChange: (Boolean) -> Unit,
    onAiRunsChange: (List<AiRunStore.Run>) -> Unit,
    onNote: (String?) -> Unit,
    onImportResult: () -> Unit,
    onDismiss: () -> Unit
) {
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
private fun rememberSpecAuthorState(artifacts: AuthorArtifacts, project: Project): SpecAuthorUiState {
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

private suspend fun importAiResult(
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

private suspend fun specAutoSave(
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
