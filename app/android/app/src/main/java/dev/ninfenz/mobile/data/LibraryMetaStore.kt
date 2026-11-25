package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 库元数据：收藏 + 项目标签。 */
class LibraryMetaStore(private val filesDir: File) {
    private fun file(): File = File(filesDir, "library-meta.json")

    private fun read(): Pair<Set<String>, Map<String, Set<String>>> {
        val f = file()
        if (!f.isFile) return emptySet<String>() to emptyMap()
        return runCatching {
            val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            val fav = o["favorites"]?.jsonArray?.mapNotNull { it.jsonPrimitive.content }?.toSet().orEmpty()
            val tags = o["tags"]?.jsonObject?.mapValues { (_, v) ->
                (v as? JsonArray)?.mapNotNull { it.jsonPrimitive.content }?.toSet().orEmpty()
            }.orEmpty()
            fav to tags
        }.getOrElse { emptySet<String>() to emptyMap() }
    }

    private fun write(favorites: Set<String>, tags: Map<String, Set<String>>) {
        val favArr = buildJsonArray { favorites.sorted().forEach { add(JsonPrimitive(it)) } }
        val tagObj = buildJsonObject {
            tags.toSortedMap().forEach { (id, values) ->
                put(id, buildJsonArray { values.sorted().forEach { add(JsonPrimitive(it)) } })
            }
        }
        AtomicFiles.writeText(file(), buildJsonObject { put("favorites", favArr); put("tags", tagObj) }.toString())
    }

    fun favorites(): Set<String> = read().first
    fun isFavorite(id: String): Boolean = id in favorites()

    fun toggle(id: String): Boolean {
        val (fav, tags) = read()
        val next = fav.toMutableSet()
        val added = if (next.contains(id)) { next.remove(id); false } else { next.add(id); true }
        write(next, tags)
        return added
    }

    fun tags(id: String): Set<String> = read().second[id].orEmpty()

    fun allTags(): Set<String> = read().second.values.flatten().toSet()

    fun addTag(id: String, tag: String): Set<String> {
        val (fav, tags) = read()
        val clean = tag.trim()
        if (clean.isEmpty()) return tags[id].orEmpty()
        val next = tags.toMutableMap()
        next[id] = (next[id].orEmpty() + clean)
        write(fav, next)
        return next[id].orEmpty()
    }

    fun removeTag(id: String, tag: String): Set<String> {
        val (fav, tags) = read()
        val next = tags.toMutableMap()
        val updated = next[id].orEmpty() - tag
        if (updated.isEmpty()) next.remove(id) else next[id] = updated
        write(fav, next)
        return updated
    }
}
