package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put

/** 导入历史：按内容 digest 识别重复导入，只做提示，不阻断用户。 */
class ImportHistoryStore(private val filesDir: File) {
    data class Entry(val digest: String, val name: String, val importedAt: Long)

    private fun file(): File = File(File(filesDir, "drafts").apply { mkdirs() }, "import-history.json")

    fun find(digest: String): Entry? {
        if (digest.isBlank()) return null
        return load().firstOrNull { it.digest == digest }
    }

    fun recent(limit: Int = 10): List<Entry> = load().take(limit.coerceAtLeast(0))

    fun clear() {
        file().delete()
    }

    fun record(digest: String, name: String) {
        if (digest.isBlank()) return
        val now = System.currentTimeMillis()
        val next = (load().filterNot { it.digest == digest } + Entry(digest, name, now))
            .sortedByDescending { it.importedAt }
            .take(100)
        val arr = buildJsonArray {
            next.forEach { e ->
                add(buildJsonObject {
                    put("digest", e.digest)
                    put("name", e.name)
                    put("imported_at", e.importedAt)
                })
            }
        }
        AtomicFiles.writeText(file(), arr.toString())
    }

    private fun load(): List<Entry> {
        val f = file()
        if (!f.isFile) return emptyList()
        return try {
            val arr = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonArray
            arr.mapNotNull { el ->
                val o = el as? JsonObject ?: return@mapNotNull null
                Entry(
                    digest = o["digest"]?.jsonPrimitive?.content ?: return@mapNotNull null,
                    name = o["name"]?.jsonPrimitive?.content ?: "",
                    importedAt = o["imported_at"]?.jsonPrimitive?.long ?: 0L
                )
            }
        } catch (t: Throwable) {
            emptyList()
        }
    }
}
