package dev.ninfenz.mobile.ui.screens

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
import dev.ninfenz.mobile.data.AuthorArtifactStore
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.SaveArtifactResult
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.AuthorOverlayStore
import dev.ninfenz.mobile.data.ProtocolDraftStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.SaveOverlayResult
import dev.ninfenz.mobile.model.GraphEdge
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.GraphNode
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.SpecSection
import dev.ninfenz.mobile.model.SpecSlot
import dev.ninfenz.mobile.model.ProtocolModel
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
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
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
    val specOverride = java.io.File(java.io.File(java.io.File(authorContext.filesDir, "projects"), project.id), "authoring/spec-override.json")
    val templateReference = remember(project.id, authorReload) {
        java.io.File(java.io.File(java.io.File(authorContext.filesDir, "projects"), project.id), "authoring/template.md")
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
                TextButton(
                    onClick = {
                        if (AuthorTab.entries[tab] == AuthorTab.PROTOCOL) saveRequest++
                    },
                    modifier = Modifier.heightIn(min = 48.dp)
                ) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_save))
                }
                TextButton(
                    onClick = {
                        if (AuthorTab.entries[tab] == AuthorTab.PROTOCOL) saveAndDeliverRequest++
                        else onAssembly()
                    },
                    modifier = Modifier.heightIn(min = 48.dp)
                ) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_go_deliver))
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
                    style = MaterialTheme.typography.bodySmall,
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
                        style = MaterialTheme.typography.bodySmall,
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
                style = MaterialTheme.typography.bodySmall,
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
    val protocol = artifacts.protocol
    val context = androidx.compose.ui.platform.LocalContext.current
    val importPrefill = remember(project.id) {
        runCatching {
            val dir = java.io.File(java.io.File(java.io.File(context.filesDir, "projects"), project.id), "authoring")
            val file = dir.listFiles()?.firstOrNull { it.isFile && it.name.startsWith("import-") } ?: return@runCatching emptyMap()
            dev.ninfenz.mobile.data.ImportPrefill.fromJson(file.readText(Charsets.UTF_8))
        }.getOrDefault(emptyMap())
    }
    val importPrefillByLabel = remember(importPrefill, artifacts.spec) {
        dev.ninfenz.mobile.data.ImportPrefill.bySlotName(importPrefill, artifacts.spec.slots)
    }
    val templatePrefill = remember(project.id, artifacts.protocolJson) {
        runCatching {
            val file = java.io.File(java.io.File(java.io.File(context.filesDir, "projects"), project.id), "authoring/template.md")
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
    }
    data class Snapshot(val values: Map<String, String>, val enabled: Map<String, Boolean>)
    val draftStore = remember { ProtocolDraftStore(context.filesDir) }
    val draft = remember(project.id, artifacts.protocolJson) { draftStore.load(project.id) }
    var values by remember(artifacts.protocolJson) {
        mutableStateOf(protocol.fields.associate {
            it.id to (draft?.values?.get(it.id) ?: importPrefill[it.id] ?: importPrefillByLabel[it.label] ?: templatePrefill[it.id] ?: it.defaultText ?: "")
        })
    }
    var enabled by remember(artifacts.protocolJson) {
        mutableStateOf(protocol.clauses.associate {
            it.id to (draft?.enabled?.get(it.id) ?: it.enabled)
        })
    }
    var edited by remember { mutableStateOf(draft != null) }
    var undo by remember { mutableStateOf<List<Snapshot>>(emptyList()) }
    var rendered by remember { mutableStateOf<List<String>?>(null) }
    var renderError by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    var saveMessage by remember {
        mutableStateOf(if (draft != null) context.getString(dev.ninfenz.mobile.R.string.author_draft_restored) else null)
    }
    var saveError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val store = remember { AuthorOverlayStore(context.filesDir) }

    fun save(then: () -> Unit = {}) {
        if (saving) return
        saving = true
        saveMessage = null
        saveError = null
        scope.launch {
            val result = store.save(project, pack, enabled, values)
            when (result) {
                is SaveOverlayResult.Saved -> {
                    draftStore.clear(project.id)
                    saveMessage = context.getString(dev.ninfenz.mobile.R.string.author_saved, result.status.wire, result.overlaySha256.take(12))
                    onSaved()
                    then()
                }
                is SaveOverlayResult.Failure -> saveError = "[" + result.code + "] " + result.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + result.fix
            }
            saving = false
        }
    }

    LaunchedEffect(saveRequest) {
        if (saveRequest > 0) save()
    }

    LaunchedEffect(deliverRequest) {
        if (deliverRequest > 0) save { onAssembly() }
    }

    fun pushUndo() {
        undo = UndoStack.push(undo, Snapshot(values, enabled))
        edited = true
    }

    LaunchedEffect(project.id, values, enabled, edited) {
        if (edited) {
            delay(500)
            draftStore.save(project.id, values, enabled)
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        if (importPrefill.isNotEmpty()) {
            Text(
                pluralStringResource(dev.ninfenz.mobile.R.plurals.author_import_prefill, importPrefill.size, importPrefill.size),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_clauses, protocol.clauses.size))
        for (clause in protocol.clauses) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(clause.id + " · " + clause.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                        NfStatusChip(clause.level)
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.author_enable), style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                        Switch(
                            checked = enabled[clause.id] ?: clause.enabled,
                            onCheckedChange = { checked ->
                                pushUndo()
                                enabled = enabled + (clause.id to checked)
                            }
                        )
                    }
                    Text(clause.text, style = MaterialTheme.typography.bodyMedium)
                    val check = ProtocolModel.checkClause(protocol, clause, values)
                    if (!check.ok) {
                        if (check.missing.isNotEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.author_missing, check.missing.joinToString(", ")), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                        if (check.unknown.isNotEmpty()) Text(stringResource(dev.ninfenz.mobile.R.string.author_unknown, check.unknown.joinToString(", ")), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    }
                    for (field in protocol.fields.filter { it.clause == clause.id }) {
                        Column {
                            Text(field.id + " · " + field.label + (if (field.required) stringResource(dev.ninfenz.mobile.R.string.author_required) else ""), style = MaterialTheme.typography.labelLarge)
                            OutlinedTextField(
                                value = values[field.id] ?: "",
                                onValueChange = { text ->
                                    pushUndo()
                                    values = values + (field.id to text)
                                },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }
            }
        }
        Row(
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
        ) {
            OutlinedButton(
                enabled = undo.isNotEmpty() && !saving,
                onClick = {
                    val last = undo.last()
                    undo = undo.dropLast(1)
                    values = last.values
                    enabled = last.enabled
                    saveMessage = null
                    saveError = null
                }
            ) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
            Button(
                enabled = !saving,
                onClick = { save() }
            ) { Text(if (saving) stringResource(dev.ninfenz.mobile.R.string.author_saving) else stringResource(dev.ninfenz.mobile.R.string.author_save)) }
        }
        saveMessage?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        saveError?.let { message ->
            NfErrorCard("NF-PCK-003", message, stringResource(dev.ninfenz.mobile.R.string.author_diag_fix), modifier = Modifier.padding(horizontal = NfSpacing.page))
        }
        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                busy = true
                renderError = null
                scope.launch {
                    val payload = buildJsonObject {
                        put("pack", artifacts.protocolJson)
                        put("values", buildJsonObject { for ((k, v) in values) put(k, v) })
                    }
                    val response: CoreResponse = safeCall("protocol-render", payload)
                    if (response.ok) {
                        val clauses = response.resultObject()?.get("clauses")?.jsonArray
                        rendered = clauses?.mapNotNull { element ->
                            (element as? JsonObject)?.let { J.optString(it, "id") + "：" + J.optString(it, "text") }
                        } ?: emptyList()
                    } else {
                        renderError = response.error
                    }
                    busy = false
                }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_rendering) else stringResource(dev.ninfenz.mobile.R.string.author_render)) }
        renderError?.let { error ->
            NfErrorCard(error.code, error.message, error.fix, modifier = Modifier.padding(horizontal = NfSpacing.page))
        }
        rendered?.let { lines ->
            NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_render_results, lines.size))
            for (line in lines) {
                Text(line, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page))
            }
        }
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
    val snackbar = remember { SnackbarHostState() }
    val haptics = LocalHapticFeedback.current
    val snackbarScope = rememberCoroutineScope()
    fun deleteNode(node: GraphNode) {
        val previous = graph
        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
        apply(
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
                graph = previous
            }
        }
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
    LaunchedEffect(graph) {
        if (!autoSavePrimed) {
            autoSavePrimed = true
        } else {
            delay(900)
            when (val result = store.saveGraph(project, graph)) {
                is SaveArtifactResult.Saved -> {
                    savedMsg = context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12))
                    onSaved()
                }
                is SaveArtifactResult.Failure -> error = CoreError(result.code, result.message, result.fix, null, 1)
            }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_nodes, graph.nodes.size))
        for (node in graph.nodes) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(node.id + " · " + node.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                        NfStatusChip(node.kind)
                        TextButton(onClick = { deleteNode(node) }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_delete)) }
                    }
                    Text(
                        stringResource(
                            dev.ninfenz.mobile.R.string.author_module,
                            node.moduleId ?: stringResource(dev.ninfenz.mobile.R.string.author_not_bound),
                            node.portsIn.joinToString(","),
                            node.portsOut.joinToString(",")
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    graph.weights[node.id]?.let { Text(stringResource(dev.ninfenz.mobile.R.string.author_weight, it), style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_edges, graph.edges.size))
        for (edge in graph.edges) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Text(
                    edge.from + "." + edge.fromPort + " → " + edge.to + "." + edge.toPort + "（" + edge.type + "）",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.weight(1f)
                )
                TextButton(onClick = { apply(graph.copy(edges = graph.edges.filter { it.id != edge.id })) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.author_delete))
                }
            }
        }

        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_add_node))
        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs), modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_id), value = nodeId, onValueChange = { nodeId = it })
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_title), value = nodeTitle, onValueChange = { nodeTitle = it })
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_kind), value = nodeKind, onValueChange = { nodeKind = it })
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_node_module), value = nodeModule, onValueChange = { nodeModule = it })
            Button(onClick = {
                if (nodeId.isNotBlank()) {
                    val module = nodeModule.trim().ifBlank { null }
                    apply(
                        graph.copy(
                            nodes = graph.nodes + GraphNode(
                                id = nodeId.trim(), kind = nodeKind.trim().ifBlank { "stage" },
                                title = nodeTitle.trim().ifBlank { nodeId.trim() },
                                portsIn = emptyList(), portsOut = listOf("out"),
                                moduleId = module, moduleVersion = null, moduleDigest = null
                            )
                        )
                    )
                    nodeId = ""
                    nodeTitle = ""
                    nodeModule = ""
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_add_node)) }
        }

        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_add_edge))
        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs), modifier = Modifier.padding(horizontal = NfSpacing.page)) {
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_from), value = edgeFrom, onValueChange = { edgeFrom = it })
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_to), value = edgeTo, onValueChange = { edgeTo = it })
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_from_port), value = edgeFromPort, onValueChange = { edgeFromPort = it })
            FormTextField(label = stringResource(dev.ninfenz.mobile.R.string.author_edge_to_port), value = edgeToPort, onValueChange = { edgeToPort = it })
            Button(onClick = {
                if (edgeFrom.isNotBlank() && edgeTo.isNotBlank()) {
                    val next = (graph.edges.mapNotNull { Regex("E(\\d+)").matchEntire(it.id)?.groupValues?.get(1)?.toIntOrNull() }.maxOrNull() ?: 0) + 1
                    val id = "E" + next.toString().padStart(2, '0')
                    apply(
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

        Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            TextButton(enabled = undo.isNotEmpty(), onClick = {
                val previous = undo.removeAt(undo.lastIndex)
                redo.add(graph)
                graph = previous
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
            TextButton(enabled = redo.isNotEmpty(), onClick = {
                val next = redo.removeAt(redo.lastIndex)
                undo.add(graph)
                graph = next
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_redo)) }
        }

        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                busy = true
                error = null
                report = null
                scope.launch {
                    val response = safeCall("graph-validate", buildJsonObject { put("graph", GraphModel.toJson(graph)) })
                    if (response.ok) report = summarizeReport(context, response) else error = response.error
                    busy = false
                }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_validating) else stringResource(dev.ninfenz.mobile.R.string.author_validate_graph)) }

        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                busy = true
                error = null
                savedMsg = null
                scope.launch {
                    when (val result = store.saveGraph(project, graph)) {
                        is SaveArtifactResult.Saved -> {
                            savedMsg = context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12))
                            onSaved()
                        }
                        is SaveArtifactResult.Failure -> error = CoreError(result.code, result.message, result.fix, null, 1)
                    }
                    busy = false
                }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_saving_artifact) else stringResource(dev.ninfenz.mobile.R.string.author_save_graph)) }

        report?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        savedMsg?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        SnackbarHost(hostState = snackbar, modifier = Modifier.padding(horizontal = NfSpacing.page))
    }
}

