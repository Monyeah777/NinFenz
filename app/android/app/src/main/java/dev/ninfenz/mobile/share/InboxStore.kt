package dev.ninfenz.mobile.share

import dev.ninfenz.mobile.data.AtomicFiles
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

/** 分享 Inbox：保存最近收到的分享载荷，支持去重、重新导入、删除。 */
class InboxStore(private val filesDir: File) {
    data class Entry(val id: String, val at: Long, val payload: SharePayload)

    private fun file(): File = File(File(filesDir, "inbox").apply { mkdirs() }, "queue.json")

    fun load(): List<Entry> {
        val f = file()
        if (!f.isFile) return emptyList()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonArray.mapNotNull { el ->
                val o = el as? JsonObject ?: return@mapNotNull null
                Entry(
                    id = o["id"]?.jsonPrimitive?.content ?: "",
                    at = o["at"]?.jsonPrimitive?.long ?: 0L,
                    payload = parsePayload(o["payload"]?.jsonObject ?: return@mapNotNull null)
                )
            }
        }.getOrElse { emptyList() }
    }

    fun enqueue(context: android.content.Context, payload: SharePayload): List<Entry> {
        val id = "i" + System.currentTimeMillis().toString(36)
        val items = payload.items.mapIndexed { index, item ->
            val uri = item.uri ?: return@mapIndexed item
            runCatching {
                val dir = File(File(filesDir, "inbox"), id).apply { mkdirs() }
                val name = (item.name ?: "item").replace(Regex("[^A-Za-z0-9._-]"), "_")
                val target = File(dir, index.toString() + "-" + name)
                context.contentResolver.openInputStream(android.net.Uri.parse(uri))?.use { input ->
                    target.outputStream().use { output -> input.copyTo(output) }
                } ?: return@runCatching item
                item.copy(uri = android.net.Uri.fromFile(target).toString(), name = target.name)
            }.getOrDefault(item)
        }
        return enqueue(payload.copy(items = items))
    }

    fun enqueue(payload: SharePayload): List<Entry> {
        if (payload.count == 0) return load()
        val encoded = payloadToJson(payload).toString()
        val existing = load().filterNot { payloadToJson(it.payload).toString() == encoded }
        val entry = Entry("i" + System.currentTimeMillis().toString(36), System.currentTimeMillis(), payload)
        val next = (listOf(entry) + existing).take(50)
        write(next)
        return next
    }

    fun remove(id: String) { write(load().filterNot { it.id == id }) }

    fun clear() { file().delete() }

    private fun write(entries: List<Entry>) {
        val arr = buildJsonArray {
            entries.forEach { e ->
                add(buildJsonObject {
                    put("id", e.id); put("at", e.at); put("payload", payloadToJson(e.payload))
                })
            }
        }
        AtomicFiles.writeText(file(), arr.toString())
    }

    private fun payloadToJson(payload: SharePayload): JsonObject = buildJsonObject {
        put("kind", payload.kind)
        payload.mime?.let { put("mime", it) }
        payload.processText?.let { put("process_text", it) }
        put("items", buildJsonArray {
            payload.items.forEach { item ->
                add(buildJsonObject {
                    item.uri?.let { put("uri", it) }
                    item.text?.let { put("text", it) }
                    item.mime?.let { put("mime", it) }
                    item.name?.let { put("name", it) }
                })
            }
        })
    }

    private fun parsePayload(o: JsonObject): SharePayload = SharePayload(
        kind = o["kind"]?.jsonPrimitive?.content ?: "unknown",
        mime = o["mime"]?.jsonPrimitive?.content,
        items = o["items"]?.jsonArray?.map { el ->
            val i = el.jsonObject
            SharedItem(
                uri = i["uri"]?.jsonPrimitive?.content,
                text = i["text"]?.jsonPrimitive?.content,
                mime = i["mime"]?.jsonPrimitive?.content,
                name = i["name"]?.jsonPrimitive?.content
            )
        }.orEmpty(),
        processText = o["process_text"]?.jsonPrimitive?.content
    )
}
