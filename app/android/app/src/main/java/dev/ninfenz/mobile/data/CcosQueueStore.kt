package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put

/** CCOS 任务队列：本地保存待提交任务，避免一次只能处理一个。 */
class CcosQueueStore(private val filesDir: File) {
    data class Item(val id: String, val at: Long, val task: JsonObject)

    private fun file(): File = File(filesDir, "ccos-queue.json")

    fun load(): List<Item> {
        val f = file()
        if (!f.isFile) return emptyList()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonArray.mapNotNull { el ->
                val o = el.jsonObject
                Item(
                    id = o["id"]?.jsonPrimitive?.content ?: "",
                    at = o["at"]?.jsonPrimitive?.long ?: 0L,
                    task = o["task"]?.jsonObject ?: return@mapNotNull null
                )
            }
        }.getOrElse { emptyList() }
    }

    fun add(task: JsonObject): List<Item> {
        val encoded = task.toString()
        if (load().any { it.task.toString() == encoded }) return load()
        val item = Item("q" + System.currentTimeMillis().toString(36), System.currentTimeMillis(), task)
        val next = (listOf(item) + load()).take(50)
        write(next)
        return next
    }

    fun remove(id: String) { write(load().filterNot { it.id == id }) }

    fun clear() { file().delete() }

    private fun write(items: List<Item>) {
        val arr = buildJsonArray {
            items.forEach { i ->
                add(buildJsonObject { put("id", i.id); put("at", i.at); put("task", i.task) })
            }
        }
        AtomicFiles.writeText(file(), arr.toString())
    }
}
