package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** 作者管线图（nf-pipeline-graph/1）：节点 / 边 / 权重 / 必需阶段。 */
data class GraphNode(
    val id: String,
    val kind: String,
    val title: String,
    val portsIn: List<String>,
    val portsOut: List<String>,
    val moduleId: String?,
    val moduleVersion: String?,
    val moduleDigest: String?
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
)

/** 本地表单检查条目：非契约校验（权威校验走核心 graph-validate），但 code 与错误码表一致。 */
data class FormIssue(
    val code: String,
    val path: String,
    val message: String,
    val fix: String
)

object GraphModel {
    const val SCHEMA = "nf-pipeline-graph/1"
    val NODE_ID = Regex("^N[0-9]{2,3}$")
    val EDGE_ID = Regex("^E[0-9]{2,3}$")
    val WEIGHT_RANGE = 0..100

    fun parse(text: String): PipelineGraph = parse(J.parseObject(text, SCHEMA))

    fun parse(o: JsonObject): PipelineGraph {
        J.schema(o, SCHEMA)
        val nodes = J.array(o, "nodes", "").mapIndexed { i, el ->
            val n = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/nodes/" + i, "节点应为对象", "按 schema 修正")
            val p = "/nodes/" + i
            val ports = J.optChild(n, "ports")
            val moduleRef = J.optChild(n, "module_ref")
            GraphNode(
                id = J.string(n, "id", p),
                kind = J.string(n, "kind", p),
                title = J.string(n, "title", p),
                portsIn = ports?.let { J.optStringList(it, "in") } ?: emptyList(),
                portsOut = ports?.let { J.optStringList(it, "out") } ?: emptyList(),
                moduleId = moduleRef?.let { J.optString(it, "id") },
                moduleVersion = moduleRef?.let { J.optString(it, "version") },
                moduleDigest = moduleRef?.let { J.optString(it, "digest") }
            )
        }
        val edges = J.array(o, "edges", "").mapIndexed { i, el ->
            val e = el as? JsonObject
                ?: throw ModelException("NF-E-002", "/edges/" + i, "边应为对象", "按 schema 修正")
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

    /** 回写 nf-pipeline-graph/1（供核心 graph-validate / graph-compile 使用；不含 digest 字段）。 */
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
                    put("module_ref", buildJsonObject {
                        put("id", n.moduleId)
                        if (n.moduleVersion != null) put("version", n.moduleVersion)
                        if (n.moduleDigest != null) put("digest", n.moduleDigest)
                    })
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
        put("weights", buildJsonObject {
            for ((k, v) in g.weights) put(k, v)
        })
        put("params", g.params)
        put("settings", buildJsonObject {
            put("required_stages", strArray(g.requiredStages))
            if (g.seed != null) put("seed", g.seed)
        })
    }

    /** 本地表单检查（明确非契约校验；图语义权威校验由核心承担）。 */
    fun formIssues(g: PipelineGraph): List<FormIssue> {
        val issues = mutableListOf<FormIssue>()
        checkNodes(g, issues)
        checkEdges(g, issues)
        checkWeights(g, issues)
        val stages = g.nodes.filter { it.kind == "stage" }
        val modules = g.nodes.filter { it.kind == "module" }
        if (stages.isEmpty()) issues.add(FormIssue("NF-GRF-005", "/nodes", "图至少需要 1 个 stage 节点", "补 stage 节点"))
        if (modules.isEmpty()) issues.add(FormIssue("NF-GRF-005", "/nodes", "图至少需要 1 个 module 节点", "补 module 节点"))
        checkRequiredStages(g, issues)
        if (g.mode == "simple") checkSimpleMode(g, issues)
        if (hasCycle(g)) {
            issues.add(FormIssue("NF-GRF-004", "/edges", "图含环（非 DAG）", "删除回边或改为 DAG"))
        }
        return issues
    }

    private fun checkNodes(g: PipelineGraph, issues: MutableList<FormIssue>) {
        val nodeIds = mutableMapOf<String, Int>()
        for (n in g.nodes) {
            val count = (nodeIds[n.id] ?: 0) + 1
            nodeIds[n.id] = count
            if (!NODE_ID.matches(n.id)) {
                issues.add(FormIssue("NF-GRF-001", "/nodes", "节点 id 不合规：" + n.id, "改用 N## / N### 形式"))
            }
            if (n.kind == "module" && n.moduleId.isNullOrBlank()) {
                issues.add(FormIssue("NF-GRF-001", "/nodes/" + n.id, "module 节点缺 module_ref", "补 module_ref.id"))
            }
        }
        for ((id, count) in nodeIds) {
            if (count > 1) issues.add(FormIssue("NF-GRF-002", "/nodes", "节点 id 重复：" + id, "改用唯一 id"))
        }
    }

    private fun checkEdges(g: PipelineGraph, issues: MutableList<FormIssue>) {
        val edgeIds = mutableMapOf<String, Int>()
        for (e in g.edges) {
            edgeIds[e.id] = (edgeIds[e.id] ?: 0) + 1
            if (!EDGE_ID.matches(e.id)) {
                issues.add(FormIssue("NF-GRF-001", "/edges", "边 id 不合规：" + e.id, "改用 E## / E### 形式"))
            }
            val from = g.nodes.firstOrNull { it.id == e.from }
            val to = g.nodes.firstOrNull { it.id == e.to }
            if (from == null || to == null) {
                issues.add(FormIssue("NF-GRF-003", "/edges/" + e.id, "边端点不存在：" + e.from + " -> " + e.to, "先建节点或修边端点"))
                continue
            }
            if (e.fromPort !in from.portsOut) {
                issues.add(FormIssue("NF-GRF-003", "/edges/" + e.id, "from_port 未在节点输出端口声明：" + e.fromPort, "补端口声明"))
            }
            if (e.toPort !in to.portsIn) {
                issues.add(FormIssue("NF-GRF-003", "/edges/" + e.id, "to_port 未在节点输入端口声明：" + e.toPort, "补端口声明"))
            }
        }
        for ((id, count) in edgeIds) {
            if (count > 1) issues.add(FormIssue("NF-GRF-002", "/edges", "边 id 重复：" + id, "改用唯一 id"))
        }
    }

    private fun checkWeights(g: PipelineGraph, issues: MutableList<FormIssue>) {
        for ((nodeId, weight) in g.weights) {
            val node = g.nodes.firstOrNull { it.id == nodeId }
            if (node == null) {
                issues.add(FormIssue("NF-GRF-007", "/weights/" + nodeId, "权重挂在未知节点", "删除该权重项"))
            } else if (node.kind != "stage" && node.kind != "module") {
                issues.add(FormIssue("NF-GRF-007", "/weights/" + nodeId, "权重只能挂 stage/module，当前 " + node.kind, "改用 stage/module 或删除权重"))
            }
            if (weight !in WEIGHT_RANGE) {
                issues.add(FormIssue("NF-GRF-007", "/weights/" + nodeId, "权重越界：" + weight, "权重限 0..100"))
            }
        }
    }

    private fun checkRequiredStages(g: PipelineGraph, issues: MutableList<FormIssue>) {
        for (req in g.requiredStages) {
            if (g.nodes.none { it.id == req }) {
                issues.add(FormIssue("NF-GRF-005", "/settings/required_stages", "required_stages 指向不存在的节点：" + req, "补节点或改 required_stages"))
            }
        }
    }

    private fun checkSimpleMode(g: PipelineGraph, issues: MutableList<FormIssue>) {
        val forbidden = g.nodes.filter { it.kind == "branch" || it.kind == "merge" || it.kind == "asset" }
        for (n in forbidden) {
            issues.add(FormIssue("NF-GRF-006", "/nodes/" + n.id, "simple 模式禁止 " + n.kind + " 节点", "切 pro/expert 模式或删节点"))
        }
    }

    /** Kahn 拓扑排序：检测环（本地预检；核心 L1 会再判一次）。 */
    fun hasCycle(g: PipelineGraph): Boolean {
        val indegree = LinkedHashMap<String, Int>()
        for (n in g.nodes) indegree[n.id] = 0
        val adjacency = LinkedHashMap<String, MutableList<String>>()
        for (e in g.edges) {
            if (e.from !in indegree || e.to !in indegree) continue
            adjacency.getOrPut(e.from) { mutableListOf() }.add(e.to)
            indegree[e.to] = (indegree[e.to] ?: 0) + 1
        }
        val queue = ArrayDeque<String>()
        for ((id, deg) in indegree) if (deg == 0) queue.add(id)
        var visited = 0
        while (queue.isNotEmpty()) {
            val id = queue.removeFirst()
            visited++
            for (next in adjacency[id] ?: emptyList()) {
                val d = (indegree[next] ?: 1) - 1
                indegree[next] = d
                if (d == 0) queue.add(next)
            }
        }
        return visited != indegree.size
    }

    fun nextNodeId(g: PipelineGraph): String {
        var max = 0
        for (n in g.nodes) {
            val digits = n.id.drop(1).toIntOrNull() ?: continue
            if (digits > max) max = digits
        }
        val next = max + 1
        return if (next < 100) "N" + next.toString().padStart(2, '0') else "N" + next
    }

    fun nextEdgeId(g: PipelineGraph): String {
        var max = 0
        for (e in g.edges) {
            val digits = e.id.drop(1).toIntOrNull() ?: continue
            if (digits > max) max = digits
        }
        val next = max + 1
        return if (next < 100) "E" + next.toString().padStart(2, '0') else "E" + next
    }

    fun withNode(g: PipelineGraph, node: GraphNode): PipelineGraph =
        g.copy(nodes = g.nodes.filter { it.id != node.id } + node)

    fun withoutNode(g: PipelineGraph, nodeId: String): PipelineGraph = g.copy(
        nodes = g.nodes.filter { it.id != nodeId },
        edges = g.edges.filter { it.from != nodeId && it.to != nodeId },
        weights = g.weights - nodeId,
        requiredStages = g.requiredStages.filter { it != nodeId }
    )

    fun withEdge(g: PipelineGraph, edge: GraphEdge): PipelineGraph =
        g.copy(edges = g.edges.filter { it.id != edge.id } + edge)

    fun withoutEdge(g: PipelineGraph, edgeId: String): PipelineGraph =
        g.copy(edges = g.edges.filter { it.id != edgeId })

    fun withWeight(g: PipelineGraph, nodeId: String, weight: Int?): PipelineGraph {
        val weights = LinkedHashMap(g.weights)
        if (weight == null) weights.remove(nodeId) else weights[nodeId] = weight
        return g.copy(weights = weights)
    }

    private fun strArray(values: List<String>): JsonArray = JsonArray(values.map { JsonPrimitive(it) })
}
