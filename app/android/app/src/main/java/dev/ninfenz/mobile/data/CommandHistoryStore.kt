package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

/** 命令面板最近使用：最多 5 个 id，最近优先。 */
class CommandHistoryStore(private val filesDir: File) {
    private fun file(): File = File(filesDir, "command-history.json")

    fun load(): List<String> {
        val f = file()
        if (!f.isFile) return emptyList()
        return try {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonArray
                .mapNotNull { it.jsonPrimitive.content.takeIf { id -> id.isNotBlank() } }
        } catch (t: Throwable) {
            emptyList()
        }
    }

    fun record(id: String) {
        if (id.isBlank()) return
        val next = (listOf(id) + load().filterNot { it == id }).take(5)
        AtomicFiles.writeText(file(), buildJsonArray {
            next.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) }
        }.toString())
    }
}
