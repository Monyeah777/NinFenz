package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

/** 本地搜索历史：最多 10 条，去重后最近优先；不联网。 */
class SearchHistoryStore(private val filesDir: File) {
    private fun file(): File = File(filesDir, "search-history.json")

    fun load(): List<String> {
        val f = file()
        if (!f.isFile) return emptyList()
        return try {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonArray
                .mapNotNull { it.jsonPrimitive.content.takeIf { q -> q.isNotBlank() } }
        } catch (t: Throwable) {
            emptyList()
        }
    }

    fun record(query: String) {
        val q = query.trim()
        if (q.isEmpty()) return
        val next = (listOf(q) + load().filterNot { it == q }).take(10)
        val arr = buildJsonArray { next.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
        AtomicFiles.writeText(file(), arr.toString())
    }

    fun clear() {
        file().delete()
    }
}
