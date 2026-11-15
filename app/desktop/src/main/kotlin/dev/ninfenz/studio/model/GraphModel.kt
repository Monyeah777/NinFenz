package dev.ninfenz.studio.model

import dev.ninfenz.studio.core.J
import dev.ninfenz.studio.core.ModelException
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

data class GraphNode(
    val id: String,
    val kind: String,
    val title: String,
    val portsIn: List<String>,
    val portsOut: List<String>,
    val moduleId: String?
)

data class GraphEdge(
    val id: String,
    val from: String,
    val to: String,
    val fromPort: String,
    val toPort: String,
    val type: String
)

data class PipelineGraph(
    val id: String,
    val version: String,
    val title: String,
    val mode: String,
    val nodes: List<GraphNode>,
    val edges: List<GraphEdge>,
    val weights: Map<String, Int>,
    val requiredStages: List<String>,
    val seed: Int?,
    val params: JsonObject
) {
    companion object {
        fun empty(): PipelineGraph = PipelineGraph(
            id = "draft-graph", version = "0.1.0", title = "未命名管线", mode = "pro",
            nodes = emptyList(), edges = emptyList(), weights = emptyMap(),
            requiredStages = emptyList(), seed = null,
            params = JsonObject(emptyMap())
        )
    }
}

data class GraphIssue(val code: String, val path: String, val message: String, val fix: String)

object GraphModel {
    const val SCHEMA = "nf-pipeline-graph/1"
    val NODE_ID = Regex("^N[0-9]{2,3}$")
    val EDGE_ID = Regex("^E[0-9]{2,3}$")
    val NODE_KINDS = listOf("stage", "module", "asset", "gate", "merge", "branch")

