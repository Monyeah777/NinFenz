package dev.ninfenz.mobile.data

import java.io.File
import java.text.Normalizer
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
    val projectId: String? = null,
    val body: String = ""
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
        val q = normalize(query)
        if (q.isBlank()) return emptyList()
        val terms = q.split(Regex("\\s+")).filter { it.isNotBlank() }
        return hits
            .map { hit -> hit to rank(hit, q, terms) }
            .filter { it.second >= 0 }
            .sortedWith(compareByDescending<Pair<SearchHit, Int>> { it.second }.thenBy { it.first.title })
            .map { (hit, _) ->
                if (!contains(hit.title, terms) && !contains(hit.detail, terms) && contains(hit.body, terms)) {
                    hit.copy(detail = snippet(hit.body, terms.first()))
                } else hit
            }
    }

    private fun normalize(s: String): String =
        Normalizer.normalize(s, Normalizer.Form.NFKC).trim().lowercase()

    private fun contains(text: String, terms: List<String>): Boolean {
        val t = normalize(text)
        return terms.all { term ->
            t.contains(term) || fuzzyWord(t, term)
        }
    }

    private fun fuzzyWord(text: String, term: String): Boolean {
        if (term.length < 3) return false
        val words = Regex("[\\p{L}\\p{N}]+").findAll(text).map { it.value }.take(400)
        return words.any { w -> Math.abs(w.length - term.length) <= 1 && distance(w, term) <= 1 }
    }

    private fun distance(a: String, b: String): Int {
        if (a == b) return 0
        val n = a.length
        val m = b.length
        if (Math.abs(n - m) > 1) return 2
        val d = Array(n + 1) { IntArray(m + 1) }
        for (i in 0..n) d[i][0] = i
        for (j in 0..m) d[0][j] = j
        for (i in 1..n) {
            for (j in 1..m) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                d[i][j] = minOf(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
                if (i > 1 && j > 1 && a[i - 1] == b[j - 2] && a[i - 2] == b[j - 1]) {
                    d[i][j] = minOf(d[i][j], d[i - 2][j - 2] + 1)
                }
            }
        }
        return d[n][m]
    }

    private fun snippet(body: String, term: String): String {
        val norm = normalize(body)
        val at = norm.indexOf(term).coerceAtLeast(0)
        val start = (at - 24).coerceAtLeast(0)
        val end = (at + term.length + 48).coerceAtMost(norm.length)
        return "正文：" + body.substring(start, end).replace('\n', ' ').trim()
    }

    private fun rank(hit: SearchHit, q: String, terms: List<String>): Int {
        val title = normalize(hit.title)
        val detail = normalize(hit.detail)
        val body = normalize(hit.body)
        var score = 0
        if (title == q) score += 120
        if (title.startsWith(q)) score += 90
        if (title.contains(q)) score += 60
        if (detail.contains(q)) score += 35
        if (body.contains(q)) score += 12
        for (term in terms) {
            if (title.contains(term)) score += 20
            else if (detail.contains(term)) score += 8
            else if (body.contains(term)) score += 3
            else if (fuzzyWord(title + " " + detail + " " + body, term)) score += 1
            else return -1
        }
        return score
    }

    private fun projects(): List<SearchHit> {
        val dir = File(filesDir, "projects")
        val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".nfproject.json") } ?: return emptyList()
        return files.mapNotNull { file ->
            val obj = readJson(file) ?: return@mapNotNull null
            val id = text(obj, "id")
            SearchHit(SearchKind.PROJECT, text(obj, "title"), id + " · " + text(obj, "status"), projectId = id, body = projectBody(id))
        }
    }

    private fun projectBody(projectId: String): String {
        if (projectId.contains("..") || projectId.contains('/') || projectId.contains('\\')) return ""
        val dir = File(File(filesDir, "projects"), projectId)
        if (!dir.isDirectory) return ""
        val parts = mutableListOf<String>()
        File(dir, "authoring").listFiles()?.filter { it.isFile && it.name.startsWith("import-") }?.sortedBy { it.name }?.forEach { file ->
            parts += file.readText(Charsets.UTF_8).take(MAX_BODY)
        }
        File(dir, "authoring/zero-slice.json").takeIf { it.isFile }?.let { file ->
            runCatching {
                val root = Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
                root["slot_values"]?.jsonObject?.values?.forEach { value ->
                    val text = value.jsonPrimitive.content
                    if (text.isNotBlank()) parts += text
                }
            }
        }
        return parts.joinToString("\n\n").take(MAX_BODY)
    }

    private fun readJson(file: File): JsonObject? = try {
        if (!file.isFile) null else Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
    } catch (t: Throwable) {
        null
    }

    private fun text(obj: JsonObject, key: String): String = obj[key]?.jsonPrimitive?.content ?: ""

    private companion object {
        const val MAX_BODY = 256 * 1024
    }
}
