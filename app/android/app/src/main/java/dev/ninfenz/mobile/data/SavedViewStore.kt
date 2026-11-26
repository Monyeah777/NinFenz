package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 本地保存视图：状态/排序/收藏/标签组合；扩展视图只读合并。 */
class SavedViewStore(private val filesDir: File) {
    data class View(
        val id: String,
        val name: String,
        val status: String?,
        val sort: String,
        val favoritesOnly: Boolean,
        val tag: String?,
        val readOnly: Boolean = false
    )

    private fun file(): File = File(filesDir, "saved-views.json")

    fun load(): List<View> {
        val f = file()
        if (!f.isFile) return emptyList()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["views"]?.jsonArray?.mapNotNull { el ->
                val o = el.jsonObject
                View(
                    id = o["id"]?.jsonPrimitive?.content ?: return@mapNotNull null,
                    name = o["name"]?.jsonPrimitive?.content ?: return@mapNotNull null,
                    status = o["status"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                    sort = o["sort"]?.jsonPrimitive?.content ?: "RECENT",
                    favoritesOnly = o["favorites_only"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false,
                    tag = o["tag"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
                )
            }.orEmpty()
        }.getOrElse { emptyList() }
    }

    fun save(view: View): List<View> {
        val clean = view.copy(name = view.name.trim(), readOnly = false)
        if (clean.name.isBlank()) return load()
        val next = (load().filterNot { it.name == clean.name } + clean).takeLast(20)
        write(next)
        return next
    }

    fun remove(id: String): List<View> {
        val next = load().filterNot { it.id == id }
        write(next)
        return next
    }

    private fun write(views: List<View>) {
        val arr = buildJsonArray {
            views.forEach { v ->
                add(buildJsonObject {
                    put("id", v.id)
                    put("name", v.name)
                    put("sort", v.sort)
                    v.status?.let { put("status", it) }
                    if (v.favoritesOnly) put("favorites_only", true)
                    v.tag?.let { put("tag", it) }
                })
            }
        }
        AtomicFiles.writeText(file(), buildJsonObject { put("views", arr) }.toString())
    }

    /** 从扩展 contribution 读出只读视图；id 前缀避免与本地冲突。 */
    fun fromExtension(id: String, config: kotlinx.serialization.json.JsonObject): View? {
        val name = config["name"]?.jsonPrimitive?.content?.trim().orEmpty().ifBlank { id }
        return View(
            id = "ext:" + id,
            name = name,
            status = config["status"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
            sort = config["sort"]?.jsonPrimitive?.content ?: "RECENT",
            favoritesOnly = config["favorites_only"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false,
            tag = config["tag"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
            readOnly = true
        )
    }
}
