package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.put

/** 协议编辑未保存草稿：按项目保存 values/enabled，保存成功后清理。 */
class ProtocolDraftStore(private val filesDir: File) {
    data class Draft(val values: Map<String, String>, val enabled: Map<String, Boolean>)

    private fun file(projectId: String): File {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        return File(File(filesDir, "drafts").apply { mkdirs() }, "author-protocol-" + safe + ".json")
    }

    fun load(projectId: String): Draft? {
        val f = file(projectId)
        if (!f.isFile) return null
        return try {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            val values = (root["values"] as? JsonObject)?.entries?.associate { it.key to it.value.jsonPrimitive.content } ?: emptyMap()
            val enabled = (root["enabled"] as? JsonObject)?.entries?.associate {
                it.key to (it.value.jsonPrimitive.boolean)
            } ?: emptyMap()
            Draft(values, enabled)
        } catch (t: Throwable) {
            null
        }
    }

    fun save(projectId: String, values: Map<String, String>, enabled: Map<String, Boolean>) {
        if (values.isEmpty() && enabled.isEmpty()) return
        val payload = buildJsonObject {
            put("schema", "nf-author-protocol-draft/1")
            put("project_id", projectId)
            put("values", buildJsonObject { values.forEach { (k, v) -> put(k, v) } })
            put("enabled", buildJsonObject { enabled.forEach { (k, v) -> put(k, v) } })
        }
        AtomicFiles.writeText(file(projectId), payload.toString())
    }

    fun clear(projectId: String) {
        file(projectId).delete()
    }
}