    fun parse(text: String): PipelineGraph = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): PipelineGraph {
        J.schema(o, SCHEMA)
        val nodes = J.array(o, "nodes", "").mapIndexed { i, el ->
            val n = el as? JsonObject ?: throw ModelException("NF-E-002", "/nodes/" + i, "节点应为对象", "按 schema 修正")
            val p = "/nodes/" + i
            val ports = J.optChild(n, "ports")
            val module = J.optChild(n, "module_ref")
            GraphNode(
                id = J.string(n, "id", p),
                kind = J.string(n, "kind", p),
                title = J.string(n, "title", p),
                portsIn = ports?.let { J.optStringList(it, "in") } ?: emptyList(),
                portsOut = ports?.let { J.optStringList(it, "out") } ?: emptyList(),
                moduleId = module?.let { J.optString(it, "id") }
            )
        }
        val edges = J.array(o, "edges", "").mapIndexed { i, el ->
            val e = el as? JsonObject ?: throw ModelException("NF-E-002", "/edges/" + i, "边应为对象", "按 schema 修正")
            val p = "/edges/" + i
            GraphEdge(
                id = J.string(e, "id", p),
                from = J.string(e, "from", p),
                to = J.string(e, "to", p),
                fromPort = J.string(e, "from_port", p),
                toPort = J.string(e, "to_port", p),
                type = J.string(e, "type", p)
            )
        }
        val weights = LinkedHashMap<String, Int>()
        val weightsObj = J.optChild(o, "weights")
        if (weightsObj != null) {
            for ((key, value) in weightsObj) {
                val v = (value as? JsonPrimitive)?.content?.toIntOrNull()
                    ?: throw ModelException("NF-E-002", "/weights/" + key, "权重应为整数", "改用 0..100 整数")
                weights[key] = v
            }
        }
        val settings = J.child(o, "settings", "")
        return PipelineGraph(
            id = J.string(o, "id", ""),
            version = J.string(o, "version", ""),
            title = J.optString(o, "title") ?: J.string(o, "id", ""),
            mode = J.string(o, "mode", ""),
            nodes = nodes,
            edges = edges,
            weights = weights,
            requiredStages = J.optStringList(settings, "required_stages"),
            seed = J.optInt(settings, "seed"),
            params = J.optChild(o, "params") ?: JsonObject(emptyMap())
        )
    }

    fun toJson(g: PipelineGraph): JsonObject = buildJsonObject {
        put("schema", SCHEMA)
        put("id", g.id)
        put("version", g.version)
        put("title", g.title)
        put("mode", g.mode)
        put("nodes", JsonArray(g.nodes.map { n ->
            buildJsonObject {
                put("id", n.id)
                put("kind", n.kind)
                put("title", n.title)
                if (n.moduleId != null) {
                    put("module_ref", buildJsonObject { put("id", n.moduleId) })
                }
                put("ports", buildJsonObject {
                    put("in", strArray(n.portsIn))
                    put("out", strArray(n.portsOut))
                })
            }
        }))
        put("edges", JsonArray(g.edges.map { e ->
            buildJsonObject {
                put("id", e.id)
                put("from", e.from)
                put("to", e.to)
                put("from_port", e.fromPort)
                put("to_port", e.toPort)
                put("type", e.type)
            }
        }))
        put("weights", buildJsonObject { for ((k, v) in g.weights) put(k, v) })
        put("params", g.params)
        put("settings", buildJsonObject {
            put("required_stages", strArray(g.requiredStages))
            if (g.seed != null) put("seed", g.seed)
        })
    }

    fun issues(g: PipelineGraph): List<GraphIssue> {
        val out = mutableListOf<GraphIssue>()
        val ids = mutableSetOf<String>()
        for (n in g.nodes) {
            if (!ids.add(n.id)) out.add(GraphIssue("NF-GRF-002", "/nodes", "节点 id 重复：" + n.id, "改用唯一 id"))
            if (!NODE_ID.matches(n.id)) out.add(GraphIssue("NF-GRF-001", "/nodes", "节点 id 不合规：" + n.id, "用 N##"))
            if (n.kind == "module" && n.moduleId.isNullOrBlank()) out.add(GraphIssue("NF-GRF-001", "/nodes/" + n.id, "module 节点缺 module_ref", "补 module_ref"))
        }
        val edgeIds = mutableSetOf<String>()
        for (e in g.edges) {
            if (!edgeIds.add(e.id)) out.add(GraphIssue("NF-GRF-002", "/edges", "边 id 重复：" + e.id, "改用唯一 id"))
            if (!EDGE_ID.matches(e.id)) out.add(GraphIssue("NF-GRF-001", "/edges", "边 id 不合规：" + e.id, "用 E##"))
            val from = g.nodes.firstOrNull { it.id == e.from }
            val to = g.nodes.firstOrNull { it.id == e.to }
            if (from == null || to == null) {
                out.add(GraphIssue("NF-GRF-003", "/edges/" + e.id, "边端点不存在", "补节点/修边"))
                continue
            }
            if (e.fromPort !in from.portsOut) out.add(GraphIssue("NF-GRF-003", "/edges/" + e.id, "from_port 未声明", "补端口"))
            if (e.toPort !in to.portsIn) out.add(GraphIssue("NF-GRF-003", "/edges/" + e.id, "to_port 未声明", "补端口"))
        }
        for ((nodeId, weight) in g.weights) {
            val node = g.nodes.firstOrNull { it.id == nodeId }
            if (node == null) out.add(GraphIssue("NF-GRF-007", "/weights/" + nodeId, "权重挂未知节点", "删权重"))
            else if (node.kind != "stage" && node.kind != "module") out.add(GraphIssue("NF-GRF-007", "/weights/" + nodeId, "权重只能挂 stage/module", "改挂载点"))
            if (weight !in 0..100) out.add(GraphIssue("NF-GRF-007", "/weights/" + nodeId, "权重越界", "限 0..100"))
        }
        if (g.nodes.none { it.kind == "stage" }) out.add(GraphIssue("NF-GRF-005", "/nodes", "缺 stage 节点", "补 stage"))
        if (g.nodes.none { it.kind == "module" }) out.add(GraphIssue("NF-GRF-005", "/nodes", "缺 module 节点", "补 module"))
        for (req in g.requiredStages) {
            if (g.nodes.none { it.id == req }) out.add(GraphIssue("NF-GRF-005", "/settings/required_stages", "required_stages 指向不存在节点：" + req, "补节点"))
        }
        if (g.mode == "simple") {
            for (n in g.nodes.filter { it.kind in listOf("branch", "merge", "asset") }) {
                out.add(GraphIssue("NF-GRF-006", "/nodes/" + n.id, "simple 模式禁止 " + n.kind, "切 pro 或删节点"))
            }
        }
        if (hasCycle(g)) out.add(GraphIssue("NF-GRF-004", "/edges", "图含环", "删回边"))
        return out
    }

    fun hasCycle(g: PipelineGraph): Boolean {
        val indegree = LinkedHashMap<String, Int>()
        for (n in g.nodes) indegree[n.id] = 0
        val adj = LinkedHashMap<String, MutableList<String>>()
        for (e in g.edges) {
            if (e.from !in indegree || e.to !in indegree) continue
            adj.getOrPut(e.from) { mutableListOf() }.add(e.to)
            indegree[e.to] = (indegree[e.to] ?: 0) + 1
        }
        val queue = ArrayDeque<String>()
        for ((id, deg) in indegree) if (deg == 0) queue.add(id)
        var visited = 0
        while (queue.isNotEmpty()) {
            val id = queue.removeFirst()
            visited++
            for (next in adj[id] ?: emptyList()) {
                val d = (indegree[next] ?: 1) - 1
                indegree[next] = d
                if (d == 0) queue.add(next)
            }
        }
        return visited != indegree.size
    }

    fun nextNodeId(g: PipelineGraph): String {
        val max = g.nodes.mapNotNull { it.id.drop(1).toIntOrNull() }.maxOrNull() ?: 0
        val next = max + 1
        return if (next < 100) "N" + next.toString().padStart(2, '0') else "N" + next
    }

    fun nextEdgeId(g: PipelineGraph): String {
        val max = g.edges.mapNotNull { it.id.drop(1).toIntOrNull() }.maxOrNull() ?: 0
        val next = max + 1
        return if (next < 100) "E" + next.toString().padStart(2, '0') else "E" + next
    }

    fun withNode(g: PipelineGraph, node: GraphNode): PipelineGraph = g.copy(nodes = g.nodes.filter { it.id != node.id } + node)

    fun withoutNode(g: PipelineGraph, id: String): PipelineGraph = g.copy(
        nodes = g.nodes.filter { it.id != id },
        edges = g.edges.filter { it.from != id && it.to != id },
        weights = g.weights - id,
        requiredStages = g.requiredStages.filter { it != id }
    )

    fun withEdge(g: PipelineGraph, edge: GraphEdge): PipelineGraph = g.copy(edges = g.edges.filter { it.id != edge.id } + edge)
    fun withoutEdge(g: PipelineGraph, id: String): PipelineGraph = g.copy(edges = g.edges.filter { it.id != id })
    fun withWeight(g: PipelineGraph, id: String, weight: Int?): PipelineGraph {
        val map = LinkedHashMap(g.weights)
        if (weight == null) map.remove(id) else map[id] = weight
        return g.copy(weights = map)
    }

    private fun strArray(values: List<String>): JsonArray = JsonArray(values.map { JsonPrimitive(it) })
}
