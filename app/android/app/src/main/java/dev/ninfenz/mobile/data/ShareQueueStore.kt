package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 多条目分享队列的进程死亡恢复（仅当前队列，不含正文副本）。 */
class ShareQueueStore(private val filesDir: File) {
    data class Saved(val items: List<SharedItem>, val cursor: Int)

    private fun file(): File = File(filesDir, "share-queue.json")

    fun load(): Saved? {
        val f = file()
        if (!f.isFile) return null
        return try {
            val root = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            val items = root["items"]?.jsonArray?.mapNotNull { el ->
                val o = el as? kotlinx.serialization.json.JsonObject ?: return@mapNotNull null
                SharedItem(
                    uri = o["uri"]?.jsonPrimitive?.content,
                    text = o["text"]?.jsonPrimitive?.content,
                    mime = o["mime"]?.jsonPrimitive?.content,
                    name = o["name"]?.jsonPrimitive?.content
                )
            } ?: emptyList()
            if (items.isEmpty()) null else Saved(items, root["cursor"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0)
        } catch (t: Throwable) {
            null
        }
    }

    fun save(items: List<SharedItem>, cursor: Int) {
        if (items.isEmpty()) {
            file().delete()
            return
        }
        val obj = buildJsonObject {
            put("cursor", cursor)
            put("items", buildJsonArray {
                items.forEach { item ->
                    add(buildJsonObject {
                        item.uri?.let { put("uri", it) }
                        item.text?.let { put("text", it) }
                        item.mime?.let { put("mime", it) }
                        item.name?.let { put("name", it) }
                    })
                }
            })
        }
        AtomicFiles.writeText(file(), obj.toString())
    }

    fun clear() {
        file().delete()
    }
}
