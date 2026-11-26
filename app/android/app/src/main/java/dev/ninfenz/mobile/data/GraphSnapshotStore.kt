package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.PipelineGraph
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 管线图快照：本地 JSON，最多 20 份；恢复时重新过 GraphModel.parse。 */
class GraphSnapshotStore(private val filesDir: File, private val projectId: String) {
    data class Snapshot(
        val id: String,
        val at: Long,
        val nodes: Int,
        val edges: Int,
        val json: String
    )

    private fun dir(): File =
        File(File(File(File(filesDir, "projects"), projectId), "authoring"), "graph-snapshots").apply { mkdirs() }

    fun list(): List<Snapshot> = dir().listFiles()
        ?.filter { it.isFile && it.name.endsWith(".json") }
        ?.sortedByDescending { it.lastModified() }
        ?.mapNotNull { f ->
            runCatching {
                val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
                Snapshot(
                    id = f.nameWithoutExtension,
                    at = o["at"]?.jsonPrimitive?.content?.toLongOrNull() ?: f.lastModified(),
                    nodes = o["nodes"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0,
                    edges = o["edges"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0,
                    json = o["graph"]?.jsonPrimitive?.content ?: return@runCatching null
                )
            }.getOrNull()
        }.orEmpty()

    fun save(graph: PipelineGraph): List<Snapshot> {
        val at = System.currentTimeMillis()
        val o = buildJsonObject {
            put("at", at)
            put("nodes", graph.nodes.size)
            put("edges", graph.edges.size)
            put("graph", GraphModel.toJson(graph).toString())
        }
        AtomicFiles.writeText(File(dir(), "graph-" + at + ".json"), o.toString())
        val all = list()
        all.drop(20).forEach { runCatching { File(dir(), it.id + ".json").delete() } }
        return list()
    }

    fun remove(id: String) {
        File(dir(), id + ".json").delete()
    }

    fun restore(snapshot: Snapshot): PipelineGraph = GraphModel.parse(snapshot.json)
}
