package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 库页状态过滤/排序的跨进程持久化。 */
class LibraryViewStore(private val filesDir: File) {
    data class View(val status: String?, val sort: String?)

    private fun file(): File = File(filesDir, "library-view.json")

    fun load(): View? {
        val f = file()
        if (!f.isFile) return null
        return try {
            val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            View(
                o["status"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                o["sort"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
            )
        } catch (t: Throwable) {
            null
        }
    }

    fun save(status: String?, sort: String?) {
        if (status == null && sort == null) {
            file().delete()
            return
        }
        AtomicFiles.writeText(file(), buildJsonObject {
            status?.let { put("status", it) }
            sort?.let { put("sort", it) }
        }.toString())
    }
}
