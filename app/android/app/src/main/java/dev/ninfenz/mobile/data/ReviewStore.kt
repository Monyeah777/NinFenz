package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put

/** 0.3 块级评审：nf-review/1 sidecar，评论锚定 block_digest。 */
class ReviewStore(private val filesDir: File) {
    data class Comment(
        val id: String,
        val blockId: String,
        val blockDigest: String,
        val author: String,
        val body: String,
        val status: String,
        val createdAt: Long,
        val resolvedAt: Long? = null
    )

    data class Document(
        val projectId: String,
        val subjectDigest: String,
        val comments: List<Comment>,
        val verdict: String,
        val reviewer: String,
        val note: String
    )

    fun fileFor(projectId: String): File = file(projectId)

    private fun file(projectId: String): File =
        File(File(filesDir, "reviews").apply { mkdirs() }, projectId + ".json")

    fun load(projectId: String, subjectDigest: String): Document {
        val f = file(projectId)
        if (!f.isFile) return Document(projectId, subjectDigest, emptyList(), "pending", "", "")
        return runCatching {
            val o = Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject
            Document(
                projectId = o["project_id"]?.jsonPrimitive?.content ?: projectId,
                subjectDigest = o["subject_digest"]?.jsonPrimitive?.content ?: subjectDigest,
                comments = o["comments"]?.jsonArray?.mapNotNull { el ->
                    val c = el as? JsonObject ?: return@mapNotNull null
                    Comment(
                        id = c["id"]?.jsonPrimitive?.content ?: "",
                        blockId = c["block_id"]?.jsonPrimitive?.content ?: "",
                        blockDigest = c["block_digest"]?.jsonPrimitive?.content ?: "",
                        author = c["author"]?.jsonPrimitive?.content ?: "",
                        body = c["body"]?.jsonPrimitive?.content ?: "",
                        status = c["status"]?.jsonPrimitive?.content ?: "unresolved",
                        createdAt = c["created_at"]?.jsonPrimitive?.long ?: 0L,
                        resolvedAt = c["resolved_at"]?.jsonPrimitive?.long
                    )
                }.orEmpty(),
                verdict = o["verdict"]?.jsonPrimitive?.content ?: "pending",
                reviewer = o["reviewer"]?.jsonPrimitive?.content ?: "",
                note = o["note"]?.jsonPrimitive?.content ?: ""
            )
        }.getOrElse { Document(projectId, subjectDigest, emptyList(), "pending", "", "") }
    }

    fun save(doc: Document) {
        val arr = buildJsonArray {
            doc.comments.forEach { c ->
                add(buildJsonObject {
                    put("id", c.id); put("block_id", c.blockId); put("block_digest", c.blockDigest)
                    put("author", c.author); put("body", c.body); put("status", c.status); put("created_at", c.createdAt)
                    c.resolvedAt?.let { put("resolved_at", it) }
                })
            }
        }
        val o = buildJsonObject {
            put("schema", "nf-review/1")
            put("project_id", doc.projectId)
            put("subject_digest", doc.subjectDigest)
            put("comments", arr)
            put("verdict", doc.verdict)
            put("reviewer", doc.reviewer)
            put("note", doc.note)
        }
        AtomicFiles.writeText(file(doc.projectId), o.toString())
    }

    fun add(doc: Document, blockId: String, blockText: String, body: String, author: String): Document {
        val c = Comment(
            id = "c" + System.currentTimeMillis().toString(36) + (doc.comments.size + 1),
            blockId = blockId,
            blockDigest = sha256(blockText),
            author = author.ifBlank { "local" },
            body = body.trim(),
            status = "unresolved",
            createdAt = System.currentTimeMillis()
        )
        val next = doc.copy(comments = doc.comments + c)
        save(next)
        return next
    }

    fun setStatus(doc: Document, id: String, status: String): Document {
        val next = doc.copy(comments = doc.comments.map {
            if (it.id == id) it.copy(status = status, resolvedAt = if (status == "resolved") System.currentTimeMillis() else null) else it
        })
        save(next)
        return next
    }

    fun verdict(doc: Document, verdict: String, reviewer: String, note: String): Document {
        val next = doc.copy(verdict = verdict, reviewer = reviewer, note = note)
        save(next)
        return next
    }

    fun clear(projectId: String) { file(projectId).delete() }

    companion object {
        fun sha256(text: String): String {
            val d = MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
            return d.joinToString("") { "%02x".format(it) }
        }
    }
}
