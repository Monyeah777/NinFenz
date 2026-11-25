package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 自动动作的“为什么/可撤销”：本地 append-only 记录，不联网。 */
data class DecisionRecord(
    val id: String,
    val action: String,
    val reason: String,
    val undoable: Boolean,
    val reversed: Boolean = false,
    val at: Long = System.currentTimeMillis()
)

class DecisionStore(private val filesDir: File) {
    private fun file(): File = File(filesDir, "decisions.json")

    fun load(): List<DecisionRecord> = try {
        val root = Json.parseToJsonElement(file().readText(Charsets.UTF_8)).jsonObject
        root["records"]?.jsonArray?.mapNotNull { e ->
            val o = e.jsonObject
            DecisionRecord(
                id = o["id"]?.jsonPrimitive?.content ?: return@mapNotNull null,
                action = o["action"]?.jsonPrimitive?.content ?: "",
                reason = o["reason"]?.jsonPrimitive?.content ?: "",
                undoable = o["undoable"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false,
                reversed = o["reversed"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false,
                at = o["at"]?.jsonPrimitive?.content?.toLongOrNull() ?: 0L
            )
        }.orEmpty()
    } catch (_: Throwable) { emptyList() }

    fun append(action: String, reason: String, undoable: Boolean): DecisionRecord {
        val rec = DecisionRecord("d-" + System.nanoTime(), action, reason, undoable)
        save(load() + rec)
        return rec
    }

    fun reverse(id: String): Boolean {
        val all = load()
        val idx = all.indexOfFirst { it.id == id && it.undoable && !it.reversed }
        if (idx < 0) return false
        save(all.toMutableList().also { it[idx] = it[idx].copy(reversed = true) })
        return true
    }

    private fun save(records: List<DecisionRecord>) {
        val root = buildJsonObject {
            put("schema", "nf-decision-log/1")
            putJsonArray("records") {
                records.forEach { r ->
                    add(buildJsonObject {
                        put("id", r.id); put("action", r.action); put("reason", r.reason)
                        put("undoable", r.undoable); put("reversed", r.reversed); put("at", r.at)
                    })
                }
            }
        }
        file().writeText(root.toString(), Charsets.UTF_8)
    }
}
