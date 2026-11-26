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
import kotlinx.serialization.json.put

/** 智能集合：all/any 规则树，动态匹配项目；扩展贡献只读合并。 */
class SmartCollectionStore(private val filesDir: File) {
    data class Rule(val field: String, val value: String)
    data class Collection(
        val id: String,
        val name: String,
        val matchAll: Boolean,
        val rules: List<Rule>,
        val readOnly: Boolean = false
    )

    private fun file(): File = File(filesDir, "smart-collections.json")

    fun load(): List<Collection> {
        val f = file()
        if (!f.isFile) return emptyList()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["collections"]?.jsonArray?.mapNotNull { el ->
                val o = el.jsonObject
                Collection(
                    id = o["id"]?.jsonPrimitive?.content ?: return@mapNotNull null,
                    name = o["name"]?.jsonPrimitive?.content ?: return@mapNotNull null,
                    matchAll = o["match_all"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: true,
                    rules = (o["rules"] as? JsonArray)?.mapNotNull { r ->
                        val ro = r as? JsonObject ?: return@mapNotNull null
                        Rule(ro["field"]?.jsonPrimitive?.content ?: "", ro["value"]?.jsonPrimitive?.content ?: "")
                    }.orEmpty()
                )
            }.orEmpty()
        }.getOrElse { emptyList() }
    }

    fun fromExtension(id: String, config: JsonObject): Collection? {
        val name = config["name"]?.jsonPrimitive?.content?.trim().orEmpty().ifBlank { id }
        val rules = (config["rules"] as? JsonArray)?.mapNotNull { r ->
            val ro = r as? JsonObject ?: return@mapNotNull null
            Rule(ro["field"]?.jsonPrimitive?.content ?: "", ro["value"]?.jsonPrimitive?.content ?: "")
        }.orEmpty()
        if (rules.isEmpty()) return null
        return Collection(
            id = "ext:" + id,
            name = name,
            matchAll = config["match_all"]?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: true,
            rules = rules,
            readOnly = true
        )
    }

    fun matches(collection: Collection, entry: ProjectEntry, meta: LibraryMetaStore, now: Long = System.currentTimeMillis()): Boolean {
        if (collection.rules.isEmpty()) return false
        val checks = collection.rules.map { rule ->
            when (rule.field) {
                "status" -> entry.project.status.wire == rule.value
                "title" -> entry.project.title.contains(rule.value, true)
                "pack" -> entry.project.refs.basePackId == rule.value
                "tag" -> rule.value in meta.tags(entry.project.id)
                "favorite" -> meta.isFavorite(entry.project.id) == rule.value.toBooleanStrictOrNull().orTrue()
                "recent_days" -> {
                    val days = rule.value.toLongOrNull() ?: 0L
                    days > 0 && now - entry.file.lastModified() <= days * 86_400_000L
                }
                else -> false
            }
        }
        return if (collection.matchAll) checks.all { it } else checks.any { it }
    }

    private fun Boolean?.orTrue(): Boolean = this ?: true
}
