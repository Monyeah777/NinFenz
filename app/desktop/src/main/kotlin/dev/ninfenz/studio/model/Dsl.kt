package dev.ninfenz.studio.model

import kotlinx.serialization.json.JsonObject

data class DslIssue(val line: Int, val message: String, val fix: String)

data class DslResult(val graph: PipelineGraph, val issues: List<DslIssue>) {
    val ok: Boolean get() = issues.isEmpty()
}

/**
 * Author DSL（Studio 文本作者面）：与人读的图编辑等价，产物是 nf-pipeline-graph/1。
 * 语法（行首 # 为注释）：
 *   graph <id> <semver>
 *   mode <simple|pro|expert>
 *   node <N##> <kind> "<title>" [module=<module-id>]
 *   edge <E##> <from>:<fromPort> -> <to>:<toPort> [type=data|control]
 *   weight <N##> <0..100>
 *   required <N##>
 * 解析失败给出 line + fix，绝不静默吞行。
 */
object Dsl {

    private val TITLE = Regex("\"([^\"]*)\"")
    private val EDGE = Regex("^edge\\s+(E[0-9]{2,3})\\s+([^\\s]+)\\s+->\\s+([^\\s]+)(?:\\s+type=(\\w+))?$")
    private val NODE = Regex("^node\\s+(N[0-9]{2,3})\\s+(\\w+)\\s+(.+)$")
    private val WEIGHT = Regex("^weight\\s+(N[0-9]{2,3})\\s+(-?[0-9]+)$")
    private val REQUIRED = Regex("^required\\s+(N[0-9]{2,3})$")
    private val GRAPH = Regex("^graph\\s+(\\S+)\\s+(\\S+)$")
    private val MODE = Regex("^mode\\s+(simple|pro|expert)$")

