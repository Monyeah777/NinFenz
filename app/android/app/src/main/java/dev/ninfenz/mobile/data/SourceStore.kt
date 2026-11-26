package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 本地来源库：一条一个文件，按摘要去重；只存摘录，不存整页镜像。 */
class SourceStore(private val filesDir: File, private val projectId: String) {
    data class Source(
        val id: String,
        val title: String,
        val url: String,
        val sha256: String,
        val status: String,
        val excerpt: String,
        val license: String,
        val fetchedAt: Long
    )

    private fun dir(): File =
        File(File(File(filesDir, "projects"), projectId), "sources").apply { mkdirs() }

    fun list(): List<Source> = dir().listFiles()
        ?.filter { it.isFile && it.name.endsWith(".json") }
        ?.sortedBy { it.name }
        ?.mapNotNull { f ->
            runCatching {
                val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
                Source(
                    id = o["id"]?.jsonPrimitive?.content ?: return@runCatching null,
                    title = o["title"]?.jsonPrimitive?.content.orEmpty(),
                    url = o["url"]?.jsonPrimitive?.content.orEmpty(),
                    sha256 = o["sha256"]?.jsonPrimitive?.content.orEmpty(),
                    status = o["status"]?.jsonPrimitive?.content ?: "unverified",
                    excerpt = o["excerpt"]?.jsonPrimitive?.content.orEmpty(),
                    license = o["license"]?.jsonPrimitive?.content.orEmpty(),
                    fetchedAt = o["fetched_at"]?.jsonPrimitive?.content?.toLongOrNull() ?: 0L
                )
            }.getOrNull()
        }.orEmpty()

    fun add(title: String, text: String, url: String = "", license: String = ""): Source {
        val excerpt = text.take(4096)
        val sha = sha256(excerpt)
        list().firstOrNull { it.sha256 == sha }?.let { return it }
        val id = "src-" + sha.take(12)
        val source = Source(
            id = id,
            title = title.ifBlank { "来源" }.take(120),
            url = url,
            sha256 = sha,
            status = "unverified",
            excerpt = excerpt,
            license = license,
            fetchedAt = System.currentTimeMillis()
        )
        val o = buildJsonObject {
            put("schema", "nf-source/1")
            put("id", source.id)
            put("title", source.title)
            if (source.url.isNotBlank()) put("url", source.url)
            put("fetched_at", source.fetchedAt)
            put("sha256", source.sha256)
            put("status", source.status)
            put("excerpt", source.excerpt)
            if (source.license.isNotBlank()) put("license", source.license)
        }
        AtomicFiles.writeText(File(dir(), id + ".json"), o.toString())
        return source
    }

    fun remove(id: String) {
        File(dir(), id + ".json").delete()
    }

    fun citation(id: String): String = "[[src:$id]]"

    fun appendix(): String {
        val items = list()
        if (items.isEmpty()) return ""
        return buildString {
            appendLine()
            appendLine("## 来源")
            items.forEachIndexed { index, source ->
                append(index + 1)
                append(". ")
                append(source.title)
                if (source.url.isNotBlank()) {
                    append(" — ")
                    append(source.url)
                }
                append(" (sha256:")
                append(source.sha256.take(12))
                append(")")
                appendLine()
            }
        }
    }

    private fun sha256(text: String): String =
        MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
}
