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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
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
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifacts
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.PackEntry
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

private enum class AuthorTab(val label: String) {
    PROTOCOL("协议"),
    GRAPH("管线"),
    SPEC("规格")
}

/**
 * W4 创作台：项目头 + 协议/管线/规格三段。读取项目绑定 Pack 的只读内容，
 * 支持本地预检 + 核心 protocol-render / graph-validate / spec-validate。
 * 编辑保存（写回引用/digest）留 W4 后续；当前明确标「本地预演」。
 */
@Composable
fun AuthorScreen(project: Project, pack: PackEntry?, onBack: () -> Unit, onAssembly: () -> Unit) {
    if (pack == null) {
        Column(modifier = Modifier.fillMaxSize()) {
            NfTopAppBar(title = project.title, onBack = onBack)
            NfEmptyState(
                icon = Icons.Filled.Info,
                title = "绑定的 Pack 不在本机",
                message = "项目引用的 " + project.refs.basePackId + " · " + project.refs.basePackVersion + " 未安装或已移动。",
                actionLabel = "返回",
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
                        "Pack：" + project.refs.basePackId + " · " + project.refs.basePackVersion,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        "本地预演：编辑不写回项目（保存/撤销在 W4 后续接入）；校验走核心。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                        Button(onClick = onAssembly) { Text("去交付") }
                    }
                }
            }
            TabRow(selectedTabIndex = tab) {
                AuthorTab.entries.forEachIndexed { index, item ->
                    Tab(selected = tab == index, onClick = { tab = index }, text = { Text(item.label) })
                }
            }
            if (loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page))
            if (loadError != null) {
                NfErrorCard(
                    "NF-PCK-003",
                    "读取项目内容失败：" + loadError!!,
                    "重装绑定的 Pack，或重新创建项目",
                    modifier = Modifier.padding(horizontal = NfSpacing.page)
                )
            }
            val current = artifacts
            if (current != null) {
                when (AuthorTab.entries[tab]) {
                    AuthorTab.PROTOCOL -> ProtocolAuthorContent(current)
                    AuthorTab.GRAPH -> GraphAuthorContent(current)
                    AuthorTab.SPEC -> SpecAuthorContent(current)
                }
            }
        }
    }
}

@Composable
private fun ProtocolAuthorContent(artifacts: AuthorArtifacts) {
    val pack = artifacts.protocol
    var values by remember(artifacts.protocolJson) { mutableStateOf(pack.fields.associate { it.id to (it.defaultText ?: "") }) }
    var enabled by remember(artifacts.protocolJson) { mutableStateOf(pack.clauses.associate { it.id to it.enabled }) }
    var rendered by remember { mutableStateOf<List<String>?>(null) }
    var renderError by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        NfSectionHeader("条款（" + pack.clauses.size + "）")
        for (clause in pack.clauses) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(clause.id + " · " + clause.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                        NfStatusChip(clause.level)
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("启用本条", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                        Switch(checked = enabled[clause.id] ?: clause.enabled, onCheckedChange = { enabled = enabled + (clause.id to it) })
                    }
                    Text(clause.text, style = MaterialTheme.typography.bodyMedium)
                    val check = ProtocolModel.checkClause(pack, clause, values)
                    if (!check.ok) {
                        if (check.missing.isNotEmpty()) Text("缺必填：" + check.missing.joinToString(", ") + "（NF-PRT-003）", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                        if (check.unknown.isNotEmpty()) Text("未声明占位符：" + check.unknown.joinToString(", ") + "（NF-PRT-004）", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    }
                    for (field in pack.fields.filter { it.clause == clause.id }) {
                        Column {
                            Text(field.id + " · " + field.label + (if (field.required) "（必填）" else ""), style = MaterialTheme.typography.labelLarge)
                            OutlinedTextField(
                                value = values[field.id] ?: "",
                                onValueChange = { values = values + (field.id to it) },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }
            }
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
        ) { Text(if (busy) "渲染中…" else "用核心渲染协议") }
        renderError?.let { error ->
            NfErrorCard(error.code, error.message, error.fix, modifier = Modifier.padding(horizontal = NfSpacing.page))
        }
        rendered?.let { lines ->
            NfSectionHeader("渲染结果（" + lines.size + "）")
            for (line in lines) {
                Text(line, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page))
            }
        }
    }
}

@Composable
private fun GraphAuthorContent(artifacts: AuthorArtifacts) {
    val graph = artifacts.graph
    var report by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        NfSectionHeader("节点（" + graph.nodes.size + "）")
        for (node in graph.nodes) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Row {
                        Text(node.id + " · " + node.title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                        NfStatusChip(node.kind)
                    }
                    Text(
                        "模块：" + (node.moduleId ?: "未绑定") + " · in=" + node.portsIn.joinToString(",") + " · out=" + node.portsOut.joinToString(","),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    graph.weights[node.id]?.let { Text("权重：" + it, style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
        NfSectionHeader("边（" + graph.edges.size + "）")
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
                    if (response.ok) report = summarizeReport(response) else error = response.error
                    busy = false
                }
            }
        ) { Text(if (busy) "校验中…" else "核心校验管线") }
        report?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    }
}

@Composable
private fun SpecAuthorContent(artifacts: AuthorArtifacts) {
    val spec = artifacts.spec
    var report by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.m)) {
        NfSectionHeader("章节（" + spec.sections.size + "）")
        for (section in spec.sections) {
            NfCard(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                    Text(section.id + " · " + section.title, style = MaterialTheme.typography.titleMedium)
                    Text(
                        "order=" + section.order + (if (section.required) " · 必填" else " · 可选") + " · slots=" + section.slots.joinToString(","),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
        NfSectionHeader("槽位（" + spec.slots.size + "）")
        for (slot in spec.slots) {
            Text(
                slot.id + " · " + slot.name + " · " + slot.kind + (if (slot.required) " · 必填" else ""),
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
                    if (response.ok) report = summarizeReport(response) else error = response.error
                    busy = false
                }
            }
        ) { Text(if (busy) "校验中…" else "核心校验规格") }
        report?.let { text -> Text(text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
        error?.let { err -> NfErrorCard(err.code, err.message, err.fix, modifier = Modifier.padding(horizontal = NfSpacing.page)) }
    }
}

private fun summarizeReport(response: CoreResponse): String {
    val result = response.resultObject()
    val verdict = result?.get("verdict")?.jsonPrimitive?.content ?: "pass"
    val summary = result?.get("summary")?.toString() ?: ""
    val issues = result?.get("issues")?.let { if (it is JsonArray) it.size else 0 } ?: 0
    return "校验结果：" + verdict + " · issues=" + issues + (if (summary.isNotBlank()) " · " + summary else "")
}
