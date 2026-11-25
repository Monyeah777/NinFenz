package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put

/** 装配输入预设：保存/应用一组槽位值；不绑定 plan 版本，应用时只填空。 */
class AssemblyPresetStore(private val filesDir: File) {
    data class Preset(val id: String, val name: String, val at: Long, val inputs: Map<String, String>)

    private fun file(projectId: String): File =
        File(File(filesDir, "assembly-presets").apply { mkdirs() }, projectId + ".json")

    fun load(projectId: String): List<Preset> {
        val f = file(projectId)
        if (!f.isFile) return emptyList()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["presets"]?.jsonArray?.mapNotNull { el ->
                val o = el.jsonObject
                Preset(
                    id = o["id"]?.jsonPrimitive?.content ?: "",
                    name = o["name"]?.jsonPrimitive?.content ?: "",
                    at = o["at"]?.jsonPrimitive?.long ?: 0L,
                    inputs = o["inputs"]?.jsonObject?.mapValues { it.value.jsonPrimitive.content }.orEmpty()
                )
            }.orEmpty()
        }.getOrElse { emptyList() }
    }

    fun save(projectId: String, name: String, inputs: Map<String, String>): List<Preset> {
        val current = load(projectId)
        val preset = Preset(
            id = "a" + System.currentTimeMillis().toString(36),
            name = name.trim().ifBlank { "Preset" },
            at = System.currentTimeMillis(),
            inputs = inputs.filterValues { it.isNotBlank() }
        )
        val next = (listOf(preset) + current).take(20)
        write(projectId, next)
        return next
    }

    fun remove(projectId: String, id: String) { write(projectId, load(projectId).filterNot { it.id == id }) }

    fun clear(projectId: String) { file(projectId).delete() }

    private fun write(projectId: String, presets: List<Preset>) {
        val arr = buildJsonArray {
            presets.forEach { p ->
                add(buildJsonObject {
                    put("id", p.id); put("name", p.name); put("at", p.at)
                    put("inputs", buildJsonObject { p.inputs.forEach { (k, v) -> put(k, v) } })
                })
            }
        }
        AtomicFiles.writeText(file(projectId), buildJsonObject { put("presets", arr) }.toString())
    }
}
