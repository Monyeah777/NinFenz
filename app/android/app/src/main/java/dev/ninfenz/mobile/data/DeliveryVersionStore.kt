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

/** 装配结果版本：本地 sidecar，最多 20 个；用于 diff/恢复。 */
class DeliveryVersionStore(private val filesDir: File) {
    data class Version(val at: Long, val markdown: String)

    private fun file(projectId: String): File =
        File(File(filesDir, "exports/versions").apply { mkdirs() }, projectId + ".json")

    fun load(projectId: String): List<Version> {
        val f = file(projectId)
        if (!f.isFile) return emptyList()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["versions"]?.jsonArray?.mapNotNull { el ->
                val o = el.jsonObject
                Version(o["at"]?.jsonPrimitive?.long ?: 0L, o["markdown"]?.jsonPrimitive?.content ?: "")
            }.orEmpty()
        }.getOrElse { emptyList() }
    }

    fun save(projectId: String, markdown: String) {
        if (markdown.isBlank()) return
        val current = load(projectId)
        if (current.firstOrNull()?.markdown == markdown) return
        val next = (listOf(Version(System.currentTimeMillis(), markdown)) + current).take(20)
        val arr = buildJsonArray {
            next.forEach { v ->
                add(buildJsonObject {
                    put("at", v.at)
                    put("markdown", v.markdown)
                })
            }
        }
        AtomicFiles.writeText(file(projectId), buildJsonObject { put("versions", arr) }.toString())
    }

    fun clear(projectId: String) { file(projectId).delete() }
}
