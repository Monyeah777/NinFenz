package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

enum class SearchKind(val label: String) {
    PROJECT("项目"),
    PACK("Pack"),
    CLAUSE("条款"),
    FIELD("字段"),
    NODE("管线节点"),
    SECTION("规格章节"),
    SLOT("规格槽位")
}

data class SearchHit(
    val kind: SearchKind,
    val title: String,
    val detail: String,
    val packId: String? = null,
    val packVersion: String? = null,
    val projectId: String? = null
)

/** 本地内存索引（v0.02）：Pack 元数据/条款/字段/节点/章节/槽位 + 项目标题/ID。 */
class SearchIndex(private val filesDir: File) {

    fun build(): List<SearchHit> {
        val hits = mutableListOf<SearchHit>()
        hits += projects()
        for (packDir in PackStore(filesDir).scan().packs) {
            hits += SearchHit(SearchKind.PACK, packDir.title, packDir.id + " · " + packDir.version + " · " + packDir.itemCount + " 项", packDir.id, packDir.version)
            val protocol = readJson(File(packDir.dir, "protocol/nf-protocol-pack.json"))
            protocol?.get("clauses")?.jsonArray?.forEach { element ->
                val clause = element.jsonObject
                hits += SearchHit(SearchKind.CLAUSE, text(clause, "title"), text(clause, "id") + " · " + text(clause, "level"), packDir.id, packDir.version)
            }
            protocol?.get("fields")?.jsonArray?.forEach { element ->
                val field = element.jsonObject
                hits += SearchHit(SearchKind.FIELD, text(field, "label"), text(field, "id"), packDir.id, packDir.version)
            }
            val graph = readJson(File(packDir.dir, "pipeline/main.nfg.json"))
            graph?.get("nodes")?.jsonArray?.forEach { element ->
                val node = element.jsonObject
                hits += SearchHit(SearchKind.NODE, text(node, "title"), text(node, "id") + " · " + text(node, "kind"), packDir.id, packDir.version)
            }
            val spec = readJson(File(packDir.dir, "spec/main.nfspec.json"))
            spec?.get("sections")?.jsonArray?.forEach { element ->
                val section = element.jsonObject
                hits += SearchHit(SearchKind.SECTION, text(section, "title"), text(section, "id"), packDir.id, packDir.version)
            }
            spec?.get("slots")?.jsonArray?.forEach { element ->
                val slot = element.jsonObject
                val name = text(slot, "name").ifBlank { text(slot, "id") }
                hits += SearchHit(SearchKind.SLOT, name, text(slot, "id") + " · " + text(slot, "kind"), packDir.id, packDir.version)
            }
        }
        return hits
    }

    fun search(hits: List<SearchHit>, query: String): List<SearchHit> {
        val q = query.trim().lowercase()
        if (q.isEmpty()) return emptyList()
        return hits
            .map { hit -> hit to rank(hit, q) }
            .filter { it.second >= 0 }
            .sortedWith(compareByDescending<Pair<SearchHit, Int>> { it.second }.thenBy { it.first.title })
            .map { it.first }
    }

    private fun rank(hit: SearchHit, q: String): Int {
        val title = hit.title.lowercase()
        val detail = hit.detail.lowercase()
        return when {
            title.startsWith(q) -> 3
            q in title -> 2
            q in detail -> 1
            else -> -1
        }
    }

    private fun projects(): List<SearchHit> {
        val dir = File(filesDir, "projects")
        val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".nfproject.json") } ?: return emptyList()
        return files.mapNotNull { file ->
            val obj = readJson(file) ?: return@mapNotNull null
            val id = text(obj, "id")
            SearchHit(SearchKind.PROJECT, text(obj, "title"), id + " · " + text(obj, "status"), projectId = id)
        }
    }

    private fun readJson(file: File): JsonObject? = try {
        if (!file.isFile) null else Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
    } catch (t: Throwable) {
        null
    }

    private fun text(obj: JsonObject, key: String): String = obj[key]?.jsonPrimitive?.content ?: ""
}
