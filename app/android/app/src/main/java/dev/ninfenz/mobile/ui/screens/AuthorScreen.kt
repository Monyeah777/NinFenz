package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.AuthorOverlayStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.SaveOverlayResult
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProtocolModel
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.Dispatchers
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
fun AuthorScreen(project: Project, pack: PackEntry?, onBack: () -> Unit, onAssembly: () -> Unit, onSaved: () -> Unit = {}) {
    if (pack == null) {
        Column(modifier = Modifier.fillMaxSize()) {
            NfTopAppBar(title = project.title, onBack = onBack)
            NfEmptyState(
                icon = Icons.Filled.Info,
                title = stringResource(dev.ninfenz.mobile.R.string.author_pack_missing_title),
                message = stringResource(dev.ninfenz.mobile.R.string.author_pack_missing_body, project.refs.basePackId, project.refs.basePackVersion),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.author_back),
                onAction = onBack
            )
        }
        return
    }

    var tab by remember { mutableIntStateOf(0) }
    var artifacts by remember { mutableStateOf<AuthorArtifacts?>(null) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(pack.dir.absolutePath) {
        loading = true
        loadError = null
        try {
            artifacts = withContext(Dispatchers.IO) { AuthorArtifactsLoader.load(pack) }
        } catch (t: Throwable) {
            loadError = t.message ?: t.javaClass.simpleName
        }
        loading = false
    }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = project.title, onBack = onBack)
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
        ) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(project.title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                        NfStatusChip(projectStatusLabel(project))
                    }
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.author_pack_label, project.refs.basePackId, project.refs.basePackVersion),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.author_preview_note),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Button(onClick = onAssembly) { Text(stringResource(dev.ninfenz.mobile.R.string.author_go_deliver)) }
                    }
                }
            }
            TabRow(selectedTabIndex = tab) {
                AuthorTab.entries.forEachIndexed { index, item ->
                    Tab(selected = tab == index, onClick = { tab = index }, text = { Text(stringResource(item.labelRes)) })
                }
            }
            if (loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page))
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
                    AuthorTab.PROTOCOL -> ProtocolAuthorContent(current, project, pack, onSaved)
                    AuthorTab.GRAPH -> GraphAuthorContent(current)
                    AuthorTab.SPEC -> SpecAuthorContent(current)
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
    onSaved: () -> Unit
) {
    val protocol = artifacts.protocol
    val context = androidx.compose.ui.platform.LocalContext.current
    data class Snapshot(val values: Map<String, String>, val enabled: Map<String, Boolean>)
    var values by remember(artifacts.protocolJson) { mutableStateOf(protocol.fields.associate { it.id to (it.defaultText ?: "") }) }
    var enabled by remember(artifacts.protocolJson) { mutableStateOf(protocol.clauses.associate { it.id to it.enabled }) }
    var undo by remember { mutableStateOf<List<Snapshot>>(emptyList()) }
    var rendered by remember { mutableStateOf<List<String>?>(null) }
    var renderError by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    var saveMessage by remember { mutableStateOf<String?>(null) }
    var saveError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val store = remember { AuthorOverlayStore(context.filesDir) }

    fun pushUndo() {
        undo = undo + Snapshot(values, enabled)
    }

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
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
                onClick = {
                    saving = true
                    saveMessage = null
                    saveError = null
                    scope.launch {
                        val result = store.save(project, pack, enabled, values)
                        when (result) {
                            is SaveOverlayResult.Saved -> {
                                saveMessage = context.getString(dev.ninfenz.mobile.R.string.author_saved, result.status.wire, result.overlaySha256.take(12))
                                onSaved()
                            }
                            is SaveOverlayResult.Failure -> saveError = "[" + result.code + "] " + result.message + "；修复：" + result.fix
                        }
                        saving = false
                    }
                }
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
private fun GraphAuthorContent(artifacts: AuthorArtifacts) {
    val graph = artifacts.graph
    val context = androidx.compose.ui.platform.LocalContext.current
    var report by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_nodes, graph.nodes.size))
        for (node in graph.nodes) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Row {
                        Text(node.id + " · " + node.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                        NfStatusChip(node.kind)
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
            Text(
                edge.from + "." + edge.fromPort + " → " + edge.to + "." + edge.toPort + "（" + edge.type + "）",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                busy = true
                error = null
                report = null
                scope.launch {
                    val response = safeCall("graph-validate", buildJsonObject { put("graph", artifacts.graphJson) })
                    if (response.ok) report = summarizeReport(context, response) else error = response.error
                    busy = false
                }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_validating) else stringResource(dev.ninfenz.mobile.R.string.author_validate_graph)) }
        report?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    }
}

@Composable
private fun SpecAuthorContent(artifacts: AuthorArtifacts) {
    val spec = artifacts.spec
    val context = androidx.compose.ui.platform.LocalContext.current
    var report by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.author_sections, spec.sections.size))
        for (section in spec.sections) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(section.id + " · " + section.title, style = MaterialTheme.typography.titleMedium)
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
            Text(
                slot.id + " · " + slot.name + " · " + slot.kind + (if (slot.required) " · " + stringResource(dev.ninfenz.mobile.R.string.author_required_label) else ""),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(horizontal = NfSpacing.page)
            )
        }
        Button(
            enabled = !busy,
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            onClick = {
                busy = true
                error = null
                report = null
                scope.launch {
                    val response = safeCall("spec-validate", buildJsonObject { put("spec", artifacts.specJson) })
                    if (response.ok) report = summarizeReport(context, response) else error = response.error
                    busy = false
                }
            }
        ) { Text(if (busy) stringResource(dev.ninfenz.mobile.R.string.author_validating) else stringResource(dev.ninfenz.mobile.R.string.author_validate_spec)) }
        report?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
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
