package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.SpecModel
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 规格快照：本地 JSON，最多 20 份；用于保存/恢复/轻量对比。 */
class SpecSnapshotStore(private val filesDir: File, private val projectId: String) {
    data class Snapshot(val id: String, val at: Long, val sections: Int, val slots: Int, val json: String)

    private fun dir(): File = File(File(File(File(filesDir, "projects"), projectId), "authoring"), "spec-snapshots").apply { mkdirs() }

    fun list(): List<Snapshot> = dir().listFiles()?.filter { it.isFile && it.name.endsWith(".json") }
        ?.sortedByDescending { it.lastModified() }
        ?.mapNotNull { f ->
            runCatching {
                val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
                Snapshot(
                    id = f.nameWithoutExtension,
                    at = o["at"]?.jsonPrimitive?.content?.toLongOrNull() ?: f.lastModified(),
                    sections = o["sections"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0,
                    slots = o["slots"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0,
                    json = o["spec"]?.toString() ?: return@runCatching null
                )
            }.getOrNull()
        }.orEmpty()

    fun save(spec: MdSpec): List<Snapshot> {
        val id = "snap-" + System.currentTimeMillis()
        val o = buildJsonObject {
            put("at", System.currentTimeMillis())
            put("sections", spec.sections.size)
            put("slots", spec.slots.size)
            put("spec", SpecModel.toJson(spec))
        }
        AtomicFiles.writeText(File(dir(), id + ".json"), o.toString())
        val all = list()
        all.drop(20).forEach { runCatching { File(dir(), it.id + ".json").delete() } }
        return list()
    }

    fun remove(id: String) {
        File(dir(), id + ".json").delete()
    }

    fun restore(snapshot: Snapshot): MdSpec = SpecModel.parse(snapshot.json)
}
