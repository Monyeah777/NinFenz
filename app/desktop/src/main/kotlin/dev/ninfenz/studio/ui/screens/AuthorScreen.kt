package dev.ninfenz.studio.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.ninfenz.studio.core.CoreError
import dev.ninfenz.studio.core.CoreResponse
import dev.ninfenz.studio.core.J
import dev.ninfenz.studio.model.Dsl
import dev.ninfenz.studio.model.DslIssue
import dev.ninfenz.studio.model.GraphEdge
import dev.ninfenz.studio.model.GraphModel
import dev.ninfenz.studio.model.GraphNode
import dev.ninfenz.studio.model.PipelineGraph
import dev.ninfenz.studio.model.ValidateReport
import dev.ninfenz.studio.model.ReportModel
import dev.ninfenz.studio.ui.ErrorCard
import dev.ninfenz.studio.ui.Field
import dev.ninfenz.studio.ui.FileDialogs
import dev.ninfenz.studio.ui.KeyValue
import dev.ninfenz.studio.ui.Mono
import dev.ninfenz.studio.ui.Notice
import dev.ninfenz.studio.ui.Section
import dev.ninfenz.studio.ui.safeCall
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@Composable
fun AuthorScreen() {
    val scope = rememberCoroutineScope()
    var graph by remember { mutableStateOf(PipelineGraph.empty()) }
    var dslText by remember { mutableStateOf(Dsl.emit(PipelineGraph.empty())) }
    var dslIssues by remember { mutableStateOf<List<DslIssue>>(emptyList()) }
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var planSummary by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var busy by remember { mutableStateOf(false) }

    var nodeTitle by remember { mutableStateOf("") }
    var nodeKind by remember { mutableStateOf("stage") }
    var edgeFrom by remember { mutableStateOf("") }
    var edgeTo by remember { mutableStateOf("") }
    var weightNode by remember { mutableStateOf("") }
    var weightValue by remember { mutableStateOf("") }

    fun validateWithCore() {
        val g = graph
        scope.launch {
            busy = true
            error = null
            report = null
            try {
                val response = safeCall("graph-validate", buildJsonObject { put("graph", GraphModel.toJson(g)) })
                if (response.resultObject() != null) {
                    report = ReportModel.parse(response.resultObject()!!)
                }
                if (!response.ok) error = response.error
            } finally {
                busy = false
            }
        }
    }

    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Section("GraphEditor（图编辑）") {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedButton(onClick = {
                        val file = FileDialogs.openFile("打开 .nfg.json", "json")
                        if (file != null) {
                            try {
                                graph = GraphModel.parse(file.readText(Charsets.UTF_8))
                                dslText = Dsl.emit(graph)
                                error = null
                            } catch (e: Exception) {
                                error = CoreResponse.failure("NF-GRF-001", "图解析失败：" + (e.message ?: e.javaClass.simpleName), "按 schema 修正", 1).error
                            }
                        }
                    }) { Text("打开图…") }
                    OutlinedButton(onClick = {
                        graph = PipelineGraph.empty()
                        dslText = Dsl.emit(graph)
                        report = null
                        planSummary = null
                    }) { Text("新建空图") }
                    Button(onClick = { dslText = Dsl.emit(graph) }) { Text("生成 DSL") }
                }
                KeyValue("id/version", graph.id + " " + graph.version + " · mode=" + graph.mode)
                KeyValue("nodes/edges", graph.nodes.size.toString() + " / " + graph.edges.size)
                for (node in graph.nodes) {
                    Row(modifier = Modifier.fillMaxWidth()) {
                        Text(node.id + " " + node.kind + " " + node.title, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                        Text("w=" + (graph.weights[node.id] ?: "-"), style = MaterialTheme.typography.bodySmall)
                        OutlinedButton(onClick = { graph = GraphModel.withoutNode(graph, node.id) }) { Text("删") }
                    }
                }
                for (edge in graph.edges) {
                    Row(modifier = Modifier.fillMaxWidth()) {
                        Text(edge.id + " " + edge.from + ":" + edge.fromPort + " -> " + edge.to + ":" + edge.toPort,
                            style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                        OutlinedButton(onClick = { graph = GraphModel.withoutEdge(graph, edge.id) }) { Text("删") }
                    }
                }
                Field("新节点标题", nodeTitle, { nodeTitle = it })
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedButton(onClick = { nodeKind = "stage" }) { Text(if (nodeKind == "stage") "[stage]" else "stage") }
                    OutlinedButton(onClick = { nodeKind = "module" }) { Text(if (nodeKind == "module") "[module]" else "module") }
                    OutlinedButton(onClick = { nodeKind = "gate" }) { Text(if (nodeKind == "gate") "[gate]" else "gate") }
                    Button(onClick = {
                        if (nodeTitle.isNotBlank()) {
                            val id = GraphModel.nextNodeId(graph)
                            graph = GraphModel.withNode(graph, GraphNode(
                                id = id, kind = nodeKind, title = nodeTitle,
                                portsIn = listOf("in"), portsOut = listOf("out"),
                                moduleId = if (nodeKind == "module") "module-" + id.lowercase() else null
                            ))
                            nodeTitle = ""
                        }
                    }) { Text("加节点") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Field("from", edgeFrom, { edgeFrom = it })
                    Field("to", edgeTo, { edgeTo = it })
                }
                Button(onClick = {
                    if (edgeFrom.isNotBlank() && edgeTo.isNotBlank()) {
                        graph = GraphModel.withEdge(graph, GraphEdge(
                            GraphModel.nextEdgeId(graph), edgeFrom, edgeTo, "out", "in", "data"
                        ))
                    }
                }) { Text("加边（out -> in）") }
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Field("weight 节点", weightNode, { weightNode = it })
                    Field("权重 0..100", weightValue, { weightValue = it })
                    Button(onClick = {
                        val value = weightValue.toIntOrNull()
                        if (weightNode.isNotBlank() && value != null) {
                            graph = GraphModel.withWeight(graph, weightNode, value)
                        }
                    }) { Text("设权重") }
                }
            }
            Section("本地检查（非契约校验）") {
                val issues = GraphModel.issues(graph)
                if (issues.isEmpty()) Notice("本地检查通过") else for (issue in issues) Notice(issue.code + " " + issue.path + "：" + issue.message)
            }
        }

        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Section("DslEditor（文本作者面）") {
                OutlinedTextField(
                    value = dslText,
                    onValueChange = { dslText = it },
                    modifier = Modifier.fillMaxWidth().height(320.dp),
                    textStyle = MaterialTheme.typography.bodySmall
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Button(onClick = {
                        val parsed = Dsl.parse(dslText)
                        graph = parsed.graph
                        dslIssues = parsed.issues
                    }) { Text("解析 DSL → 图") }
                    OutlinedButton(onClick = { dslIssues = Dsl.parse(dslText).issues }) { Text("只校验") }
                }
                if (dslIssues.isEmpty()) Notice("DSL 无问题") else for (issue in dslIssues) {
                    Notice("行 " + issue.line + "：" + issue.message + "（修复：" + issue.fix + "）")
                }
            }
            Section("核心校验 / 编译") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = !busy, onClick = { validateWithCore() }) { Text(if (busy) "调用中…" else "core graph-validate") }
                    Button(enabled = !busy, onClick = {
                        val g = graph
                        scope.launch {
                            busy = true
                            error = null
                            planSummary = null
                            try {
                                val response = safeCall("graph-compile", buildJsonObject { put("graph", GraphModel.toJson(g)) })
                                if (response.ok) {
                                    val result = response.resultObject()
                                    planSummary = if (result == null) "核心未返回 plan" else
                                        "plan digest=" + (J.optString(result, "digest") ?: "-") +
                                            " · steps=" + J.optArray(result, "steps").size +
                                            " · slots=" + J.optStringList(result, "slots").joinToString(",")
                                } else {
                                    error = response.error
                                }
                            } finally {
                                busy = false
                            }
                        }
                    }) { Text(if (busy) "调用中…" else "core graph-compile") }
                }
                error?.let { ErrorCard(it) }
                report?.let { r ->
                    KeyValue("校验", r.line())
                    for (issue in r.issues) Notice(issue.code + " " + (issue.path ?: "-") + "：" + issue.message)
                }
                planSummary?.let { Mono(it) }
            }
        }
    }
}
