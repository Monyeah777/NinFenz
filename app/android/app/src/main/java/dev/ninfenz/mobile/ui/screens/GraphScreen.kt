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
import androidx.compose.ui.res.stringResource
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
import dev.ninfenz.mobile.ui.design.NfType
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

private fun emptyGraph(title: String): PipelineGraph {
    return PipelineGraph(
        id = "draft-graph",
        version = "0.1.0",
        title = title,
        mode = "pro",
        nodes = emptyList(),
        edges = emptyList(),
        weights = emptyMap(),
        requiredStages = emptyList(),
        seed = null,
        params = JsonObject(emptyMap())
    )
}

@Composable
fun GraphScreen(store: LibraryStore, onBack: () -> Unit) {
    val context = LocalContext.current
    val unnamedTitle = stringResource(dev.ninfenz.mobile.R.string.unnamed_pipeline)
    val scope = rememberCoroutineScope()
    var graph by remember { mutableStateOf<PipelineGraph?>(null) }
    var error by remember { mutableStateOf<CoreError?>(null) }
    var report by remember { mutableStateOf<ValidateReport?>(null) }
    var planSummary by remember { mutableStateOf<String?>(null) }
    var compileRepro by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var nodeTitle by remember { mutableStateOf("") }
    var nodeKind by remember { mutableStateOf("stage") }
    var edgeFrom by remember { mutableStateOf("") }
    var edgeTo by remember { mutableStateOf("") }
    var edgeFromPort by remember { mutableStateOf("out") }
    var edgeToPort by remember { mutableStateOf("in") }
    var savedPath by remember { mutableStateOf<String?>(null) }

    val picker = rememberGraphPicker(context, scope,
        onLoaded = { graph = it; error = null; report = null; planSummary = null },
        onError = { error = it })

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.graph_title), onBack = onBack) {
        GraphHeaderCard(graph, unnamedTitle, context,
            onOpen = { picker(arrayOf("application/json", "text/plain")) },
            onNew = {
                graph = emptyGraph(unnamedTitle)
                report = null
                planSummary = null
                error = null
            })

        error?.let { ErrorNotice(it) }

        val g = graph
        if (g != null) {
            GraphNodesCard(g, nodeTitle, nodeKind,
                onGraphChange = { graph = it }, onNodeTitleChange = { nodeTitle = it },
                onNodeKindChange = { nodeKind = it }, onInvalidate = { report = null; planSummary = null })
            GraphEdgesCard(g, edgeFrom, edgeTo, edgeFromPort, edgeToPort,
                onGraphChange = { graph = it }, onEdgeFromChange = { edgeFrom = it },
                onEdgeToChange = { edgeTo = it }, onEdgeFromPortChange = { edgeFromPort = it },
                onEdgeToPortChange = { edgeToPort = it }, onInvalidate = { report = null; planSummary = null })
            GraphLocalCheckCard(g, context)
            GraphCoreCards(GraphCoreCardsArgs(g, store, busy, savedPath, report, planSummary, compileRepro,
                onBusyChange = { busy = it }, onError = { error = it }, onReport = { report = it },
                onPlanSummary = { planSummary = it }, onCompileRepro = { compileRepro = it },
                onSavedPath = { savedPath = it }))
        }
    }
}

@Composable
private fun rememberGraphPicker(
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    onLoaded: (PipelineGraph) -> Unit,
    onError: (CoreError?) -> Unit
): (Array<String>) -> Unit {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                onLoaded(GraphModel.parse(FileAccess.readText(context, uri)))
            } catch (e: Exception) {
                onError(CoreResponse.failure(
                    (e as? dev.ninfenz.mobile.core.ModelException)?.code ?: "NF-GRF-001",
                    context.getString(dev.ninfenz.mobile.R.string.graph_parse_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.graph_parse_failed_fix),
                    1
                ).error)
            }
        }
    }
    return { input -> picker.launch(input) }
}

@Composable
private fun GraphHeaderCard(
    graph: PipelineGraph?,
    unnamedTitle: String,
    context: android.content.Context,
    onOpen: () -> Unit,
    onNew: () -> Unit
) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.graph_card)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onOpen) { Text(stringResource(dev.ninfenz.mobile.R.string.graph_open)) }
            OutlinedButton(onClick = onNew) { Text(stringResource(dev.ninfenz.mobile.R.string.graph_new)) }
        }
        if (graph == null) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.graph_empty))
        } else {
            KeyValue("id/version", graph.id + " " + graph.version)
            KeyValue("mode", graph.mode)
            KeyValue(context.getString(dev.ninfenz.mobile.R.string.graph_nodes_edges), graph.nodes.size.toString() + " / " + graph.edges.size)
            KeyValue("required_stages", graph.requiredStages.joinToString(",").ifBlank { context.getString(dev.ninfenz.mobile.R.string.graph_empty_value) })
        }
    }
}

