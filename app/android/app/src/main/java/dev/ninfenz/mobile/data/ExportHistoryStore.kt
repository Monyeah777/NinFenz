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

/** 最近导出记录：格式/文件名/sha256/时间，最多 20 条。 */
class ExportHistoryStore(private val filesDir: File) {
    data class Entry(
        val format: String,
        val name: String,
        val path: String,
        val sha256: String,
        val at: Long,
        val ok: Boolean? = null,
        val message: String? = null
    )

    private fun file(): File = File(File(filesDir, "exports").apply { mkdirs() }, "history.json")

    fun load(): List<Entry> {
        val f = file()
        if (!f.isFile) return emptyList()
        return try {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonArray.mapNotNull { el ->
                val o = el as? JsonObject ?: return@mapNotNull null
                Entry(
                    format = o.text("format"),
                    name = o.text("name"),
                    path = o.text("path"),
                    sha256 = o.text("sha256"),
                    at = o["at"]?.jsonPrimitive?.long ?: 0L,
                    ok = o["ok"]?.jsonPrimitive?.content?.toBooleanStrictOrNull(),
                    message = o.optText("message")
                )
            }
        } catch (t: Throwable) {
            emptyList()
        }
    }

    fun record(format: String, file: File, sha256: String, ok: Boolean? = null, message: String? = null) {
        val name = file.name
        val next = (listOf(
            Entry(format, name, file.absolutePath, sha256, System.currentTimeMillis(), ok, message)
        ) + load().filterNot { it.path == file.absolutePath }).take(20)
        val arr = buildJsonArray {
            next.forEach { e ->
                add(buildJsonObject {
                    put("format", e.format)
                    put("name", e.name)
                    put("path", e.path)
                    put("sha256", e.sha256)
                    put("at", e.at)
                    e.ok?.let { put("ok", it) }
                    e.message?.let { put("message", it) }
                })
            }
        }
        AtomicFiles.writeText(file(), arr.toString())
    }

    fun clear(): Boolean = file().delete()

    private fun JsonObject.text(key: String): String =
        this[key]?.jsonPrimitive?.content ?: ""

    private fun JsonObject.optText(key: String): String? =
        this[key]?.jsonPrimitive?.content
}
