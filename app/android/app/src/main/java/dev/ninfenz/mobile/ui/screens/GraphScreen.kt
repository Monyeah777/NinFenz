package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.model.GraphEdge
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.GraphNode
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.ValidateReport
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.ErrorNotice
import dev.ninfenz.mobile.ui.components.FormTextField
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.JsonPrimitive
import java.io.File

private fun emptyGraph(): PipelineGraph = PipelineGraph(
    id = "draft-graph",
    version = "0.1.0",
    title = "未命名管线",
    mode = "pro",
    nodes = emptyList(),
    edges = emptyList(),
    weights = emptyMap(),
    requiredStages = emptyList(),
    seed = null,
    params = JsonObject(emptyMap())
)

@Composable
fun GraphScreen(store: LibraryStore, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var graph by remember { mutableStateOf<PipelineGraph?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var planSummary by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var nodeTitle by remember { mutableStateOf("") }
    var nodeKind by remember { mutableStateOf("stage") }
    var edgeFrom by remember { mutableStateOf("") }
    var edgeTo by remember { mutableStateOf("") }
    var edgeFromPort by remember { mutableStateOf("out") }
    var edgeToPort by remember { mutableStateOf("in") }
    var savedPath by remember { mutableStateOf<String?>(null) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                graph = GraphModel.parse(text)
                error = null
                report = null
                planSummary = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-GRF-001",
                    "管线图解析失败：" + (e.message ?: e.javaClass.simpleName),
                    "按 app/schema/nf-pipeline-graph.schema.json 修正",
                    1
                ).error
            }
        }
    }

    NfScaffold(title = "Graph · 管线图", onBack = onBack) {
        CardBox(title = "图") {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { picker.launch(arrayOf("application/json", "text/plain")) }) { Text("打开 .nfg.json") }
                OutlinedButton(onClick = {
                    graph = emptyGraph()
                    report = null
                    planSummary = null
                    error = null
                }) { Text("新建空图") }
            }
            val g = graph
            if (g == null) {
                EmptyState("尚未打开管线图。节点/边/权重编辑在本地；校验与编译必须走核心。")
            } else {
                KeyValue("id/version", g.id + " " + g.version)
                KeyValue("mode", g.mode)
                KeyValue("节点/边", g.nodes.size.toString() + " / " + g.edges.size)
                KeyValue("required_stages", g.requiredStages.joinToString(",").ifBlank { "（空）" })
            }
        }

        error?.let { ErrorNotice(it) }

        val g = graph
        if (g != null) {
            CardBox(title = "节点列表") {
                if (g.nodes.isEmpty()) EmptyState("无节点。至少需要 1 个 stage + 1 个 module。")
                for (node in g.nodes) {
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(node.id + " · " + node.kind + " · " + node.title, style = MaterialTheme.typography.bodyMedium)
                            Text("ports in=" + node.portsIn.joinToString(",") + " out=" + node.portsOut.joinToString(","),
                                style = MaterialTheme.typography.bodySmall)
                        }
                        FormTextField(
                            label = "权重",
                            value = g.weights[node.id]?.toString() ?: "",
                            onValueChange = { v ->
                                val weight = v.toIntOrNull()
                                graph = GraphModel.withWeight(g, node.id, if (v.isBlank()) null else weight)
                            }
                        )
                        OutlinedButton(onClick = { graph = GraphModel.withoutNode(g, node.id) }) { Text("删") }
                    }
                }
                FormTextField(label = "新节点标题", value = nodeTitle, onValueChange = { nodeTitle = it })
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { nodeKind = "stage" }) { Text(if (nodeKind == "stage") "[stage]" else "stage") }
                    OutlinedButton(onClick = { nodeKind = "module" }) { Text(if (nodeKind == "module") "[module]" else "module") }
                    Button(onClick = {
                        if (nodeTitle.isBlank()) return@Button
                        val id = GraphModel.nextNodeId(g)
                        val node = GraphNode(
                            id = id,
                            kind = nodeKind,
                            title = nodeTitle,
                            portsIn = listOf("in"),
                            portsOut = listOf("out"),
                            moduleId = if (nodeKind == "module") "module-" + id.lowercase() else null,
                            moduleVersion = if (nodeKind == "module") "0.0.0" else null,
                            moduleDigest = null
                        )
                        graph = GraphModel.withNode(g, node)
                        nodeTitle = ""
                        report = null
                        planSummary = null
                    }) { Text("加节点") }
                }
            }

            CardBox(title = "边列表") {
                if (g.edges.isEmpty()) EmptyState("无边。边 from/to 必须引用已存在节点与已声明端口。")
                for (edge in g.edges) {
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(edge.id + " · " + edge.from + "(" + edge.fromPort + ") -> " + edge.to + "(" + edge.toPort + ")",
                                style = MaterialTheme.typography.bodySmall)
                            Text("type=" + edge.type, style = MaterialTheme.typography.labelSmall)
                        }
                        OutlinedButton(onClick = { graph = GraphModel.withoutEdge(g, edge.id) }) { Text("删") }
                    }
                }
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    FormTextField(label = "from", value = edgeFrom, onValueChange = { edgeFrom = it })
                    FormTextField(label = "to", value = edgeTo, onValueChange = { edgeTo = it })
                }
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    FormTextField(label = "from_port", value = edgeFromPort, onValueChange = { edgeFromPort = it })
                    FormTextField(label = "to_port", value = edgeToPort, onValueChange = { edgeToPort = it })
                }
                Button(onClick = {
                    if (edgeFrom.isBlank() || edgeTo.isBlank()) return@Button
                    val edge = GraphEdge(
                        id = GraphModel.nextEdgeId(g),
                        from = edgeFrom,
                        to = edgeTo,
                        fromPort = edgeFromPort,
                        toPort = edgeToPort,
                        type = "data"
                    )
                    graph = GraphModel.withEdge(g, edge)
                    report = null
                    planSummary = null
                }) { Text("加边") }
            }

            CardBox(title = "本地表单检查（非契约校验）") {
                val issues = GraphModel.formIssues(g)
                if (issues.isEmpty()) Notice("本地检查未发现问题。", Tone.INFO)
                for (issue in issues) Notice(issue.code + " " + issue.path + "：" + issue.message + "；修复：" + issue.fix, Tone.WARN)
            }

            CardBox(title = "核心校验 / 编译") {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = !busy, onClick = {
                        scope.launch {
                            busy = true
                            error = null
                            report = null
                            try {
                                val payload = buildJsonObject { put("graph", GraphModel.toJson(g)) }
                                val response = safeCall("graph-validate", payload)
                                if (response.ok) {
                                    response.resultObject()?.let { report = ReportModel.parse(it) }
                                } else if (response.exit == 1 && response.result != null) {
                                    (response.result as? JsonObject)?.let { report = ReportModel.parse(it) }
                                    error = response.error
                                } else {
                                    error = response.error
                                }
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(if (busy) "调用中…" else "core graph-validate") }
                    Button(enabled = !busy, onClick = {
                        scope.launch {
                            busy = true
                            error = null
                            planSummary = null
                            try {
                                val payload = buildJsonObject { put("graph", GraphModel.toJson(g)) }
                                val response = safeCall("graph-compile", payload)
                                if (response.ok) {
                                    val result = response.resultObject()
                                    planSummary = if (result == null) "核心未返回 plan" else
                                        "plan digest=" + (J.optString(result, "digest") ?: "（无）") +
                                            " steps=" + J.optArray(result, "steps").size +
                                            " slots=" + J.optStringList(result, "slots").joinToString(",")
                                } else {
                                    error = response.error
                                }
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(if (busy) "调用中…" else "core graph-compile") }
                }
                report?.let { r ->
                    KeyValue("校验", ReportModel.line(r))
                    for (issue in r.issues) Notice(issue.code + " " + (issue.path ?: "-") + "：" + issue.message + "；修复：" + issue.fix,
                        if (issue.severity == "error") Tone.ERROR else Tone.WARN)
                }
                planSummary?.let { MonoText(it) }
            }

            CardBox(title = "保存") {
                Button(onClick = {
                    val path = store.saveDraft("graph-" + g.id, GraphModel.toJson(g).toString())
                    savedPath = path.absolutePath
                }) { Text("保存图草稿") }
                savedPath?.let { Notice("已保存：" + it, Tone.INFO) }
            }
        }
    }
}
