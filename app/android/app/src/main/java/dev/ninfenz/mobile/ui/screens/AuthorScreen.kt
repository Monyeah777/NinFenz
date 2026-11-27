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

internal class ProtocolAuthorUiState(
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