@Composable
private fun SpecAuthorContent(artifacts: AuthorArtifacts, project: Project, onSaved: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var spec by remember(artifacts.specJson) { mutableStateOf(artifacts.spec) }
    val undo = remember { mutableStateListOf<dev.ninfenz.mobile.model.MdSpec>() }
    val redo = remember { mutableStateListOf<dev.ninfenz.mobile.model.MdSpec>() }
    fun apply(next: dev.ninfenz.mobile.model.MdSpec) {
        undo.add(spec)
        redo.clear()
        spec = next
    }
    var report by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    var savedMsg by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val store = remember { AuthorArtifactStore(context.filesDir) }
    var autoSavePrimed by remember { mutableStateOf(false) }
    LaunchedEffect(spec) {
        if (!autoSavePrimed) {
            autoSavePrimed = true
        } else {
            delay(900)
            when (val result = store.saveSpec(project, spec)) {
                is SaveArtifactResult.Saved -> {
                    savedMsg = context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12))
                    onSaved()
                }
                is SaveArtifactResult.Failure -> error = CoreError(result.code, result.message, result.fix, null, 1)
            }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_sections, spec.sections.size))
        for (section in spec.sections) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(section.id + " · order=" + section.order, style = MaterialTheme.typography.bodySmall)
                    FormTextField(
                        label = stringResource(dev.ninfenz.mobile.R.string.author_section_title),
                        value = section.title,
                        onValueChange = { newTitle ->
                            apply(spec.copy(sections = spec.sections.map { if (it.id == section.id) it.copy(title = newTitle) else it }))
                        }
                    )
                    Text(
                        stringResource(
                            dev.ninfenz.mobile.R.string.author_order,
                            section.order,
                            if (section.required) stringResource(dev.ninfenz.mobile.R.string.author_required_label) else stringResource(dev.ninfenz.mobile.R.string.author_optional_label),
                            section.slots.joinToString(",")
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_slots, spec.slots.size))
        for (slot in spec.slots) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(slot.id + " · " + slot.kind + (if (slot.required) " · " + stringResource(dev.ninfenz.mobile.R.string.author_required_label) else ""), style = MaterialTheme.typography.bodySmall)
                    FormTextField(
                        label = stringResource(dev.ninfenz.mobile.R.string.author_slot_name),
                        value = slot.name,
                        onValueChange = { newName ->
                            apply(spec.copy(slots = spec.slots.map { if (it.id == slot.id) it.copy(name = newName) else it }))
                        }
                    )
                }
            }
        }
        Row(modifier = Modifier.padding(horizontal = NfSpacing.page), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            TextButton(enabled = undo.isNotEmpty(), onClick = {
                val previous = undo.removeAt(undo.lastIndex)
                redo.add(spec)
                spec = previous
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_undo)) }
            TextButton(enabled = redo.isNotEmpty(), onClick = {
                val next = redo.removeAt(redo.lastIndex)
                undo.add(spec)
                spec = next
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.author_redo)) }
        }
        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                busy = true
                error = null
                report = null
                scope.launch {
                    val response = safeCall("spec-validate", buildJsonObject { put("spec", SpecModel.toJson(spec)) })
                    if (response.ok) report = summarizeReport(context, response) else error = response.error
                    busy = false
                }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_validating) else stringResource(dev.ninfenz.mobile.R.string.author_validate_spec)) }
        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                busy = true
                error = null
                savedMsg = null
                scope.launch {
                    when (val result = store.saveSpec(project, spec)) {
                        is SaveArtifactResult.Saved -> {
                            savedMsg = context.getString(dev.ninfenz.mobile.R.string.author_saved_artifact, result.path, result.sha256.take(12))
                            onSaved()
                        }
                        is SaveArtifactResult.Failure -> error = CoreError(result.code, result.message, result.fix, null, 1)
                    }
                    busy = false
                }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_saving_artifact) else stringResource(dev.ninfenz.mobile.R.string.author_save_spec)) }
        report?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        savedMsg?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    }
}

private fun summarizeReport(context: Context, response: CoreResponse): String {
    val result = response.resultObject()
    val verdict = result?.get("verdict")?.jsonPrimitive?.content ?: "pass"
    val summary = result?.get("summary")?.toString() ?: ""
    val issues = result?.get("issues")?.let { if (it is JsonArray) it.size else 0 } ?: 0
    val line = context.getString(dev.ninfenz.mobile.R.string.author_validate_result, verdict, issues)
    return line + (if (summary.isNotBlank()) " · " + summary else "")
}
