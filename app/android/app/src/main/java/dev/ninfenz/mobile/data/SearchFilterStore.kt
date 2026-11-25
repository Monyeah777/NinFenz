package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 搜索过滤（kind/pack）跨进程持久化；空过滤不落盘。 */
class SearchFilterStore(private val filesDir: File) {
    data class Filter(val kind: String?, val packId: String?, val projectId: String? = null)

    private fun file(): File = File(filesDir, "search-filter.json")

    fun load(): Filter? {
        val f = file()
        if (!f.isFile) return null
        return try {
            val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            val kind = o["kind"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
            val pack = o["pack_id"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
            val project = o["project_id"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
            if (kind == null && pack == null && project == null) null else Filter(kind, pack, project)
        } catch (t: Throwable) {
            null
        }
    }

    fun save(kind: String?, packId: String?, projectId: String? = null) {
        if (kind == null && packId == null && projectId == null) {
            file().delete()
            return
        }
        val obj = buildJsonObject {
            kind?.let { put("kind", it) }
            packId?.let { put("pack_id", it) }
            projectId?.let { put("project_id", it) }
        }
        AtomicFiles.writeText(file(), obj.toString())
    }
}
