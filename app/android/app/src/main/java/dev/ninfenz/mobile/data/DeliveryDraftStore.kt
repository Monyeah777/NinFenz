package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 交付台槽位输入草稿：进入/离开/防抖时写入，进程被杀后可恢复。 */
class DeliveryDraftStore(private val filesDir: File) {
    private fun file(projectId: String): File {
        val safe = projectId.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }
        return File(File(filesDir, "drafts").apply { mkdirs() }, "delivery-" + safe + ".json")
    }

    fun loadPlan(projectId: String): JsonObject? {
        val f = file(projectId)
        if (!f.isFile) return null
        return try {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            root["plan"] as? JsonObject
        } catch (t: Throwable) {
            null
        }
    }

    fun load(projectId: String): Map<String, String> {
        val f = file(projectId)
        if (!f.isFile) return emptyMap()
        return try {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            val slots = root["slots"] as? JsonObject ?: return emptyMap()
            slots.entries.associate { (k, v) -> k to v.jsonPrimitive.content }
        } catch (t: Throwable) {
            emptyMap()
        }
    }

    fun loadMarkdown(projectId: String): String? {
        val f = file(projectId)
        if (!f.isFile) return null
        return try {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            root["markdown"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
        } catch (t: Throwable) {
            null
        }
    }

    fun save(projectId: String, slots: Map<String, String>, plan: JsonObject? = null, markdown: String? = null) {
        val nonBlank = slots.filterValues { it.isNotBlank() }
        val f = file(projectId)
        if (nonBlank.isEmpty() && plan == null && markdown.isNullOrBlank()) {
            f.delete()
            return
        }
        val payload = buildJsonObject {
            put("schema", "nf-delivery-draft/1")
            put("project_id", projectId)
            put("slots", buildJsonObject { nonBlank.forEach { (k, v) -> put(k, v) } })
            put("markdown", markdown.orEmpty())
            plan?.let { put("plan", it) }
        }
        AtomicFiles.writeText(f, payload.toString())
    }

    fun clear(projectId: String) {
        file(projectId).delete()
    }
}
