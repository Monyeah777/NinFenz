package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 本地 Pack 树固定（非密码学签名）：用户显式信任某个 pack 当前 tree。 */
class PackTrustStore(private val filesDir: File) {
    data class Pinned(val id: String, val version: String, val tree: String)

    private fun file(): File = File(filesDir, "pack-trust.json")

    fun load(): Map<String, Pinned> {
        val f = file()
        if (!f.isFile) return emptyMap()
        return try {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject.mapValues { (key, value) ->
                val o = value as JsonObject
                Pinned(key.substringBefore('@'), key.substringAfter('@', ""), o["tree"]?.jsonPrimitive?.content ?: "")
            }
        } catch (t: Throwable) {
            emptyMap()
        }
    }

    fun pin(id: String, version: String, tree: String) {
        val next = load().toMutableMap()
        next[key(id, version)] = Pinned(id, version, tree)
        save(next)
    }

    fun clear(id: String, version: String) {
        val next = load().toMutableMap()
        next.remove(key(id, version))
        save(next)
    }

    fun pinnedTree(id: String, version: String): String? =
        load()[key(id, version)]?.tree

    fun isPinned(id: String, version: String, tree: String): Boolean =
        pinnedTree(id, version) == tree

    private fun save(values: Map<String, Pinned>) {
        val obj = buildJsonObject {
            values.forEach { (key, value) -> put(key, buildJsonObject { put("tree", value.tree) }) }
        }
        AtomicFiles.writeText(file(), obj.toString())
    }

    private fun key(id: String, version: String) = id + "@" + version
}