@Composable
private fun GraphLocalCheckCard(g: PipelineGraph, context: android.content.Context) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.graph_local_check)) {
        val issues = GraphModel.formIssues(g)
        if (issues.isEmpty()) Notice(stringResource(dev.ninfenz.mobile.R.string.graph_local_ok), Tone.INFO)
        for (issue in issues) Notice(issue.code + " " + issue.path + "：" + issue.message + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + issue.fix, Tone.WARN)
    }
}

@Composable
private fun GraphNodesCard(
    g: PipelineGraph,
    nodeTitle: String,
    nodeKind: String,
    onGraphChange: (PipelineGraph) -> Unit,
    onNodeTitleChange: (String) -> Unit,
    onNodeKindChange: (String) -> Unit,
    onInvalidate: () -> Unit
) {
    val context = LocalContext.current
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.graph_nodes)) {
        if (g.nodes.isEmpty()) EmptyState(stringResource(dev.ninfenz.mobile.R.string.graph_no_nodes))
        for (node in g.nodes) {
            Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(node.id + " · " + node.kind + " · " + node.title, style = NfType.secondary)
                    Text(stringResource(dev.ninfenz.mobile.R.string.graph_ports, node.portsIn.joinToString(","), node.portsOut.joinToString(",")),
                        style = NfType.meta)
                }
                FormTextField(
                    label = context.getString(dev.ninfenz.mobile.R.string.graph_weight),
                    value = g.weights[node.id]?.toString() ?: "",
                    onValueChange = { v ->
                        val weight = v.toIntOrNull()
                        onGraphChange(GraphModel.withWeight(g, node.id, if (v.isBlank()) null else weight))
                    }
                )
                OutlinedButton(onClick = { onGraphChange(GraphModel.withoutNode(g, node.id)) }) { Text(stringResource(dev.ninfenz.mobile.R.string.graph_delete)) }
            }
        }
        FormTextField(label = context.getString(dev.ninfenz.mobile.R.string.graph_new_node_title), value = nodeTitle, onValueChange = onNodeTitleChange)
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { onNodeKindChange("stage") }) { Text(if (nodeKind == "stage") "[stage]" else "stage") }
            OutlinedButton(onClick = { onNodeKindChange("module") }) { Text(if (nodeKind == "module") "[module]" else "module") }
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
                onGraphChange(GraphModel.withNode(g, node))
                onNodeTitleChange("")
                onInvalidate()
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.graph_add_node)) }
        }
    }
}

@Composable
private fun GraphEdgesCard(
    g: PipelineGraph,
    edgeFrom: String,
    edgeTo: String,
    edgeFromPort: String,
    edgeToPort: String,
    onGraphChange: (PipelineGraph) -> Unit,
    onEdgeFromChange: (String) -> Unit,
    onEdgeToChange: (String) -> Unit,
    onEdgeFromPortChange: (String) -> Unit,
    onEdgeToPortChange: (String) -> Unit,
    onInvalidate: () -> Unit
) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.graph_edges)) {
        if (g.edges.isEmpty()) EmptyState(stringResource(dev.ninfenz.mobile.R.string.graph_no_edges))
        for (edge in g.edges) {
            Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(edge.id + " · " + edge.from + "(" + edge.fromPort + ") -> " + edge.to + "(" + edge.toPort + ")",
                        style = NfType.meta)
                    Text(stringResource(dev.ninfenz.mobile.R.string.graph_type, edge.type), style = NfType.meta)
                }
                OutlinedButton(onClick = { onGraphChange(GraphModel.withoutEdge(g, edge.id)) }) { Text(stringResource(dev.ninfenz.mobile.R.string.graph_delete)) }
            }
        }
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FormTextField(label = "from", value = edgeFrom, onValueChange = onEdgeFromChange)
            FormTextField(label = "to", value = edgeTo, onValueChange = onEdgeToChange)
        }
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FormTextField(label = "from_port", value = edgeFromPort, onValueChange = onEdgeFromPortChange)
            FormTextField(label = "to_port", value = edgeToPort, onValueChange = onEdgeToPortChange)
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
            onGraphChange(GraphModel.withEdge(g, edge))
            onInvalidate()
        }) { Text(stringResource(dev.ninfenz.mobile.R.string.graph_add_edge)) }
    }
}