    fun parse(text: String): DslResult {
        var id = "draft-graph"
        var version = "0.1.0"
        var mode = "pro"
        val nodes = mutableListOf<GraphNode>()
        val edges = mutableListOf<GraphEdge>()
        val weights = LinkedHashMap<String, Int>()
        val required = mutableListOf<String>()
        val issues = mutableListOf<DslIssue>()

        text.lines().forEachIndexed { index, rawLine ->
            val lineNo = index + 1
            val line = rawLine.trim()
            if (line.isEmpty() || line.startsWith("#")) return@forEachIndexed
            when {
                line.startsWith("graph ") -> {
                    val m = GRAPH.matchEntire(line)
                    if (m == null) issues.add(DslIssue(lineNo, "graph 语法错误：" + line, "graph <id> <semver>"))
                    else {
                        id = m.groupValues[1]
                        version = m.groupValues[2]
                    }
                }
                line.startsWith("mode ") -> {
                    val m = MODE.matchEntire(line)
                    if (m == null) issues.add(DslIssue(lineNo, "mode 只能是 simple/pro/expert", "mode pro"))
                    else mode = m.groupValues[1]
                }
                line.startsWith("node ") -> {
                    val m = NODE.matchEntire(line)
                    if (m == null) {
                        val message = if (TITLE.find(line) == null) "node 缺带引号标题" else "node 语法错误：" + line
                        issues.add(DslIssue(lineNo, message, "node N01 stage \"标题\""))
                        return@forEachIndexed
                    }
                    val nodeId = m.groupValues[1]
                    val kind = m.groupValues[2]
                    val rest = m.groupValues[3]
                    val titleMatch = TITLE.find(rest)
                    val title = titleMatch?.groupValues?.get(1)
                    val moduleId = Regex("module=([A-Za-z0-9._-]+)").find(rest)?.groupValues?.get(1)
                    if (kind !in GraphModel.NODE_KINDS) {
                        issues.add(DslIssue(lineNo, "未知节点类型：" + kind, GraphModel.NODE_KINDS.joinToString("/")))
                        return@forEachIndexed
                    }
                    if (title.isNullOrBlank()) {
                        issues.add(DslIssue(lineNo, "node 缺带引号标题", "node " + nodeId + " " + kind + " \"标题\""))
                        return@forEachIndexed
                    }
                    if (nodes.any { it.id == nodeId }) {
                        issues.add(DslIssue(lineNo, "节点 id 重复：" + nodeId, "改用唯一 id"))
                        return@forEachIndexed
                    }
                    val portsIn = if (kind == "stage" && nodes.isEmpty()) emptyList() else listOf("in")
                    val portsOut = listOf("out")
                    nodes.add(GraphNode(nodeId, kind, title, portsIn, portsOut, moduleId))
                    if (kind == "module" && moduleId == null) {
                        issues.add(DslIssue(lineNo, "module 节点缺 module=<id>", "node " + nodeId + " module \"标题\" module=mod-x"))
                    }
                }
                line.startsWith("edge ") -> {
                    val m = EDGE.matchEntire(line)
                    if (m == null) {
                        issues.add(DslIssue(lineNo, "edge 语法错误：" + line, "edge E01 N01:out -> N02:in"))
                        return@forEachIndexed
                    }
                    val edgeId = m.groupValues[1]
                    val fromSpec = m.groupValues[2]
                    val toSpec = m.groupValues[3]
                    val edgeType = if (m.groupValues[4].isBlank()) "data" else m.groupValues[4]
                    val fromParts = fromSpec.split(":")
                    val toParts = toSpec.split(":")
                    if (fromParts.size != 2 || toParts.size != 2) {
                        issues.add(DslIssue(lineNo, "端点必须写 node:port", "edge " + edgeId + " N01:out -> N02:in"))
                        return@forEachIndexed
                    }
                    if (edges.any { it.id == edgeId }) {
                        issues.add(DslIssue(lineNo, "边 id 重复：" + edgeId, "改用唯一 id"))
                        return@forEachIndexed
                    }
                    val fromNode = nodes.firstOrNull { it.id == fromParts[0] }
                    val toNode = nodes.firstOrNull { it.id == toParts[0] }
                    if (fromNode == null) {
                        issues.add(DslIssue(lineNo, "边引用未声明节点：" + fromParts[0], "先声明 node " + fromParts[0]))
                    }
                    if (toNode == null) {
                        issues.add(DslIssue(lineNo, "边引用未声明节点：" + toParts[0], "先声明 node " + toParts[0]))
                    }
                    if (fromNode != null && fromParts[1] !in fromNode.portsOut) {
                        issues.add(DslIssue(lineNo, "from_port 未声明：" + fromParts[1], "端口只能是 out"))
                    }
                    if (toNode != null && toParts[1] !in toNode.portsIn) {
                        issues.add(DslIssue(lineNo, "to_port 未声明：" + toParts[1], "节点输入端口为 in"))
                    }
                    edges.add(GraphEdge(edgeId, fromParts[0], toParts[0], fromParts[1], toParts[1], edgeType))
                }
                line.startsWith("weight ") -> {
                    val m = WEIGHT.matchEntire(line)
                    if (m == null) {
                        issues.add(DslIssue(lineNo, "weight 语法错误：" + line, "weight N01 30"))
                    } else if (m.groupValues[2].toInt() !in 0..100) {
                        issues.add(DslIssue(lineNo, "权重越界（0..100）：" + m.groupValues[2], "weight " + m.groupValues[1] + " 30"))
                    } else {
                        weights[m.groupValues[1]] = m.groupValues[2].toInt()
                    }
                }
                line.startsWith("required ") -> {
                    val m = REQUIRED.matchEntire(line)
                    if (m == null) issues.add(DslIssue(lineNo, "required 语法错误：" + line, "required N01"))
                    else required.add(m.groupValues[1])
                }
                else -> issues.add(DslIssue(lineNo, "未知指令：" + line,
                    "支持 graph/mode/node/edge/weight/required（# 注释）"))
            }
        }

        val graph = PipelineGraph(
            id = id, version = version, title = id, mode = mode,
            nodes = nodes, edges = edges, weights = weights,
            requiredStages = required, seed = null, params = JsonObject(emptyMap())
        )
        val semantic = GraphModel.issues(graph).map { DslIssue(0, it.code + " " + it.path + "：" + it.message, it.fix) }
        return DslResult(graph, issues + semantic)
    }

    fun emit(g: PipelineGraph): String {
        val sb = StringBuilder()
        sb.appendLine("# nf-pipeline-graph/1（Studio DSL；由 Graph 面板生成）")
        sb.appendLine("graph " + g.id + " " + g.version)
        sb.appendLine("mode " + g.mode)
        for (n in g.nodes) {
            val module = if (n.moduleId != null) " module=" + n.moduleId else ""
            sb.appendLine("node " + n.id + " " + n.kind + " \"" + n.title + "\"" + module)
        }
        for (e in g.edges) {
            sb.appendLine("edge " + e.id + " " + e.from + ":" + e.fromPort + " -> " + e.to + ":" + e.toPort + " type=" + e.type)
        }
        for ((nodeId, weight) in g.weights) {
            sb.appendLine("weight " + nodeId + " " + weight)
        }
        for (req in g.requiredStages) {
            sb.appendLine("required " + req)
        }
        return sb.toString()
    }
}
