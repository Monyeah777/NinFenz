package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 协议填写快照：保存 values/enabled 两组状态，最多 20 份。 */
class ProtocolSnapshotStore(private val filesDir: File, private val projectId: String) {
    data class Snapshot(
        val id: String,
        val at: Long,
        val values: Map<String, String>,
        val enabled: Map<String, Boolean>
    )

    private fun dir(): File = File(File(File(File(filesDir, "projects"), projectId), "authoring"), "protocol-snapshots").apply { mkdirs() }

    fun list(): List<Snapshot> = dir().listFiles()?.filter { it.isFile && it.name.endsWith(".json") }
        ?.sortedByDescending { it.lastModified() }
        ?.mapNotNull { f ->
            runCatching {
                val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
                Snapshot(
                    id = f.nameWithoutExtension,
                    at = o["at"]?.jsonPrimitive?.content?.toLongOrNull() ?: f.lastModified(),
                    values = (o["values"] as? JsonObject)?.mapValues { it.value.jsonPrimitive.content }.orEmpty(),
                    enabled = (o["enabled"] as? JsonObject)?.mapValues {
                        it.value.jsonPrimitive.content.toBooleanStrictOrNull() ?: false
                    }.orEmpty()
                )
            }.getOrNull()
        }.orEmpty()

    fun save(values: Map<String, String>, enabled: Map<String, Boolean>): List<Snapshot> {
        val o = buildJsonObject {
            put("at", System.currentTimeMillis())
            put("values", buildJsonObject { values.forEach { (k, v) -> put(k, v) } })
            put("enabled", buildJsonObject { enabled.forEach { (k, v) -> put(k, v) } })
        }
        AtomicFiles.writeText(File(dir(), "snap-" + System.currentTimeMillis() + ".json"), o.toString())
        val all = list()
        all.drop(20).forEach { runCatching { File(dir(), it.id + ".json").delete() } }
        return list()
    }

    fun remove(id: String) {
        File(dir(), id + ".json").delete()
    }
}
